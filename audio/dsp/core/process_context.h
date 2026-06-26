// audiomix
// AudioMIX
// audio/dsp/core/process_context.h
//
/*
   ProcessContext represents runtime state of a single audio processing block
   Provides DSP modules w/ access to current input/output buffers,
   frame count, channel count, + other real-time processing info.
   A new context is created for each audio block processed by the AudioMIX engine

   By packaging block-lvl data into a single structure, the DSP chain (dsp_chain.h)
   can evolve to support additional feats w/o changing core processing func signatures.

   I will be adding automation, MIDI, transport state,
   sidechains, + more modules as AudioMIX evolves.
*/

#pragma once

namespace audiomix::dsp {

// ProcessContext -> runtime block data (process phase)
struct ProcessContext {
    const float* const* inputs = nullptr;
    float* const* outputs = nullptr;
    unsigned int numChannels = 0;
    unsigned int numFrames = 0;
    double sampleRate = 44100.0;    // 44.1 kHz

    // TODO (later):
    // TransportState*
    // MidiBuffer
    // ParamState
    // MeterBus
};

} // namespace audiomix::dsp
