// audiomix
// AudioMIX
// audio/dsp/modules/clipper_module.h
//
/*
   Clipper module
   Soft clipping gently rounds signal peaks as they exceed a threshold
   Soft clip algorithm - normalized tanh soft limiting (stable, musical)

   Hard clipping abruptly cuts off audio signal once it exceeds set threshold
   Hard clip algorithm - clamp to ± ceiling (aggressive, simple)
*/

#pragma once
#include <algorithm>
#include <atomic>
#include <cmath>
#include <string>

#include "audio/dsp/core/dsp_module.h"
#include "audio/dsp/core/smoothed_parameter.h"


namespace audiomix::dsp {

class ClipperModule final : public DspModule {
public:
    enum class Mode : int { Hard = 0, Soft = 1 };

    ClipperModule() = default;

    void prepare(double sampleRate, unsigned int maxBlockSize) override;
    void reset() override;

    void process(const float* inL, const float* inR,
                 float* outL, float* outR,
                 unsigned int numFrames) override;

    // Legacy convenience API (not RT-safe)
    void setParameter(const std::string& id, float value) override;

    // Control plane hooks (non-RT)
    // placeholders for now TODO
    void registerParameters(control::ParamRegistry& registry) override;
    void bindParameters(control::ParamBindingTable& bindings) override;

    // Convenience API (C++ callers/tests)
    void setDriveDb(float db);
    float getDriveDb() const { return mDriveDb; }

    void setCeilingDb(float db);
    float getCeilingDb() const { return mCeilingDb; }

    void setMix(float mix01);
    float getMix() const { return mMix; }

    void setMode(Mode m) noexcept { mMode.store(m, std::memory_order_relaxed); }
    Mode getMode() const noexcept { return mMode.load(std::memory_order_relaxed); }

    void setSmoothingTimeMs(float ms);

    // RT-safe target setters
    // intended for bindings/audio thread
    void setDriveDbTarget(float dB, float rampTimeMs) noexcept;
    void setCeilingDbTarget(float dB, float rampTimeMs) noexcept;
    void setMixTarget(float mix01, float rampTimeMs) noexcept;

private:
    static float dBToLinear(float dB) {
        return std::pow(10.0f, dB / 20.0f);
    }

    static float clampf(float v, float lo, float hi) {
        return std::max(lo, std::min(v, hi));
    }

    static inline float hardClip(float x, float t) {
        // t assumed >= 0
        if (x > t) return t;
        if (x < -t) return -t;
        return x;
    }

    static inline float softClipTanh(float x, float t) {
        // soft limiting style, normalized by ceiling
        const float safeT = std::max(t, 1e-6f);
        const float xn = x / safeT;
        const float yn = std::tanh(xn);
        return yn * safeT;
    }

    void syncTargetsImmediate_() noexcept;

private:
    double mSampleRate = 44100.0;    // 44.1 kHz
    unsigned int mMaxBlockSize = 0;

    // UI domain values (non-RT)
    float mDriveDb = 0.0f;           // pre-gain into clipper
    float mCeilingDb = -0.1f;        // default output ceiling (<= 0 dBFS) "almost 0"
    float mMix = 1.0f;               // 0..1
    std::atomic<Mode> mMode { Mode::Soft };

    float mSmoothingMs = 20.0f;

    // Smoothed params (RT-safe read)
    // drive + ceiling are smoothed in linear space
    SmoothedParameter mDriveLin;
    SmoothedParameter mCeilingLin;
    SmoothedParameter mMixSmoothed;    // keep in 0..1 directly, still smooths fine

    // Control plane ParamKeys
    // placeholders TODO: wire later
    control::ParamKey mDriveDbKey   = 0;
    control::ParamKey mCeilingDbKey = 0;
    control::ParamKey mMixKey       = 0;
    control::ParamKey mModeKey      = 0;
};

} // namespace audiomix::dsp
