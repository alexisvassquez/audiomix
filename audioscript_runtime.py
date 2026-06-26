# audiomix
# AudioMIX
# audioscript_runtime.py

"""
This is the main runtime for AudioMIX's AudioScript.
It provides the shell interface, command registry, and
built-in commands.
It also loads command modules from the 
`performance_engine/modules` directory.
The runtime supports a "safe mode" which only loads a 
limited set of modules for environments with strict security requirements.

Usage: python3 audioscript_runtime.py [--safe] [--no-emoji] [--no-symbols] [--debug] [script.audioscript]

1. Run this script to start the AudioScript shell.
2. Use load("module.py") to load command modules.
3. Type AudioScript commands to control audio playback,
LED patterns, and more.

The runtime also supports running .audioscript files passed as command-line arguments.
"""

from __future__ import annotations
import sys, os, importlib, shlex, atexit
import time as _time
import readline
from performance_engine.modules.context import command_registry

# Allowlist -> SAFE_MODE (for lighter runtime load)
SAFE_MODE = os.environ.get("AUDIOMIX_SAFE", "0") == "1"
SAFE_MODE_ALLOWLIST = {
    "context.py",
    "shell_tools.py",
    "clip_launcher.py",
    "provider_commands.py",
    "eq_commands.py",
    "led_controller.py",
    "shared.py",
}

# Enable persistent shell history
histfile = os.path.expanduser("~/.audioscript_history")
try:
    readline.read_history_file(histfile)
except FileNotFoundError:
    pass
atexit.register(readline.write_history_file, histfile)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

USE_EMOJIS = True
USE_SYMBOLS = True
# Set to True for debugging logs with --debug flag
VERBOSE = True

# Register commands to registry function
def register_command(name: str, func):
    command_registry[name] = func

def say(text, emoji=""):
    """
    Print text with optional emoji, respecting global settings for emojis and symbols.
     - text: the message to print
     - emoji: optional emoji to prefix the message
    """
    from audioscript_runtime import USE_EMOJIS, USE_SYMBOLS

    # Replace visual symbols with Unicode-safe versions
    if USE_EMOJIS and emoji:
        text = text.replace("->", "\u2192")
        text = text.replace("=>", "\u21D2")
        text = text.replace("<-", "\u2190")

    if USE_EMOJIS and emoji:
        print (f"{emoji} {text}")
    else:
        print (text)

# Module loader
def load_modules():
    """
    Load command modules from the performance_engine/modules directory.
    In SAFE_MODE, only load modules in the SAFE_MODE_ALLOWLIST.
    Each module should have a register() function that returns a dict of command_name: function pairs.
    """
    module_dir = "performance_engine/modules"
    for file in os.listdir(module_dir):
        if not file.endswith(".py") or file.startswith("__"):
             continue
        _t = _time.time()

        if SAFE_MODE and file not in SAFE_MODE_ALLOWLIST:
            if VERBOSE: say(f"Safe mode: skipping {file}")
            continue

        # dot-path..for safety
        mod_path = f"performance_engine.modules.{file[:-3]}".replace("-", "_")
        try:
            module = importlib.import_module(mod_path)
            if hasattr(module, "register"):
                registered = module.register()
                if registered:
                    if VERBOSE:
                        say(f"Registering from {file}: {list(registered.keys())}", "🧠")
                    command_registry.update(registered)
                    command_registry["trigger_zones"] = trigger_zones
                elif VERBOSE:
                    say(f"⚠️ {file} register() returned nothing", "❓")
            elif VERBOSE:
                say(f"⚠️ No register() in {file}", "🚫")
        except Exception as e:
            if VERBOSE:
                say(f"❌ Failed to import {file}: {e}", "💥")
        if VERBOSE:
            say(f"  loaded in {_time.time()-_t:.2f}s")

# Built-in AS functions
# Lazy imports
def glow(color):
    """ 
    Trigger LED glow with specified color. Color can be a name or hex code. 
    Example: glow("red") or glow("#FF0000") 
    """
    say(f"[LED] glowing {color}", "💡")

# Global playback state
# PLAYBACK_MODE = ("lossless" or "lossy", codec_key)
PLAYBACK_MODE = ("lossless", "wav")    # default

# mode: 'lossless' or 'lossy'
# codec: one of codec_sim.CODEC_MAP keys (ignored for lossless)
def set_mode(mode: str, codec: str = "mp3_320"):
    """
    Set playback mode to 'lossless' or 'lossy' with specified codec for lossy.
     - mode: 'lossless' or 'lossy'
     - codec: codec key for lossy mode (e.g. 'mp3_128', 'aac_256')
    """
    global PLAYBACK_MODE
    m = (mode or "").strip().lower()
    if m not in ("lossless", "lossy"):
        raise ValueError("set_mode: mode must be 'lossless' or 'lossy'")
    if m == "lossy":
        # Validate the codec upfront
        from audio.utils.codec_sim import parse_codec    # lazy
        parse_codec(codec)
        PLAYBACK_MODE = (m, codec)
        say(f"Playback mode set to LOSSY ({codec})", "🎚️")
    else:
        PLAYBACK_MODE = ("lossless", "wav")
        say("Playback mode set to LOSSLESS", "🎚️")

def get_mode():
    """
    Get current playback mode and codec if applicable.
    Returns a string describing the current mode"""
    mode, codec = PLAYBACK_MODE
    if mode == "lossy":
        say(f"Current mode: LOSSY ({codec})", "🎚️")
    else:
        say("Current mode: LOSSLESS", "🎚️")

# AS commands ex: set_mode("lossy", codec="mp3_128")
register_command("set_mode", set_mode)
register_command("get_mode", get_mode)

# Load 'path', ensure internal WAV format. If mode is 'lossy', round-trip through codec.
# Hand off to existing low-latency playback (PortAudio)
def play(path: str, **kwargs):
    """
    Play the specified audio file with current playback mode settings via the AudioPlayer module.
    Delegates to performance_engine.modules.audio_player
    """
    if SAFE_MODE:
        say(f"[SAFE] Would play: {path} (no audio in safe mode)")
        return
    from performance_engine.modules.audio_player import play as _play
    _play(path)

    #lazy
    from audio.ai.modules.convert_audio import ensure_internal
    from audio.utils.codec_sim import roundtrip_lossy

    mode, codec = PLAYBACK_MODE
    # normalize input to internal WAV32F
    internal_wav = ensure_internal(path, target_sr=48000)

    # if lossy, encode/decode to WAV32F
    try:
        if mode == "lossy":
            sim_wav = roundtrip_lossy(internal_wav, codec_key=codec, target_sr=48000)
            _do_play(sim_wav, **kwargs)
            try: os.remove(sim_wav)
            except OSError: pass
        else:
            _do_play(internal_wav, **kwargs)
    # clean up normalized wav if temp
    finally:
        try: os.remove(internal_wav)
        except OSError: pass

def _do_play(wav_path: str, **kwargs):
    """
    Internal function to play a WAV file using PortAudio.
     - wav_path: path to the WAV file to play
     - kwargs: additional parameters for playback (e.g. volume, loop)
     """
    say(f"Now playing: {os.path.basename(wav_path)}", "🔊")

def pulse(color, bpm):
    """ 
    Trigger LED pulse with specified color and BPM.
     - color: name or hex code of the color (e.g. "blue" or "#0000FF")
     - bpm: beats per minute for the pulse rate (e.g. 120) 
     Example: pulse("blue", 120) 
    """
    say(f"[LED] pulsing {color} @ {bpm} BPM", "💡")

def mood_set(mood):
    """ Set the current mood for lighting and effects. 
    Mood can be any string (e.g. 'calm', 'energetic', 'dark'). 
     Example: mood_set("calm") 
    """
    say(f"[MOOD] context set to: {mood}", "🎼")

def trigger_zones(zones, mood="calm", bpm=120):
    """ 
    Trigger lighting profiles for specified zones with given mood and BPM.
     - zones: list of zone names to trigger (e.g. ["zone1", zone2"])
     - mood: current mood for lighting effects (default: "calm")
     - bpm: current BPM for pulse synchronization (default: 120)
     Example: trigger_zones(["zone1", "zone2"], mood="energetic", bpm=140)
     Note: In SAFE_MODE, this will only print the intended action without triggering actual lighting changes.
    """
    if SAFE_MODE:
        say(f"[SAFE] Would trigger zones={zones} mood={mood} bpm={bpm}")
        return
    try:
        # lazy
        from audio.ai.analysis.inference_engine import generate_lighting_profile
        generate_lighting_profile({mood}, bpm=bpm, zone=zones)
        say(f"[LIGHTING] Triggered zones: {zones} | Mood: {mood} | BPM: {bpm}", "🌈")
    except Exception as e:
        say(f"[ERROR] Lighting trigger failed: {e}", "❌")

# Command execution
def parse_and_execute(line):
    """ 
    Parse a line of input and execute the corresponding command.
     - line: the input string to parse and execute
     The expected format is: command(arg1, arg2, ...)
     Arguments are parsed using shlex.split to handle quoted strings.
     If the command is registered in the command_registry, it will be executed with the parsed arguments.
     The result of the command execution will be printed. If the command is not found or if there is a syntax error, an error message will be printed instead.
    """
    line = (line or "").strip()
    if line.startswith("#") or not line:
        # ignore comments and blank lines
        return

    if "(" in line and line.endswith(")"):
        command, arg_str = line.split("(", 1)
        arg_str = arg_str[:-1] # Remove trailing ")"

        if not arg_str:
            # no arguments
            parts = []
        elif '"' in arg_str or "'" in arg_str:
            # quoted strings
            # use shlex to handle them correctly
            parts = [p.strip(",") for p in shlex.split(arg_str)]
        else:
            # numeric or simple args - split on commas
            parts = [p.strip() for p in arg_str.split(",") if p.strip()]

        func = command_registry.get(command)
        if func:
            try:
                result = func(*parts)
                if isinstance(result, list):
                    for item in result:
                        say(item)
                elif isinstance(result, str):
                    say(result)
                elif result is not None:
                    say(str(result))
            except Exception as e:
                say(f"[ERROR] Execution failed: {e}", "❌")
        else:
            say(f"[ERROR] Unknown command: {command}", "⚠️")
    else:
        say(f"[ERROR] Invalid syntax: {line}", "❕")

# AS Shell loop
def main():
    global USE_EMOJIS, USE_SYMBOLS, VERBOSE, SAFE_MODE

    # CLI flags
    if "--no-emoji" in sys.argv:
        USE_EMOJIS = False
    if "--no-symbols" in sys.argv:
        USE_SYMBOLS = False
    if "--debug" in sys.argv:
        VERBOSE = True
    if "--safe" in sys.argv:
        SAFE_MODE = True

    LAUNCH_DSP = "--no-dsp" not in sys.argv
    HEADLESS_DSP = "--no-headless" not in sys.argv

    # Boot the event bus and attach
    # DSP bridge
    from performance_engine.event_bus import bus
    from performance_engine.dsp_bridge import attach_dsp_bridge

    bridge = attach_dsp_bridge(bus, launch=LAUNCH_DSP, headless=HEADLESS_DSP, verbose=VERBOSE)
    say("DSP bridge attached", "🌉")

    # Load command modules after global settings are set
    load_modules()

    say("Welcome to AudioMIX - AudioScript Shell v0.1", "🎚️")
    say("Type AudioScript commands below. Ctrl+C to exit.\\n")

    # Run script file if passed
    for arg in sys.argv[1:]:
        if arg.endswith(".audioscript") or arg.endswith(".as"):
            say(f"Running AudioScript file: {arg}", "▶️")
            with open(arg, "r") as f:
                for line in f:
                    parse_and_execute(line.strip())
            return

    midi_tick = None if SAFE_MODE else command_registry.get("midi_tick")

    # Interactive loop
    while True:
        try:
            if midi_tick:
                midi_tick()    # keep processing realtime MIDI events
            line = input("🎛️ > ")
            parse_and_execute(line)
        except KeyboardInterrupt:
            say("Exiting AudioMIX Shell. Goodbye 👋", "🛑")
            try:
                readline.write_history_file(histfile)
            except OSError:
                pass
            bridge.shutdown()
            break
        except Exception as e:
            say(f"[AS Shell Error] {e}", "❌")
            _time.sleep(0.01)

if __name__ == "__main__":
    main()
