# audiomix
# AudioMIX
# audio/ai/analysis/features_summary.py

# This script loads the extracted audio features from
# a JSON file and provides a summary of each feature,
# including mean, variance, and other statistics. 
# It also includes an optional plotting function to
# visualize specific features over time.

import json
import numpy as np
import matplotlib.pyplot as plt
import os

def load_features(json_path):
    """
    Load JSON features from file.
    """
    with open(json_path, "r") as f:
        data = json.load(f)
    return data

def summarize_features(name, values):
    """
    Print summary statistics for a given feature.
    """
    def print_stats(label, arr):
        arr = np.array(arr)
        print (f"  [{label.upper()}]")
        print (f"  Count: {len(arr)}")
        print (f"  Mean: {arr.mean():.2f}")
        print (f"  Median: {np.median(arr):.2f}")
        print (f"  Min: {arr.min():.2f}")
        print (f"  Max: {arr.max():.2f}")

    print (f"\n[ {name.upper()} ]")

    if isinstance(values, list):
        print_stats("all", values)

    elif isinstance(values, dict):
        if "mean" in values:
            print_stats("mean", values["mean"])
        if "var" in values:
            print_stats("var", values["var"])

    else:
        print (f"  Could not summarize (unsupported format)")

def plot_feature(data, key):
    """
    Plot a specific feature over time.
     - Handles both list and dict formats for the feature values.
    """
    values = data.get(key)
    if values is None:
        print (f"Feature '{key}' not found for plotting.")
        return

    if isinstance(values, dict): # For keys like 'spectral_bandwidth'
        for subkey, subvalues in values.items():
            if isinstance(subvalues, list):
                plt.plot(subvalues, label=f"{key}_{subkey}")
    elif isinstance(values, list):
        plt.plot(values, label=key)
    else:
        print (f"Unsupported type for plotting '{key}': {type(values)}")
        return

    plt.title(f"{key} Over Time")
    plt.xlabel("Frame")
    plt.ylabel("Value")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

# Main execution
if __name__ == "__main__":
    # Set path to JSON file
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(BASE_DIR, "../analysis_output/features_summary.json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found at: {json_path}")

    # Load and summarize
    data = load_features(json_path)

    # Summarize all features
    for key, value in data.items():
        if key == "tempo":
            try: 
                print (f"\n[ TEMPO ]\n  Value: {value[0]:.2f}")
            except Exception:
                print (f"\n[ TEMPO ]\n  Could not summarize tempo")
            continue

        summarize_features(key, value)

    # Optional plot
    plot_feature(data, "spectral_bandwidth")
