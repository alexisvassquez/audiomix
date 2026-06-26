// audiomix
// AudioMIX
// audio/dsp/modules/shimmer.h
//
/* 
  SFX: shimmer
  Texturized sound as ethereal, glassy created by a combo of reverb + pitch-shifting
  Reverb is processed w/ pitch-shifted harmonics (~octave higher)
  Implementation: a feedback delay line w/ modulated delay time to approximate pitch shift
  Control parameters:
    - Wet/dry mix
    - Feedback amount (how much of the output is fed back into the input)
    - Octave mix (how much of the delayed signal is pitch-shifted and added back in)
    - Base delay time (modulated around this time, sets the overall character of the effect)
  Threading model: safe to use with multichannel bridge, parameters can be set from control thread via setParameter() with string IDs (AS-friendly) - will clamp and sanitize inputs
*/

#pragma once
#include <string>
#include <vector>
#include <cmath>

#include "dsp_module.h"

namespace audiomix::dsp {

// A simple shimmer-style effect:
// - Feedback delay line
// - Slightly modulated delay time to approx pitch lift
// - Soft-saturated feedback tail
class ShimmerModule : public DspModule {
public:
    ShimmerModule();

    void prepare(double sampleRate,
                 unsigned int maxBlockSize) override;
    void process(const float* inL, const float* inR,
                 float* outL, float* outR,
                 unsigned int numFrames) override;
    void reset() override;
    void setParameter(const std::string& name, float value) override;

private:
    // Internal fractional delay line
    struct DelayLine {
        std::vector<float> buffer;
        std::size_t writeIndex{0};
        float delaySamples{0.0f};

        void resize(std::size_t maxSamples);
        void setDelaySamples(float d);
        float process(float x);    // x = input; returns delayed sample
        void clear();
    };

    double mSampleRate{44100.0};
    unsigned int mMaxBlockSize{512};

    DelayLine mDelayL;
    DelayLine mDelayR;

    // Parameters
    float mWet{0.35f};             // 0..1
    float mFeedback{0.6f};         // 0..0.95
    float mOctaveMix{1.0f};        // 0..1, how strong the shimmer tail is
    float mBaseDelayMs{450.0f};    // base delay time in ms

    // Simple LFO for delay modulation (approx pitch shift)
    float mPhase{0.0f};
    float mPhaseInc{0.0f};         // radians p/sample

    // Feedback memory
    float mFbL{0.0f};
    float mFbR{0.0f};

    static float clamp(float v, float lo, float hi);
};

} // namespace audiomix::dsp
