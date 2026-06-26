// audiomix
// AudioMIX
// audio/dsp/core/control/param_registry.h
//
// Supports future modules registering additional params dynamically
// Useful for hot-loading modules and user racks

#pragma once
#include <cstdint>
#include <string>
#include <unordered_map>
#include <stdexcept>

#include "param_ids.h"

namespace audiomix::control {

// Dynamic param keys live in separate range from ParamID
// avoids breaking RT code, keeps core params stable
using ParamKey = uint32_t;

constexpr ParamKey kDynamicBase = 1u << 16;    // 65536+

class ParamRegistry {
public:
    // Registers a dynamic parameter name -> ParamKey
    // Non-RT only
    ParamKey registerDynamic(const std::string& fullName) {
        auto it = nameToKey_.find(fullName);
        if (it != nameToKey_.end()) return it->second;

        ParamKey key = kDynamicBase + nextDynamic_++;
        nameToKey_.emplace(fullName, key);
        return key;
    }

    // Core params can be referenced by ParamID w/o registration
    static constexpr ParamKey toKey(ParamID id) noexcept {
        return static_cast<ParamKey>(id);
    }

private:
    std::unordered_map<std::string, ParamKey> nameToKey_;
    uint32_t nextDynamic_ = 0;
};

} // namespace audiomix::control
