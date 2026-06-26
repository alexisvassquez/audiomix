// audiomix
// AudioMIX
// audio/dsp/core/process_spec.h
//
/*
   ProcessSpec defines the static config used to prepare DSP modules
   before real-time audio processing begins.

   It describes the processing environn (incl sample rate, max block size, + channel count).
   Modules use this info to allocate buffers, initialize filters, + config
   internal state during prepare() phase.

   ProcessSpec separates engine setup time info from per-audio-block runtime
   data so we can be sure that modules will/can be initialized safely before
   entering the audio thread.

   Prevents bugs, zipper noise, crashes, etc.
*/

#pragma once

namespace audiomix::dsp {

// ProcessSpec -> setup time config (prep phase)
struct ProcessSpec {
    double sampleRate = 44100.0;    // 44.1 kHz
    unsigned int maxBlockSize = 0;
    unsigned int numChannels = 0;
};

} // namespace audiomix::dsp
