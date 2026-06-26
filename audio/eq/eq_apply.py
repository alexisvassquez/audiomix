# audiomix
# AudioMIX
# audio/eq/eq_apply.py

# This module applies EQ filters to audio files
# using the specified parameters.
# It reads an input WAV file, processes it with
#  the given EQ settings, and saves the output.
# Usage:
# 1. Define your EQ filters as a list of dictionaries,
#  each containing 'freq', 'q', and 'gain_db'.
# 2. Call process_wav_file with the input file path,
#  output file path, and the filters list.

import numpy as np
import soundfile as sf
from scipy.signal import iirpeak, lfilter

def apply_eq_filters(audio, sr, filters):
    """
    Apply EQ filters to the audio signal.
    Parameters:
      - audio: numpy array of audio samples
      - sr: sample rate of the audio
      - filters: list of dictionaries with 'freq', 'q', and 'gain_db'
    Returns:processed audio signal
    """
    processed = audio.copy()

    for f in filters:
        freq = f["freq"]
        q = f["q"]
        gain_db = f["gain_db"]

        # Convert gain from dB to linear
        gain = 10 ** (gain_db / 20)

        # Create peaking filter (IIR peak)
        b, a = iirpeak(freq / (sr / 2), q)

        # Apply gain
        b *= gain

        # Apply filter
        processed = lfilter(b, a, processed)

    return processed

def process_wav_file(input_path, output_path, filters):
    """
    Read a WAV file, apply EQ filters, and save the processed audio.
    Parameters:
      - input_path: path to the input WAV file
      - output_path: path to save the processed WAV file
      - filters: list of dictionaries with 'freq', 'q', and 'gain_db'"""
    audio, sr = sf.read(input_path)

    # If stereo, process each channel independently
    if len(audio.shape) == 2:
        processed = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            processed[:, ch] = apply_eq_filters(audio[:, ch], sr, filters)
    else:
        processed = apply_eq_filters(audio, sr, filters)

    # Save the processed audio
    sf.write(output_path, processed, sr)
    print (f"✅ Processed file saved to: {output_path}")
