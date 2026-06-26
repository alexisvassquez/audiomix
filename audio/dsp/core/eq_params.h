// audiomix
// AudioMIX
// audio/dsp/core/eq_params.h
//
// Minimal header file for EQ parameters
// 10-band standard

#pragma once
#include <array>
#include <cstdint>

namespace audiomix::dsp {

enum class EqBandType : uint8_t {
    Peaking = 0,
    LowShelf = 1,
    HighShelf = 2
};

struct EqBand {
    EqBandType type = EqBandType::Peaking;
    float f0 = 1000.0f;    // Hz
    float q = 1.0f;        // unitless
    float gain_db = 0.0f;  // dB
    bool enabled = true;
};

struct EqParams {
    int sample_rate = 44100;    // 44.1 kHz
    float preamp_db = 0.0f;

    static constexpr int kMaxBands = 10;
    int band_count = 0;
    std::array<EqBand, kMaxBands> bands{};
};

} // namespace audiomix::dsp
