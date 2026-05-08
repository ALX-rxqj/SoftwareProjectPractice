from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


BBox = Tuple[int, int, int, int]


@dataclass(frozen=True)
class DetectionResult:
    bbox: BBox
    confidence: float
    face_roi: np.ndarray


@dataclass(frozen=True)
class TrackedFace:
    face_id: int
    bbox: BBox
    confidence: float
    face_roi: np.ndarray
    is_live: bool
    tracking_score: float


@dataclass(frozen=True)
class FrameContext:
    frame: np.ndarray
    timestamp: float
    source_name: str
    frame_index: int


@dataclass(frozen=True)
class UIFramePacket:
    frame: np.ndarray
    faces: List[Dict[str, Any]]
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame": self.frame,
            "faces": self.faces,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class FeatureFramePacket:
    timestamp: float
    faces: List[Dict[str, Any]]
    owner_face_id: int
    frame: np.ndarray

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "faces": self.faces,
            "owner_face_id": self.owner_face_id,
            "frame": self.frame,
        }


@dataclass
class PreprocessingStats:
    frames_read: int = 0
    frames_processed: int = 0
    invalid_frames: int = 0
    detection_failures: int = 0
    recovery_count: int = 0
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    source_opened: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)
