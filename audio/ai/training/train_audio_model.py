# AudioMIX
# audio/ai/train_audio_model.py

# Trains AudioMIX PyTorch model (Juniper2.0) to predict mood tags from audio features.
# This module loads a merged dataset of audio features and mood labels,
#  prepares a PyTorch dataset and dataloader,
#  defines a simple feedforward model, and trains the model,
#  saving the trained weights to disk.
# It is designed to be run as a standalone script,
#  and expects the following files to exist:
#   - audio/ai/datasets/AudioMIX_metadata.csv
#   - audio/ai/datasets/labels.jsonl
# Example usage:
#   python3 -m audio.ai.train_audio_model

import os
import json
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import pandas as pd
from pathlib import Path
from sklearn.preprocessing import MultiLabelBinarizer

# Local imports
from audio.ai.modules.merge_dataset import load_and_merge_datasets
from validate_dataset import main as validate_dataset

# Configuration
DATASET_DIR = Path("audio/ai/datasets/")
ROOT_MODEL_DIR = Path("models")
MODEL_DIR = ROOT_MODEL_DIR / "juniper"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "mood_classifier.pt"

BATCH_SIZE = 8
EPOCHS = 25
LEARNING_RATE = 0.001
FEATURE_COLUMNS = ["bpm", "energy", "valence", "danceability"]
TARGET_COLUMN = "moods"

# Dataset Class
class MoodDataset(Dataset):
    def __init__(self, df, mlb):
        """
        Initializes the dataset with features and multi-label targets.
        Args:
            df: A pandas DataFrame containing the merged dataset with features and labels.
            mlb: A fitted MultiLabelBinarizer instance for encoding mood tags.
        """
        self.X = torch.tensor(df[FEATURE_COLUMNS].values, dtype=torch.float32)
        self.y = torch.tensor(mlb.transform(df[TARGET_COLUMN]), dtype=torch.float32)

    # Returns the number of samples in the dataset
    def __len__(self):
        return len(self.X)

    # Returns a single sample (features and labels) at the given index
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

# Model Definition
class JuniperMoodNet(nn.Module):
    def __init__(self, input_dim, output_dim):
        """
        Defines a simple feedforward neural network for multi-label mood classification.
        """
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 32),
            nn.ReLU(),
            nn.Linear(32, output_dim),
            nn.Sigmoid(),    # for multi-label probabilities
        )

    # Forward pass through the network
    def forward(self, X):
        return self.net(X)

# Helpers
def info(msg): print (f"🟢  {msg}")
def warn(msg): print (f"⚠️  {msg}")
def error(msg): print (f"❌  {msg}")

# Training Pipeline
def train_mood_model():
    """
    Main function to train the Juniper2.0 mood classifier model.
    This function performs the following steps:
    1. Validates the dataset using an external validation function.
    2. Loads and merges the metadata and labels into a single DataFrame.
    3. Preprocesses the data, including filtering and encoding labels.
    4. Initializes the PyTorch dataset and dataloader.
    5. Defines the model architecture, loss function, and optimizer.
    6. Runs the training loop for a specified number of epochs,
        printing loss information.
    7. Saves the trained model weights to disk.
    """
    print ("\n🎵  Training Juniper2.0 PyTorch Mood Classifier\n" + "=" * 55)

    # 1. Validate dataset
    # This will print warnings/errors if there are issues with the dataset,
    #  but will not stop execution (we want to train on whatever data is available).
    try:
        validate_dataset()
    except SystemExit:
        pass

    # 2. Merge metadata + labels
    # This will load the CSV and JSONL files, merge them on the 'file' column,
    #  and return a DataFrame. If either file is empty,
    #  it will return an empty DataFrame and print a warning.
    df = load_and_merge_datasets()
    if df.empty:
        warn("Dataset is empty - nothing to train.")
        return

    if TARGET_COLUMN not in df.columns:
        warn("Missing 'moods' column - cannot train.")
        return

    # 3. Preprocess
    # Filter out reference-only tracks and ensure target column is a list of tags
    df = df[df["reference_only"].astype(str).str.lower() != "true"]
    df[TARGET_COLUMN] = df[TARGET_COLUMN].apply(lambda X: X if isinstance(X, list) else [])

    # Encode multi-label targets using MultiLabelBinarizer
    mlb = MultiLabelBinarizer(sparse_output=False)
    target_matrix = mlb.fit_transform(df[TARGET_COLUMN])
    df[TARGET_COLUMN] = np.asarray(target_matrix).tolist()

    dataset = MoodDataset(df, mlb)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    # 4. Initialize model
    # The input dimension is the number of feature columns
    #  (e.g. bpm, energy, valence, danceability),
    #  and the output dimension is the number of unique mood tags (or 1 if no tags).
    input_dim = len(FEATURE_COLUMNS)
    output_dim = len(mlb.classes_) if len(mlb.classes_) > 0 else 1
    model = JuniperMoodNet(input_dim, output_dim)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

    # 5. Train loop
    # This loop iterates over the specified number of epochs, and for each epoch,
    #  it iterates over the batches of data from the dataloader, performing forward
    #  and backward passes, and updating the model weights. It also accumulates
    #  the loss for each batch and prints the average loss at the end of each epoch.
    info(f"Training on {len(dataset)} samples for {EPOCHS} epochs...")
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        for X_batch, y_batch in dataloader:
            optimizer.zero_grad()
            outputs = model(X_batch)
            loss = criterion(outputs, y_batch)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg_loss = total_loss / len(dataloader)
        print (f"Epoch [{epoch+1}/{EPOCHS}]  Loss: {avg_loss:.4f}")

    # 6. Save model
    # After training is complete, the model's state dictionary (which contains the learned weights)
    #  is saved to the specified MODEL_PATH.
    #  This allows us to load the trained model later for inference.
    torch.save(model.state_dict(), MODEL_PATH)
    info(f"✅  Model saved to {MODEL_PATH}")

    print ("\nTraining complete! Juniper2.0 now has a neural mood sense")


if __name__ == "__main__":
    train_mood_model()
