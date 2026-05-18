from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .contracts import BBox, DetectionResult, TrackedFace


@dataclass
class _TrackState:
    face_id: int
    bbox: BBox
    center: Tuple[float, float]
    misses: int = 0


class SimpleFaceTracker:
    def __init__(self, max_distance: float = 90.0, max_misses: int = 12):
        self.max_distance = max_distance
        self.max_misses = max_misses
        self._next_face_id = 1
        self._tracks: Dict[int, _TrackState] = {}

    def reset(self) -> None:
        self._tracks.clear()
        self._next_face_id = 1

    def update(self, detections: Sequence[DetectionResult]) -> List[TrackedFace]:
        if not detections:
            self._age_tracks()
            return []

        used_tracks = set()
        tracked_faces: List[TrackedFace] = []

        for detection in detections:
            bbox = detection.bbox
            center = self._bbox_center(bbox)
            track = self._match_track(center, used_tracks)
            if track is None:
                track = self._create_track(bbox, center)
            else:
                track.bbox = bbox
                track.center = center
                track.misses = 0

            used_tracks.add(track.face_id)
            tracking_score = max(0.0, 1.0 - self._distance(track.center, center) / max(self.max_distance, 1.0))
            tracked_faces.append(
                TrackedFace(
                    track_id=track.face_id,
                    bbox=bbox,
                    confidence=detection.confidence,
                    face_roi=detection.face_roi,
                    is_live=True,
                    tracking_score=tracking_score,
                )
            )

        self._age_tracks(exclude_ids=used_tracks)
        return tracked_faces

    def _match_track(self, center: Tuple[float, float], used_tracks: set[int]) -> _TrackState | None:
        candidate = None
        candidate_distance = None

        for track_id, track in self._tracks.items():
            if track_id in used_tracks:
                continue
            distance = self._distance(track.center, center)
            if distance > self.max_distance:
                continue
            if candidate is None or distance < candidate_distance:
                candidate = track
                candidate_distance = distance

        return candidate

    def _create_track(self, bbox: BBox, center: Tuple[float, float]) -> _TrackState:
        track = _TrackState(face_id=self._next_face_id, bbox=bbox, center=center)
        self._tracks[track.face_id] = track
        self._next_face_id += 1
        return track

    def _age_tracks(self, exclude_ids: set[int] | None = None) -> None:
        exclude_ids = exclude_ids or set()
        stale_ids = []
        for track_id, track in self._tracks.items():
            if track_id in exclude_ids:
                continue
            track.misses += 1
            if track.misses > self.max_misses:
                stale_ids.append(track_id)

        for track_id in stale_ids:
            self._tracks.pop(track_id, None)

    @staticmethod
    def _bbox_center(bbox: BBox) -> Tuple[float, float]:
        x, y, w, h = bbox
        return x + w / 2.0, y + h / 2.0

    @staticmethod
    def _distance(first: Tuple[float, float], second: Tuple[float, float]) -> float:
        return float(np.linalg.norm(np.array(first) - np.array(second)))
