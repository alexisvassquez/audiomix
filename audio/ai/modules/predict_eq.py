# AudioMIX
# audio/ai/modules/predict_eq.py

# Predicts EQ tags for a given audio file using a trained Lightning model.
# This module takes extracted features as input and outputs
#  predicted EQ tags with confidence scores.
# It is designed to be run as a standalone script,
#  taking an audio file path as a command-line argument.
# Example usage:
#   python3 -m audio.ai.modules.predict_eq path/to/audiofile.mp3

import torch
import numpy as np
import librosa
import sys
from audio.ai.modules.lightning_module import LightningEQNet

# Paths to model and labels
LABELS_PATH = "models/eq/eq_labels.txt"
MODEL_PATH = "models/eq/eq_model.pt"

def load_labels():
    """
    Loads EQ tag labels from a text file, one label per line.
    Returns:
        List of label strings.
    """
    with open(LABELS_PATH, "r") as f:
        return f.read().strip().split(",")

def flatten_features_dict(features_dict):
    """Flattens a nested dictionary of features into a single list of numeric values.
    Handles nested mean/var structures and simple numeric lists.
    Args:
        features_dict: A dictionary where values can be numeric,
          lists, or nested dicts with 'mean' and 'var'.
    Returns:
        A flat list of numeric feature values."""
    flat = []
    for key, value in features_dict.items():
        if isinstance(value, dict):    # nested mean/var
            flat.extend(value.get("mean", []))
            flat.extend(value.get("var", []))
        elif isinstance(value, (list, np.ndarray)):
            flat.extend(value)
        elif isinstance(value, (int, float)):
            flat.append(value)
        else:
            print (f"[!] Skipping unsupported feature type: {key}")
    return flat

def predict_labels(features_dict):
    """
    Predicts EQ tags based on extracted features using a trained Lightning model.
    Args:
        features_dict: A dictionary of extracted features for an audio file.
    Returns:
        A list of predicted EQ tags with confidence above 0.5.
    """
    labels = load_labels()
    flat_features = flatten_features_dict(features_dict)

    # Handle input features 
    x = torch.tensor(flat_features, dtype=torch.float32).unsqueeze(0)

    # Load Lightning model
    model = LightningEQNet(input_dim=len(flat_features), num_classes=len(labels))
    model.load_state_dict(torch.load(MODEL_PATH))
    model.eval()

    # Predict EQ tags
    with torch.no_grad():
        output = model(x).squeeze(0).numpy()

    predictions = {label: float(score) for label, score in zip(labels, output)}
    sorted_preds = sorted(predictions.items(), key=lambda x: x[1], reverse=True)

    # Display predicted tags with confidence scores
    print ("\n🎛️ Predicted EQ Tags:")
    selected_labels = []
    for label, score in sorted_preds:
        status = "✅" if score > 0.5 else "❌"
        print (f"{status} {label:<10} -> confidence: {score:.2f}")
        if score > 0.5:
            selected_labels.append(label)

    return selected_labels

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print ("Usage: python3 -m audio.ai.modules.predict_eq <audio_file>")
        sys.exit(1)

    file_path = sys.argv[1]

    # Extract features from the audio file
    from audio.ai.modules.feature_extraction import extract_features
    features = extract_features(file_path)

    if not features:
        print ("[❌] Failed to extract features.")
        sys.exit(1)

    print (f"[+] Extracted features from {file_path}")
    tags = predict_labels(features)

    print ("\Final EQ Tags Selected:", tags)
