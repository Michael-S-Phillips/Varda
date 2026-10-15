"""Matching two images for the mosaic: kornia's LoFTR (a learned matcher,
robust where hand-crafted features struggle) or OpenCV's SIFT.

Images arrive as float32 arrays with NaN where there's no data. Points go
back in pixel coordinates with (0, 0) at the first pixel's corner (both
libraries put pixel centers on whole numbers, so 0.5 is added).
"""

from __future__ import annotations

from collections.abc import Callable

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from kornia.feature import LoFTR

from varda_torch_worker.models import device

LOFTR_SIZE = 1024  # LoFTR's memory grows fast with size: it sees at most this
SIFT_FEATURES = 4000
SIFT_RATIO = 0.75  # Lowe's ratio test


def normalized(image: np.ndarray) -> np.ndarray:
    """0-1 by the 1st and 99th percentiles; no-data becomes 0."""
    finite = image[np.isfinite(image)]
    if not finite.size:
        return np.zeros(image.shape, np.float32)
    low, high = np.percentile(finite, (1, 99))
    scaled = (np.nan_to_num(image, nan=low) - low) / ((high - low) or 1.0)
    return np.clip(scaled, 0.0, 1.0).astype(np.float32)


def sift(
    reference: np.ndarray, moving: np.ndarray, progress: Callable[[float, str], None]
) -> np.ndarray:
    progress(0.1, "finding SIFT features")
    detector = cv2.SIFT_create(nfeatures=SIFT_FEATURES)
    found = []
    for image in (reference, moving):
        valid = np.isfinite(image).astype(np.uint8) * 255
        keypoints, descriptors = detector.detectAndCompute(
            (normalized(image) * 255).astype(np.uint8), valid
        )
        found.append((keypoints, descriptors))
    (k1, d1), (k2, d2) = found
    if d1 is None or d2 is None or len(k1) < 2 or len(k2) < 2:
        return np.zeros((0, 5), np.float32)
    progress(0.6, "matching SIFT features")
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(d1, d2, k=2)
    rows = []
    for pair in pairs:
        if len(pair) == 2 and pair[0].distance < SIFT_RATIO * pair[1].distance:
            best, second = pair
            (x1, y1), (x2, y2) = k1[best.queryIdx].pt, k2[best.trainIdx].pt
            rows.append(
                (
                    x1 + 0.5,
                    y1 + 0.5,
                    x2 + 0.5,
                    y2 + 0.5,
                    1 - best.distance / second.distance,
                )
            )
    return np.array(rows, np.float32).reshape(-1, 5)


def loftr(
    reference: np.ndarray, moving: np.ndarray, progress: Callable[[float, str], None]
) -> np.ndarray:
    progress(0.05, "loading LoFTR (downloaded once)")
    where = device()
    matcher = LoFTR(pretrained="outdoor").eval().to(where)
    scale = max(1.0, max(*reference.shape, *moving.shape) / LOFTR_SIZE)
    tensors = []
    for image in (reference, moving):
        t = torch.from_numpy(normalized(image))[None, None]
        if scale > 1:
            size = (round(image.shape[0] / scale), round(image.shape[1] / scale))
            t = F.interpolate(t, size=size, mode="area")
        tensors.append(t.to(where))
    progress(0.3, "matching with LoFTR")
    with torch.inference_mode():
        out = matcher({"image0": tensors[0], "image1": tensors[1]})
    first = out["keypoints0"].cpu().numpy()
    second = out["keypoints1"].cpu().numpy()
    confidence = out["confidence"].cpu().numpy()
    # back to full-size pixels: the reduced pixel centers scale with the image
    first, second = (first + 0.5) * scale, (second + 0.5) * scale
    return np.column_stack([first, second, confidence]).astype(np.float32)


METHODS = {"sift": sift, "loftr": loftr}
