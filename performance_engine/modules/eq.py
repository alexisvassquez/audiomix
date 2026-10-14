# AudioMIX
# performance_engine/modules/eq.py
#
# AudioMIX 10-band EQ, Python command module (forwarder)
# Python-side command module for the AudioMIX graphic EQ.
# Forwards AudioScript (AS) shell commands to the C++ EqModule via
# the EventBus -> DSPBridge -> controlLoop (eq.set) pipeline.
# All DSP lives in C++ (audio/dsp/modules/eq_module.h)
# This module only owns the band layout + live gain state and emits
# full-state eq.set packets.
#
# Registered commands:
#    eq.set - set one band's gain (dB); emits the full 10-band state
#    eq.preset - recall a named preset's band gains
#    eq.preamp - set the EQ input preamp (dB)
#    eq.reset - flatten all bands to 0 dB
#    eq.status - print current band gains
#    eq.list - list available presets
#
# The cpp parser (eq_params_parse.h) rebuilds EqParams from scratch each
# message and sets band_count to the number of bands present.

from performance_engine.event_bus import bus
from audio.eq.eq_loader import load_eq_preset

# Canonical 10-band layout.
# Fixed center freqs, only gain_db changes at runtime.
# Band index here matches the order sent to the cpp module
# Cpp side is index-addressed and never sees these names.
BANDS = [
    ("sub_bass", 60.0),
    ("bass", 120.0),
    ("low_mid", 250.0),
    ("mid", 500.0),
    ("high_mid", 1000.0),
    ("presence", 2000.0),
    ("brilliance", 4000.0),
    ("air", 8000.0),
    ("sparkle", 12000.0),
    ("ultra", 16000.0),
]
NAME_TO_INDEX = {name: i for i, (name, _f0) in enumerate(BANDS)}

SAMPLE_RATE = 44100
BAND_Q = 1.0
# UI/author range, Cpp clamps to +-24
GAIN_MIN, GAIN_MAX = -12.0, 12.0

# Live state
# per-band gain in dB, indexed like BANDS
_gains = [0.0] * len(BANDS)
_preamp_db = 0.0

# Presets (band-name -> gain) loaded from JSON.
# The "semantic" block is keyed by the same band used here
# "filters" block is ignored
PRESETS = load_eq_preset("presets_combined.json")

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _emit():
    """
    Emit the full 10-band state as an eq.set packet.
    """
    payload = {
        "sample_rate": SAMPLE_RATE,
        "preamp_db": _preamp_db,
        "bands": [
            {
                "type": "peaking",
                "f0": f0,
                "q": BAND_Q,
                "gain_db": _gains[i],
                "enabled": True,
            }
            for i, (_name, f0) in enumerate(BANDS)
        ],
    }
    # DSPBridge spreads this dict under {"cmd":"eq.set", ...} so
    # nesting it in "payload" yields the envelope eq_params_parse.h expects
    bus.emit("dsp.eq.set", {"payload": payload})

def eq_set(band=None, value=None):
    """
    Set one band's gain in dB, then emit the full state.
    Examples:
      eq.set("bass", 5) - by name
      eq.set(1, 5) - by index
    """
    if band is None or value is None:
        return "[eq.set] ❌ usage: eq.set(band, gain_db)"

    if isinstance(band, str) and band in NAME_TO_INDEX:
        idx = NAME_TO_INDEX[band]
    else:
        try:
            idx = int(band)
        except (ValueError, TypeError):
            return f"[eq.set] ❌ unknown band: {band}"
    if not (0 <= idx < len(BANDS)):
        return f"[eq.set] ❌ band out of range: {idx}"

    try:
        g = float(value)
    except (ValueError, TypeError):
        return f"[eq.set] ❌ gain must be a number, got {value}"

    _gains[idx] = _clamp(g, GAIN_MIN, GAIN_MAX)
    _emit()
    name, f0 = BANDS[idx]
    return f"[EQ] {name} ({int(f0)}Hz) = {_gains[idx]:+.1f} dB"

def eq_preset(name=None):
    """
    Recall a preset's band gains.
    Zeros the rest then emit.
    """
    key = (name or "").strip()
    preset = PRESETS.GET(key)
    if not preset:
        return f"[eq.preset] ❌ not found: {key}"
    sem = preset.get("semantic")
    if not sem:
        return f"[eq.preset] ❌ '{key}' has no band map (filters-only preset)"

    for i in range(len(_gains)):
        _gains[i] = 0.0
    for bname, g in sem.items():
        i = NAME_TO_INDEX.get(bname)
        if i is not None:
            _gains[i] = _clamp(float(g), GAIN_MIN, GAIN_MAX)
    _emit()
    return f"[EQ] loaded preset: {key}"

def eq_preamp(value=None):
    """
    Set the EQ input preamp in dB.
    """
    global _preamp_db
    if value is None:
        return "[eq.preamp] ❌ usage: eq.preamp(gain_db)"
    try:
        _preamp_db = _clamp(float(value), -24.0, 24.0)
    except (ValueError, TypeError):
        return f"[eq.preamp] ❌ gain must be a number, got {value}"
    _emit()
    return f"[EQ] preamp = {_preamp_db:+.1f} dB"

def eq_reset(payload=None):
    """
    Flatten all bands + preamp to 0 dB.
    """
    global _preamp_db
    for i in range(len(_gains)):
        _gains[i] = 0.0
    _preamp_db = 0.0
    _emit()
    return "[EQ] reset - all bands 0 dB"

def eq_status(payload=None):
    lines = ["[EQ STATUS]", f" preamp : {_preamp_db:+.1f} dB"]
    for i, (name, f0) in enumerate(BANDS):
        lines.append(f" {name:<11}{int(f0):>6}Hz : {_gains[i]:+.1f} dB")
    return "\n".join(lines)

def eq_list(payload=None):
    if not PRESETS:
        return "[EQ] no presets loaded"
    return "[EQ PRESETS]\n" + "\n".join(f" - {n}" for n in PRESETS.keys())

def register():
    return {
        "eq.set": eq_set,
        "eq.preset": eq_preset,
        "eq.preamp": eq_preamp,
        "eq.reset": eq_reset,
        "eq.status": eq_status,
        "eq.list": eq_list,
    }

