# AudioMIX
# performance_engine/modules/compressor.py
#
# AudioMIX Compressor Module
"""
Python-side command module for the AudioMIX dynamic range compressor.

Registers AudioScript (AS) shell commands for controlling the C++ CompressorModule
via the EventBus and DSPBridge pipeline.

Registered commands:
    compressor.set - set all compressor parameters at once
    compressor.status - print current compressor param values
    compressor.reset - reset compressor to default params

Event emitted:
    "dsp.compressor.set" - consumed by DSPBridge -> C++ controlLoop

Parameter ranges:
    threshold: dBFS, typically -60.0 - 0.0 (default -18.0)
    ratio: compression ratio, 1.0 - 20.0 (default 4.0)
    attack_ms: attack time in ms, 0.1 - 300.0 (default 10.0)
    release_ms: release time in ms, 10.0 - 2000 (default 80.0)
    knee_db: soft-knee width in dB, 0.0 - 24.0 (default 6.0)
    makeup_db: makeup gain in dB, -24.0 - 24.0 (default 0.0)
    mix: wet/dry blend, 0.0 - 1.0 (default 1.0)

Usage in AudioScript shell:
    compressor.set(threshold=-18.0, ratio=4.0)
    compressor.set(-18.0, 4.0, 10.0, 80.0, 6.0, 0.0, 1.0)
    compressor.status()
    compressor.reset()
"""

from performance_engine.event_bus import bus

# Default parameters
DEFAULTS = {
    "threshold": -18.0,
    "ratio": 4.0,
    "attack_ms": 10.0,
    "release_ms": 80.0,
    "knee_db": 6.0,
    "makeup_db": 0.0,
    "mix": 1.0,
}

# Live state
# updated every time compressor.set is called
_current = dict(DEFAULTS)

# Validation
def _validate(
        threshold, 
        ratio, 
        attack_ms, 
        release_ms, 
        knee_db, 
        makeup_db,
        mix,
    ):
    """
    Validate compressor params before sending to the DSP engine.
    Raises ValueError with a descriptive message if any value is out of range.
    Ranges mirror compressor_limits in compressor_params.h
    """
    if not -60.0 <= threshold <= 0.0:
        raise ValueError(f"threshold must be between -60.0 and 0.0 dBfs, got {threshold}")
    if not 1.0 <= ratio <= 20.0:
        raise ValueError(f"ratio must be between 1.0 and 20.0, got {ratio}")
    if not 0.01 <= attack_ms <= 500.0:
        raise ValueError(f"attack_ms must be between 0.1 and 500.0, got {attack_ms}")
    if not 10.0 <= release_ms <= 5000.0:
        raise ValueError(f"release_ms must be between 10.0 and 5000.0, got {release_ms}")
    if not 0.0 <= knee_db <= 24.0:
        raise ValueError(f"knee_db must be between 0.0 and 24.0, got {knee_db}")
    if not -24.0 <= makeup_db <= 24.0:
        raise ValueError(f"makeup_db must be between -24.0 and 24.0, got {makeup_db}")
    if not 0.0 <= mix <= 1.0:
        raise ValueError(f"mix must be between 0.0 and 1.0, got {mix}")

# Commands
def compressor_set(
        threshold=None, 
        ratio=None, 
        attack_ms=None, 
        release_ms=None,
        knee_db=None,
        makeup_db=None,
        mix=None,
    ):
    """
    Set compressor params and emit to the DSO engine via the EventBus.
    
    All arguments are optional.
    Omitted values retain their current setting.
    Arguments arriving from the AudioScript shell may be strings or
    numbers, so this function coerces to float before use either way.
    
    Example:
        compressor.set(threshold=-18.0, ratio=4.0)
        compressor.set(-24.0)    # threshold only, rest unchanged
    """
    global _current

    # Coerce from shell strings to float
    # fallback to current value if omitted
    try:
        t = float(threshold) if threshold is not None else _current["threshold"]
        r = float(ratio) if ratio is not None else _current["ratio"]
        a = float(attack_ms) if attack_ms is not None else _current["attack_ms"]
        rl = float(release_ms) if release_ms is not None else _current["release_ms"]
        k = float(knee_db) if knee_db is not None else _current["knee_db"]
        m = float(makeup_db) if makeup_db is not None else _current["makeup_db"]
        mx = float(mix) if mix is not None else _current["mix"]
    except ValueError:
        return "[compressor.set] ❌ All parameters must be numbers"
    
    try:
        _validate(t, r, a, rl, k, m, mx)
    except ValueError as e:
        return f"[compressor.set] ❌ {e}"
    
    # Update live state
    _current = {
        "threshold": t,
        "ratio": r,
        "attack_ms": a,
        "release_ms": rl,
        "knee_db": k,
        "makeup_db": m,
        "mix": mx,
    }

    # Fire event -> DSPBridge -> C++ CompressorModule
    bus.emit("dsp.compressor.set", dict(_current))

    return (
        f"[COMPRESSOR] threshold={t} dBFS | ratio={r}:1 | "
        f"attack={a}ms | release={rl}ms | knee={k}dB | "
        f"makeup={m}dB | mix={mx}"
    )

def compressor_status(payload=None):
    """
    Print the current compressor parameter values w/o
    chaning anything.
    
    Example:
        compressor.status()
    """
    c = _current
    return (
        f"[COMPRESSOR STATUS]\n"
        f" threshold : {c['threshold']} dBFS\n"
        f" ratio     : {c['ratio']}:1\n"
        f" attack    : {c['attack_ms']} ms\n"
        f" release   : {c['release_ms']} ms\n"
        f" knee      : {c['knee_db']} dB\n"
        f" makeup    : {c['makeup_db']} dB\n"
        f" mix       : {c['mix']}"
    )

def compressor_reset(payload=None):
    """
    Reset compressor to default parameters and emit to
    the DSP engine.
    
    Example:
        compressor.reset()
    """
    global _current
    _current = dict(DEFAULTS)
    bus.emit("dsp.compressor.set", dict(_current))
    return "[COMPRESSOR] Reset to defaults."

# Registration
def register():
    """
    Register compressor commands with the AudioScript (AS)
    runtime shell.
    Called automatically by the module loader in      
      audioscript_runtime.py
    """
    return {
        "compressor.set" : compressor_set,
        "compressor.status": compressor_status,
        "compressor.reset": compressor_reset,
    }