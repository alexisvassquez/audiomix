# audiomix
# AudioMIX
# audioscript/compiler/audio2script/analyzer.py

import numpy as np
import librosa
import librosa.feature
import librosa.segment

from typing import List, Tuple
from audioscript.compiler.audio2script.script_ir import FeatureFrame, Section

"""
Mid-complex audio analyzer for AudioScript (AS) compiler

Analyzer extracts:
- BPM (tempo)
- RMS energy envelope
- Onset strength envelope
- Band energies (bass, mids, highs)
- Spectral centroid (brightness)
- Structural segmentation in sections (intro, build, drop, outro)

Output will be List[FeatureFrame], List[Section], bpm
"""

# Utility: normalize arrays
def _norm(X):
    if len(X) == 0:
        return X
    mn, mx = np.min(X), np.max(X)
    if mx - mn < 1e-9:
        return np.zeros_like(X)
    return (X - mn) / (mx - mn)

# Load audio & basic time indexing
def analyze_audio(audio_path: str) -> Tuple[List[FeatureFrame], List[Section], float]:
    # Load audio (mono - single channel)
    y, sr = librosa.load(audio_path, sr=None, mono=True)

    # Frame size consistent with analysis
    hop = 512
    frame_times = librosa.frames_to_time(np.arange(len(y) // hop + 1), sr=sr, hop_length=hop)

    # Tempo (BPM)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo)

    # RMS Energy
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    rms = librosa.util.fix_length(rms, size=len(frame_times))
    rms_norm = _norm(rms)

    # Onset envelope (transient strength)
    # the beginning of a musical note/sound
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_env = librosa.util.fix_length(onset_env, size=len(frame_times))
    onset_norm = _norm(onset_env)

    # Mel-Spectrogram Bands (bass/mids/highs)
    """
    Definition: visual representation of the freq content of an audio signal over time
    Freq axis is transformed to the mel scale to better approx human hearing
    """
    mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, hop_length=hop)
    mel_db = librosa.power_to_db(mel, ref=np.max)

    # Split mel bands roughly
    bass = _norm(np.mean(mel_db[0:20, :], axis=0))    # 0-200Hz approx
    mids = _norm(np.mean(mel_db[20:60, :], axis=0))   # 200-1200Hz
    highs = _norm(np.mean(mel_db[60:128, :], axis=0)) # 1200-8000+ Hz

    # Spectral centroid (brightness)
    """
    Definition: measure of the center of mass of a sound's spectrum
    Calculated as the weighted average of the freqs present in a signal

    Higher values correspond to brighter sounds
    Computed from sound's spectogram (refer to above) by analyzing its
    magnitude/power at each freq bin
    """
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]
    centroid = librosa.util.fix_length(centroid, size=len(frame_times))
    centroid_norm = _norm(centroid)

    # Structural Segmentation - memory management
    """
    Divides into logical units (segments)
    Compatible with all librosa versions (old-API safe)
    """
    # Compute self-similarity matrix
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    S = librosa.segment.recurrence_matrix(chroma, width=3, mode='affinity')

    # Compute + normalize novelty curve function (classic method)
    novelty = librosa.onset.onset_strength(S=S, sr=sr)
    novelty = _norm(novelty)

    # Pick peaks as segment boundaries (simple structure for now)
    boundaries = librosa.util.peak_pick(
        novelty, pre_max=3, post_max=3, pre_avg=3, post_avg=5,
        delta=0.2, wait=10
    )
    # Always incl start and end
    boundaries = [0] + boundaries.tolist() + [len(frame_times) - 1]

    # Label sections crudely (intro -> build -> drop -> outro)
    section_labels = ["intro", "build", "drop", "outro"]
    sections: List[Section] = []

    # Evently dist labels across detected boundaries
    for i in range(len(boundaries) - 1):
        start_frame = boundaries[i]
        end_frame = boundaries[i + 1]

        if i < len(section_labels):
            label = section_labels[i]
        else:
            label = "section" + str(i)

        start_time = float(frame_times[start_frame])
        end_time = float(frame_times[end_frame])

        sections.append(Section(start=start_time, end=end_time, label=label))

    # Build FeatureFrames
    feature_frames: List[FeatureFrame] = []

    for i, t in enumerate(frame_times):
        # in case mel or other bands are shorter
        idx = min(i, len(rms_norm) - 1)

        feature_frames.append(
            FeatureFrame(
                time=float(t),
                bpm=bpm,
                energy=float(rms_norm[idx]),
                bass_level=float(bass[idx]),
                mids_level=float(mids[idx]),
                highs_level=float(highs[idx]),
                onset_strength=float(onset_norm[idx]),
                section_label=None,    # optional - mapper can infer
            )
        )

    return feature_frames, sections, bpm
