# AudioMIX
# performance_engine/modules/gain.py
#
# AS commands for the DSP gain stage.
# Validates input, then emits dsp.gain.set on the EventBus.
# DSPBridge (dsp_bridge.py) forwards that to the C++ controlLoop's
# gain.set handler (main.cpp), which calls GainModule::setGainDb().
#
# Unlike compressor.set (4 params, partial-update aware), gain has
# exactly one parameter.
# There is not "ommitted argument retains current value" case to support,
# since omitting the only argument leaves nothing to set.

from performance_engine.event_bus import bus
from performance_engine.utils.shell_output import say

# Tracked locally so gain.status() can report the last value sent,
# since the C++ side doesn't export a "read current gain" round-trip.
# This is a Python-side echo of intent, not a live query into the
# DSP engine.
_current_gain_db = 0.0

def gain_set(gain_db: str):
    """
    Set the master gain stage in dB.
     - gain_db: gain in decibels (ex: -6 or 3.5)
    Clamped to [-60, 24] dB on the cpp side as a safety net.
    Validated here first too, so a bad value gets a clear AS-shell error
    instead of a silent cpp-side clamp w/ no feedback to the user.
    Example: gain.set(-6)
    """
    global _current_gain_db
    try:
        value = float(gain_db)
    except (TypeError, ValueError):
        say(f"[gain] Invalid gain_db: {gain_db!r} (must be a number)", "⚠️")
        return

    if not (-60.0 <= value <= 24.0):
        say(f"[gain] {value} dB is out of range [-60, 24]", "⚠️")
        return

    _current_gain_db = value
    bus.emit("dsp.gain.set", {"gain_db": value})
    say(f"[gain] Set to {value} dB", "🎚️")

def gain_status():
    """
    Report the last gain value sent via gain.set().
    Reflects intent (what was last sent), not a live read back from
    the DSP engine.
    No round-trip query for that.
    """
    say(f"[gain] Current: {_current_gain_db} dB", "🎚️")

def gain_reset():
    """
    Reset gain to 0 dB (unity)
    """
    gain_set("0")

def register():
    return {
        "gain.set": gain_set,
        "gain.status": gain_status,
        "gain.reset": gain_reset,
    }
