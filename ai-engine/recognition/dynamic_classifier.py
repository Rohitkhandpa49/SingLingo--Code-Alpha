from __future__ import annotations

import torch
from torch import nn


class DynamicLandmarkClassifier(nn.Module):
    """LSTM baseline over two hands' normalized pose and camera-space wrist motion."""

    def __init__(
        self,
        class_count: int,
        *,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        if class_count < 2:
            raise ValueError("class_count must be at least two")
        if hidden_size < 1 or num_layers < 1:
            raise ValueError("hidden_size and num_layers must be positive")
        if not 0 <= dropout < 1:
            raise ValueError("dropout must be in [0, 1)")
        self.recurrent = nn.LSTM(
            input_size=2 * 22 * 3,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(hidden_size, class_count)

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        batch, frames, hands, points, coordinates = sequence.shape
        flattened = sequence.reshape(batch, frames, hands * points * coordinates)
        recurrent_output, _ = self.recurrent(flattened)
        final_state = recurrent_output[:, frames - 1]
        return self.classifier(self.dropout(final_state))
