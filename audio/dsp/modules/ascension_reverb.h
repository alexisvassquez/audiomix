// audiomix
// AudioMIX
// audio/dsp/modules/ascension_reverb.h
//
/*
  AscensionReverbModule - 8 line Feedback Delay Network
  (FDN) reverb

  An FDN reverb works by routing audio through N delay lines whose outputs are mixed through a feedback matrix and fed back into their own inputs.

  Please refer to docs/dsp/AscensionReverbModule.md file for
  further in-depth code analysis and architectural decisions.
*/

#pragma once

#include <array>
#include <atomic>
#include <cmath>
#include <string>
#include <vector>

#include "audio/dsp/core/dsp_module.h"
#include "audio/dsp/core/smoothed_parameter.h"

namespace audiomix::dsp {

// Reverb Params
struct ReverbParams {
    // 0..100 ms - onset separation 
    float pre_delay_ms = 20.0f;
    // 0.1..12 s - T60 (time to -60 dB)
    float decay_s = 2.5f;
    // 0.1..4.0 - room size scale
    float size = 1.2f;
    // 0..1 - HF absorption (0=bright, 1=dark)
    float damping = 0.55f;
    // 0..1 - wet/dry mix
    float wet = 0.25f;
    // 0..1 - stereo decorrelation
    float width = 1.0f;
    int sample_rate = 44100;
};

class AscensionReverbModule : public DspModule {
public:
    static constexpr int kFdnN = 8;
    
    // DspModule interface
    void prepare(double sampleRate, unsigned int maxBlockSize) override {
        mSampleRate = (sampleRate > 0.0) ? sampleRate : 44100.0;
        mMaxBlockSize = (maxBlockSize > 0) ? maxBlockSize : 512;

        mPacketReadyIndex.store(-1, std::memory_order_relaxed);
        mPacketWriteIndex.store(0, std::memory_order_relaxed);

        // Prepare SmoothedParameters
        // 20 ms ramp - avoids zipper noise
        mWetSmoothed.prepare(mSampleRate, 20.0f);
        mWidthSmoothed.prepare(mSampleRate, 20.0f);

        allocateBuffers();

        // Push default params so the audio thread has something to consume
        setParams(mActive);

        mPrepared = true;
    }

    void reset() override {
        for (auto& dl : mDelayLines) dl.clear();
        mPreDelay[0].clear();
        mPreDelay[1].clear();
        for (int i = 0; i < kFdnN; ++i) mDampState[i] = 0.0f;
    }

    // Stereo process
    // delegates to processMulti via base class bridge
    void process(const float* inL, const float* inR, float* outL, float* outR, unsigned int numFrames) override {
        if (!mPrepared || !outL || !outR) return;

        consumePendingPacket();

        for (unsigned int n = 0; n < numFrames; ++n) {
            const float xL = inL ? inL[n] : 0.0f;
            const float xR = inR ? inR[n] : 0.0f;

            // Pre-delay
            const float pdL = mPreDelay[0].read();
            const float pdR = mPreDelay[1].read();
            mPreDelay[0].write(xL);
            mPreDelay[1].write(xR);

            // Downmix to mono for FDN input
            // FDN operates on a single excitation signal;
            // stereo comes back from decorrelated routing,
            // not from stereo input
            const float mono = 0.5f * (pdL + pdR);
            
            // FDN: read delay line outputs
            std::array<float, kFdnN> y{};
            for (int i = 0; i < kFdnN; ++i)
                y[i] = mDelayLines[i].read();
                
            // Hadamard mix (feedback matrix)
            // Energy-preserving:
            // unitary matrix prevents self-oscillation
            const std::array<float, kFdnN> v = hadamard8(y);

            // Write back: 
            // gain + HF damping + inject mono input
            for (int i = 0; i < kFdnN; ++i) {
                // one-pole lowpass on each feedback path
                // air/material absorption
                mDampState[i] = mDampCoeff * mDampState[i] + (1.0f - mDampCoeff) * v[i];

                // T60-derived gain then inject mono excitation
                mDelayLines[i].write(mLineGain[i] * mDampState[i] + mono);
            }

            // Stereo output via M/S (mid/side) decorrelation
            // Even-indexed lines -> Left group,
            // Odd-indexed -> Right group.
            // Natural because the lines have different lengths(coprime delays)
            // so they're already time-decorrelated; M/S just controls the blend.
            float wetL = 0.0f, wetR = 0.0f;
            for (int i = 0; i < kFdnN; ++i) {
                if (i % 2 == 0) wetL += y[i];
                else wetR += y[i];
            }
            // normalize each group (4 lines per side)
            constexpr float kGroupNorm = 1.0f / (kFdnN / 2);
            wetL *= kGroupNorm;
            wetR *= kGroupNorm;

            // M/S width encode
            // mid = average of both groups (consisten across width)
            // side = half-difference (scales with width)
            const float mid = 0.5f * (wetL + wetR);
            const float side = 0.5f * (wetL - wetR);
            const float w = mWidthSmoothed.process();
            wetL = mid + w * side;
            wetR = mid - w * side;

            // Wet/dry blend
            const float wet = mWetSmoothed.process();
            const float dry = 1.0f - wet;
            outL[n] = dry * xL + wet * wetL;
            outR[n] = dry * xR + wet * wetR;
        }
    }

    // Control thread API
    // Call from control thread only.
    // Builds and publishes a RvbPacket atomically so the
    // audio thread picks it up at the next block boundary.
    void setParams(const ReverbParams& p) {
        ReverbParams params = p;
        sanitize(params);

        const double sr = (params.sample_rate > 0) ? static_cast<double>(params.sample_rate) : mSampleRate;

        RvbPacket pkt{};
        pkt.active = params;

        // Pre-delay in samples
        // clamped to allocated buffer size
        pkt.preDelaySamples = static_cast<int>(
            std::round(params.pre_delay_ms * 0.001 * sr)
        );

        // Base delay lengths (ms)
        // mutually coprime to avoid comb resonance
        static constexpr float kBaseMs[kFdnN] = {
            29.0f, 37.0f, 43.0f, 53.0f, 59.0f, 71.0f, 79.0f, 89.0f
        };

        const float t60 = std::max(0.01f, params.decay_s);
        const float sizeMul = params.size;

        for (int i = 0; i < kFdnN; ++i) {
            const int d = std::max(1, static_cast<int>(std::round(kBaseMs[i] * sizeMul * 0.001 * sr)));
            pkt.delaySamples[i] = d;

            // Per-line gain
            pkt.lineGain[i] = std::pow(10.0f, -3.0f * static_cast<float>(d) / (t60 * static_cast<float>(sr)));
        }

        // HF (high-freq) dampening
        // maps dampening [0..1] to a one-pole LP (low-pass) cutoff
        {
            constexpr float kFcMax = 20000.0f;
            constexpr float kFcMin = 300.0f;
            const float fc = kFcMax * std::pow(kFcMin / kFcMax, params.damping);
            pkt.dampCoeff = std::exp(-2.0f * 3.14159265f * fc / static_cast<float>(sr));
        }

        // Wet/width targets
        // audio thread reads via SmoothParameter
        pkt.wet = params.wet;
        pkt.width = params.width;

        publishPacket(pkt);
    }

    // Legacy string API
    // not RT-safe, for AudioScript setParameter() calls
    void setParameter(const std::string& id, float value) override {
        ReverbParams p = mActive;
        if (id == "wet") p.wet = value;
        else if (id == "decay") p.decay_s = value;
        else if (id == "size") p.size = value;
        else if (id == "dampening") p.damping = value;
        else if (id == "pre_delay_ms") p.pre_delay_ms = value;
        else if (id == "width") p.width = value;
        setParams(p);
    }

    const ReverbParams& activeParams() const noexcept { return mActive; }

    // Control plane stubs
    // TODO: wire when ParamRegistry is extended to reverb
    void registerParameters(control::ParamRegistry& /*registry*/) override {}
    void bindParameters(control::ParamBindingTable& /*bindings*/) override {}

private:
    // Circular buffer
    // used for both pre-delay and FDN delay lines
    struct CircularBuffer {
        std::vector<float> data;
        int writePos = 0;
        int delaySamples = 1;

        void resize(int maxSamples) {
            data.assign(static_cast<std::size_t>(maxSamples), 0.0f);
            writePos = 0;
        }

        void setDelay(int d) {
            delaySamples = std::max(1, std::min(d, static_cast<int>(data.size()) - 1));
        }

        float read() const {
            int readPos = writePos - delaySamples;
            if (readPos < 0) readPos += static_cast<int>(data.size());
            return data[static_cast<std::size_t>(readPos)];
        }

        void write(float x) {
            data[static_cast<std::size_t>(writePos)] = x;
            if (++writePos >= static_cast<int>(data.size())) writePos = 0;
        }

        void clear() {
            std::fill(data.begin(), data.end(), 0.0f);
            writePos = 0;
        }
    };

    // Normalized 8x8 Hadamard mixing matrix
    // via iterative Walsh-Hadamard
    static std::array<float, kFdnN> hadamard8(std::array<float, kFdnN> x) {
        // Butterfly passes
        for (int len = 1; len < kFdnN; len <<= 1) {
            for (int i = 0; i < kFdnN; i += len << 1) {
                for (int j = 0; j < len; ++j) {
                    const float u = x[i + j];
                    const float w = x[i + j + len];
                    x[i + j] = u + w;
                    x[i + j + len] = u - w; 
                }
            }
        }
        // Normalize: 1/sqrt(8) ≈ 0.35355339f
        constexpr float kNorm = 0.35355339f;
        for (auto& s : x) s *= kNorm;
        return x;
    }

    // Double-buffered control -> audio packet
    // same pattern as EqModule
    struct RvbPacket {
        ReverbParams active{};
        int preDelaySamples = 0;
        std::array<int, kFdnN> delaySamples{};
        std::array<float, kFdnN> lineGain;
        float dampCoeff = 0.0f;
        float wet = 0.25f;
        float width = 1.0f;
    };

    void publishPacket(const RvbPacket& pkt) {
        const int next = 1 - mPacketWriteIndex.load(std::memory_order_relaxed);
        mPackets[next] = pkt;
        mPacketWriteIndex.store(next, std::memory_order_relaxed);
        mPacketReadyIndex.store(next, std::memory_order_release);
    }

    void consumePendingPacket() {
        const int idx = mPacketReadyIndex.exchange(-1, std::memory_order_acq_rel);
        if (idx < 0) return;

        const RvbPacket& pkt = mPackets[idx];
        mActive = pkt.active;

        mPreDelay[0].setDelay(pkt.preDelaySamples);
        mPreDelay[1].setDelay(pkt.preDelaySamples);

        for (int i = 0; i < kFdnN; ++i) {
            mDelayLines[i].setDelay(pkt.delaySamples[i]);
            mLineGain[i] = pkt.lineGain[i];
        }

        mDampCoeff = pkt.dampCoeff;

        mWetSmoothed.setTarget(pkt.wet);
        mWidthSmoothed.setTarget(pkt.width);
    }

    // Buffer allocation
    void allocateBuffers() {
        // Pre-delay: 0..100 ms at up to 192 kHz + headroom
        const int preMax = static_cast<int>(std::ceil(0.105 * mSampleRate)) + 16;

        for (int ch = 0; ch < 2; ++ch) {
            mPreDelay[ch].resize(preMax);
            mPreDelay[ch].setDelay(0);
        }

        // FDN lines
        const int lineMax = static_cast<int>(std::ceil(0.09 * 4.2 * mSampleRate)) + 16;

        for (int i = 0; i < kFdnN; ++i) {
            mDelayLines[i].resize(lineMax);
            mDelayLines[i].setDelay(1);
            mLineGain[i] = 0.9f;
        }
    }

    // Helpers
    static void sanitize(ReverbParams& p) {
        p.pre_delay_ms = clampf(p.pre_delay_ms, 0.0f, 100.0f);
        p.decay_s = clampf(p.decay_s, 0.1f, 12.0f);
        p.size = clampf(p.size, 0.1f, 4.0f);
        p.damping = clampf(p.damping, 0.0f, 1.0f);
        p.wet = clampf(p.wet, 0.0f, 1.0f);
        p.width = clampf(p.width, 0.0f, 1.0f);
        if (p.sample_rate <= 0) p.sample_rate = 44100;
    }

    static float clampf(float v, float lo, float hi) {
        return std::max(lo, std::min(v, hi));
    }

    // State
    double mSampleRate = 44100.0;     // 44.1 kHz
    unsigned int mMaxBlockSize = 512; // 512 frames
    bool mPrepared = false;

    // Double-buffered control -> audio
    std::array<RvbPacket, 2> mPackets{};
    std::atomic<int> mPacketReadyIndex{-1};
    std::atomic<int> mPacketWriteIndex{0};

    ReverbParams mActive{};

    // FDN delay lines + per-line state
    std::array<CircularBuffer, kFdnN> mDelayLines{};
    std::array<float, kFdnN> mLineGain{};
    std::array<float, kFdnN> mDampState{};
    float mDampCoeff = 0.0f;

    // Pre-delay (stereo)
    std::array<CircularBuffer, 2> mPreDelay{};

    // Smoothed wet/width
    // audio-thread only, no zipper noise on transitions
    SmoothedParameter mWetSmoothed;
    SmoothedParameter mWidthSmoothed;
};

} // namespace audiomix::dsp
