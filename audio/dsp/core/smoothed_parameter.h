// audiomix
// AudioMIX
// audio/dsp/core/smoothed_parameter.h
//
/* 
  Simple exponential smoothing (for wet/dry, depth, etc.)
  Smooths parameter changes over time to avoid zipper noise and create more natural transitions
  Uses a time constant (in ms) to determine the smoothing factor (alpha)
  Alpha is calculated as: alpha = 1 - exp(-1 / (sampleRate * tau)) where tau is the time constant in seconds (timeMs * 0.001)
  The process() method updates the current value towards the target value using the smoothing factor
*/

#pragma once
#include <cmath>

namespace audiomix::dsp {

class SmoothedParameter {
public:
    void prepare(double sampleRate, float timeMs) {
        mSampleRate = (sampleRate > 0.0 ? sampleRate : 44100.0);
        setTimeMs(timeMs);
        mCurrent = mTarget;
    }

    void setTimeMs(float timeMs) {
        if (timeMs <= 0.0f) {
            mAlpha = 1.0f;
            return;
        }

        const float tau = timeMs * 0.001f;
        mAlpha = 1.0f - std::exp(-1.0f / (static_cast<float>(mSampleRate) * tau));
    }

    void setTarget(float value) {
        mTarget = value;
        if (mAlpha >= 1.0f) {
            mCurrent = mTarget;
        }
    }

    float getCurrent() const { return mCurrent; }
    float getTarget() const { return mTarget; }

    float process() {
        mCurrent += mAlpha * (mTarget - mCurrent);
        return mCurrent;
    }

private:
    double mSampleRate = 44100.0;    // 44.1 kHz
    float mAlpha = 1.0f;
    float mCurrent = 0.0f;
    float mTarget = 0.0f;
};

} // namespace audiomix::dsp
