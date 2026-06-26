# audiomix
# AudioMIX
# runtime/core.py

# Refactored audioscript_runtime.py
# Haskell-inspired

from __future__ import annotations
import sys, os, importlib, shlex, atexit, time
import readline
from performance_engine.modules.context import command_registry
from runtime.runtime_state import set_var, get_var, has_var
from runtime.dsl_helpers import get_fx_registry, apply_fx_chain

SAFE_MODE = os.environ.get("AUDIOMIX_SAFE", "0") == "1"
SAFE_MODE_ALLOWLIST = {
    "context.py", "shell_tools.py", "clip_launcher.py",
    "provier_commands.py", "eq_commands.py",
    "led_controller.py", "shared.py"
}

histfile = os.path.expanduser("~/.audioscript_history")
try: readline.read_history_file(histfile)
    except FileNotFoundError: pass
atextit.register(readline.write_history_file, histfile)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
USE_EMOJIS = True
USE_SYMBOLS = True
VERBOSE = False
PLAYBACK_MODE = ("lossless", "wav")

def register_command(name: str, func):
    command_registry[name] = func

def say(text, emoji=""):
    if USE_EMOJIS and emoji:
        text = text.replace("->", "→").replace("=>", "⇒").replace("<-", "←")
        print (f"{emoji} {text}")
    else:
        print (text)

def load_modules():
    module_dir = "performance_engine/modules"
    for file in os.listdir(module_dir):
        if not file.endswith(".py") or file.startswith("__"): continue
        if SAFE_MODE and file not in SAFE_MODE_ALLOWLIST: continue
        mod_path = f"performance_engine.modules.{file[:-3]}".replace("-", "_")
        try:
            module = importlib.import_module(mod_path)
            if hasattr(module, "register"):
                registered = module.register()
                if registered:
                    command_registry.update(registered)
                    command_registry["trigger_zones"] = trigger_zones
        except Exception as e:
            if VERBOSE:
                say (f"[ERROR] Failed to load {file}: {e}")

# Core Built-in Commands
def glow(color): say(f"[LED] glowing {color}", "💡")
def pulse(color, bpm): say(f"[LED] pulsing {color} @ {bpm} BPM", "💡")
def mood_set(mood): say(f"[MOOD] context set to: {mood}", "🎼")

def set_mode(mode: str, codec: str = "mp3_320"):
    global PLAYBACK_MODE
    if mode == "lossy": PLAYBACK_MODE = (mode, codec)
    else: PLAYBACK_MODE = ("lossless", "wav")
    get_mode()

def get_mode():
    mode, codec = PLAYBACK_MODE
    say(f"Current mode: {mode.upper()} ({codec})")

register_command("set_mode", set_mode)
register_command("get_mode", get_mode)

def trigger_zones(zones, mood="calm", bpm=120):
    if SAFE_MODE:
        say(f"[SAFE] Would trigger zones={zones} mood={mood} bpm={bpm}")
        return
    try:
        from audio.ai.inference_engine import generate_lighting_profile
        generate_lighting_profile({mood}, bpm=bpm, zones=zones)
        say(f"[LIGHTING] Triggered zones: {zones} | Mood: {mood} | BPM: {bpm}", "🌈")
    except Exception as e:
        say(f"[ERROR] Lighting trigger failed: {e}", "❌")

# AS Command Parser
def parse_and_execute(line):
    line = line.strip()
    if not line or line.startswith("#"): return

    # Simple variable assignemt
    if line.startswith("let "):
        try:
            _, name, eq, expr = shlex.split(line, posix=True)
            if eq != "=": raise SyntaxError("Invalid let syntax")
            value = eval(expr, {}, get_fx_registry())
            set_var(name, value)
            say(f"[VAR] {name} set")
        except Exception as e:
            say(f"[let error] {e}", "❌")
        return

    # Func call with optional 'with' chaining
    if "(" in line and line.endswith(")"):
        try:
            if " with " in line:
                command_part, fx_part = line.split(" with ", 1)
                command, arg_str = command_part.split("(", 1)
                arg_str = arg_str.rstrip(")")
                args = shlex.split(arg_str)
                fx_names = [name.strip() for name in fx_part.split("+")]
                fx_chain = [get_fx_registry()[name] for name in fx_name if name in get_fx_registry()]
                result = command_registry[command](*args)
                if isinstance(result, list):
                    result = apply_fx_chain(result, fx_chain)
                    for item in result: say(item)
                return
            else:
                command, arg_str = line.split("(", 1)
                args = shlex.split(arg_str[:1])
                func = command_registry.get(command)
                if func: func(*args)
                else: say(f"[ERROR] Unknown command: {command}", "⚠️")
        except Exception as e:
            say(f"[ERROR] {e}", "❌")
        return

    # Fallback
    say(f"[Invalid syntax] {line}", "❕")

# Shell Entry
def main():
    global USE_EMOJIS, USE_SYMBOLS, VERBOSE, SAFE_MODE

    if "--no-emoji" in sys.argv: USE_EMOJIS = False
    if "--no-symbols" in sys.argv: USE_SYMBOLS = False
    if "--debug" in sys.argv: VERBOSE = True
    if "--safe" in sys.argv: SAFE_MODE = True

    load_modules()

    say("Welcome to AudioMIX - AudioScript Shell v0.2", "🎚️")
    say("Type AudioScript commands below. Ctrl+C to exit.\n")

    for arg in sys.argv[1:]:
        if arg.endswith(".audioscript") or arg.endswith(".as"):
            say("Running AudioScript file: {arg}", "▶️")
            with open(arg, "r") as f:
                for line in f: parse_and_execute(line)
            return

    midi_tick = None if SAFE_MODE else command_registry.get("midi_tick")

    while True:
        try:
            if midi_tick: midi_tick()
            line = input("🎛️  > ")
            parse_and_execute(line)
        except KeyboardInterrupt:
            say("Exiting AudioMIX Shell. Goodbye 👋")
            break
        except Exception as e:
            say(f"[AS Shell Error] {e}", "❌")
            time.sleep(0.01)

if __name__ == "__main__":
    main()
