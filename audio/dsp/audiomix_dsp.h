// audiomix
// AudioMIX
// audio/dsp/audiomix_dsp.h

/*
  Umbrella header for AudioMIX DSP
  core and module includes.

  Includes only headers that main.cpp directly interacts with (module interfaces and their parameter/parse types).

  Uses this single header in main.cpp instead of individ files.
  Internal utility headers (such as biquad, lfo, delay_line, smoothed_parameter, rbj_coeffs, etc.) are pulled in transitively by the modules that use them. 
  They are not included here.

  As chain grows, new DSP modules added here.
*/

#pragma once

// Core
// chain infrastructure
#include "audio/dsp/core/dsp_chain.h"
#include "audio/dsp/core/dsp_module.h"

// parameter structs + parsers
// one pair per controllable module
#include "audio/dsp/core/eq_params.h"
#include "audio/dsp/core/eq_params_parse.h"
#include "audio/dsp/core/compressor_params.h"
#include "audio/dsp/core/compressor_params_parse.h"

// control plane
#include "audio/dsp/core/control/param_ids.h"
#include "audio/dsp/core/control/param_registry.h"

// Modules
#include "audio/dsp/modules/ascension_reverb.h"
#include "audio/dsp/modules/clipper_module.h"
#include "audio/dsp/modules/compressor_module.h"
#include "audio/dsp/modules/digital_choir.h"
#include "audio/dsp/modules/eq_module.h"
#include "audio/dsp/modules/gain_module.h"
#include "audio/dsp/modules/null_sink.h"
#include "audio/dsp/modules/shimmer.h"
#include "audio/dsp/modules/subbass_isolation.h"