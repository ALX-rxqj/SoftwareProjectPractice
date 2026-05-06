from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LivenessResult:
    is_live: bool
    score: float


class HeuristicLivenessDetector:
    def __init__(self, variance_threshold: float = 35.0, min_size: int = 48):
        self.variance_threshold = variance_threshold
        self.min_size = min_size

    def evaluate(self, face_roi: np.ndarray) -> LivenessResult:
        if face_roi is None or face_roi.size == 0:
            return LivenessResult(is_live=False, score=0.0)

        height, width = face_roi.shape[:2]
        if min(height, width) < self.min_size:
            return LivenessResult(is_live=False, score=0.1)

        gray = self._to_gray(face_roi)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness_std = float(gray.std())
        score = min(1.0, (laplacian_var / max(self.variance_threshold, 1.0)) * 0.7 + (brightness_std / 64.0) * 0.3)
        return LivenessResult(is_live=laplacian_var >= self.variance_threshold, score=score)

    @staticmethod
    def _to_gray(face_roi: np.ndarray) -> np.ndarray:
        if face_roi.ndim == 2:
            return face_roi
        return cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)


try:
    import cv2
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("opencv-python is required for liveness detection") from exc
