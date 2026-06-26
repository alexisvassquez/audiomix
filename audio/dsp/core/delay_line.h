// audiomix
// AudioMIX
// audio/dsp/core/delay_line.h
//
// Fractional delay with linear interpolation
// Method for estimating a missing value btwn two known data points by drawing
// a straight line btwn them.

#pragma once
#include <vector>
#include <algorithm>
#include <cmath>

namespace audiomix::dsp {

class DelayLine {
public:
    void prepare(double sampleRate, float maxDelayMs) {
        mSampleRate = (sampleRate > 0.0 ? sampleRate : 44100.0);
        const int maxSamples =
            static_cast<int>(std::ceil(maxDelayMs * 0.001 * mSampleRate)) + 4;
        mBuffer.assign(maxSamples, 0.0f);
        mWriteIndex = 0;
    }

    // Write then read a delayed sample
    float process(float inputSample, float delayMs) {
        if (mBuffer.empty()) return inputSample;

        mBuffer[mWriteIndex] = inputSample;

        const float delaySamples = delayMs * 0.001f * static_cast<float>(mSampleRate);
        const int maxIndex = static_cast<int>(mBuffer.size()) - 1;
        float d = delaySamples;
        if (d < 0.0f) d = 0.0f;
        if (d > static_cast<float>(maxIndex - 2)) {
            d = static_cast<float>(maxIndex - 2);
        }

        float readIndex = static_cast<float>(mWriteIndex) - d;
        while (readIndex < 0.0f) {
            readIndex += static_cast<float>(mBuffer.size());
        }

        const int idx0 = static_cast<int>(readIndex);
        const int idx1 = (idx0 + 1) % static_cast<int>(mBuffer.size());
        const float frac = readIndex - static_cast<float>(idx0);

        const float s0 = mBuffer[idx0];
        const float s1 = mBuffer[idx1];
        const float out = s0 + (s1 - s0) * frac;

        mWriteIndex = (mWriteIndex + 1) % static_cast<int>(mBuffer.size());
        return out;
    }

    void reset() {
        std::fill(mBuffer.begin(), mBuffer.end(), 0.0f);
        mWriteIndex = 0;
    }

private:
    double mSampleRate = 44100.0;
    std::vector<float> mBuffer;
    int mWriteIndex = 0;
};

} // namespace audiomix::dsp
