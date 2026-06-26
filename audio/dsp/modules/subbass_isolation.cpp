// audiomix
// AudioMIX
// audio/dsp/modules/subbass_isolation.cpp
//
/*
  Normalizes filter coefficients so that a0 = 1
  This keeps processing efficient and predictable.
*/

#include "subbass_isolation.h"

namespace audiomix::dsp {

static inline void normalize(
    float& b0, float& b1, float& b2,
    float& a0, float& a1, float& a2,
    Biquad& bq)
{
    b0 /= a0;
    b1 /= a0;
    b2 /= a0;
    a1 /= a0;
    a2 /= a0;

    bq.setCoeffs(b0, b1, b2, a1, a2);
}

/*
  RBJ Lowpass Filter:
    f0 = cutoff freq
    Q = resonance (0.707 = flat Butterworth)
*/
void RBJ::lowpass(float fs, float f0, float Q, Biquad& bq)
{
    const float w0 = 2.0f * (float)M_PI * (f0 / fs);
    const float c  = std::cos(w0);
    const float s  = std::sin(w0);
    const float alpha = s / (2.0f * Q);

    float b0 = (1.0f + c) * 0.5f;
    float b1 = -(1.0f + c);
    float b2 = (1.0f + c) * 0.5f;
    float a0 = 1.0f + alpha;
    float a1 = -2.0f * c;
    float a2 = 1.0f - alpha;

    normalize(b0,b1,b2,a0,a1,a2,bq);
}

} // namespace audiomix::dsp
