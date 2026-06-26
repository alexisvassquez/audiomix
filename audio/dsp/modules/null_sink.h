// audiomix
// AudioMIX
// audio/dsp/modules/null_sink.h
//
/**
  * A headless / dummy DSP sink.
  * This module consumes audio buffers and intentionally produces silence.
  * It is used for:
  * - headless execution (WSL, CI, SSH builds)
  * - DSP correctness testing without audio hardware
  * - offline processing pipelines
  *
  * NullSink guarantees that the DSP chain remains valid even when
  * no physical audio output device is avail
  */

#pragma once

#include "../core/dsp_module.h"

namespace audiomix::dsp {

class NullSink final : public DspModule {
public:
    NullSink() = default;
    ~NullSink() override = default;

    void prepare(double /*sampleRate*/, unsigned int /*blockSize*/) override {
        // No-op
    }

    void reset() override {
        // No-op
    }

    void process(const float* inL,
                 const float* inR,
                 float* outL,
                 float* outR,
                 unsigned int frames) override
    {
        // Intentionally discard audio output
        // Zeroing ensures downstream safety if buffers are reused
        for (unsigned int i = 0; i < frames; ++i) {
            outL[i] = 0.0f;
            outR[i] = 0.0f;
        }
    }
};

} // namespace audiomix::dsp
