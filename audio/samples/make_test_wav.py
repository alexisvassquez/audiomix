# AudioMIX
# audio/samples/make_test_wav.py

import numpy as np
import wave

duration = 3    # seconds
samplerate = 44100
freq = 440.0    # A4
volume = 0.3

t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
samples = (np.sin(2 * np.pi * freq * t) * volume * 32767).astype(np.int16)

with wave.open("test_tone.wav", "w") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)    # 16-bit
    wf.setframerate(samplerate)
    wf.writeframes(samples.tobytes())
