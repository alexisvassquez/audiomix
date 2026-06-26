# AudioMIX
# audio/led/audio_reactive.py

from audio.led.controller import LightController
from audio.led.color_profiles import get_color_for_mood, get_pattern_for_mood

def react_to_audio(mood, bpm=120, zone="main"):
    led = LightController()
    color = get_color_for_mood(mood)
    pattern = get_pattern_for_mood(mood)

    print(f"[Live Trigger] Mood: {mood} >> Pattern: {pattern}, Zone: {zone}")

    if pattern == "strobe" or bpm > 140:
        led.strobe(color, bpm, zone)
    elif pattern == "chase" or bpm > 100:
        led.pulse(color, bpm, zone)
    else:
        led.fade_to(color, duration=2.0, zone=zone)

    return {
        "zone": zone,
        "mood": mood,
        "color": color,
        "pattern": pattern,
        "bpm": bpm
    }
