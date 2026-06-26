# audiomix
# AudioMIX
# audio/eq/predict_and_apply_eq.py

import os
import sys
import json
from audio.ai.modules.convert_audio import convert_to_wav
from audio.ai.modules.feature_extraction import extract_features
from audio.ai.modules.predict_eq import predict_labels
from audio.eq.eq_loader import load_eq_preset
from audio.eq.eq_apply import process_wav_file

OUTPUT_DIR = "audio/analysis_output"

def generate_audioscript(eq_labels, audio_filename, bpm=120):
    lines = [f'# AudioScript generated for {audio_filename}']
    for label in eq_labels:
        lines.append(f'eq.set("{label}")')
    lines.append(f'play("{audio_filename}")')
    lines.append(f'pulse("cyan", bpm={bpm})')
    return "\n".join(lines)

def main(input_audio_path):
    print (f"[🎧] Processing file: {input_audio_path}")
    wav_path = convert_to_wav(input_audio_path)

    # Feature extraction
    features = extract_features(wav_path)

    # Predict EQ labels
    eq_labels = predict_labels(features)    # Must return label e.g. ['bass_boost', 'treble']
    print (f"[🔊] Predicted EQ labels: {eq_labels}")

    # Load presets
    filters = []
    for label in eq_labels:
        preset_data = load_eq_preset("presets_combined.json")
        if label in preset_data:
            filters.extend(preset_data[label]["filters"])
        else:
            print (f"[⚠️] Preset not found for label: {label}")

    # Apply EQ filters to WAV
    base_name = os.path.splitext(os.path.basename(wav_path))[0]
    output_eq_path = os.path.join(OUTPUT_DIR, f"{base_name}_eq.wav")
    process_wav_file(wav_path, output_eq_path, filters)

    # Write AudioScript
    audioscript = generate_audioscript(eq_labels, os.path.basename(output_eq_path))
    audioscript_path = os.path.join(OUTPUT_DIR, f"{base_name}_eq.audioscript")
    with open(audioscript_path, "w") as f:
        f.write(audioscript)
    print (f"[🎼] AudioScript saved to: {audioscript_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print ("Usage: python3 predict_and_apply_eq.py <audio_file>")
        sys.exit(1)

    main(sys.argv[1])
