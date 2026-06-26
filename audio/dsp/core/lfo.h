// audiomix
// AudioMIX
// audio/dsp/core/lfo.h
//
// Base sine LFO
// Definition: Low-freq oscillation (LFO) is an electronic freq that is
// usually below 20Hz and creates a rhythmic pulse or sweep.
// LFOs are used to modulate musical equipment (ex; synths) to create audio effects

#pragma once
#include <cmath>

namespace audiomix::dsp {

class SimpleLFO {
public:
    void prepare(double sampleRate) {
        mSampleRate = (sampleRate > 0.0 ? sampleRate : 44100.0);
        updateIncrement();
    }

    void setFrequency(float freqHz) {
        mFrequency = (freqHz >= 0.0f ? freqHz : 0.0f);
        updateIncrement();
    }

    void reset(float phase = 0.0f) { mPhase = phase; }

    float process() {
        float value = std::sin(mPhase);
        mPhase += mPhaseInc;
        if (mPhase > twoPi) mPhase -= twoPi;
        return value;
    }

private:
    void updateIncrement() {
        mPhaseInc = twoPi * mFrequency / static_cast<float>(mSampleRate);
    }

    static constexpr float twoPi = 6.28318530717958647693f;

    double mSampleRate = 44100.0;
    float mFrequency = 0.5f;
    float mPhase = 0.0f;
    float mPhaseInc = twoPi * 0.5f / 44100.0f;
};

} // namespace audiomix::dsp
