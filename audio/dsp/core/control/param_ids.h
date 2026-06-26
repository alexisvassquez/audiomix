// audiomix
// AudioMIX
// audio/dsp/core/control/param_ids.h
//
/*
   Minimal small starter ID list
   Included a global ParamID plus a few basics
   Not the final API surface - bootstrap spine
   Small starter ID list at first
   Adding more as we wire modules
   IDs are RT-facing keys (no strings in the audio callback)
   v1 :)
*/

#pragma once
#include <cstdint>

namespace audiomix::control {

enum class ParamID : uint16_t {
    // Global / engine-level
    GainDb = 0,          // dB gain for GainModule
    GainSmoothingMs,     // external control of smoothing

    // EQ
    // Mostly placeholder, will expand when wiring EQ
    EqEnabled,           // 0/1
    EqBand1GainDb,
    EqBand1FreqHz,
    EqBand1Q,

    // Clipper
    ClipperEnabled,      // 0/1
    ClipperMode,         // 0 = Hard, 1 = Soft
    ClipperDriveDb,      // pre-gain into clipping stage
    ClipperCeilingDb,    // <= 0 dBFS
    ClipperMix,          // 0..1
    ClipperSmoothingMs,  // optional

    ParamCount           // always last
};

constexpr uint16_t toIndex(ParamID id) noexcept {
    return static_cast<uint16_t>(id);
}

constexpr uint16_t paramCount() noexcept {
    return static_cast<uint16_t>(ParamID::ParamCount);
}

} // namespace audiomix::control
