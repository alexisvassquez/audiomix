# AudioMIX
# dev_tools/waveform_tools.py

import os
import numpy as np
import soundfile as sf
from performance_engine.utils.shell_output import say

def plot_waveform(file_path):
    if not os.path.exists(file_path):
        say(f"[❌] File not found: {file_path}", "❌")
        return

    try:
        data, samplerate = sf.read(file_path)
    except Exception as e:
        say(f"[❌] Failed to read audio file: {e}", "❌")
        return

    if data.ndim > 1:
        data = data[:, 0]    # Use left channel if stereo

    duration = len(data) / samplerate
    time_axis = np.linspace(0, duration, num=len(data))

    try:
        import matplotlib.pyplot as plt    # Delay-import to avoid shell startup kill

        plt.figure(figsize=(12, 4))
        plt.plot(time_axis, data, linewidth=0.7, color='mediumseagreen')
        plt.title(f"Waveform: {os.path.basename(file_path)}")
        plt.xlabel("Time (s)")
        plt.ylabel("Amplitude")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

        say(f"[🌀] Displayed waveform for: {file_path}", "🌀")

    except Exception as e:
        say(f"[❌] Plotting failed: {e}", "❌")

def register():
    return {
        # "plot_waveform": plot_waveform
    }
