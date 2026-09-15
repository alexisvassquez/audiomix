// AudioMIX
// audio/dsp/core/clipper_params_parse.h

/*
  NDJSON parser for clipper.set control messages.
  Unlike eq_params_parse.h or compressor_params_parse.h, this does
  NOT fill a freshly-constructed params struct with per-field fallbacks.
  The ClipperModule itself contains real getters (getDriveDb(), getCeilingDb(),
  getMix(), getMode()).
  Each field listed is std::optional, only present if the incoming JSON actually
  included it.
  The caller (main.cpp's controlLoop) only calls the corresponding setter when a
  field is present, leaving every other param untouched on the live module.
  Not silently reset to a default variable.
*/

#pragma once

#include <nlohmann/json.hpp>
#include <string>
#include <optional>
#include <algorithm>

#include "audio/dsp/modules/clipper_module.h"

namespace audiomix::dsp {

    struct ClipperParsedFields {
        std::optional<float> driveDb;
        std::optional<float> ceilingDb;
        std::optional<float> mix;
        // hard or soft clipper mode
        std::optional<ClipperModule::Mode> mode;
    };

    inline bool parseClipperSetLine(const std::string& line, ClipperParsedFields& out) {
        try {
            auto j = nlohmann::json::parse(line);
            if (j.value("cmd", "") != "clipper.set") return false;

            if (j.contains("drive_db")) {
                float v = j.at("drive_db").get<float>();
                out.driveDb = std::max(-24.0f, std::min(v, 24.0f));
            }
            if (j.contains("ceiling_db")) {
                float v = j.at("ceiling_db").get<float>();
                out.ceilingDb = std::max(-60.0f, std::min(v, 0.0f));
            }
            if (j.contains("mix")) {
                float v = j.at("mix").get<float>();
                out.mix = std::max(0.0f, std::min(v, 1.0f));
            }
            if (j.contains("mode")) {
                std::string m = j.at("mode").get<std::string>();
                if (m == "hard") out.mode = ClipperModule::Mode::Hard;
                else if (m == "soft") out.mode = ClipperModule::Mode::Soft;
            }

            return true;
        } catch (...) {
            return false;
        }
    }
} // namespace audiomix::dsp