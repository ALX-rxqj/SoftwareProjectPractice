from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from .contracts import DetectionResult, FrameContext, PreprocessingStats, TrackedFace
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
    enable_illumination_normalization: bool = True
    clahe_clip_limit: float = 2.0
    clahe_tile_grid_size: Tuple[int, int] = (8, 8)
    target_brightness: float = 128.0
    min_gamma: float = 0.75
    max_gamma: float = 1.35


class IlluminationNormalizer:
    def __init__(self, config: PipelineConfig):
        self._enabled = config.enable_illumination_normalization
        self._target_brightness = float(config.target_brightness)
        self._min_gamma = float(config.min_gamma)
        self._max_gamma = float(config.max_gamma)
        self._clahe = cv2.createCLAHE(
            clipLimit=float(config.clahe_clip_limit),
            tileGridSize=tuple(config.clahe_tile_grid_size),
        )

    def apply(self, frame: np.ndarray) -> np.ndarray:
        if not self._enabled or frame is None or frame.size == 0:
            return frame

        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        l_channel = self._clahe.apply(l_channel)
        balanced = cv2.cvtColor(
            cv2.merge((l_channel, a_channel, b_channel)),
            cv2.COLOR_LAB2BGR,
        )
        return self._apply_gamma_balance(balanced)

    def _apply_gamma_balance(self, frame: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h_channel, s_channel, v_channel = cv2.split(hsv)
        brightness = float(v_channel.mean())
        if brightness <= 1.0:
            return frame

        gain = self._target_brightness / max(brightness, 1.0)
        gain = float(np.clip(gain, self._min_gamma, self._max_gamma))
        corrected_v = np.clip(v_channel.astype(np.float32) * gain, 0, 255).astype(np.uint8)
        return cv2.cvtColor(
            cv2.merge((h_channel, s_channel, corrected_v)),
            cv2.COLOR_HSV2BGR,
        )


class FaceDetector:
    def __init__(self, min_face_size: int, roi_normalizer: Optional[IlluminationNormalizer] = None,
                 yolo_model_path: str | Path = "weights/yolov8-face.pt",
                 yolo_model: Any = None, mtcnn: Any = None):
        self.min_face_size = min_face_size
        self._roi_normalizer = roi_normalizer
        if yolo_model is not None:
            self._yolo = yolo_model
        else:
            self._yolo = None
            self._init_yolo(yolo_model_path)
        self._mtcnn = mtcnn if mtcnn is not None else (MTCNN() if MTCNN is not None else None)
        self._cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def detect(self, frame: np.ndarray, roi_size: Tuple[int, int]) -> List[DetectionResult]:
        if self._yolo is not None:
            detections = self._detect_with_yolo(frame, roi_size)
            if detections:
                return detections
        if self._mtcnn is not None:
            detections = self._detect_with_mtcnn(frame, roi_size)
            if detections:
                return detections
        return self._detect_with_cascade(frame, roi_size)

    def _init_yolo(self, yolo_model_path: str | Path) -> None:
        model_path = Path(yolo_model_path)
        if not model_path.exists():
            return
        try:
            os.environ.setdefault(
                "YOLO_CONFIG_DIR",
                str(Path(__file__).resolve().parents[2] / ".ultralytics"),
            )
            from ultralytics import YOLO

            self._yolo = YOLO(str(model_path))
        except Exception:
            self._yolo = None

    def _detect_with_yolo(self, frame: np.ndarray, roi_size: Tuple[int, int]) -> List[DetectionResult]:
        results = self._yolo.predict(source=frame, verbose=False, device="cpu")
        detections: List[DetectionResult] = []
        if not results:
            return detections
        boxes = getattr(results[0], "boxes", None)
        if boxes is None:
            return detections
        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else boxes.xyxy
        confs = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else boxes.conf
        for box, confidence in zip(xyxy, confs):
            x1, y1, x2, y2 = [int(v) for v in box[:4]]
            w = max(0, x2 - x1)
            h = max(0, y2 - y1)
            if min(w, h) < self.min_face_size:
                continue
            bbox = self._clip_bbox((x1, y1, w, h), frame.shape)
            face_roi = self._extract_roi(frame, bbox, roi_size, self._roi_normalizer)
            detections.append(
                DetectionResult(
                    bbox=bbox,
                    confidence=float(confidence),
                    face_roi=face_roi,
                )
            )
        return detections

    def _detect_with_mtcnn(self, frame: np.ndarray, roi_size: Tuple[int, int]) -> List[DetectionResult]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._mtcnn.detect_faces(rgb)
        detections: List[DetectionResult] = []
        for item in results:
            x, y, w, h = item.get("box", [0, 0, 0, 0])
            if min(w, h) < self.min_face_size:
                continue
            bbox = self._clip_bbox((x, y, w, h), frame.shape)
            face_roi = self._extract_roi(frame, bbox, roi_size, self._roi_normalizer)
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
            face_roi = self._extract_roi(frame, bbox, roi_size, self._roi_normalizer)
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
    def _extract_roi(
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        roi_size: Tuple[int, int],
        roi_normalizer: Optional[IlluminationNormalizer] = None,
    ) -> np.ndarray:
        x, y, w, h = bbox
        roi = frame[y:y + h, x:x + w]
        if roi.size == 0:
            return np.empty((0, 0, 3), dtype=frame.dtype)
        roi = cv2.resize(roi, roi_size)
        if roi_normalizer is not None:
            roi = roi_normalizer.apply(roi)
        return roi


class PreprocessingPipeline:
    def __init__(self, config: PipelineConfig | None = None, logger: Logger | None = None):
        self.config = config or PipelineConfig()
        self.logger = logger or (lambda message: None)
        self.stats = PreprocessingStats()
        self._illumination_normalizer = IlluminationNormalizer(self.config)
        self._detector = FaceDetector(
            self.config.min_face_size,
            roi_normalizer=self._illumination_normalizer,
        )
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

            self.stats.frames_processed += 1
            self.stats.consecutive_failures = 0
            return {
                "frame": frame,
                "timestamp": context.timestamp,
                "tracked_faces": tracked_faces,
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
        normalized = self._illumination_normalizer.apply(normalized)
        return normalized

    def _apply_liveness(self, tracked_faces: Sequence[TrackedFace]) -> List[TrackedFace]:
        updated_faces: List[TrackedFace] = []
        for face in tracked_faces:
            result = self._liveness.evaluate(face.face_roi)
            updated_faces.append(
                TrackedFace(
                    track_id=face.track_id,
                    bbox=face.bbox,
                    confidence=face.confidence,
                    face_roi=face.face_roi,
                    is_live=result.is_live,
                    tracking_score=min(1.0, (face.tracking_score + result.score) / 2.0),
                    embedding=face.embedding,
                )
            )
        return updated_faces

    def _record_failure(self, message: str) -> None:
        self.stats.detection_failures += 1
        self.stats.consecutive_failures += 1
        self.stats.last_error = message
        self.logger(message)
