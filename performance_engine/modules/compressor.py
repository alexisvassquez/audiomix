# AudioMIX
# performance_engine/modules/compressor.py

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
    release_ms: release time in ms, 10.0 - 2000 (default: 80.0)

Usage in AudioScript shell:
    compressor.set(-18.0, 4.0, 10.0, 80.0)
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
}

# Live state
# updated every time compressor.set is called
_current = dict(DEFAULTS)

# Validation
def _validate(threshold, ratio, attack_ms, release_ms):
    """
    Validate compressor params before sending to the DSP engine.
    Raises ValueError with a descriptive message if any value is out of range.
    """
    if not -60.0 <= threshold <= 0.0:
        raise ValueError(f"threshold must be between -60.0 and 0.0 dBfs, got {threshold}")
    if not 1.0 <= ratio <= 20.0:
        raise ValueError(f"ratio must be between 1.0 and 20.0, got {ratio}")
    if not 0.01 <= attack_ms <= 300.0:
        raise ValueError(f"attack_ms must be between 0.1 and 300.0, got {attack_ms}")
    if not 10.0 <= release_ms <= 2000.0:
        raise ValueError(f"release_ms must be between 10.0 and 2000.0, got {release_ms}")

# Commands
def compressor_set(threshold=None, ratio=None, attack_ms=None, release_ms=None):
    """
    Set compressor params and emit to the DSO engine via the EventBus.
    
    All arguments are optional.
    Omitted values retain their current setting.
    Arguments arriving from teh AudioScript shell are strings, so this function coerces them to float before use.
    
    Example:
        compressor.set(-18.0, 4.0, 10.0, 80.0)
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
    except ValueError:
        return "[compressor.set] ❌ All parameters must be numbers"
    
    try:
        _validate(t, r, a, rl)
    except ValueError as e:
        return f"[compressor.set] ❌ {e}"
    
    # Update live state
    _current = {
        "threshold": t,
        "ratio": r,
        "attack_ms": a,
        "release_ms": rl,
    }

    # Fire event -> DSPBridge -> C++ CompressorModule
    bus.emit("dsp.compressor.set", dict(_current))

    return (
        f"[COMPRESSOR] threshold={t} dBFS | ratio={r}:1 | "
        f"attack={a}ms | release={rl}ms"
    )

def compressor_status(payload=None):
    """
    Print the current compressor parameter values w/o
    chaning anything.
    
    Example:
        compressor.status()
    """
    t = _current["threshold"]
    r = _current["ratio"]
    a = _current["attack_ms"]
    rl = _current["release_ms"]
    return (
        f"[COMPRESSOR STATUS]\n"
        f" threshold : {t} dBFS\n"
        f" ratio     : {r}:1\n"
        f" attack    : {a} ms\n"
        f" release   : {rl} ms"
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