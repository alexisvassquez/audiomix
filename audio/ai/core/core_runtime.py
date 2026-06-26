# audiomix
# AudioMIX
# audio/ai/core/core_runtime.py

# Core Runtime for AudioMIX AI
# This module serves as the main entry point for
#  processing audio files, extracting features, and
#  running the inference engine to generate
#  AudioScripts and lighting profiles.
# It handles audio conversion, feature extraction, 
# and orchestrates the overall AI workflow for
#  analyzing audio and generating outputs for the LED
#  system.

import json
import sys
import numpy as np
import os
from audio.ai.modules.convert_audio import convert_to_wav
from audio.ai.modules.feature_extraction import extract_features
from audio.ai.analysis.inference_engine import interpret_from_features

def convert_ndarrays(obj):
    """
    Recursively converts any numpy arrays in the given object to lists, making it JSON serializable.
    This function is useful for preparing the extracted features for JSON serialization,
      as numpy arrays cannot be directly serialized to JSON. By converting them to lists, we can easily save the features in a JSON file for later analysis or debugging."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_ndarrays(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_ndarrays(i) for i in obj]
    else:
        return obj

def analyze(file_path):
    """
    Main function to analyze an audio file. 
    It converts the audio to WAV format,
      extracts features, and saves a summary of the features to a JSON file. 
    The extracted features are returned as a dictionary for further processing.
    This function serves as the core runtime for
      processing audio files in the AudioMIX AI system. It ensures that the audio is in the correct format, extracts relevant features, and prepares the data for inference and script generation.
    """
    wav_path = convert_to_wav(file_path)
    features = extract_features(wav_path)
    features_clean = convert_ndarrays(features)

    output_dir = "audio/analysis_output"
    os.makedirs(output_dir, exist_ok=True)

    # Save to JSON file
    json_path = os.path.join(output_dir, "features_summary.json")
    with open(json_path, "w") as f:
        json.dump(features_clean, f, indent=2)

    return features_clean

# Example usage: python3 core_runtime.py path/to/audiofile.mp3
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print ("Usage: python3 core_runtime.py <audio_file>")
        sys.exit(1)

    result = analyze(sys.argv[1])

    # Run AI interpretation ad script generation
    print ("[+] Running inference engin...")
    interpret_from_features(result)
