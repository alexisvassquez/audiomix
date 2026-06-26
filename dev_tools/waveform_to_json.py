# audiomix
# AudioMIX
# dev_tools/waveform_to_json.py

import os
import json
import numpy as np
import soundfile as sf
import sys
from pydub import AudioSegment

def convert_to_wav_if_needed(input_path):
    ext = os.path.splitext(input_path)[1].lower()
    if ext in [".wav", ".flac", ".aiff", ".aifc", ".ogg"]:
        return input_path    # supported by soundfile

    if ext == ".mp3":
        audio = AudioSegment.from_mp3(input_path)
    elif ext == ".m4a":
        audio = AudioSegment.from_file(input_path, format="m4a")
    elif ext == ".aac":
        audio = AudioSegment.from_file(input_path, format="aac")
    else:
        print (f"[❌] Unsupported file type: {ext}")
        return None

    # Export to WAV
    wav_path = os.path.splitext(input_path)[0] + "_converted.wav"
    audio.export(wav_path, format="wav")
    print (f"[🔁] Converted {input_path} -> {wav_path}")
    return wav_path

def parse_markers(marker_arg):
    markers = {}
    if not marker_arg:
        return markers
    for pair in marker_arg.split(","):
        if "=" in pair:
            label, value = pair.split("=")
            try:
                markers[label.strip()] = float(value.strip())
            except ValueError:
                continue
    return markers

def convert_to_waveform_json(input_path, output_dir="audio/analysis_output/data", num_points=1000, marker_arg=None):
    wav_path = convert_to_wav_if_needed(input_path)
    if not wav_path:
        return

    try:
        data, samplerate = sf.read(wav_path)
    except Exception as e:
        print (f"[❌] Failed to read audio file: {e}")
        return

    if data.ndim > 1:
        data = data[:, 0]    # Use left channel if stereo

    duration = len(data) / samplerate

    # Normalize and downsample
    data = data / np.max(np.abs(data))    # normalize to [-1, 1]
    indices = np.linspace(0, len(data) - 1, num_points).astype(int)
    downsampled = data[indices].tolist()

    # Parse loop markers
    markers = parse_markers(marker_arg)

    # Output structure
    waveform_data = {
        "duration": round(duration, 4),
        "samplerate": samplerate,
        "points": downsampled,
        "markers": markers
    }

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_waveform.json")

    with open(output_path, "w") as f:
        json.dump(waveform_data, f, indent=2)

    print (f"[✅] Waveform JSON saved to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print ("Usage: python3 waveform_to_json.py <audio_file> [--markers intro=0,drop=15]")
    else:
        input_path = sys.argv[1]
        marker_arg = None
        if "--markers" in sys.argv:
            marker_index = sys.argv.index("--markers")
            if marker_index + 1 < len(sys.argv):
                marker_arg = sys.argv[marker_index + 1]
        convert_to_waveform_json(input_path, marker_arg=marker_arg)
