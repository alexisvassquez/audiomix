# audiomix
# AudioMIX
# audio/ai/analyze_audio.py

# This script analyzes an audio file 
# using librosa to extract features like MFCCs,
# spectral contrast, spectral bandwidth, and tempo.

import librosa
import json
import sys
import numpy as np
# import sounddevice as sd
from pydub import AudioSegment
import tempfile
import os
import time
import soundfile as sf

SAMPLE_DIR = "audio/samples/"

def convert_to_wav(input_path):
    """
    Convert an audio file to WAV format using pydub.
    This ensures compatibility with librosa and consistent sample rates.
    """
    # Load original file (mp3, flac, etc.)
    audio = AudioSegment.from_file(input_path)

    # Normalize + ensure consistent sample rate/channel format
    audio = audio.set_frame_rate(44100).set_channels(2).normalize()
    
    # Export to temp .wav file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
        audio.export(temp_wav.name, format="wav")
        return temp_wav.name

def analyze(file_path, sr=22050, duration=None, hop_length=1024, verbose=True):
    """
    Analyze an audio file and extract features using librosa.
     - file_path: Path to the input audio file (mp3, flac, wav, etc.)
     - sr: Sample rate for loading audio (default 22050 Hz)
     - duration: Duration to load in seconds (default None = full length)
     - hop_length: Hop length for feature extraction (default 1024)
     - verbose: Whether to print detailed info during processing
    """
    wav_path = convert_to_wav(file_path)
    y, sr = librosa.load(wav_path, sr=sr, duration=duration)

    start_time = time.time()

    if verbose:
        print (f"[INFO] Loaded {file_path} | Duration: {librosa.get_duration(y=y, sr=sr): .2f}s | Sample Rate: {sr}")

    # Extract features
    mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=hop_length, n_mfcc=13)
    spectral = librosa.feature.spectral_contrast(y=y, sr=sr, hop_length=hop_length)
    spectral_bw = librosa.feature.spectral_bandwidth(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(tempo)

    result = {
        "filename": file_path,
	"mfcc_mean": np.mean(mfcc, axis=1).tolist(),
        "mfcc_var": np.var(mfcc, axis=1).tolist(),
	"spectral_contrast_mean": np.mean(spectral, axis=1).tolist(),
        "spectral_contrast_var": np.var(spectral, axis=1).tolist(),
        "spectral_bandwidth": {
            "mean": [np.mean(spectral_bw)],
            "var": [np.var(spectral_bw)]
        },
        "tempo": [tempo]
    }

    if verbose:
        print (f"[INFO] Tempo: {float(tempo):.2f} BPM")
        print (f"[INFO] MFCC shape: {mfcc.shape}")
        print (f"[INFO] Spectral Contrast shape: {spectral.shape}")
        print (f"[INFO] Spectral Bandwidth shape: {spectral_bw.shape}")
        print (f"[INFO] Analysis completed in {time.time() - start_time:.2f}s")

    return result, y, sr

# After loading audio with librosa (optional)
def fallback_play(path):
    """
    Fallback method to play audio using ffplay if sounddevice fails.
    """
    try:
        print (f"[INFO] Playing audio using ffplay...")
        os.system(f"ffplay -nodisp -autoexit \"{path}\"")
    except Exception as e:
        print (f"[ERROR] Failed to play audio: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print ("Usage: python3 analyze_audio.py <input_audio>")
        sys.exit(1)

    path = sys.argv[1]
    features, y, sr = analyze(path)

    # Save to JSON file explicitly
    output_path = "audio/analysis_output/data/audio_features.json"
    filename = os.path.basename(path)

    # Load existing data if available
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            all_features = json.load(f)
    else:
        all_features = {}

    # Add or update entry
    all_features[filename] = features

    # Save back
    with open(output_path, 'w') as f:
        json.dump(all_features, f, indent=2)

    print (f"[✅] Features for {filename} saved to {output_path}")

    if "--play" in sys.argv:
        fallback_play(path)
