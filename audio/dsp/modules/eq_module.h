// audiomix
// AudioMIX
// audio/dsp/modules/eq_module.h
//
/*
   Real-time EQ engine up to 10 bands
   Per-channel biquad state
   Smooth coefficient morphing (over N samples - no clicks)
   Shared RBJ coeff generation (control thread) + per-channel state processing (audio thread)
   Supports multichannel processing through processMulti() (default bridge -> stereo)
*/

#pragma once
#include <vector>
#include <array>
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <atomic>
#include <mutex>

#include "../core/dsp_module.h"
#include "../core/rbj_coeffs.h"
#include "../core/biquad.h"
#include "../core/eq_params.h"

namespace audiomix::dsp {
  using rbj::BiquadCoeffs;
  using rbj::RbjCoeffs;

  // a0 normalized to 1
  class EqModule final : public DspModule {
  public:
    EqModule() = default;

    // thin stereo wrapper around processMulti()
    void process(const float* inL, const float* inR, float* outL, float* outR, unsigned int numFrames) override {
      const float* const inputs[2] = { inL, inR };
      float* const outputs[2] = { outL, outR };
      processMulti(inputs, outputs, 2, numFrames);
    }

    void prepare(double sr, unsigned int maxBlock) override {
      mSampleRate = (sr > 0.0) ? sr : 44100.0;          // 44.1 kHz
      mMaxBlock   = (maxBlock > 0) ? maxBlock : 512;    // 512 buffer size

      /*
        Default: chain is 4ch (Master L/R + Booth L/R)
        allocate per actual processMulti channel count lazily
        Coeffs are fixed-size (10 band EQ), states allocated for channels
        Starts in a known state (no pending packets)
      */
      mPacketReadyIndex.store(-1, std::memory_order_relaxed);
      mPacketWriteIndex.store(0, std::memory_order_relaxed);
      mPrepared = true;
    }

    void reset() override {
      std::fill(mPreampLin.begin(), mPreampLin.end(), 1.0f);
      mPreampLinGlobal = 1.0f;

      for (auto& stCh : mState) {
      for (auto& stBand : stCh) stBand = {};
    }

      for (int b = 0; b < EqParams::kMaxBands; ++b) {
        mCurrent[b] = BiquadCoeffs::identity();
        mTarget[b] = BiquadCoeffs::identity();
        mDelta[b] = {};
        mSmoothRemaining[b] = 0;
      }

        mPreampLinGlobal = 1.0f;
        mPreampTarget = 1.0f;
        mPreampDelta = 0.0f;
        mPreampSmoothRemaining = 0;

        mActive = EqParams{};
        mPacketReadyIndex.store(-1, std::memory_order_relaxed);
    }

    // Control thread API
    // Builds target coeffs off audio thread
    // publishes immutable packet that the audio thread can consume lock-free
    void setParams(const EqParams& p, float smoothMs = 10.0f) {
        EqParams params = p;
        sanitize(params);

        // compute coeffs are normalized
        CoeffPacket pkt{};
        pkt.active = params;

        const double sr = (params.sample_rate > 0) ? static_cast<double>(params.sample_rate) : mSampleRate;

        pkt.sampleRate = sr;
        pkt.preampTarget = dbToLinear(params.preamp_db);

        const int smoothSamples = std::max(1, static_cast<int>(std::round(smoothMs * 0.001f) * sr));
        pkt.smoothSamples = smoothSamples;

        for (int i = 0; i < EqParams::kMaxBands; ++i) {
            if (i < params.band_count) {
                pkt.targets[i] = makeBand(params.bands[i], sr);
            } else {
                pkt.targets[i] = BiquadCoeffs::identity();
            };
        }

        // Double-buffered publish to audio thread (lock-free)
        const int currentWriteIndex = mPacketWriteIndex.load(std::memory_order_relaxed);
        const int nextWriteIndex = (1 + currentWriteIndex) & 1; // toggle between 0 and 1

        mPackets[nextWriteIndex] = pkt;
        mPacketReadyIndex.store(nextWriteIndex, std::memory_order_release);
        mPacketWriteIndex.store(nextWriteIndex, std::memory_order_relaxed);
    }

    void processMulti(const float* const* inputs, float* const* outputs, unsigned int numChannels, unsigned int numFrames) override {
      if (!mPrepared || !inputs || !outputs ||  numChannels == 0 || numFrames == 0) { return;
      }

      // ensure channel state exists before consuming packet
      ensureChannels(numChannels);
      consumePendingPacket();

      const unsigned int frames = std::min(numFrames, mMaxBlock);

      for (unsigned int i = 0; i < frames; ++i) {
        // advance smoothing one sample at a time for all bands (shared) + preamp
        stepSmoothing();

        for (unsigned int ch = 0; ch < numChannels; ++ch) {
          const float* in = inputs[ch];
          float* out = outputs[ch];
          if (!out) continue;

          float x = (in ? in[i] : 0.0f) * mPreampLinGlobal;

          for (int band = 0; band < EqParams::kMaxBands; ++band) { 
            x = biquad_process_sample(mCurrent[band], mState[ch][band], x);
          }

          out[i] = x;
        }
    }
  }

  const EqParams& activeParams() const noexcept { 
    return mActive;
  };

  private:
    struct CoeffPacket {
        EqParams active{};
        std::array<BiquadCoeffs,EqParams::kMaxBands> targets{};    
        double sampleRate = 44100.0;    // 44.1 kHz

        int bandCount = 0;
        int smoothSamples = 1;

        float preampTarget = 1.0f;
    };

    static inline float clampf(float v, float lo, float hi) {
        return std::max(lo, std::min(v, hi));
    }

    static inline float dbToLinear(float db) {
        return std::pow(10.0f, db / 20.0f);
    }

    static void sanitize(EqParams& p) {
        p.sample_rate = (p.sample_rate > 0) ? p.sample_rate : 44100;    // 44.1 kHz
        p.preamp_db = clampf(p.preamp_db, -24.0f, 24.0f);
        p.band_count = std::max(0, std::min(p.band_count, EqParams::kMaxBands));

        for (int i = 0; i < p.band_count; ++i) {
            p.bands[i].f0 = clampf(p.bands[i].f0, 20.0f, 20000.0f);    // 20k Hz
            p.bands[i].q = clampf(p.bands[i].q, 0.1f, 18.0f);    // q factor (narrow/wide)
            p.bands[i].gain_db = clampf(p.bands[i].gain_db, -24.0f, 24.0f); // gain limit
        }
    }

    void ensureChannels(unsigned int numChannels) {
        if (mState.size() == numChannels) {
            return;
        }

        mState.assign(numChannels, {});
        mPreampLin.assign(numChannels, 1.0f);

        // each channel has 10 band states
        for (auto& stCh : mState) {
            stCh.fill({});
        }
    }

    BiquadCoeffs makeBand(const EqBand& band, double sampleRate) const {
        const float sr = static_cast<float>((sampleRate > 0) ? sampleRate : mSampleRate);
        const float f0 = clampf(band.f0, 20.0f, 20000.0f);
        const float q = clampf(band.q, 0.1f, 18.0f);
        const float gainDb = clampf(band.gain_db, -24.0f, 24.0f);

        switch (band.type) {
            case EqBandType::Peaking:
              return RbjCoeffs::makePeakingEQ(sr, f0, q, gainDb);
            case EqBandType::LowShelf:
              return RbjCoeffs::makeLowShelf(sr, f0, gainDb, 1.0f);
            case EqBandType::HighShelf:
              return RbjCoeffs::makeHighShelf(sr, f0, gainDb, 1.0f);
            default:
                return BiquadCoeffs::identity();
        }
    }

    void consumePendingPacket() {
        const int idx = mPacketReadyIndex.exchange(-1, std::memory_order_acq_rel);
        if (idx < 0) {
            return;
        }

        const CoeffPacket &pkt = mPackets[idx];

        // apply packet state at a clean boundary (after current block), then smooth towards target
        mActive = pkt.active;
        mSampleRate = (pkt.sampleRate > 0.0) ? pkt.sampleRate : mSampleRate;

        const int smoothSamples = std::max(1, pkt.smoothSamples);

        // preamp smoothing targets (deltas)
        // audio thread only writes smoothing state
        mPreampTarget = pkt.preampTarget;
        mPreampSmoothRemaining = smoothSamples;
        mPreampDelta = (mPreampTarget - mPreampLinGlobal) / static_cast<float>(smoothSamples);

        // band smoothing
        // audio thread only writes smoothing state
        for (int i = 0; i < EqParams::kMaxBands; ++i) {
            mTarget[i] = pkt.targets[i];
            mSmoothRemaining[i] = smoothSamples;

            mDelta[i].b0 = (mTarget[i].b0 - mCurrent[i].b0) / static_cast<float>(smoothSamples);
            mDelta[i].b1 = (mTarget[i].b1 - mCurrent[i].b1) / static_cast<float>(smoothSamples);
            mDelta[i].b2 = (mTarget[i].b2 - mCurrent[i].b2) / static_cast<float>(smoothSamples);
            mDelta[i].a1 = (mTarget[i].a1 - mCurrent[i].a1) / static_cast<float>(smoothSamples);
            mDelta[i].a2 = (mTarget[i].a2 - mCurrent[i].a2) / static_cast<float>(smoothSamples);
        }
    }

    void stepSmoothing() {
        if (mPreampSmoothRemaining > 0) {
            mPreampLinGlobal += mPreampDelta;
            --mPreampSmoothRemaining;

            if (mPreampSmoothRemaining == 0) {
                mPreampLinGlobal = mPreampTarget; // ensure exact target at end
            }
        }

        for (int i = 0; i < EqParams::kMaxBands; ++i) {
            if (mSmoothRemaining[i] > 0) {
                mCurrent[i].b0 += mDelta[i].b0;
                mCurrent[i].b1 += mDelta[i].b1;
                mCurrent[i].b2 += mDelta[i].b2;
                mCurrent[i].a1 += mDelta[i].a1;
                mCurrent[i].a2 += mDelta[i].a2;

                --mSmoothRemaining[i];

                if (mSmoothRemaining[i] == 0) {
                    mCurrent[i] = mTarget[i]; // ensure exact target at end
                }
            }
        }
    }

  private:
    double mSampleRate = 44100.0;    // 44.1 kHz
    unsigned int mMaxBlock = 512;    // max buffer size 512 samples
    bool mPrepared = false;

    // dbl-buffered param pkts (control -> audio)
    std::array<CoeffPacket, 2> mPackets{};
    std::atomic<int> mPacketReadyIndex{-1};
    std::atomic<int> mPacketWriteIndex{0};

    EqParams mActive{};

    // Coeff smoothing
    // shared across channels, states are p/channel
    std::array<BiquadCoeffs, EqParams::kMaxBands> mCurrent{};
    std::array<BiquadCoeffs, EqParams::kMaxBands> mTarget{};
    std::array<BiquadCoeffs, EqParams::kMaxBands> mDelta{};
    std::array<int, EqParams::kMaxBands> mSmoothRemaining{};

    // p/channel, p/band runtime states
    std::vector<std::array<BiquadState, EqParams::kMaxBands>> mState;

    // Preamp smoothing
    float mPreampLinGlobal = 1.0f;
    float mPreampTarget = 1.0f;
    float mPreampDelta = 0.0f;
    int mPreampSmoothRemaining = 0;

    // reserved p/channel preamp cache
    std::vector<float> mPreampLin;
};

} // namespace audiomix::dsp
