# audiomix
# AudioMIX
# audio/ai/modules/lightning_module.py

# This module defines a PyTorch Lightning module for training a simple feedforward neural network
#  (LightningEQNet) to predict audio labels based on extracted features. 
# The model consists of linear layers with ReLU activations and dropout for regularization. 
# The training and validation steps compute the binary
#  cross-entropy loss, and the optimizer used is Adam.
#  The module is designed to be easily integrated into a
#  PyTorch Lightning training loop for efficient
#  training and validation.

import torch
import torch.nn as nn
from lightning import LightningModule as pl.LightningModule

# Example usage:
# model = LightningEQNet(input_dim=100, num_classes=10)
# trainer = pl.Trainer(max_epochs=10)
# trainer.fit(model, train_dataloader, val_dataloader)
class LightningEQNet(pl.LightningModule):
    def __init__(self, input_dim, num_classes, lr=1e-3):
        """
        A simple feedforward neural network for audio label prediction.
        Args:
            input_dim: The number of input features.
            num_classes: The number of output classes (labels).
            lr: Learning rate for the optimizer.
        """
        super().__init__()
        self.save_hyperparameters()
        self.model = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, num_classes),
            nn.Sigmoid()
        )
        self.loss_fn = nn.BCELoss()

    # Forward pass through the model.
    # Takes input features and returns predicted
    #  probabilities for each class.
    def forward(self, x):
        return self.model(x)

    # Training step for a batch of data.
    # Computes the training loss and logs it.
    def training_step(self, batch, batch_idx):
        x, y = batch
        y_hat = self(x)
        loss = self.loss_fn(y_hat, y)
        self.log("train_loss", loss)
        return loss

    # Validation step for a batch of data.
    # Computes the validation loss and logs it.
    def validation_step(self, batch, batch_idx):
        x, y = batch
        y_hat = self(x)
        loss = self.loss_fn(y_hat, y)
        self.log("val_loss", loss)

    # Optimizer configuration for training
    # Uses Adam optimizer with the learning rate specified in hyperparameters.
    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=self.hparams['lr'])
