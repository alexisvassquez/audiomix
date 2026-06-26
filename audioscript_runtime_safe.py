# audiomix
# AudioMIX
# audioscript_runtime_safe.py

import os, sys, importlib, shlex

print ("🎧  AudioMIX Ultra-safe Shell - type load(\"module.py\") or Ctrl+C to exit")

LOADED = {}

def load(mod_file: str):
    mod_file = mod_file.strip().strip('"').strip("'")
    if not mod_file.endswith(".py"):
        mod_path = mod_file
        name = mod_file.split(".")[-1]
    else:
        name = mod_file[:-3]
        mod_path = f"performance_engine.modules.{name}".replace("-", "_")
    print (f"....importing {mod_path}")
    try:
        m = importlib.import_module(mod_path)
        LOADED[name] = m
        if hasattr(m, "register"):
            try:
                m.register()    # self register
                print (f"✅  registered commands from {name}")
            except Exception as e:
                print (f"⚠️  register() failed in {name}: {e}")
        else:
            print (f"ℹ️  no register() in {name}")
    except Exception as e:
        print (f"❌  import failed for {name}: {e}")

def list_loaded():
    if not LOADED:
        print ("ℹ️  no modules loaded yet")
        return
    for k in LOADED:
        print (f" - {k}")

def show_help():
    print ("Available commands:")
    print ("  load(\"module.py\")      → Load a command module")
    print ("  list() or list_loaded()  → Show loaded modules")
    print ("  analyze(\"file.wav\")    → Analyze audio and print mood")
    print ("  trigger_zones(...)       → Trigger LED pattern manually")

def analyze(path):
    try:
        from audio.ai.analysis.analyze_audio import analyze as run
        from audio.ai.analysis.inference_engine import interpret_from_features

        result, *_ = run(path)
        if not result or not isinstance(result, dict):
            print (f"⚠️  no valid features returned.")
            return
        if "times" not in result or "rms" not in result:
            print ("⚠️  [analyze] Missing 'times' or 'rms'. Skipping mood inference.")
            mood = None
        else:
            mood = interpret_from_features(result)
    except Exception as e:
        print (f"❌  Analysis failed: {e}")

# `zones=` kwarg to be coded into inference_engine.py script for LED zone support in future
def trigger_zones(mood="calm", bpm=120):
    try:
        from audio.ai.analysis.inference_engine import generate_lighting_profile
        generate_lighting_profile({mood}, bpm=bpm)
        print (f"🌈  Mood: {mood} | BPM: {bpm}")
    except Exception as e:
        print (f"❌  Lighting trigger failed: {e}")

def parse_and_execute(line: str):
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return
    if "(" in line and line.endswith(")"):
        cmd, arg = line.split("(", 1)
        arg = arg[:-1]
        if cmd == "load":
            load(arg)
        elif cmd in ("list", "list_loaded"):
            list_loaded()
        elif cmd == "analyze":
            analyze(arg.strip().strip('"'))
        elif cmd == "trigger_zones":
            # optional LED test
            trigger_zones(mood="excited", bpm=128)
        elif cmd == "help":
            show_help()
        else:
            print (f"⚠️  unknown command: {cmd}")
    else:
        print ("ℹ️  use load(\"module.py\") or list_loaded()")

try:
    while True:
        line = input("🛡️  > ")
        parse_and_execute(line)
except KeyboardInterrupt:
    print("\nsee you later! 👋")
