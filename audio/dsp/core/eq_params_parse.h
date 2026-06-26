// audiomix
// AudioMIX
// audio/dsp/core/eq_params_parse.h
//
// JSON parsing for EQ parameters
// Using nlohmann/json (header-only)
// Validate and clamp cmd == "eq.set"
// Converts payload into EqParams
// Enforces 10 bands

#pragma once
#include <string>
#include <algorithm>
#include <cctype>

#include "../core/eq_params.h"
#include <nlohmann/json.hpp>

namespace audiomix::dsp {

static inline float clampf(float v, float lo, float hi) {
    return std::max(lo, std::min(v, hi));
}

static inline EqBandType parseBandType(const std::string& s) {
    if (s == "lowshelf") return EqBandType::LowShelf;
    if (s == "highshelf") return EqBandType::HighShelf;
    return EqBandType::Peaking;
}

// Returns true on success; fills out parameters
// Returns false on failure (caller logs once)
static inline bool parseEqSetLine(const std::string& line, EqParams& outParams) {
    using nlohmann::json;

    json j;
    try {
        j = json::parse(line);
    } catch (...) {
        return false;
    }

    if (!j.contains("cmd") || j["cmd"] != "eq.set") return false;
    if (!j.contains("payload") || !j["payload"].is_object()) return false;

    const auto& p = j["payload"];

    EqParams params;
    params.sample_rate = p.value("sample_rate", 44100);    // 44.1 kHz
    params.preamp_db   = clampf(p.value("preamp_db", 0.0f), -24.0f, 24.0f);    // gain -24..+24

    if (p.contains("bands") && p["bands"].is_array()) {
        int count = 0;
        for (const auto& b : p["bands"]) {
            if (!b.is_object()) continue;
            if (count >= EqParams::kMaxBands) break;

            EqBand band;
            band.enabled = b.value("enabled", true);

            std::string typeStr = b.value("type", "peaking");
            band.type = parseBandType(typeStr);

            band.f0 = clampf(b.value("f0", 1000.0f), 20.0f, 20000.0f);
            band.q  = clampf(b.value("q", 1.0f), 0.1f, 18.0f);
            band.gain_db = clampf(b.value("gain_db", 0.0f), -24.0f, 24.0f);

            params.bands[count++] = band;
        }
        params.band_count = count;
    }

    outParams = params;
    return true;
}

} // namespace audiomix::dsp
