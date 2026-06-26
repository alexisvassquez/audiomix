# AudioMIX
# audio/ai/modules/merge_dataset.py

# Merges metadata from AudioMIX_metadata.csv with labels 
# from labels.jsonl into a single dataframe for training.
# This module is designed to be run after both datasets have been generated, 
# and will handle cases where one or both datasets are empty.

import pandas as pd
import json
from pathlib import Path

# Loads metadata (csv) and labels (jsonl) into a single merged dataframe
def load_and_merge_datasets(meta_path="audio/ai/datasets/AudioMIX_metadata.csv",
                            label_path="audio/ai/datasets/labels.jsonl"):
    meta = pd.read_csv(meta_path, comment="#")
    with open(label_path, "r", encoding="utf-8") as f:
        labels = [json.loads(line) for line in f if line.strip() and not line.startswith("#")]

    if meta.empty:
        print ("[!] AudioMIX_metadata.csv is empty - nothing to merge yet.")
        return pd.DataFrame()

    if not labels:
        print ("[!] labels.jsonl is empty - creating placeholder merge.")
        df_labels = pd.DataFrame(columns=["file"])
    else:
        df_labels = pd.DataFrame(labels)
        if "file" not in df_labels.columns:
            raise KeyError("labels.jsonl missing required 'file' field.")

    if "file" not in meta.columns:
        raise KeyError("AudioMIX_metadata.csv missing required 'file' column header.")

    df_merged = pd.merge(meta, df_labels, on="file", how="left")

    # Ensure numeric fields are properly typed
    for col in ["energy", "valence", "danceability", "bpm"]:
        if col in df_merged.columns:
            df_merged[col] = pd.to_numeric(df_merged[col], errors="coerce")

    print ("✅  Merged {len(df_merged)} entries ({df_labels.shape[0]} labels)")
    return df_merged

if __name__ == "__main__":
    df = load_and_merge_datasets()
    print (df.head())
