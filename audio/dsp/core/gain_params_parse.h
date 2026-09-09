// AudioMIX
// audio/dsp/core/gain_params_parse.h

/*
  NDJSON parser for gain.set control messages.
  Companion to gain_module.h, same flat-JSON convention as
  compressor_params_parse.h (no nested "payload" wrapper).
  Matches DSPBridge._handle_gain_set's actual send shape:
    {"cmd": "gain.set", "gain_db": -3.0}

  Unlike compressor.set, gain.set has exactly one parameter, so this
  is a required field rather than a partial update merge.
  A message missing gain_db is rejected outright instead of silently keeping the
  prev value, since there's nothing else the command could be trying to do.

  Returns true if parsing succeeded, the cmd field matches, and gain_db was
  present.
  Returns false otherwise; outGainDb is left unmodified on failure so the caller
  can safely retain its prev state.
*/

#pragma once

#include <nlohmann/json.hpp>
#include <string>
#include <algorithm>

namespace audiomix::dsp {

    inline bool parseGainSetLine(const std::string& line, float& outGainDb) {
        try {
            auto j = nlohmann::json::parse(line);

            if (j.value("cmd", "") != "gain.set") return false;
            if (!j.contains("gain_db")) return false;

            float value = j.value("gain_db", 0.0f);
            // clamp to a sane range - avoids a stray huge value from a
            // malformed or malicious payload driving the signal to a
            // damaging level.
            outGainDb = std::max(-60.0f, std::min(value, 24.0f));
            return true;
        } catch (...) {
            return false;
        }
    }
} // namespace audiomix::dsp