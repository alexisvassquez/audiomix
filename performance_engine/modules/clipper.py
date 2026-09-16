# AudioMIX
# performance_engine/modules/clipper.py
#
# AS commands for the DSP clipper/limiter stage.
# Validates input, then emits dsp.clipper.set on the EventBus -
# DSPBridge forwards it to C++'s controlLoop, which only applies the
# fields actually present in the message (see clipper_params_parse.h).
#
# Supports both calling styles:
#   clipper.set("", "", "", "hard") - positional, "" (unchanged)
#   clipper.set(drive_db=6, mode="hard") - keyword args (preferred)
# A parameter left as None (default) or as an empty string is
# skipped and left at its current DSP-side value.

from typing import Optional, Union
from performance_engine.event_bus import bus
from performance_engine.utils.shell_output import say

Numeric = Union[int, float, str]

def clipper_set(
        drive_db: Optional[Numeric] = None, 
        ceiling_db: Optional[Numeric] = None, 
        mix: Optional[Numeric] = None, 
        mode: Optional[str] = None
    ):
        """
        Set clipper (limiter) parameters.
        Any parameter left as None or "" is skipped and left unchanged.
          - drive_db: pre-gain into the clipper, in dB. Range [-24, 24]
          - ceiling_db: output ceiling in dB. Range [-60, 0]
          - mix: dry/wet blend, 0.0 (bypass) to 1.0 (full effect)
          - mode: "hard" or "soft" 
        Ex:
          clipper.set(drive_db=6, mode="hard")  - sets drive and mode only
          clipper.set("6", "", "", "hard") - same result as above (positional)
        """
        payload = {}

        if drive_db is not None and drive_db != "":
            try:
                v = float(drive_db)
            except (TypeError, ValueError):
                say(f"[clipper] Invalid drive_db: {drive_db!r}", "⚠️")
                return
            if not (-24.0 <= v <= 24.0):
                say(f"[clipper] drive_db {v} out of range [-24, 24]", "⚠️")
                return
            payload["drive_db"] = v

        if ceiling_db is not None and ceiling_db != "":
            try:
                v = float(ceiling_db)
            except (TypeError, ValueError):
                say(f"[clipper] Invalid ceiling_db: {ceiling_db!r}", "⚠️")
                return
            if not (-60.0 <= v <= 0.0):
                say(f"[clipper] ceiling_db {v} out of range [-60, 0]", "⚠️")
                return
            payload["ceiling_db"] = v

        if mix is not None and mix != "":
            try:
                v = float(mix)
            except (TypeError, ValueError):
                say(f"[clipper] Invalid mix: {mix!r}", "⚠️")
                return
            if not (0.0 <= v <= 1.0):
                say(f"[clipper] mix {v} out of range [0, 1]", "⚠️")
                return
            payload["mix"] = v

        if mode is not None and mode != "":
            m = mode.strip().lower()
            if m not in ("hard", "soft"):
                say(f"[clipper] Invalide mode: {mode!r} ('hard' or 'soft')", "⚠️")
                return
            payload["mode"] = m

        if not payload:
            say(f"[clipper] No parameters given - nothing to set", "⚠️")
            return

        bus.emit("dsp.clipper.set", payload)
        say(f"[clipper] Updated: {payload}", "🎚️")

def clipper_reset():
    """
    Reset clipper to defaults:
      drive=0dB,
      ceiling=-0.1dB,
      mix=1.0,
      soft mode
    """
    clipper_set(drive_db=0, ceiling_db=-0.1, mix=1.0, mode="soft")

def register():
    return {
        "clipper.set": clipper_set,
        "clipper.reset": clipper_reset
    }
         
