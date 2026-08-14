import torch
import torch.nn as nn
from typing import Tuple

class Autoencoder(nn.Module):
    """
    3-layer symmetric bottleneck autoencoder for anomaly detection.
    Trained on benign-only data.
    Anomaly score is the MSE reconstruction error.
    """
    def __init__(self, input_dim: int):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32), 
            nn.ReLU(),
            nn.Linear(32, 16), 
            nn.ReLU(),
            nn.Linear(16, 8)
        )
        self.decoder = nn.Sequential(
            nn.Linear(8, 16), 
            nn.ReLU(),
            nn.Linear(16, 32), 
            nn.ReLU(),
            nn.Linear(32, input_dim)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded

    def compute_reconstruction_error(self, x: torch.Tensor) -> torch.Tensor:
        """
        Compute MSE reconstruction error for each sample.
        x shape: (batch_size, input_dim)
        returns shape: (batch_size,)
        """
        reconstructed = self.forward(x)
        mse = torch.mean((x - reconstructed) ** 2, dim=1)
        return mse
