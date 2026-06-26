# audiomix
# AudioMIX
# audio/ai/modules/feature_extraction.py

"""
This module provides functions to extract audio 
features from music files using the librosa library.
It includes features such as MFCCs, spectral
contrast, spectral bandwidth, and tempo. 
The extracted features are returned in a structured
format for use in machine learning models or other
applications. 
The module also includes verbose logging to provide insights 
into the feature extraction process and the time taken for each step.
"""

import librosa
import numpy as np
import time

def extract_features(file_path, sr=22050, duration=None, hop_length=1024, verbose=True):
    """
    Extracts audio features from a given audio file.
    Args:
        file_path (str): Path to the audio file.
        sr (int): Sample rate for loading the audio. Default is 22050 Hz.
        duration (float): Duration of the audio to load in seconds. Default is None (load full audio).
        hop_length (int): Number of samples between successive frames. Default is 1024.
        verbose (bool): If True, prints information about the loaded audio and feature extraction process. Default is True.
    Returns:
        dict: A dictionary containing the extracted audio features.
    """
    y, sr = librosa.load(file_path, sr=sr, duration=duration)
    features = {}
    if verbose:
        print(f"[INFO] Loaded {file_path} | Duration: {librosa.get_duration(y=y, sr=sr):.2f}s | Sample Rate: {sr}")

    start_time = time.time()

    # MFCCs
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    features["mfcc_mean"] = mfcc.mean(axis=1).tolist()    
    features["mfcc_var"] = mfcc.var(axis=1).tolist()

    # Spectral Contrast
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
    features["spectral_contrast_mean"] = contrast.mean(axis=1).tolist()
    features["spectral_contrast_var"] = contrast.var(axis=1).tolist()

    # Spectral Bandwidth
    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
    features["spectral_bandwidth"] = {
        "mean": spectral_bandwidth.mean(axis=1).tolist(),
        "var": spectral_bandwidth.var(axis=1).tolist(),
    }

    # Tempo
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    features["tempo"] = tempo

    elapsed_time = time.time() - start_time

# Verbose logging of feature extraction time
    if verbose:
        print(f"[INFO] Extracted features from {file_path} in {elapsed_time:.2f} seconds")
    return features
