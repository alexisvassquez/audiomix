// audiomix
// AudioMIX
// audio/dsp/core/subbass_bus.h
//
/*
  This struct acts a real-time safe communication bridge between:
     1. SubBassIsolationModule (analysis stage)
     2. Other DSP modules (EQModule, etc. check the directory)
     3. UI / meters (to plug in)

   We are using std::atomic<float> to avoid mutexes
   Audio thread must never block - we can't have that during live performances
   All writes use relaxed memory order since this is one-way telemetry
*/

#pragma once
#include <atomic>

namespace audiomix::dsp {

struct SubBassBus {
    // RMS energy of left sub-band (linear amplitude)
    std::atomic<float> rmsL{0.0f};

    // RMS energy of right sub-band
    std::atomic<float> rmsR{0.0f};

    // smoothed mono RMS (used for EQ automation decisions)
    std::atomic<float> rmsMono{0.0f};

    // suggested EQ adjustment in dB
    // allows analysis modules to recommend corrections
    // it is optional: EQ Module may choose to use or ignore this
    std::atomic<float> suggestedLowShelfOffsetDb{0.0f};

    // stored for UI/debug visibility
    std::atomic<float> bandLowHz{20.0f};
    std::atomic<float> bandHighHz{90.0f};
};

} // namespace audiomix::dsp
