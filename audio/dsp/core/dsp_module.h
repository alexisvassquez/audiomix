// audiomix
// AudioMIX
// audio/dsp/core/dsp_module.h
//
// Base class all DSP effects implement
// Provides stereo process() + default multichannel bridge processMulti()
// Accepts multiple inputs
// Adds optional parameter registration + RT-safe binding hooks 
// for the control plane

#pragma once
#include <string>
#include <algorithm>
#include <cstdint>

namespace audiomix::control {
    // RT-facing key type
    // Non-RT code may map human-readable names -> ParamKey
    using ParamKey = uint32_t;

    // forward decls
    // avoids pulling control-plane headers into DSP core
    // lives in audio/dsp/core/control
    class ParamRegistry;
    class ParamBindingTable;
} // namespace audiomix::control

namespace audiomix::dsp {

class DspModule {
public:
    virtual ~DspModule() = default;

    // Called before processing starts (or when sample rate (SR) changes)
    virtual void prepare(double sampleRate,
                         unsigned int maxBlockSize) = 0;

    // Clear internal state (delay lines, filters, etc)
    virtual void reset() = 0;

    // Process one stereo block
    // inL/inR (input left, input r) may alias outL/outR (output left, output right)
    // for in-place processing
    virtual void process(const float* inL, const float* inR, float* outL, float* outR, unsigned int numFrames) = 0;

    /*
      Multichannel entry point (default bridge -> stereo)
      Channels are interleaved as L/R pairs:
        0/1 = Master L/R, 2/3 = Booth L/R
      Modules that need true multichannel behavior can override
    */
    virtual void processMulti(const float* const* inputs, float* const* outputs, unsigned int numChannels, unsigned int numFrames)
    {
        if (numFrames == 0 || numChannels == 0) return;

        auto zeroIfWritable = [&](float* out) {
            if (out) std::fill(out, out + numFrames, 0.0f);
        };

        // Process in stereo pairs (0,1) (2,3)
        for (unsigned int ch = 0; ch < numChannels; ch += 2) {
            const float* inL = (ch < numChannels) ? inputs[ch] : nullptr;
            const float* inR = (ch + 1 < numChannels) ? inputs[ch + 1] : nullptr;

            float* outL = (ch < numChannels) ? outputs[ch] : nullptr;
            float* outR = (ch + 1 < numChannels) ? outputs[ch + 1] : nullptr;

            // if outputs are missing, nothing to do for this pair
            // continue
            if (!outL && !outR) continue;

            // if one side is missing, write silence to that side (null)
            if (!inL) zeroIfWritable(outL);
            if (!inR) zeroIfWritable(outR);

            /*
              if both inputs exist, run stereo process on this pair
              if one input is missing, output is already zeroed
              can still process other side if needed
              only call process() when both inputs + 1 (min) output exists
            */
            if (inL && inR) {
                process(inL, inR, outL, outR, numFrames);
            } else {
                // if only one input exists, pass through to matching output
                if (inL && outL) std::copy(inL, inL + numFrames, outL);
                if (inR && outR) std::copy(inR, inR + numFrames, outR);
            }
        }
    }

    /*
      Control plane hooks (NON-RT):
        registerParameters() declares external control surface using names
        bindParameters() creates RT-safe bindings
        no string in audio thread
      Default no-op implementation keep existing modules working unchanged

      Called during graph build/module init (non-RT)
      Modules should register human-readable parameter paths such as:
       "gain.db", "eq.band1.gain_db", "filter.cutoff_hz", etc etc etc
    */
    virtual void registerParameters(control::ParamRegistry& /*registry*/) {}

    // Called during graph build after registration (non-RT)
    // modules should bind ParamKey -> RT-safe setter ("setTarget")
    virtual void bindParameters(control::ParamBindingTable& /*bindings*/) {}

    /*
      Legacy/convenience parameter API, but not RT-safe
      Generic param hook so AudioScript/Juniper2.0 can talk to it
      IDs are arbitrary strings ("wet", "depth", "mix", etc)
      Strings are fine for tests/prototyping, but do not call from audio thread.
    */
    virtual void setParameter(const std::string& id, float value) {
        (void)id;
        (void)value;
    }
};

}  // namespace audiomix::dsp
