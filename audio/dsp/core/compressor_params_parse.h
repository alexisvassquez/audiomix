// audiomix
// AudioMIX
// audio/dsp/core/compressor_params_parse.h

/*
  NDJSON parser for compressor.set control messages.
  
  Companion to compressor_params.h,
  same pattern as eq_params_parse.h
  
  Expected format from DSPBridge:
    {
      "cmd": "compressor.set",
      "threshold": -18.0,
      "ratio": 4.0,
      "attack_ms": 10.0,
      "release_ms": 80.0
    }
  
  Returns true if parsing succeeded and
  the cmd field matches.
  Returns false if the JSON is malformed, missing, or wrong command
  On failure, `out` is left unmodified so the caller can safely retain its prev state
*/

#pragma once

#include "compressor_params.h"
#include <nlohmann/json.hpp>
#include <string>

namespace audiomix::dsp {
    inline bool parseCompressorSetLine(const std::string& line, CompressorParams& out) {
        try {
            auto j = nlohmann::json::parse(line);

            if (j.value("cmd", "") != "compressor.set") return false;

            /* 
              each field falls back to current value in `out` if absent, so partial updates from Python-side are handled gracefully
            */
           out.threshold_db = j.value("threshold", out.threshold_db);
           out.ratio = j.value("ratio", out.ratio);
           out.attack_ms = j.value("attack_ms", out.attack_ms);
           out.release_ms = j.value("release_ms", out.release_ms);

           return true;
        } catch (...) {
            return false;
        }
    }

} // namespace audiomix::dsp