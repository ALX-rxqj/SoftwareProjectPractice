from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from .contracts import DetectionResult, FeatureFramePacket, FrameContext, PreprocessingStats, TrackedFace, UIFramePacket
from .face_tracker import SimpleFaceTracker
from .liveness import HeuristicLivenessDetector

try:
    from mtcnn import MTCNN
except ImportError:  # pragma: no cover
    MTCNN = None


Logger = Callable[[str], None]


@dataclass(frozen=True)
class PipelineConfig:
    frame_size: Tuple[int, int] = (1280, 720)
    roi_size: Tuple[int, int] = (224, 224)
    min_face_size: int = 40
    max_failure_count: int = 10
    owner_smoothing: float = 0.2


class FaceDetector:
    def __init__(self, min_face_size: int):
        self.min_face_size = min_face_size
        self._mtcnn = MTCNN() if MTCNN is not None else None
        self._cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def detect(self, frame: np.ndarray, roi_size: Tuple[int, int]) -> List[DetectionResult]:
        if self._mtcnn is not None:
            detections = self._detect_with_mtcnn(frame, roi_size)
            if detections:
                return detections
        return self._detect_with_cascade(frame, roi_size)

    def _detect_with_mtcnn(self, frame: np.ndarray, roi_size: Tuple[int, int]) -> List[DetectionResult]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._mtcnn.detect_faces(rgb)
        detections: List[DetectionResult] = []
        for item in results:
            x, y, w, h = item.get("box", [0, 0, 0, 0])
            if min(w, h) < self.min_face_size:
                continue
            bbox = self._clip_bbox((x, y, w, h), frame.shape)
            face_roi = self._extract_roi(frame, bbox, roi_size)
            detections.append(
                DetectionResult(
                    bbox=bbox,
                    confidence=float(item.get("confidence", 0.0)),
                    face_roi=face_roi,
                )
            )
        return detections

    def _detect_with_cascade(self, frame: np.ndarray, roi_size: Tuple[int, int]) -> List[DetectionResult]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(self.min_face_size, self.min_face_size))
        detections: List[DetectionResult] = []
        for x, y, w, h in faces:
            bbox = self._clip_bbox((int(x), int(y), int(w), int(h)), frame.shape)
            face_roi = self._extract_roi(frame, bbox, roi_size)
            detections.append(DetectionResult(bbox=bbox, confidence=0.6, face_roi=face_roi))
        return detections

    @staticmethod
    def _clip_bbox(bbox: Tuple[int, int, int, int], shape: Tuple[int, ...]) -> Tuple[int, int, int, int]:
        x, y, w, h = bbox
        max_h, max_w = shape[:2]
        x = max(0, x)
        y = max(0, y)
        w = max(0, min(w, max_w - x))
        h = max(0, min(h, max_h - y))
        return x, y, w, h

    @staticmethod
    def _extract_roi(frame: np.ndarray, bbox: Tuple[int, int, int, int], roi_size: Tuple[int, int]) -> np.ndarray:
        x, y, w, h = bbox
        roi = frame[y:y + h, x:x + w]
        if roi.size == 0:
            return np.empty((0, 0, 3), dtype=frame.dtype)
        return cv2.resize(roi, roi_size)


class PreprocessingPipeline:
    def __init__(self, config: PipelineConfig | None = None, logger: Logger | None = None):
        self.config = config or PipelineConfig()
        self.logger = logger or (lambda message: None)
        self.stats = PreprocessingStats()
        self._detector = FaceDetector(self.config.min_face_size)
        self._tracker = SimpleFaceTracker()
        self._liveness = HeuristicLivenessDetector()
        self._owner_face_id = -1

    def reset(self) -> None:
        self._tracker.reset()
        self._owner_face_id = -1

    def process(self, context: FrameContext) -> Optional[Dict[str, Any]]:
        self.stats.frames_read += 1
        frame = self._normalize_frame(context.frame)
        if frame is None:
            self.stats.invalid_frames += 1
            self._record_failure("Invalid frame encountered")
            return None

        try:
            detections = self._detector.detect(frame, self.config.roi_size)
            tracked_faces = self._tracker.update(detections)
            tracked_faces = self._apply_liveness(tracked_faces)
            owner_face_id = self._select_owner_face_id(tracked_faces, frame.shape)

            ui_faces = [{"face_id": face.face_id, "bbox": list(face.bbox)} for face in tracked_faces]
            feature_faces = [
                {"face_id": face.face_id, "face_roi": face.face_roi}
                for face in tracked_faces
                if face.is_live
            ]

            self.stats.frames_processed += 1
            self.stats.consecutive_failures = 0
            return {
                "ui": UIFramePacket(frame=frame, faces=ui_faces, timestamp=context.timestamp),
                "feature": FeatureFramePacket(
                    timestamp=context.timestamp,
                    faces=feature_faces,
                    owner_face_id=owner_face_id,
                    frame=frame,
                ),
            }
        except Exception as exc:
            self._record_failure(str(exc))
            if self.stats.consecutive_failures >= self.config.max_failure_count:
                self.recover()
            return None

    def recover(self) -> None:
        self.stats.recovery_count += 1
        self.stats.consecutive_failures = 0
        self.reset()
        self.logger("Preprocessing pipeline recovered after consecutive failures")

    def _normalize_frame(self, frame: np.ndarray) -> Optional[np.ndarray]:
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return None
        normalized = cv2.resize(frame, self.config.frame_size)
        if normalized.ndim == 2:
            normalized = cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)
        return normalized

    def _apply_liveness(self, tracked_faces: Sequence[TrackedFace]) -> List[TrackedFace]:
        updated_faces: List[TrackedFace] = []
        for face in tracked_faces:
            result = self._liveness.evaluate(face.face_roi)
            updated_faces.append(
                TrackedFace(
                    face_id=face.face_id,
                    bbox=face.bbox,
                    confidence=face.confidence,
                    face_roi=face.face_roi,
                    is_live=result.is_live,
                    tracking_score=min(1.0, (face.tracking_score + result.score) / 2.0),
                )
            )
        return updated_faces

    def _select_owner_face_id(self, faces: Sequence[TrackedFace], shape: Tuple[int, ...]) -> int:
        live_faces = [face for face in faces if face.is_live]
        if not live_faces:
            self._owner_face_id = -1
            return -1

        frame_h, frame_w = shape[:2]
        frame_center = np.array([frame_w / 2.0, frame_h / 2.0])
        best_face = None
        best_score = None

        for face in live_faces:
            x, y, w, h = face.bbox
            area_score = (w * h) / float(frame_w * frame_h)
            face_center = np.array([x + w / 2.0, y + h / 2.0])
            distance = np.linalg.norm(face_center - frame_center)
            center_score = 1.0 - min(distance / max(frame_w, frame_h), 1.0)
            continuity_bonus = 0.2 if face.face_id == self._owner_face_id else 0.0
            score = area_score * 0.55 + center_score * 0.25 + face.tracking_score * 0.20 + continuity_bonus
            if best_face is None or score > best_score:
                best_face = face
                best_score = score

        self._owner_face_id = best_face.face_id if best_face is not None else -1
        return self._owner_face_id

    def _record_failure(self, message: str) -> None:
        self.stats.detection_failures += 1
        self.stats.consecutive_failures += 1
        self.stats.last_error = message
        self.logger(message)
