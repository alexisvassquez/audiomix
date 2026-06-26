# AudioMIX
# audio/ai/modules/train_eq_model.py

# Trains a PyTorch Lightning model to predict EQ tags from audio features.
# This module loads precomputed features and labels,
#  prepares a dataset, and trains a Lightning model,
#  saving the trained weights and label mapping.
# It is designed to be run as a standalone script,
#  and expects the following files to exist:
#   - audio/analysis_output/data/audio_features.json
#   - audio/analysis_output/data/eq_labels.json
# Example usage:
#   python3 -m audio.ai.modules.train_eq_model

import sys
import json
import torch
from lightning.pytorch import Trainer
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import MultiLabelBinarizer
from audio.ai.modules.lightning_module import LightningEQNet
from audio.ai.modules.predict_eq import flatten_features_dict
import librosa
import numpy as np
from typing import List

# toggle to False for dynamic extraction
USE_PRECOMPUTED = True

# Paths
SAMPLES_DIR = "audio/samples/"
FEATURES_PATH = "audio/analysis_output/data/audio_features.json"
LABELS_PATH = "audio/analysis_output/data/eq_labels.json"
MODEL_OUTPUT_PATH = "models/eq_model.pt"
OUTPUT_LABELS_TXT = "models/eq_labels.txt"

# Feature Extraction
def extract_features(filepath):
    """
    Extracts audio features from a file using librosa.
    Args:        
        filepath: Path to the audio file.
    Returns:
        A dictionary of extracted features.
    """
    y, sr = librosa.load(filepath, duration=10, sr=22050)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
    tempo = librosa.beat.tempo(y=y, sr=sr)

    # Flatten features into a structured dictionary
    return {
        "mfcc_mean": np.mean(mfcc, axis=1).tolist(),
        "mfcc_var": np.var(mfcc, axis=1).tolist(),
        "spectral_contrast_mean": np.mean(spectral_contrast, axis=1).tolist(),
        "spectral_contrast_var": np.var(spectral_contrast, axis=1).tolist(),
        "spectral_bandwidth": {
            "mean": [np.mean(spectral_bandwidth)],
            "var": [np.var(spectral_bandwidth)]
        },
        "tempo": tempo
    }

# PyTorch Dataset
class EQDataset(Dataset):

    def __init__(self, mlb, use_precomputed=True):
        """
        Initializes the dataset by loading features and labels, and preparing tensors.
        Args:
            mlb: An instance of MultiLabelBinarizer for encoding labels.
            use_precomputed:
              If True, loads features from a JSON file.
              If False, extracts features on-the-fly from audio files (not implemented)."""
        self.data = []
        self.labels = []

        # Load labels
        with open(LABELS_PATH, "r") as f:
            label_dict = json.load(f)

        # debugging logic    
        print (f"[INFO] Loaded labels for: {list(label_dict.keys())}")

        # Load features
        if use_precomputed:
            with open(FEATURES_PATH, "r") as f:
                raw_features = json.load(f)

            # Flatten list of single-entry dicts into one combined dict
            feature_dict = {k.strip().lower(): v for k, v in raw_features.items()}

            # debugging logic
            print (f"[INFO] Loaded features for: {list(feature_dict.keys())}")

            # Debugging logic. Shows any mismatches
            for name in label_dict.keys():
                normalized_name = name.strip().lower()
                if normalized_name not in feature_dict:
                    print (f"[WARN] Missing features for: {name}")
                else:
                    x = self.flatten_features(feature_dict[normalized_name])
                    y = label_dict[name]
                    self.data.append(x)
                    self.labels.append(y)

            print (f"[✅] Matched {len(self.data)} samples with labels + features.")
        else:
            raise NotImplementedError("Live audio feature extraction not yet implemented")

        if len(self.data) == 0:
            raise RuntimeError("[!] No data available for training. Check matching keys in labels vs features.")

        
        # debugging logic
        print (f"[DEBUG] Example input shape: {len(self.data[0])}")

        # Convert to tensors
        self.data = torch.tensor(self.data, dtype=torch.float32)
        self.labels = torch.tensor(mlb.fit_transform(self.labels), dtype=torch.float32)

    # Dataset length and item access
    def __len__(self):
        return len(self.data)

    # Returns a single sample (features, labels) pair
    def __getitem__(self, idx):
        return self.data[idx], self.labels[idx]

    # Flatten nested structure into a single list
    def flatten_features(self, features):
        flat = []
        for key, value in features.items():
            if isinstance(value, dict):
                for subvalue in value.values():
                    flat.extend(subvalue)
            elif isinstance(value, list):
                flat.extend(value)
            elif isinstance(value, (int, float)):
                flat.append(value)
        return flat

# Main Training Function
def train_model():
    with open(LABELS_PATH, "r") as f:
        all_labels = set(tag for tags in json.load(f).values() for tag in tags)
    labels = sorted(list(all_labels))
    with open(OUTPUT_LABELS_TXT, "w") as f:
        f.write(",".join(labels))

    # debugging logic
    print (f"[INFO] Final label set: {labels}")
    mlb = MultiLabelBinarizer(classes=labels)
    dataset = EQDataset(mlb, use_precomputed=USE_PRECOMPUTED)
    dataloader = DataLoader(dataset, batch_size=2, shuffle=True)

    # debugging logic
    input_dim = len(dataset.data[0])
    num_classes = len(dataset.labels[0])
    print (f"[INFO] Input dim: {input_dim}, Num classes: {num_classes}")

    # Train Lightning model
    model = LightningEQNet(input_dim=input_dim, num_classes=num_classes)
    trainer = Trainer(max_epochs=15, accelerator="cpu", logger=False, enable_checkpointing=False, enable_model_summary=False)
    trainer.fit(model, dataloader)

    # Save model and label binarizer
    torch.save(model.state_dict(), MODEL_OUTPUT_PATH)
    print ("✅ EQ model trained and saved to {MODEL_OUTPUT_PATH}.")

if __name__ == "__main__":
    train_model()
