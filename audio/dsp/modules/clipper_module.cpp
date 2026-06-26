// audiomix
// AudioMIX
// audio/dsp/modules/clipper_module.cpp
//
/* 
  Safe with multichannel bridge
  Implements hard and soft clipping modes with drive, ceiling, and mix controls
  Uses SmoothedParameter for smooth transitions of drive, ceiling, and mix
  Control plane hooks are placeholders for now, will wire up later with ParamRegistry/BindingTable
*/

#include "clipper_module.h"

namespace audiomix::dsp {

void ClipperModule::syncTargetsImmediate_() noexcept {
    // Re-prepare and set targets so reset/prepare land in a deterministic state
    mDriveLin.prepare(mSampleRate, mSmoothingMs);
    mCeilingLin.prepare(mSampleRate, mSmoothingMs);
    mMixSmoothed.prepare(mSampleRate, mSmoothingMs);

    // set initial targets based on current UI-domain state
    mDriveLin.setTarget(dBToLinear(mDriveDb));
    mCeilingLin.setTarget(dBToLinear(mCeilingDb));
    mMixSmoothed.setTarget(clampf(mMix, 0.0f, 1.0f));

    // if smoother snaps at 0 ms, these become immediate
    // otherwise this still establishes fresh target state after prep/reset
    (void)mDriveLin.process();
    (void)mCeilingLin.process();
    (void)mMixSmoothed.process();
}

void ClipperModule::prepare(double sampleRate, unsigned int maxBlockSize) {
    mSampleRate = (sampleRate > 1.0) ? sampleRate : 44100.0f;    // 44.1 kHz
    mMaxBlockSize = maxBlockSize;
    syncTargetsImmediate_();
}

void ClipperModule::reset() {
    syncTargetsImmediate_();
}

void ClipperModule::setSmoothingTimeMs(float ms) {
    mSmoothingMs = clampf(ms, 0.0f, 200.0f);

    // SmoothedParameter snaps if ms==0
    mDriveLin.setTimeMs(mSmoothingMs);
    mCeilingLin.setTimeMs(mSmoothingMs);
    mMixSmoothed.setTimeMs(mSmoothingMs);
}

void ClipperModule::setDriveDb(float db) {
    mDriveDb = clampf(db, -60.0f, 24.0f);
    mDriveLin.setTarget(dBToLinear(mDriveDb));
}

void ClipperModule::setCeilingDb(float db) {
    // ceiling should not exceed 0 dBFS
    mCeilingDb = clampf(db, -60.0f, 0.0f);
    mCeilingLin.setTarget(dBToLinear(mCeilingDb));
}

void ClipperModule::setMix(float mix01) {
    mMix = clampf(mix01, 0.0f, 1.0f);
    mMixSmoothed.setTarget(mMix);
}

void ClipperModule::setDriveDbTarget(float dB, float rampTimeMs) noexcept {
    mDriveDb = clampf(dB, -60.0f, 24.0f);
    mDriveLin.setTimeMs(clampf(rampTimeMs, 0.0f, 200.0f));
    mDriveLin.setTarget(dBToLinear(mDriveDb));
}

void ClipperModule::setCeilingDbTarget(float dB, float rampTimeMs) noexcept {
    mCeilingDb = clampf(dB, -60.0f, 0.0f);
    mCeilingLin.setTimeMs(clampf(rampTimeMs, 0.0f, 200.0f));
    mCeilingLin.setTarget(dBToLinear(mCeilingDb));
}

void ClipperModule::setMixTarget(float mix01, float rampTimeMs) noexcept {
    mMix = clampf(mix01, 0.0f, 1.0f);
    mMixSmoothed.setTimeMs(clampf(rampTimeMs, 0.0f, 200.0f));
    mMixSmoothed.setTarget(mMix);
}

void ClipperModule::setParameter(const std::string& id, float value) {
    if (id == "drive.db" || id == "drive_db" || id == "drive") {
        setDriveDb(value);
    } else if (id == "ceiling.db" || id == "ceiling_db" || id == "ceiling") {
        setCeilingDb(value);
    } else if (id == "mix" || id == "wet") {
        setMix(value);
    } else if (id == "mode") {
        mMode = (value < 0.5f) ? Mode::Hard : Mode::Soft;
    }
}

void ClipperModule::process(const float* inL, const float* inR,
                            float* outL, float* outR,
                            unsigned int numFrames) {
    if (numFrames == 0) return;

    // processMulti bridge can invoke process w/ a missing output (defensive)
    const bool hasOutL = (outL != nullptr);
    const bool hasOutR = (outR != nullptr);
    if (!hasOutL && !hasOutR) return;

    const Mode mode = mMode.load(std::memory_order_relaxed);

    // process per-sample to get smooth parameter changes w/o stepping artifacts
    // cheap (light tech debt - few mulitplies + tanh/clamp)
    for (unsigned int i = 0; i < numFrames; ++i) {
        const float dryL = (inL ? inL[i] : 0.0f);
        const float dryR = (inR ? inR[i] : 0.0f);

        const float drive   = mDriveLin.process();
        const float ceiling = std::max(mCeilingLin.process(), 1e-6f);
        const float mix     = mMixSmoothed.process();

        const float xL = dryL * drive;
        const float xR = dryR * drive;

        float wetL = 0.0f;
        float wetR = 0.0f;

        if (mMode == Mode::Hard) {
            wetL = hardClip(xL, ceiling);
            wetR = hardClip(xR, ceiling);
        } else {
            wetL = softClipTanh(xL, ceiling);
            wetR = softClipTanh(xR, ceiling);
        }

        float yL = dryL + (wetL - dryL) * mix;
        float yR = dryR + (wetR - dryR) * mix;

        // final output ceiling enforcement
        // makes "ceiling" behave as a true module output ceiling
        // not just a ceiling on the wet path
        if (mode == Mode::Hard) {
            yL = hardClip(yL, ceiling);
            yR = hardClip(yR, ceiling);
        } else {
            yL = softClipTanh(yL, ceiling);
            yR = softClipTanh(yR, ceiling);
        }

        if (hasOutL) outL[i] = yL;
        if (hasOutR) outR[i] = yR;
    }
}

// Placeholders for now
// reflects GainModule
void ClipperModule::registerParameters(control::ParamRegistry& /*registry*/) {}
void ClipperModule::bindParameters(control::ParamBindingTable& /*bindings*/) {}

} // namespace audiomix::dsp
