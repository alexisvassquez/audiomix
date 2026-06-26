# audiomix
# AudioMIX
# audio/analysis_output/plot_waveform.py

# This script reads waveform data from a CSV file
# and plots the input and output waveforms.
# The CSV file is expected to have three columns:
# "index", "input", and "output".
# The resulting plot is displayed using Matplotlib,
#  allowing for visual comparison of the waveforms. 
# This is useful for analyzing the effects of audio processing,
#  such as clipping or EQ adjustments, on the waveform shape.

import pandas as pd
import matplotlib.pyplot as plt

# Load waveform data from CSV
df = pd.read_csv("audio/analysis_output/waveform.csv")

# Check if required columns are present
plt.figure()
plt.plot(df["index"], df["input"], label="Input")
plt.plot(df["index"], df["output"], label="Output")

# Basic plot settings
plt.title("Clipper Waveform")
plt.xlabel("Sample Index")
plt.ylabel("Amplitude")
plt.legend()
plt.grid()

plt.show()
