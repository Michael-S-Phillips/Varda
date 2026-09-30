"""PyTorch patch classifiers (the optional "ml" extra): a small CNN and a ViT.

Both take patches shaped (n, bands, size, size). Importing this module
requires torch; ``classification`` guards the import.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import torch
from torch import nn


def device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


class PatchCnn(nn.Module):
    """Conv layers over the patch with bands as channels, then global pooling."""

    def __init__(
        self, bands: int, classes: int, channels: int = 32, convLayers: int = 2
    ):
        super().__init__()
        layers: list[nn.Module] = []
        inChannels = bands
        for _ in range(convLayers):
            layers += [
                nn.Conv2d(inChannels, channels, kernel_size=3, padding=1),
                nn.BatchNorm2d(channels),
                nn.ReLU(),
            ]
            inChannels = channels
        self.features = nn.Sequential(*layers)
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(channels, classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.features(x))


class PatchViT(nn.Module):
    """Transformer over the patch's pixel spectra as tokens, plus a CLS token."""

    def __init__(
        self,
        bands: int,
        classes: int,
        patchSize: int,
        embedDim: int = 64,
        heads: int = 4,
        layers: int = 2,
    ):
        super().__init__()
        tokens = patchSize * patchSize
        self.embed = nn.Linear(bands, embedDim)
        self.cls = nn.Parameter(torch.zeros(1, 1, embedDim))
        self.position = nn.Parameter(torch.zeros(1, tokens + 1, embedDim))
        nn.init.normal_(self.position, std=0.02)
        encoderLayer = nn.TransformerEncoderLayer(
            embedDim,
            heads,
            dim_feedforward=2 * embedDim,
            dropout=0.0,
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(
            encoderLayer, layers, enable_nested_tensor=False
        )
        self.norm = nn.LayerNorm(embedDim)
        self.head = nn.Linear(embedDim, classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        tokens = self.embed(x.flatten(2).transpose(1, 2))  # (n, size², bands) -> embed
        cls = self.cls.expand(tokens.shape[0], -1, -1)
        encoded = self.encoder(torch.cat([cls, tokens], dim=1) + self.position)
        return self.head(self.norm(encoded[:, 0]))


def trainClassifier(
    model: nn.Module,
    patches: np.ndarray,
    labels: np.ndarray,
    *,
    epochs: int,
    learningRate: float,
    batchSize: int,
    onEpoch: Callable[[int, float], None] | None = None,
    seed: int = 0,
) -> list[float]:
    """Train with Adam + cross-entropy on shuffled mini-batches; returns the
    per-epoch mean loss. ``patches`` are (n, size, size, bands), already
    standardised."""
    torch.manual_seed(seed)
    dev = device()
    model.to(dev).train()
    X = _toTensor(patches).to(dev)
    y = torch.as_tensor(np.asarray(labels), dtype=torch.long, device=dev)
    optimiser = torch.optim.Adam(model.parameters(), lr=learningRate)
    lossFunction = nn.CrossEntropyLoss()
    generator = torch.Generator().manual_seed(seed)

    losses = []
    for epoch in range(1, epochs + 1):
        order = torch.randperm(X.shape[0], generator=generator).to(dev)
        total = 0.0
        for start in range(0, X.shape[0], batchSize):
            batch = order[start : start + batchSize]
            optimiser.zero_grad()
            loss = lossFunction(model(X[batch]), y[batch])
            loss.backward()
            optimiser.step()
            total += float(loss.item()) * batch.numel()
        losses.append(total / X.shape[0])
        if onEpoch is not None:
            onEpoch(epoch, losses[-1])
    return losses


def predictProbabilities(
    model: nn.Module, patches: np.ndarray, batchSize: int = 1024
) -> np.ndarray:
    """(n, classes) softmax probabilities for standardised patches."""
    dev = device()
    model.to(dev).eval()
    X = _toTensor(patches)
    outputs = []
    with torch.no_grad():
        for start in range(0, X.shape[0], batchSize):
            logits = model(X[start : start + batchSize].to(dev))
            outputs.append(torch.softmax(logits, dim=1).cpu().numpy())
    return np.vstack(outputs)


def _toTensor(patches: np.ndarray) -> torch.Tensor:
    # (n, size, size, bands) -> (n, bands, size, size)
    return (
        torch.as_tensor(np.asarray(patches, dtype=np.float32))
        .permute(0, 3, 1, 2)
        .contiguous()
    )
