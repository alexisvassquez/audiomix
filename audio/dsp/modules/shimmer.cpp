// audiomix
// AudioMIX
// audio/dsp/modules/shimmer.cpp
//
// Refer to `shimmer.h`
// DelayLine implementation
// Definition: a digital filter, allows a signal to be delayed by
// a number of samples

#include <cmath>
#include <algorithm> // std::fill

#include "shimmer.h"

namespace audiomix::dsp {

void ShimmerModule::DelayLine::resize(std::size_t maxSamples) {
    buffer.assign(maxSamples, 0.0f);
    writeIndex = 0;
}

void ShimmerModule::DelayLine::setDelaySamples(float d) {
    if (d < 1.0f) d = 1.0f;
    if (buffer.empty()) d = 1.0f;
    // do not clamp above buffer size
    delaySamples = d;
}

float ShimmerModule::DelayLine::process(float x) {
    if (buffer.empty()) {
        return x;    // refer to shimmer.h
    }

    const std::size_t n = buffer.size();

    // Write input at current position
    buffer[writeIndex] = x;

    // Compute fractional read index (writeIndex - delaySamples)
    float readIndex = static_cast<float>(writeIndex) - delaySamples;
    while (readIndex < 0.0f) {
        readIndex += static_cast<float>(n);
    }

    std::size_t i0 = static_cast<std::size_t>(readIndex);
    std::size_t i1 = (i0 + 1) % n;
    float frac = readIndex - static_cast<float>(i0);

    float y0 = buffer[i0];
    float y1 = buffer[i1];
    float y = y0 + (y1 - y0) * frac;

    // Advance write head
    writeIndex = (writeIndex + 1) % n;

    return y;
}

void ShimmerModule::DelayLine::clear() {
    std::fill(buffer.begin(), buffer.end(), 0.0f);
    writeIndex = 0;
}

// ShimmerModule
ShimmerModule::ShimmerModule() = default;

float ShimmerModule::clamp(float v, float lo, float hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

void ShimmerModule::prepare(double sampleRate, unsigned int maxBlockSize) {
    mSampleRate = (sampleRate > 0.0) ? sampleRate : 44100.0;
    mMaxBlockSize = maxBlockSize > 0 ? maxBlockSize : 512;

    // allocate enough delay for base delay + some modulation + block overlap
    const float maxDelayMs = mBaseDelayMs * 1.5f;
    const std::size_t maxDelaySamples =
        static_cast<std::size_t>(maxDelayMs * 0.001f * mSampleRate) + mMaxBlockSize;

    mDelayL.resize(maxDelaySamples);
    mDelayR.resize(maxDelaySamples);

    // LFO ~0.25 Hz for subtle shimmer movement
    const float lfoFreq = 0.25f;
    const float twoPi = 6.28318530717958647692f;
    mPhaseInc = twoPi * lfoFreq / static_cast<float>(mSampleRate);
    mPhase = 0.0f;

    mFbL = 0.0f;
    mFbR = 0.0f;
}

void ShimmerModule::reset() {
    mDelayL.clear();
    mDelayR.clear();
    mPhase = 0.0f;
    mFbL = 0.0f;
    mFbR = 0.0f;
}

void ShimmerModule::setParameter(const std::string& name, float value) {
    if (name == "wet") {    // processed sound
        mWet = clamp(value, 0.0f, 1.0f);
    } else if (name == "feedback") {    // portion of sys's output is fed back to input
        mFeedback = clamp(value, 0.0f, 0.95f);
    } else if (name == "octave_mix") {    // original sound is mixed w/ 1+ copies of itself -+ an octave
        mOctaveMix = clamp(value, 0.0f, 1.0f);
    } else if (name == "delay_ms") {    // delayed by a millisecond
        mBaseDelayMs = clamp(value, 50.0f, 1500.0f);
    }    // next prepare() will size the buffer
}

void ShimmerModule::process(const float* inL, const float* inR,
                            float* outL, float* outR,
                            unsigned int numFrames) {
    if (!outL || !outR) {
        return;
    }

    const float twoPi = 6.28318530717958647692f;    // pi * 2
    const float baseDelaySamples =
        mBaseDelayMs * 0.001f * static_cast<float>(mSampleRate);

    for (unsigned int i = 0; i < numFrames; ++i) {
        const float dryL = inL ? inL[i] : 0.0f;    // original unprocessed sound
        const float dryR = inR ? inR[i] : 0.0f;

        // simple LFO modulation for delay time
        mPhase += mPhaseInc;
        if (mPhase > twoPi) {
            mPhase -= twoPi;
        }

        const float mod = 0.5f * (1.0f + std::sin(mPhase));    // 0..1
        const float modScale = 0.96f + 0.08f * mod;             // ~0.96..1.04
        const float currentDelay = baseDelaySamples * modScale;

        mDelayL.setDelaySamples(currentDelay);
        mDelayR.setDelaySamples(currentDelay);

        // Feedback input
        const float inWithFbL = dryL + mFbL * mFeedback;
        const float inWithFbR = dryR + mFbR * mFeedback;

        // Through delay
        const float delayedL = mDelayL.process(inWithFbL);
        const float delayedR = mDelayR.process(inWithFbR);

        // soft non-linearity to add "shimmer" character
        const float octaveL = std::tanh(delayedL * 1.8f);
        const float octaveR = std::tanh(delayedR * 1.8f);

        // store for next feedback iteration
        mFbL = octaveL;
        mFbR = octaveR;

        const float shimmerL = octaveL * mOctaveMix;
        const float shimmerR = octaveR * mOctaveMix;

        // Wet/dry mix
        const float dryGain = 1.0f - mWet;
        outL[i] = dryL * dryGain + shimmerL * mWet;
        outR[i] = dryR * dryGain + shimmerR * mWet;
    }
}

}  // namespace audiomix::dsp
