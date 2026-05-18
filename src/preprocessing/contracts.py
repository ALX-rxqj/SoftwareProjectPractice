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
    track_id: int
    bbox: BBox
    confidence: float
    face_roi: np.ndarray
    is_live: bool
    tracking_score: float
    embedding: Optional[np.ndarray] = None


@dataclass(frozen=True)
class MatchedFace:
    track_id: int
    face_id: Any
    student_name: str
    bbox: BBox
    face_roi: np.ndarray
    confidence: float
    face_matched: bool
    tracking_score: float
    embedding: Optional[np.ndarray] = None


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
    packet_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "frame": self.frame,
            "faces": self.faces,
            "timestamp": self.timestamp,
        }
        if self.packet_type:
            payload["type"] = self.packet_type
        return payload


@dataclass(frozen=True)
class FeatureFramePacket:
    timestamp: float
    faces: List[Dict[str, Any]]
    owner_face_id: Any
    frame: np.ndarray
    face_matched: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "faces": self.faces,
            "owner_face_id": self.owner_face_id,
            "frame": self.frame,
            "face_matched": self.face_matched,
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
    registration_requests: int = 0
    registration_successes: int = 0
    registration_failures: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)
