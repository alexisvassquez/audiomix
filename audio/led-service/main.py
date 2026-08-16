# AudioMIX
# audio/led-service/main.py
#
# FastAPI for the LED controller
# In development

import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../led')))

from fastapi import FastAPI
from pydantic import BaseModel

from audio.led.controller import LightController
from audio.led.color_profiles import get_color_for_mood, get_pattern_for_mood, get_color_for_name
from audio.led.audio_reactive import react_to_audio

app = FastAPI()
led = LightController()

if len(sys.argv) < 2:
    print("Usage: python main.py '{\"mood\": \"happy\", \"bpm\": 120}'")
    sys.exit(1)

try:
    data = json.loads(sys.argv[1])
    mood = data.get("mood")
    bpm = data.get("bpm")

    if mood is None or bpm is None:
         raise ValueError("Both 'mood' and 'bpm' must be provided in the JSON input.")

    print (f"[INPUT] Mood: {mood}, BPM: {bpm}")
    react_to_audio(mood, bpm)

except Exception as e:
    print (f"[ERROR] {e}")
    sys.exit(1)

class LEDRequest(BaseModel):
    mode: str
    rgb: tuple
    bpm: int = 120
    duration: float = 2.0

@app.post("/led")
def control_led(req: LEDRequest):
    if req.mode == "pulse":
         led.pulse(req.rgb, req.bpm)
    elif req.mode == "fade":
         led.fade_to(req.rgb, req.duration)
    elif req.mode == "strobe":
         led.strobe(req.rgb, req.bpm)
    else:
         led.set_color(req.rgb)
    return {"status": "ok", "mode": req.mode, "color": req.rgb}
