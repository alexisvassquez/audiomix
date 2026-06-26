# AudioMIX
# audio/ai/modules/tempo_analysis.py

# Analyzes the tempo (BPM) of an audio file using librosa.
# This module provides a function to extract
#  the BPM from an audio file, and can be used as part of a
#  larger feature extraction pipeline for music analysis.
# Example usage:
#   from audio.ai.modules.tempo_analysis import get_bpm_from_audio
#   bpm = get_bpm_from_audio("path/to/audiofile.mp3")

import librosa

# Extracts BPM (tempo) from an audio file using librosa's beat tracking.
def get_bpm_from_audio(file_path):
    """Extracts the BPM (tempo) from an audio file using librosa.
    Args:        file_path: Path to the audio file.
    Returns:        Estimated BPM as an integer, or 120 if detection fails.
    """
    try:
        y, sr = librosa.load(file_path)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        return int(tempo)
    except Exception as e:
        print (f"[!] BPM detection failed: {e}")
        return 120 # Fallback default BPM
