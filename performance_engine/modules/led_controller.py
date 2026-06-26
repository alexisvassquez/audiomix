# AudioMIX
# performance_engine/modules/led_controller.py

# Module to control LED hardware
# Defines glow (color name), pulse reaction
# to BPM, mood reactions, and zones
# Registers AS commands to the AudioMIX AS shell

import sys
sys.path.append("audio/led")

from audio.led.controller import LightController
from audio.led.audio_reactive import react_to_audio
from audio.led.color_profiles import get_color_for_mood
from performance_engine.utils.shell_output import say
from performance_engine.modules.context import command_registry
from audio.ai.analysis.inference_engine import generate_lighting_profile

led = LightController()

def glow(color_name):
    rgb = get_color_for_mood(color_name)
    led.set_color(rgb)
    say(f"LED glowing {color_name}", "💡")

def pulse(color_name, bpm):
    rgb = get_color_for_mood(color_name)
    led.pulse(rgb, int(bpm))
    say(f"Pulsing {color_name} @ {bpm} BPM", "💡")

def mood_react(mood, bpm):
    color = react_to_audio(mood, int(bpm))
    say(f"[MOOD] {mood} \u2192 LED color: {color}", "🎛️")

def trigger_zones(zones, mood="calm", bpm=120):
    try:
        generate_lighting_profile({mood}, bpm=bpm, zone=zones)
        say(f"[ZONES] Triggered: {zones} | Mood: {mood} | BPM: {bpm}", "🌈")
    except Exception as e:
        say(f"[ERROR] trigger_zones failed: {e}", "❌")

def register():
    return {
        "glow": glow,
        "pulse": pulse,
        "led.mood_react": mood_react,
        "trigger_zones": trigger_zones
    }
