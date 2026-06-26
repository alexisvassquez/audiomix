// audiomix
// AudioMIX
// audio/dsp/core/compressor_params.h
//
/*
  Compressor parameters - control thread side description of compressor state.

  Designed for:
    - single-band use (by default)
    - multiband use via composition (Crossover -> N CompressorModules -> Sum)
    - stereo-linked / dual-mono detection
    - optional sidechain input w/ optional highpass detection filter
    - externally readable gain reduction (lives on the module, not the thread, so it can be read by the UI without locking the thread)
  
  Detector mode starts as Branching
  Decoupled can be added later w/o breaking consumers
  The detector is fully encapsulated inside the module and its output (envelope value) is what the rest of the compressor operates on.
*/

#pragma once
#include <cstdint>

namespace audiomix::dsp {
    /* 
      DetectorMode
        Branching: separate attack and release 
         paths, with attack having a faster
         response time than release
         Classic, predictable, well-suited to live performance
        Decoupled: two cascaded smoothers (peak  follower into release smoother)
        Smoother behavior on rapidly changing material - reserved for future implemtation
      TODO: Module will fall back to Branching until it is added.
    */
    enum class DetectorMode : uint8_t {
        Branching = 0,
        Decoupled = 1
    };

    /*
      DetectorType
        Peak: fast-responding, follows transients (default for live use)
        Rms: slower, more averaged response, smoother on sustained material.
      TODO: Reserved for future implementation, module will fall back to Peak until added.
    */
    enum class DetectorType : uint8_t {
        Peak = 0,
        Rms = 1
    };

    /*
      StereoLink
        Linked: single gain reduction value applied to both channels, computed from max (L, R)
          Preserves stereo image; default for bus/master compression.
        DualMono: independent gain reduction p/channel.
          Can shift stereo image but useful for parallel/creative work & multiband bands that operate p/channel
    */
    enum class StereoLink : uint8_t {
        Linked = 0,
        DualMono = 1
    };

    /*
      CompressorParams
        threshold_db: level above which compression begins (dB, e.g., -18)
        ratio: input:output ratio above threshold (e.g., 4.0 = 4.1)
          1.0 = no compression, infinity ~= limiting
        attack_ms: time to respond to level increases above threshold
        release_ms: time to recover after level falls below threshold
        knee_db: width of the soft-knee region around threshold
          0.0 = hard knee
          typical musical values: 6 - 12 dB
        makeup_db: gain applied after compression (manual makeup)
        mix: wet/dry blend 
          (0.0 = dry, 1.0 = fully compressed)
          enables parallel ("New York") compression in-module
          
        detector_mode: Branching (default) or Decoupled
        detector_type: Peak (default) or Rms
        stereo_link: Linked (default) or DualMono
        
        sidechain_external: if True, module uses an external sidechain buffer passed into processMulti() instead of main input for detection.
          TODO: plumbing is wired now, routing later
        sidechain_hp_enabled: apply a highpass to the detection signal
          (does not affect the audio path itself)
          useful to prevent pumping on bass content
        sidechain_hp_hz: cutoff for the detection-path highpass
          (typical 60 - 200 Hz)
        sidechain_hp_q: Q for the detection-path highpass
          (0.7071 = Butterworth RBJ coeff)
          
        sample_rate: informational
          uses prepare()'s sample rate (44.1 kHz)
          mirrors EqParams convention
    */
   struct CompressorParams {
    // core dynamics
    float threshold_db = -18.0f;
    float ratio = 4.0f;
    float attack_ms = 10.0f;
    float release_ms = 100.0f;
    float knee_db = 6.0f;
    float makeup_db = 0.0f;
    float mix = 1.0f;

    // detection
    DetectorMode detector_mode = DetectorMode::Branching;
    DetectorType detector_type = DetectorType::Peak;
    StereoLink stereo_link = StereoLink::Linked;

    // sidechain
    bool sidechain_external = false;
    bool sidechain_hp_enabled = false;
    float sidechain_hp_hz = 100.0f;
    float sidechain_hp_q = 0.7071f;

    // informational; sample rate is needed for time constant calculations in the detector
    int sample_rate = 44100;
   };

   /* 
     Soft-clamp ranges - referenced by the module's sanitize() pass.
     Kept as constants so the param boundaries are documented in one place alongside the param definitions. 
   */
  namespace compressor_limits {
    inline constexpr float kThresholdMinDb = -60.0f;
    inline constexpr float kThresholdMaxDb = 0.0f;

    inline constexpr float kRatioMin = 1.0f;
    // ~limiter
    inline constexpr float kRatioMax = 100.0f;

    inline constexpr float kAttackMinMs = 0.1f;
    inline constexpr float kAttackMaxMs = 500.0f;

    inline constexpr float kReleaseMinMs = 1.0f;
    inline constexpr float kReleaseMaxMs = 5000.0f;

    inline constexpr float kKneeMinDb = 0.0f;
    inline constexpr float kKneeMaxDb = 24.0f;

    inline constexpr float kMakeupMinDb = -24.0f;
    inline constexpr float kMakeupMaxDb = 24.0f;

    inline constexpr float kMixMin = 0.0f;
    inline constexpr float kMixMax = 1.0f;

    inline constexpr float kSidechainHpHzMin = 20.0f;
    inline constexpr float kSidechainHpHzMax = 1000.0f;

    inline constexpr float kSidechainHpQMin = 0.1f;
    inline constexpr float kSidechainHpQMax = 4.0f;
  };

} // namespace audiomix::dsp