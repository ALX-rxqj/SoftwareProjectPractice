from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np
import onnxruntime as ort


class FaceEmbeddingExtractor:
    """512d face embedding extractor.

    Prefer the provided ONNX recognition model. Fall back to the previous
    deterministic projection when the model is unavailable.
    """

    def __init__(
        self,
        model_path: str | Path = "w600k_mbf.onnx",
        fallback_size: Tuple[int, int] = (16, 32),
    ):
        self.fallback_size = fallback_size
        self.model_path = Path(model_path)
        self.session: Optional[ort.InferenceSession] = None
        self.input_name: Optional[str] = None
        self._init_session()

    def _init_session(self) -> None:
        if not self.model_path.exists():
            return
        self.session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def extract(self, face_roi: np.ndarray) -> Optional[np.ndarray]:
        if face_roi is None or face_roi.size == 0:
            return None

        if self.session is not None and self.input_name is not None:
            return self._extract_with_onnx(face_roi)
        return self._extract_with_fallback(face_roi)

    def _extract_with_onnx(self, face_roi: np.ndarray) -> Optional[np.ndarray]:
        aligned = self._prepare_onnx_input(face_roi)
        output = self.session.run(None, {self.input_name: aligned})[0]
        vector = np.asarray(output[0], dtype=np.float32)
        norm = float(np.linalg.norm(vector))
        if norm < 1e-6:
            return None
        return (vector / norm).astype(np.float32)

    def _prepare_onnx_input(self, face_roi: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB) if face_roi.ndim == 3 else cv2.cvtColor(face_roi, cv2.COLOR_GRAY2RGB)
        resized = cv2.resize(rgb, (112, 112))
        normalized = (resized.astype(np.float32) - 127.5) / 128.0
        chw = np.transpose(normalized, (2, 0, 1))
        return np.expand_dims(chw, axis=0).astype(np.float32)

    def _extract_with_fallback(self, face_roi: np.ndarray) -> Optional[np.ndarray]:
        gray = face_roi if face_roi.ndim == 2 else cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, self.fallback_size)
        vector = resized.astype(np.float32).reshape(-1) / 255.0
        vector -= float(vector.mean())
        norm = float(np.linalg.norm(vector))
        if norm < 1e-6:
            return None
        return (vector / norm).astype(np.float32)


def cosine_similarity(first: np.ndarray, second: np.ndarray) -> float:
    if first is None or second is None:
        return 0.0
    first_norm = float(np.linalg.norm(first))
    second_norm = float(np.linalg.norm(second))
    if first_norm < 1e-6 or second_norm < 1e-6:
        return 0.0
    return float(np.dot(first, second) / (first_norm * second_norm))


def best_similarity(query: np.ndarray, candidates: Sequence[np.ndarray]) -> float:
    if query is None or not candidates:
        return 0.0
    return max(cosine_similarity(query, candidate) for candidate in candidates)


def summarize_pose_types(count: int) -> List[str]:
    base = ["frontal", "left", "right", "down"]
    if count <= len(base):
        return base[:count]
    return base + ["auto"] * (count - len(base))
