// audiomix
// AudioMIX
// audio/dsp/core/rbj_coeffs.h
//
/*
  RBJ Cookbook coefficient generator
  This header generates normalized biquad coefficients
  a0 noramlized to 1

  Intentionally general-purpose and does not depend on EQ business logic
*/

#pragma once
#include <cmath>
#include <algorithm>

namespace audiomix::dsp::rbj {
    struct BiquadCoeffs {
        float b0, b1, b2; // feedforward coefficients
        float a1, a2;     // feedback coefficients (a0 is normalized to 1)
    
        static constexpr BiquadCoeffs identity() noexcept {
            return {1.0f, 0.0f, 0.0f, 0.0f, 0.0f};
        }
};

enum class RbjFilterType {
    LowPass,
    HighPass,
    BandPass,
    Notch,
    AllPass,
    PeakingEQ,
    LowShelf,
    HighShelf
};

class RbjCoeffs {
public:
    static constexpr float kPi = 3.14159265358979323846f;
    static constexpr float kMinSampleRate = 1.0f; // Avoid division by zero
    static constexpr float kMinFrequency = 1.0e-3f;
    static constexpr float kMinQ = 1.0e-4f;

    static inline BiquadCoeffs makeLowpass(float sampleRate, float frequency,float q = 0.7071f) {
        const Common c = makeCommon(sampleRate, frequency, q);
        const float b0 = (1.0f - c.cos_w0) * 0.5f;
        const float b1 = 1.0f - c.cos_w0;
        const float b2 = (1.0f - c.cos_w0) * 0.5f;
        const float a0 = 1.0f + c.alpha;
        const float a1 = -2.0f * c.cos_w0;
        const float a2 = 1.0f - c.alpha;
        return normalize(b0, b1, b2, a0, a1, a2);
    }

    static inline BiquadCoeffs makeHighpass(float sampleRate, float frequency, float q = 0.7071f) {
        const Common c = makeCommon(sampleRate, frequency, q);
        const float b0 = (1.0f + c.cos_w0) * 0.5f;
        const float b1 = -(1.0f + c.cos_w0);
        const float b2 = (1.0f + c.cos_w0) * 0.5f;
        const float a0 = 1.0f + c.alpha;
        const float a1 = -2.0f * c.cos_w0;
        const float a2 = 1.0f - c.alpha;
        return normalize(b0, b1, b2, a0, a1, a2);
    }

    static inline BiquadCoeffs makeBandpass(float sampleRate, float frequency, float q = 1.0f) {
        const Common c = makeCommon(sampleRate, frequency, q);
        const float b0 = c.alpha;
        const float b1 = 0.0f;
        const float b2 = -c.alpha;
        const float a0 = 1.0f + c.alpha;
        const float a1 = -2.0f * c.cos_w0;
        const float a2 = 1.0f - c.alpha;
        return normalize(b0, b1, b2, a0, a1, a2);
    }

    static inline BiquadCoeffs makeNotch(float sampleRate, float frequency, float q = 1.0f) {
        const Common c = makeCommon(sampleRate, frequency, q);
        const float b0 = 1.0f;
        const float b1 = -2.0f * c.cos_w0;
        const float b2 = 1.0f;
        const float a0 = 1.0f + c.alpha;
        const float a1 = -2.0f * c.cos_w0;
        const float a2 = 1.0f - c.alpha;
        return normalize(b0, b1, b2, a0, a1, a2);
    }

    static inline BiquadCoeffs makeAllpass(float sampleRate, float frequency, float q = 1.0f) {
        const Common c = makeCommon(sampleRate, frequency, q);
        const float b0 = 1.0f - c.alpha;
        const float b1 = -2.0f * c.cos_w0;
        const float b2 = 1.0f + c.alpha;
        const float a0 = 1.0f + c.alpha;
        const float a1 = -2.0f * c.cos_w0;
        const float a2 = 1.0f - c.alpha;
        return normalize(b0, b1, b2, a0, a1, a2);
    }

    static inline BiquadCoeffs makePeakingEQ(float sampleRate, float frequency, float q, float gainDb) {
        const Common c = makeCommon(sampleRate, frequency, q);
        const float A = dbToAmpCookbook(gainDb);
        const float b0 = 1.0f + c.alpha * A;
        const float b1 = -2.0f * c.cos_w0;
        const float b2 = 1.0f - c.alpha * A;
        const float a0 = 1.0f + c.alpha / A;
        const float a1 = -2.0f * c.cos_w0;
        const float a2 = 1.0f - c.alpha / A;
        return normalize(b0, b1, b2, a0, a1, a2);
    }

    static inline BiquadCoeffs makeLowShelf(float sampleRate, float frequency,float gainDb, float shelfSlope = 1.0f) {
        const float sr = clampSampleRate(sampleRate);
        const float f0 = clampFrequency(frequency, sr);
        const float S = std::max(shelfSlope, kMinQ);

        const float A = dbToAmpCookbook(gainDb);
        const float w0 = 2.0f * kPi * f0 / sr;
        const float cos_w0 = std::cos(w0);
        const float sin_w0 = std::sin(w0);

        const float alpha = sin_w0 * 0.5f * std::sqrt((A + 1.0f / A) * (1.0f / S - 1.0f) + 2.0f);

        const float twoSqrtAAlpha = 2.0f * std::sqrt(A) * alpha;
        const float Aplus1 = A + 1.0f;
        const float Aminus1 = A - 1.0f;

        const float b0 = A * (Aplus1 - Aminus1 * cos_w0 + twoSqrtAAlpha);
        const float b1 = 2.0f * A * (Aminus1 - Aplus1 * cos_w0);
        const float b2 = A * (Aplus1 - Aminus1 * cos_w0 - twoSqrtAAlpha);
        const float a0 = Aplus1 + Aminus1 * cos_w0 + twoSqrtAAlpha;
        const float a1 = -2.0f * (Aminus1 + Aplus1 * cos_w0);
        const float a2 = Aplus1 + Aminus1 * cos_w0 - twoSqrtAAlpha;
        return normalize(b0, b1, b2, a0, a1, a2);
    }

    static inline BiquadCoeffs makeHighShelf(float sampleRate, float frequency, float gainDb, float shelfSlope = 1.0f) {
        const float sr = clampSampleRate(sampleRate);
        const float f0 = clampFrequency(frequency, sr);
        const float S = std::max(shelfSlope, kMinQ);

        const float A = dbToAmpCookbook(gainDb);
        const float w0 = 2.0f * kPi * f0 / sr;
        const float cos_w0 = std::cos(w0);
        const float sin_w0 = std::sin(w0);

        const float alpha = sin_w0 * 0.5f * std::sqrt((A + 1.0f / A) * (1.0f / S - 1.0f) + 2.0f);

        const float twoSqrtAAlpha = 2.0f * std::sqrt(A) * alpha;
        const float Aplus1 = A + 1.0f;
        const float Aminus1 = A - 1.0f;

        const float b0 = A * (Aplus1 + Aminus1 * cos_w0 + twoSqrtAAlpha);
        const float b1 = -2.0f * A * (Aminus1 + Aplus1 * cos_w0);
        const float b2 = A * (Aplus1 + Aminus1 * cos_w0 - twoSqrtAAlpha);
        const float a0 = Aplus1 - Aminus1 * cos_w0 + twoSqrtAAlpha;
        const float a1 = 2.0f * (Aminus1 - Aplus1 * cos_w0);
        const float a2 = Aplus1 - Aminus1 * cos_w0 - twoSqrtAAlpha;
        return normalize(b0, b1, b2, a0, a1, a2);
    }

    static inline BiquadCoeffs makeFilter(RbjFilterType type, float sampleRate, float frequency, float q = 0.7071f, float gainDb = 0.0f, float shelfSlope = 1.0f) {
        switch (type) {
            case RbjFilterType::LowPass:
                return makeLowpass(sampleRate, frequency, q);
            case RbjFilterType::HighPass:
                return makeHighpass(sampleRate, frequency, q);
            case RbjFilterType::BandPass:
                return makeBandpass(sampleRate, frequency, q);
            case RbjFilterType::Notch:
                return makeNotch(sampleRate, frequency, q);
            case RbjFilterType::AllPass:
                return makeAllpass(sampleRate, frequency, q);
            case RbjFilterType::PeakingEQ:
                return makePeakingEQ(sampleRate, frequency, q, gainDb);
            case RbjFilterType::LowShelf:
                return makeLowShelf(sampleRate, frequency, gainDb, shelfSlope);
            case RbjFilterType::HighShelf:
                return makeHighShelf(sampleRate, frequency, gainDb, shelfSlope);
            default:
                return BiquadCoeffs::identity();
        }
    }

private:
    struct Common {
        float cos_w0 {0.0f};
        float alpha {0.0f};
    };

    static inline float clampSampleRate(float sampleRate) {
        return std::max(sampleRate, kMinSampleRate);
    }

    static inline float clampFrequency(float frequency, float sampleRate) {
        const float nyquist = sampleRate * 0.5f;
        const float maxFreq = std::max(kMinFrequency, nyquist - kMinFrequency);
        return std::clamp(frequency, kMinFrequency, maxFreq);
    }

    static inline float clampQ(float q) {
        return std::max(q, kMinQ);
    }

    static inline float dbToAmpCookbook(float gainDb) {
        // RBJ cookbook convention for peaking/shelving filters uses A = 10^(gainDb/40)
        return std::pow(10.0f, gainDb / 40.0f);
    }

    static inline Common makeCommon(float sampleRate, float frequency, float q) {
        const float sr = clampSampleRate(sampleRate);
        const float f0 = clampFrequency(frequency, sr);
        const float Q = clampQ(q);

        const float w0 = 2.0f * kPi * f0 / sr;
        const float cos_w0 = std::cos(w0);
        const float sin_w0 = std::sin(w0);
        const float alpha = sin_w0 / (2.0f * Q);

        return {cos_w0, alpha};
    }

    static inline BiquadCoeffs normalize(float b0, float b1, float b2, float a0, float a1, float a2) {
        if (std::fabs(a0) < 1.0e-12f) {
            // Avoid division by zero, return identity filter
            return BiquadCoeffs::identity();
        }

        const float invA0 = 1.0f / a0;
        return {
            b0 * invA0,
            b1 * invA0,
            b2 * invA0,
            a1 * invA0,
            a2 * invA0
        };
    }
};

} // namespace audiomix::dsp::rbj