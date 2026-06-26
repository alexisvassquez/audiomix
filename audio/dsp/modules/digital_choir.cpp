// audiomix
// AudioMIX
// audio/dsp/modules/digital_choir.cpp
//
// Refer to `digital_choir.h`
// SFX: "harmonic cloud", implemented as a lush ensemble/choir

#include <algorithm>
#include <cmath>

#include "audio/dsp/modules/digital_choir.h"

namespace audiomix::dsp {

DigitalChoirModule::DigitalChoirModule(int numVoices)
    : mNumVoices(numVoices > 0 ? numVoices : 1)
{
    buildDefaultLayout();
}

void DigitalChoirModule::buildDefaultLayout() {
    mVoices.clear();
    mVoices.resize(static_cast<std::size_t>(mNumVoices));

    for (int i = 0; i < mNumVoices; ++i) {
        float t = (mNumVoices > 1)
                  ? static_cast<float>(i) / static_cast<float>(mNumVoices - 1)
                  : 0.5f;

        Voice v;
        // 10-30 ms across voices
        v.baseDelayMs = 10.0f + 20.0f * t;
        // 3-8 ms modulation
        v.modDepthMs = 3.0f + 5.0f * (1.0f - t);
        // pan spread -0.9 to +0.9
        v.pan = -0.9f + 1.8f * t;
        // slight center emphasis
        v.gain = 0.23f + 0.07f * (0.5f - std::abs(t - 0.5f));
        // vibrato
        // Definition: musical effect consisting of a rapid/regular oscillation in pitch
        // adds warmth and expressiveness to a vocal/instrumental tone
        v.vibratoRateHz = 0.35f + 0.9f * t;
        v.vibratoDepthCents = 4.0f + 4.0f * (1.0f - std::abs(t - 0.5f));

        mVoices[static_cast<std::size_t>(i)] = v;
    }
}

void DigitalChoirModule::prepare(double sampleRate,
                                 unsigned int maxBlockSize)
{
    mSampleRate = (sampleRate > 0.0 ? sampleRate : 44100.0);
    mMaxBlockSize = (maxBlockSize > 0 ? maxBlockSize : 512);

    for (auto& v : mVoices) {
        v.delay.prepare(mSampleRate, 50.0f);    // 50 ms max delay
        v.lfo.prepare(mSampleRate);             // low-freq oscillaton
        v.lfo.setFrequency(v.vibratoRateHz);
        v.lfo.reset();
    }

    // wet/dry texture - balance btwn original, unprocessed "dry" signal +
    // processed "wet" signal
    // "dry" - clean and direct sound,
    // "wet" - sound w/ effects (reverb, delay, modulation, etc.) applied
    // "wet" sounds create more spacious, atmospheric quality
    mWet.prepare(mSampleRate, 30.0f);    // 30 ms smoothing
    mDry.prepare(mSampleRate, 30.0f);
    mWet.setTarget(0.7f);
    mDry.setTarget(1.0f);
}

void DigitalChoirModule::reset() {
    for (auto& v : mVoices) {
        v.delay.reset();
        v.lfo.reset();
    }
}

void DigitalChoirModule::setParameter(const std::string& id, float value) {
    const float v = std::clamp(value, 0.0f, 1.0f);

    if (id == "wet") {
        mWet.setTarget(v);
    } else if (id == "dry") {
        mDry.setTarget(v);
    } else if (id == "spread") {
        // 0 = mono, 1 = wide
        const float spread = v;
        const std::size_t n = mVoices.size();
        for (std::size_t i = 0; i < n; ++i) {
            float t = (n > 1) ? static_cast<float>(i) / static_cast<float>(n - 1) : 0.5;
            mVoices[i].pan = spread * (-0.9f + 1.8f * t);
        }
    }
    // TODO: Future - density, brightness etc.
}

void DigitalChoirModule::process(const float* inL, const float* inR,
                                 float* outL, float* outR,
                                 unsigned int numFrames)
{
    if (!outL || !outR) return ;

    // if no input, treat as silence (just output zeros)
    const bool hasInput = (inL != nullptr && inR != nullptr);

    for (unsigned int n = 0; n < numFrames; ++n) {
        const float inSampleL = hasInput ? inL[n] : 0.0f;
        const float inSampleR = hasInput ? inR[n] : 0.0f;

        // downmix stereo -> mono for cloud
        const float monoIn = 0.5f * (inSampleL + inSampleR);

        float wetL = 0.0f;
        float wetR = 0.0f;

        for (auto& v : mVoices) {
            // vibrato as small time modulation around baseDelayMs
            const float lfoVal = v.lfo.process();    // -1..+1
            const float delayMs =
                v.baseDelayMs +
                v.modDepthMs * lfoVal;

            const float delayed = v.delay.process(monoIn, delayMs);

            // equal power pan
            const float pan = std::clamp(v.pan, -1.0f, 1.0f);
            const float angle = (pan * 0.5f + 0.5f) *
                                1.57079632679f;    // pi(3.14)/2
            const float gL = std::cos(angle);
            const float gR = std::sin(angle);

            const float vs = delayed * v.gain;
            wetL += vs * gL;
            wetR += vs * gR;
        }

        const float wet = mWet.process();
        const float dry = mDry.process();

        outL[n] = dry * inSampleL + wet * wetL;
        outR[n] = dry * inSampleR + wet * wetR;
    }
}

} // namespace audiomix::dsp
