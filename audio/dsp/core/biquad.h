// audiomix
// AudioMIX
// audio/dsp/core/biquad.h
//
/*
   RBJ Cookbook biquad processing
   Per-channel biquad state refers to the independent storage of delay variables
   for each audio channel in a digital biquad filter
   allowing a single set of filter coefficients to process multiple channels independently
   Maintains proper filter performance across stereo/multichannel signals
   Smooth coefficient morphing (over N samples - no clicks)
*/

#pragma once
#include <cmath>

#include "../core/rbj_coeffs.h"

namespace audiomix::dsp {
  using rbj::BiquadCoeffs;

  struct BiquadState {
    float z1 = 0.0f;
    float z2 = 0.0f;
  };

  inline void biquad_reset(BiquadState& s) noexcept {
    s.z1 = 0.0f;
    s.z2 = 0.0f;
  };

  inline void biquad_reset_all(BiquadState* states, unsigned int count) noexcept {
    if (!states) return;
    for (unsigned int i = 0; i < count; ++i) {
        biquad_reset(states[i]);
    };
  };

  /*
   Transposed Direct Form II (stable + efficient)
   TDF-II - a digital filter structure that implements an IIR filter
   first processes zeros (0) (called feedforward path), then poles (feedback path)
   shares delay lines, which results in fewer states + better numerical perform
   read more: https://ccrma.stanford.edu/~jos/fp/Transposed_Direct_Forms.html
  */

  inline float biquad_process_sample(const BiquadCoeffs& c, BiquadState& s, float x) noexcept {
    const float y = c.b0 * x + s.z1;
    s.z1 = c.b1 * x - c.a1 * y + s.z2;
    s.z2 = c.b2 * x - c.a2 * y;
    return y;
  };

  inline void biquad_set_identity(BiquadCoeffs& c) noexcept {
    c = BiquadCoeffs::identity();
  };

}    // namespace audiomix::dsp
