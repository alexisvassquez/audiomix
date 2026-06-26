// audiomix
// AudioMIX
// audio/dsp/modules/compressor_module.h
//
/*
  Single-band feed-forward compressor with branching peak detector.

  Designed for:
    - Stereo or N-channel processing via processMulti()
    - Linked or dual-mono detection
    - Optional sidechain input (external buffer routed through processMulti())
    - Optional highpass (hp) on the detection path (RBJ, computed off audio threshold)
    - Soft knee w/ quadratic interpolation around threshold
    - Wet/dry blend (parallel compression in-module)
    - Externally readable gain reduction in dB (atomic, lock-free)

    Threading model:
      - Control thread builds CompPacket in setParams() and publishes via atomic index (same double-buffered pattern as EqModule)
      - Audio thread consumes the latest packet at processMulti() boundary, updates smoothing targets, then runs sample by sample

    TODO: Detector mode is currently Branching only.
    Decoupled and Rms are reserved in CompressorParams and will fall back to Branching/Peak until implemented.
*/

#pragma once
#include <vector>
#include <array>
#include <cmath>
#include <algorithm>
#include <cstdint>
#include <cstddef>
#include <atomic>

#include "../core/dsp_module.h"
#include "../core/biquad.h"
#include "../core/rbj_coeffs.h"
#include "../core/compressor_params.h"
#include "eq_module.h"

namespace audiomix::dsp {

  using rbj::BiquadCoeffs;
  using rbj::RbjCoeffs;

  class CompressorModule final : public DspModule {
  public:
    CompressorModule() = default;

    // Stereo wrapper - delegates to processMulti() with no sidechain
    void process(const float *inL, const float *inR, float *outL, float *outR, unsigned int numFrames) override
    {
      const float *inputs[2] = {inL, inR};
      float *outputs[2] = {outL, outR};
      processMulti(inputs, outputs, 2, numFrames);
    }

    void prepare(double sr, unsigned int maxBlock) override
    {
      mSampleRate = (sr > 0.0) ? sr : 44100.0;
      mMaxBlock = (maxBlock > 0) ? maxBlock : 512;

      mPacketReadyIndex.store(-1, std::memory_order_relaxed);
      mPacketWriteIndex.store(0, std::memory_order_relaxed);
      mPrepared = true;
    }

    void reset() override
    {
      for (auto &env : mEnvelope)
        env = 0.0f;
      for (auto &sc : mSidechainState)
        sc = {};

      mGainReductionDb.store(0.0f, std::memory_order_relaxed);

      mAttackCoeff = 0.0f;
      mReleaseCoeff = 0.0f;
      mScHpCurrent = BiquadCoeffs::identity();
      mScHpTarget = BiquadCoeffs::identity();
      mScHpTarget = {};
      mScHpSmoothRemaining = 0;

      mActive = CompressorParams{};
      mPacketReadyIndex.store(-1, std::memory_order_relaxed);
    }

    // Control thread API
    // build coeff packet, publishes atomically
    void setParams(const CompressorParams &p, float smoothMs = 10.0f)
    {
      CompressorParams params = p;
      sanitize(params);

      const double sr = (params.sample_rate > 0) ? static_cast<double>(params.sample_rate) : mSampleRate;

      CompPacket pkt{};
      pkt.active = params;
      pkt.sampleRate = sr;
      pkt.smoothSamples = std::max(1, static_cast<int>(smoothMs * 0.001f * static_cast<float>(sr)));

      // Envelope coeffs - exponential one-pole smoothing
      // coeff = exp(-1 / (timeMs * 0.001 * sr))
      pkt.attackCoeff = computeEnvCoeff(params.attack_ms, sr);
      pkt.releaseCoeff = computeEnvCoeff(params.release_ms, sr);

      // Threshold/ratio/knee in working unit
      pkt.thresholdDb = params.threshold_db;
      pkt.ratio = params.ratio;
      pkt.kneeDb = params.knee_db;
      pkt.makeupLin = db_to_lin(params.makeup_db);
      pkt.mix = params.mix;

      // Sidechain HP coeffs
      // Re-ealuated p/packet since sr may change since prepare()
      pkt.scHpEnabled = params.sidechain_hp_enabled;
      pkt.scHpTarget = params.sidechain_hp_enabled ? RbjCoeffs::makeHighpass(params.sidechain_hp_hz, params.sidechain_hp_q) : BiquadCoeffs::identity();

      publishPacket(pkt);
    }

    // Audio thread N-channel processing with optional sidechain
    // sidechain: optional pointer to an array of channel pointers
    // if params.sidechain_external is true and non-null, detection uses sidechain buffer
    // otherwise, detection uses main input buffer (first 2 channels if stereo)
    void processMulti(const float *const *inputs, float *const *outputs, unsigned int numChannels, unsigned int numFrames) override
    {
      if (!mPrepared || numChannels == 0 || numFrames == 0)
        return;

      consumePendingPacket();
      ensureChannels(numChannels);

      const unsigned int frames = std::min(numFrames, mMaxBlock);
      const bool linked = (mActive.stereo_link == StereoLink::Linked);
      const bool useScHp = mActive.sidechain_hp_enabled;

      // external sidechain plumbing reserved
      // currently always uses main input for detection
      // TODO: when chain wires sidechain routing, this where the input pointer will swtich.
      const float *const *detectionSource = inputs;

      for (unsigned int i = 0; i < frames; ++i)
      {
        // smooth sidechain HP coeffs toward target if enabled
        if (useScHp && mScHpSmoothRemaining > 0)
        {
          mScHpCurrent.b0 += mScHpDelta.b0;
          mScHpCurrent.b1 += mScHpDelta.b1;
          mScHpCurrent.b2 += mScHpDelta.b2;
          mScHpCurrent.a1 += mScHpDelta.a1;
          mScHpCurrent.a2 += mScHpDelta.a2;
          --mScHpSmoothRemaining;
        }

        // build detection signal
        // linked: max abs across channels
        float detectionSample = 0.0f;

        if (linked)
        {
          // linked: take max absolute value across all channels for detection
          for (unsigned int ch = 0; ch < numChannels; ++ch)
          {
            const float *dIn = (detectionSource && detectionSource[ch]) ? detectionSource[ch] : nullptr;
            const float s = dIn ? dIn[i] : 0.0f;
            const float filtered = useScHp ? biquad_process_sample(mScHpCurrent, mSidechainState[ch], s) : s;
            const float a = std::fabs(filtered);
            if (a > detectionSample)
              detectionSample = a;
          }
        }

        // compute gain reduction (single value if linked)
        float linkedGainLin = 1.0f;
        float linkedGrDb = 0.0f;

        if (linked)
        {
          updateEnvelope(mEnvelope[0], detectionSample);
          const float grDb = computeGainReduction(mEnvelope[0]);
          linkedGrDb = grDb;
          linkedGainLin = db_to_lin(-grDb);
        }

        // apply per channel gain reduction with linked detection if linked, or independent detection if dual-mono
        float maxGrDbThisSample = linkedGrDb;

        for (unsigned int ch = 0; ch < numChannels; ++ch)
        {
          const float *in = (inputs && inputs[ch]) ? inputs[ch] : nullptr;
          float *out = (outputs && outputs[ch]) ? outputs[ch] : nullptr;
          if (!out)
            continue;

          const float dry = in ? in[i] : 0.0f;
          float gainLin = linkedGainLin;

          if (!linked)
          {
            // dual-mono: compute per-channel gain reduction, but still use linked detection/envelope
            const float *dIn = (detectionSource && detectionSource[ch]) ? detectionSource[ch] : nullptr;
            const float s = dIn ? dIn[i] : 0.0f;
            const float filtered = useScHp ? biquad_process_sample(mScHpCurrent, mSidechainState[ch], s) : s;
            const float det = std::fabs(filtered);

            updateEnvelope(mEnvelope[ch], det);
            const float grDb = computeGainReduction(mEnvelope[ch]);
            if (grDb > maxGrDbThisSample)
              maxGrDbThisSample = grDb;
            gainLin = db_to_lin(-grDb);
          }

          const float wet = dry * gainLin * mActive_makeupLin;
          out[i] = (1.0f - mActive.mix) * dry + mActive.mix * wet;
        }

        // publish gain reduction readout (last sample of block wins)
        if (i + 1 == frames)
        {
          mGainReductionDb.store(maxGrDbThisSample, std::memory_order_relaxed);
        }
      }
    }

    // Public readout - gain reduction in dB (postive = compressing)
    // Lock-free, safe to read from any thread
    // e.g., LEDs, modulation, UI, etc.
    float getGainReductionDb() const
    {
      return mGainReductionDb.load(std::memory_order_relaxed);
    };

  private:
    // Helpers
    static inline float clampf(float v, float lo, float hi)
    {
      return std::max(lo, std::min(hi, v));
    }

    static inline float db_to_lin(float db)
    {
      return std::pow(10.0f, db * 0.05f);
    }

    static inline float lin_to_db(float lin)
    {
      // floor to avoid log(0); -120 dB is well below audible
      // threshold and effectively silence for gain reduction readout purposes
      return 20.0f * std::log10(std::max(lin, 1.0e-6f));
    }

    static float computeEnvCoeff(float timeMs, double sampleRate)
    {
      const float timeSec = std::max(0.001f, timeMs * 0.001f);
      return std::exp(-1.0f / (timeSec * static_cast<float>(sampleRate)));
    }

    static void sanitize(CompressorParams &p)
    {
      using namespace compressor_limits;
      p.threshold_db = clampf(p.threshold_db, kThresholdMinDb, kThresholdMaxDb);
      p.ratio = clampf(p.ratio, kRatioMin, kRatioMax);
      p.attack_ms = clampf(p.attack_ms, kAttackMinMs, kAttackMaxMs);
      p.release_ms = clampf(p.release_ms, kReleaseMinMs, kReleaseMaxMs);
      p.knee_db = clampf(p.knee_db, kKneeMinDb, kKneeMaxDb);
      p.makeup_db = clampf(p.makeup_db, kMakeupMinDb, kMakeupMaxDb);
      p.mix = clampf(p.mix, kMixMin, kMixMax);

      p.sidechain_hp_hz = clampf(p.sidechain_hp_hz, kSidechainHpHzMin, kSidechainHpHzMax);
      p.sidechain_hp_q = clampf(p.sidechain_hp_q, kSidechainHpQMin, kSidechainHpQMax);

      // 44.1 kHz is default
      if (p.sample_rate <= 0)
        p.sample_rate = 44100;
    }

    void ensureChannels(unsigned int numChannels)
    {
      if (mEnvelope.size() == numChannels) return;
      mEnvelope.assign(numChannels, 0.0f);
      mSidechainState.assign(numChannels, BiquadState{});
    }

    // Branching peak envelope follower
    inline void updateEnvelope(float& env, float detection) {
      const float coeff = (detection > env) ? mAttackCoeff : mReleaseCoeff;
      env = coeff * env + (1.0f - coeff) * detection;
    }

    // Gain reduction computation with soft knee
    // Returns gain reduction in dB (positive value means compression)
    inline float computeGainReduction(float envelopeLin) {
      const float levelDb = lin_to_db(envelopeLin);
      const float threshold = mActive.threshold_db;
      const float knee = mActive.knee_db;
      const float ratio = std::max(mActive.ratio, 1.0f);

      const float halfKnee = knee * 0.5f;
      const float overshoot = levelDb - threshold;

      /*
        Hard knee compression applies the full compression ratio immediately when the signal crosses the threshold,
         resulting in aggressive, precise control suitable for drums.
         
        Soft knee gradually introduces compression as the signal approaches the threshold,
         offering a smoother, more transparent, and natural sound for vocals, acoustic instruments, and mastering.
      */

      // hard knee: simple piecewise
      if (knee <= 0.0f) {
        if (overshoot <= 0.0f) return 0.0f;
        return overshoot * (1.0f - 1.0f / ratio);
      }

      // soft knee: quadratic interpolation across the knee region
      if (overshoot <= -halfKnee) {
        // below the knee - no compression
        return 0.0f;
      }
      if (overshoot >= halfKnee) {
        // above the knee - full compression
        return overshoot * (1.0f - 1.0f / ratio);
      }
      // inside the knee - interpolate smoothly
      const float x = overshoot + halfKnee;    // 0..knee
      const float gradient = (1.0f - 1.0f / ratio);
      // quadratic ramp: gain reduction (GR) rises smoothly 
      // from 0 to gradient knee
      return gradient * (x * x) / (2.0f * knee);
    }

    // Packet publish/consume
    // Same pattern as EqModule
    struct CompPacket {
      CompressorParams active{};
      double sampleRate = 44100.0;    // 44.1 kHz
      int smoothSamples = 1;

      float attackCoeff = 0.0f;
      float releaseCoeff = 0.0f;

      float thresholdDb = -18.0f;
      float ratio = 4.0f;
      float kneeDb = 6.0f;
      float makeupLin = 1.0f;
      float mix = 1.0f;

      bool scHpEnabled = false;
      BiquadCoeffs scHpTarget = BiquadCoeffs::identity();
    };

    void publishPacket(const CompPacket& pkt) {
      const int next = 1 - mPacketWriteIndex.load(std::memory_order_relaxed);
      mPackets[next] = pkt;
      mPacketWriteIndex.store(next, std::memory_order_relaxed);
      mPacketReadyIndex.store(next, std::memory_order_release);
    }

    void consumePendingPacket() {
      const int idx = mPacketReadyIndex.exchange(-1, std::memory_order_acq_rel);
      if (idx < 0) return;

      const CompPacket& pkt = mPackets[idx];

      mActive = pkt.active;
      mSampleRate = (pkt.sampleRate > 0.0) ? pkt.sampleRate : mSampleRate;

      mAttackCoeff = pkt.attackCoeff;
      mReleaseCoeff = pkt.releaseCoeff;

      mActive_makeupLin = pkt.makeupLin;
      mActive_mix = pkt.mix;

      // Sidechain HP smoothing
      // same coeff-ramp pattern as EQ
      const int smoothSamples = std::max(1, pkt.smoothSamples);
      mScHpTarget = pkt.scHpTarget;
      mScHpSmoothRemaining = smoothSamples;
      mScHpDelta.b0 = (mScHpTarget.b0 - mScHpCurrent.b0) / smoothSamples;
      mScHpDelta.b1 = (mScHpTarget.b1 - mScHpCurrent.b1) / smoothSamples;
      mScHpDelta.b2 = (mScHpTarget.b2 - mScHpCurrent.b2) / smoothSamples;
      mScHpDelta.a1 = (mScHpTarget.a1 - mScHpCurrent.a1) / smoothSamples;
      mScHpDelta.a2 = (mScHpTarget.a2 - mScHpCurrent.a2) / smoothSamples;
    }

  private:
    // configuration
    double mSampleRate = 44100.0;    // 44.1 kHz
    unsigned int mMaxBlock = 512;
    bool mPrepared = false;

    // double-buffed control -> audio packets
    std::array<CompPacket, 2> mPackets{};
    std::atomic<int> mPacketReadyIndex{-1};
    std::atomic<int> mPacketWriteIndex{0};

    // active params (copied in from packets at boundary)
    CompressorParams mActive{};

    // cached scalars updated p/packet
    float mActive_makeupLin = 1.0f;
    float mActive_mix = 1.0f;

    // envelope coeffs (p/sample exponential decay constants)
    float mAttackCoeff = 0.0f;
    float mReleaseCoeff = 0.0f;

    // p/channel envelope state
    std::vector<float> mEnvelope;

    // p/channel sidechain HP (high pass) biquad state
    std::vector<BiquadState> mSidechainState;

    // smoothed sidechain HP coeffs (shared across channels)
    BiquadCoeffs mScHpCurrent = BiquadCoeffs::identity();
    BiquadCoeffs mScHpTarget = BiquadCoeffs::identity();
    BiquadCoeffs mScHpDelta{};
    int mScHpSmoothRemaining = 0;

    // externally readable GR in dB (positive = compressing)
    std::atomic<float> mGainReductionDb{0.0f};
  };

} // namespace audiomix::dsp