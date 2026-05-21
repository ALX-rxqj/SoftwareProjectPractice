from __future__ import annotations

import inspect
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from .contracts import FeatureFramePacket, MatchedFace, TrackedFace, UIFramePacket
from .database_backend import PreprocessingDatabaseBackend
from .pipeline import FaceDetector, PipelineConfig, PreprocessingPipeline
from .recognition import FaceEmbeddingExtractor, best_similarity, summarize_pose_types
from .video_source import VideoSource


CommandCallback = Callable[[str, Dict[str, Any]], Optional[Dict[str, Any]]]
PacketCallback = Callable[[Dict[str, Any]], None]
LogCallback = Callable[[str], None]
VideoFrameCallback = Callable[[Any, List[Dict[str, Any]], float], None]
FrameReceivedCallback = Callable[[Dict[str, Any]], None]
CameraListCallback = Callable[[List[Dict[str, Any]]], None]
EmbeddingWriter = Callable[[str, str, List[Tuple[bytes, str]]], bool]


class PreprocessingService:
    def __init__(
        self,
        ui_callback: Optional[PacketCallback] = None,
        feature_callback: Optional[PacketCallback] = None,
        log_callback: Optional[LogCallback] = None,
        config: Optional[PipelineConfig] = None,
        video_frame_callback: Optional[VideoFrameCallback] = None,
        frame_received_callback: Optional[FrameReceivedCallback] = None,
        camera_list_callback: Optional[CameraListCallback] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ):
        self.ui_callback = ui_callback
        self.feature_callback = feature_callback
        self.log_callback = log_callback or (lambda message: None)
        self.video_frame_callback = video_frame_callback
        self.frame_received_callback = frame_received_callback
        self.camera_list_callback = camera_list_callback
        self._progress_callback = progress_callback or (lambda msg, pct: None)

        self.pipeline = PreprocessingPipeline(config=config, logger=self.log_callback)
        self._progress_callback("加载人脸检测模型...", 0.3)

        self.video_source = VideoSource()
        self._stop_event = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._active_source: Optional[Dict[str, Any]] = None
        self._monitored_faces: List[str] = []
        self._face_registry: Dict[str, Dict[str, Any]] = {}
        self._face_registry_lock = threading.Lock()
        self._face_embedding_writer: Optional[EmbeddingWriter] = None
        self._database_backend = PreprocessingDatabaseBackend()
        self._embedding_extractor = FaceEmbeddingExtractor()
        self._progress_callback("加载人脸识别模型...", 0.6)

        self._registration_detector: Optional[FaceDetector] = None
        self._match_threshold = 0.6
        self._last_owner_face_id: Any = -1
        self._playback_rate = 1.0
        self._file_playback_started_at: Optional[float] = None
        self._initialize_database_backend()
        self._progress_callback("初始化数据库...", 0.9)
        self._progress_callback("预处理模块就绪", 1.0)

    def handle_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if command == "toggle_capture":
            return self.on_control_capture(
                device_id=int(params.get("device_id", 0)),
                start=bool(params.get("start", False)),
                monitored_faces=params.get("monitored_faces") or [],
            )
        if command == "load_video":
            return self.on_load_video(file_path=params.get("file_path"))
        if command == "load_video_file":
            return self.on_load_video(file_path=params.get("file_path"))
        if command == "query_cameras":
            return self.on_query_cameras()
        if command == "refresh_camera_list":
            return self.on_query_cameras()
        if command == "register_face":
            return self.register_face(
                student_name=str(params.get("student_name", "")),
                frames=list(params.get("frames") or []),
                storage_type=str(params.get("storage_type", "temp")),
                face_id=str(params.get("face_id", "")),
            )
        if command == "query_face_registry":
            return self.query_face_registry()
        if command == "stop_capture":
            return self.stop()
        if command == "delete_face":
            return self.delete_face(str(params.get("face_id", "")))
        return {"success": False, "msg": f"Unsupported command: {command}"}

    def start_camera(self, device_id: int = 0) -> Dict[str, Any]:
        self.stop()
        self.video_source.open_camera(device_id)
        self._active_source = {"type": "camera", "device_id": device_id}
        self.pipeline.stats.source_opened = True
        self._start_worker()
        return {"success": True, "msg": f"Camera {device_id} started"}

    def stop_camera(self) -> Dict[str, Any]:
        return self.stop()

    def load_video(self, file_path: str | Path | None) -> Dict[str, Any]:
        if not file_path:
            return {"success": False, "msg": "Video file path is required"}
        self.stop()
        self.video_source.open_file(file_path)
        self._active_source = {"type": "file", "file_path": str(file_path)}
        self.pipeline.stats.source_opened = True
        self._start_worker()
        return {"success": True, "msg": f"Video file loaded: {file_path}"}

    def start_video_file(self, file_path: str | Path | None) -> Dict[str, Any]:
        return self.load_video(file_path)

    def stop(self) -> Dict[str, Any]:
        self._stop_event.set()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2.0)
        self._worker = None
        self._file_playback_started_at = None
        self.video_source.close()
        self._active_source = None
        self.pipeline.stats.source_opened = False
        return {"success": True, "msg": "Capture stopped"}

    def list_cameras(self, max_devices: int = 5) -> List[Dict[str, Any]]:
        cameras: List[Dict[str, Any]] = []
        for device_id in range(max_devices):
            capture = cv2.VideoCapture(device_id, cv2.CAP_DSHOW)
            if capture.isOpened():
                cameras.append({"device_id": device_id, "device_name": f"Camera {device_id}"})
            capture.release()
        return cameras

    def query_camera_list(self) -> List[Dict[str, Any]]:
        return self.list_cameras()

    def on_control_capture(
        self, device_id: int, start: bool, monitored_faces: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        self._monitored_faces = list(monitored_faces or [])
        return self.start_camera(device_id) if start else self.stop_camera()

    def on_load_video(self, file_path: str | Path | None) -> Dict[str, Any]:
        return self.load_video(file_path)

    def on_query_cameras(self) -> Dict[str, Any]:
        camera_list = self.query_camera_list()
        self.on_camera_list_received(camera_list)
        return {"success": True, "msg": "Camera list queried", "camera_list": camera_list}

    def on_camera_list_received(self, camera_list: List[Dict[str, Any]]) -> None:
        if self.camera_list_callback is not None:
            self.camera_list_callback(camera_list)

    def register_video_frame_callback(self, callback: VideoFrameCallback) -> None:
        self.video_frame_callback = callback

    def register_frame_received_callback(self, callback: FrameReceivedCallback) -> None:
        self.frame_received_callback = callback

    def register_camera_list_callback(self, callback: CameraListCallback) -> None:
        self.camera_list_callback = callback

    def set_face_embedding_writer(self, callback: EmbeddingWriter) -> None:
        self._face_embedding_writer = callback

    def load_faces_from_db(self, faces_data: List[Dict[str, Any]]) -> None:
        with self._face_registry_lock:
            for face in faces_data:
                self._face_registry[face["face_id"]] = {
                    "student_name": face["student_name"],
                    "embeddings": [
                        np.frombuffer(item["embedding"], dtype=np.float32)
                        for item in face.get("embeddings", [])
                    ],
                    "storage_type": face.get("storage_type", "local"),
                    "registered_at": face["registered_at"],
                }

    def query_face_registry(self) -> Dict[str, Any]:
        with self._face_registry_lock:
            faces = [
                {
                    "face_id": face_id,
                    "student_name": entry["student_name"],
                    "storage_type": entry["storage_type"],
                    "registered_at": entry["registered_at"],
                }
                for face_id, entry in self._face_registry.items()
            ]
        faces.sort(key=lambda item: item.get("registered_at", 0.0))
        return {"success": True, "faces": faces}

    def delete_face(self, face_id: str) -> Dict[str, Any]:
        with self._face_registry_lock:
            if face_id in self._face_registry:
                del self._face_registry[face_id]
                print(f"[PreprocessingService] 已从内存注册表删除人脸: {face_id}")
                return {"success": True, "deleted_face_id": face_id}
            return {"success": False, "deleted_face_id": face_id,
                    "msg": f"face_id 不在注册表中: {face_id}"}

    def register_face(
        self, student_name: str, frames: List[np.ndarray], storage_type: str, face_id: str
    ) -> Dict[str, Any]:
        if not student_name or not frames or not face_id:
            return {"success": False, "face_id": face_id, "msg": "invalid params"}
        self.pipeline.stats.registration_requests += 1
        worker = threading.Thread(
            target=self._register_face_task,
            args=(student_name, frames, storage_type, face_id),
            name=f"FaceRegistration-{face_id}",
            daemon=True,
        )
        worker.start()
        return {"success": True, "face_id": face_id, "msg": "processing"}

    def get_status(self) -> Dict[str, Any]:
        stats = self.pipeline.stats
        return {
            "active_source": self._active_source,
            "source_name": self.video_source.source_name,
            "worker_alive": bool(self._worker and self._worker.is_alive()),
            "frames_read": stats.frames_read,
            "frames_processed": stats.frames_processed,
            "invalid_frames": stats.invalid_frames,
            "detection_failures": stats.detection_failures,
            "recovery_count": stats.recovery_count,
            "last_error": stats.last_error,
            "registry_size": len(self._face_registry),
            "monitored_faces": list(self._monitored_faces),
        }

    def _start_worker(self) -> None:
        self._stop_event.clear()
        self.pipeline.reset()
        self._file_playback_started_at = None
        self._worker = threading.Thread(target=self._run_loop, name="PreprocessingWorker", daemon=True)
        self._worker.start()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self._prepare_file_read_timing()
            context = self.video_source.read()
            if context is None:
                time.sleep(0.02)
                if self._active_source and self._active_source.get("type") == "file":
                    if self.video_source.reached_end:
                        self._emit_file_playback_ended()
                    break
                continue

            frame_started_at = time.perf_counter()
            result = self.pipeline.process(context)
            if result is None:
                self._pace_file_playback(context, frame_started_at)
                continue

            matched_faces = self._match_faces(result["tracked_faces"])
            owner_face_id, owner_face_matched = self._select_owner_face(
                matched_faces, result["frame"].shape, has_registered_faces=bool(self._face_registry)
            )
            ui_packet = self._build_ui_packet(
                result["frame"],
                result["timestamp"],
                matched_faces,
                context=context,
            ).to_dict()
            feature_packet = self._build_feature_packet(
                result["frame"], result["timestamp"], matched_faces, owner_face_id, owner_face_matched
            ).to_dict()
            self._log_recognition_result(feature_packet)
            self._dispatch_ui_packet(ui_packet)
            self._dispatch_feature_packet(feature_packet)
            self._pace_file_playback(context, frame_started_at)

        self.video_source.close()

    def _dispatch_ui_packet(self, ui_packet: Dict[str, Any]) -> None:
        if self.ui_callback is not None:
            self.ui_callback(ui_packet)
        if self.video_frame_callback is not None:
            frame_progress = ui_packet.get("frame_progress")
            if self._callback_accepts_frame_progress(self.video_frame_callback):
                self.video_frame_callback(
                    ui_packet["frame"],
                    ui_packet["faces"],
                    ui_packet["timestamp"],
                    frame_progress,
                )
            else:
                self.video_frame_callback(
                    ui_packet["frame"],
                    ui_packet["faces"],
                    ui_packet["timestamp"],
                )

    def _dispatch_feature_packet(self, feature_packet: Dict[str, Any]) -> None:
        if self.feature_callback is not None:
            self.feature_callback(feature_packet)
        if self.frame_received_callback is not None:
            self.frame_received_callback(feature_packet)

    def _log_recognition_result(self, feature_packet: Dict[str, Any]) -> None:
        faces = feature_packet.get("faces", []) or []
        owner_face_id = feature_packet.get("owner_face_id", -1)
        owner_face_matched = feature_packet.get("face_matched", False)
        timestamp = feature_packet.get("timestamp", 0.0)

        if not faces:
            self.log_callback(
                f"[Preprocessing][PRI-02] ts={timestamp:.3f} "
                f"owner_face_id={owner_face_id} face_matched={owner_face_matched} faces=[]"
            )
            return

        owner_face = next(
            (face for face in faces if face.get("face_id") == owner_face_id),
            faces[0] if faces else None,
        )
        if owner_face is None:
            self.log_callback(
                f"[Preprocessing][PRI-02] ts={timestamp:.3f} "
                f"owner_face_id={owner_face_id} face_matched={owner_face_matched} "
                f"faces_count={len(faces)}"
            )
            return

        self.log_callback(
            f"[Preprocessing][PRI-02] ts={timestamp:.3f} "
            f"owner_face_id={owner_face_id} "
            f"face_matched={owner_face_matched} "
            f"student_name={owner_face.get('student_name', 'unknown')} "
            f"confidence={float(owner_face.get('confidence', 0.0)):.3f} "
            f"faces_count={len(faces)}"
        )

    def _register_face_task(
        self, student_name: str, frames: List[np.ndarray], storage_type: str, face_id: str
    ) -> None:
        try:
            embeddings = self._extract_embeddings_from_frames(frames)
            if not embeddings:
                self.pipeline.stats.registration_failures += 1
                self._emit_face_registration_result(
                    success=False,
                    face_id=face_id,
                    student_name=student_name,
                    msg="未提取到有效人脸特征",
                    embeddings_count=0,
                )
                return

            with self._face_registry_lock:
                self._face_registry[face_id] = {
                    "student_name": student_name,
                    "embeddings": [embedding for embedding, _ in embeddings],
                    "storage_type": storage_type,
                    "registered_at": time.time(),
                }

            if storage_type == "local":
                payload = [
                    (embedding.astype(np.float32).tobytes(), pose_type)
                    for embedding, pose_type in embeddings
                ]
                ok = False
                if self._face_embedding_writer is not None:
                    ok = self._face_embedding_writer(face_id, student_name, payload)
                if not ok:
                    ok = self._database_backend.insert_face_embeddings_batch(
                        face_id=face_id,
                        student_name=student_name,
                        embeddings=payload,
                        registered_at=self._face_registry[face_id]["registered_at"],
                    )
                if not ok:
                    self.pipeline.stats.registration_failures += 1
                    self._emit_face_registration_result(
                        success=False,
                        face_id=face_id,
                        student_name=student_name,
                        msg="注册写入数据库失败",
                        embeddings_count=len(embeddings),
                    )
                    return

            self.pipeline.stats.registration_successes += 1
            self._emit_face_registration_result(
                success=True,
                face_id=face_id,
                student_name=student_name,
                msg="注册成功",
                embeddings_count=len(embeddings),
            )
        except Exception as exc:
            self.pipeline.stats.registration_failures += 1
            self.log_callback(f"register_face failed: {exc}")
            self._emit_face_registration_result(
                success=False,
                face_id=face_id,
                student_name=student_name,
                msg=str(exc),
                embeddings_count=0,
            )

    def _get_registration_detector(self) -> FaceDetector:
        if self._registration_detector is None:
            yolo_model = self.pipeline._detector._yolo
            self._registration_detector = FaceDetector(
                self.pipeline.config.min_face_size,
                yolo_model=yolo_model,
            )
        return self._registration_detector

    def _extract_embeddings_from_frames(
        self, frames: Sequence[np.ndarray]
    ) -> List[Tuple[np.ndarray, str]]:
        pose_types = summarize_pose_types(len(frames))
        valid_embeddings: List[Tuple[np.ndarray, str]] = []
        for frame, pose_type in zip(frames, pose_types):
            if frame is None or getattr(frame, "size", 0) == 0:
                continue
            detections = self._get_registration_detector().detect(frame, self.pipeline.config.roi_size)
            best = self._pick_best_detection(detections, frame.shape)
            if best is None:
                continue
            embedding = self._embedding_extractor.extract(best.face_roi)
            if embedding is None:
                continue
            valid_embeddings.append((embedding, pose_type))
        return valid_embeddings

    def _pick_best_detection(
        self, detections: Sequence[Any], frame_shape: Tuple[int, ...]
    ) -> Optional[Any]:
        if not detections:
            return None
        frame_h, frame_w = frame_shape[:2]
        center = np.array([frame_w / 2.0, frame_h / 2.0])

        def score(detection: Any) -> float:
            x, y, w, h = detection.bbox
            area = (w * h) / max(frame_h * frame_w, 1)
            det_center = np.array([x + w / 2.0, y + h / 2.0])
            distance = np.linalg.norm(det_center - center)
            center_score = 1.0 - min(distance / max(frame_h, frame_w), 1.0)
            return area * 0.7 + center_score * 0.2 + float(detection.confidence) * 0.1

        return max(detections, key=score)

    def _emit_face_registration_result(
        self, success: bool, face_id: str, student_name: str, msg: str, embeddings_count: int
    ) -> None:
        packet = {
            "type": "face_registration_result",
            "success": success,
            "face_id": face_id,
            "student_name": student_name,
            "msg": msg,
            "embeddings_count": embeddings_count,
        }
        if self.ui_callback is not None:
            self.ui_callback(packet)

    def _snapshot_registry(self) -> Dict[str, Dict[str, Any]]:
        with self._face_registry_lock:
            return {
                face_id: {
                    "student_name": entry["student_name"],
                    "embeddings": list(entry["embeddings"]),
                    "storage_type": entry["storage_type"],
                    "registered_at": entry["registered_at"],
                }
                for face_id, entry in self._face_registry.items()
            }

    def _initialize_database_backend(self) -> None:
        try:
            self._database_backend.initialize()
            faces_data = self._database_backend.load_all_face_embeddings()
            if faces_data:
                self.load_faces_from_db(faces_data)
        except Exception as exc:
            self.log_callback(f"database backend init failed: {exc}")

    def _match_faces(self, tracked_faces: Sequence[TrackedFace]) -> List[MatchedFace]:
        registry = self._snapshot_registry()
        matched_faces: List[MatchedFace] = []
        for face in tracked_faces:
            if not face.is_live:
                continue
            embedding = self._embedding_extractor.extract(face.face_roi)
            best_face_id = None
            best_student_name = "unknown"
            best_score = 0.0
            for face_id, entry in registry.items():
                score = best_similarity(embedding, entry["embeddings"])
                if score > best_score:
                    best_score = score
                    best_face_id = face_id
                    best_student_name = entry["student_name"]

            is_allowed = (
                not self._monitored_faces or
                (best_face_id is not None and best_face_id in self._monitored_faces)
            )
            face_matched = bool(best_face_id and best_score >= self._match_threshold and is_allowed)
            public_face_id: Any = best_face_id if face_matched else f"track_{face.track_id}"
            student_name = best_student_name if face_matched else "unknown"

            matched_faces.append(
                MatchedFace(
                    track_id=face.track_id,
                    face_id=public_face_id,
                    student_name=student_name,
                    bbox=face.bbox,
                    face_roi=face.face_roi,
                    confidence=best_score if face_matched else 0.0,
                    face_matched=face_matched,
                    tracking_score=face.tracking_score,
                    embedding=embedding,
                )
            )
        return matched_faces

    def _select_owner_face(
        self, faces: Sequence[MatchedFace], shape: Tuple[int, ...], has_registered_faces: bool
    ) -> Tuple[Any, bool]:
        if not faces:
            self._last_owner_face_id = -1
            return -1, False

        if self._monitored_faces:
            monitored_matches = [
                face for face in faces
                if face.face_matched and str(face.face_id) in self._monitored_faces
            ]
            if monitored_matches:
                best = max(monitored_matches, key=lambda face: face.confidence)
                self._last_owner_face_id = best.face_id
                return best.face_id, best.face_matched

        if not has_registered_faces and len(faces) == 1 and not faces[0].face_matched:
            best = faces[0]
            self._last_owner_face_id = best.face_id
            return best.face_id, False

        frame_h, frame_w = shape[:2]
        frame_center = np.array([frame_w / 2.0, frame_h / 2.0])
        best = None
        best_score = None
        for face in faces:
            x, y, w, h = face.bbox
            area_score = (w * h) / max(float(frame_w * frame_h), 1.0)
            face_center = np.array([x + w / 2.0, y + h / 2.0])
            distance = np.linalg.norm(face_center - frame_center)
            center_score = 1.0 - min(distance / max(frame_w, frame_h), 1.0)
            continuity_bonus = 0.2 if face.face_id == self._last_owner_face_id else 0.0
            identity_bonus = 0.2 if face.face_matched else 0.0
            score = area_score * 0.45 + center_score * 0.2 + face.tracking_score * 0.15 + identity_bonus + continuity_bonus
            if best is None or score > best_score:
                best = face
                best_score = score
        self._last_owner_face_id = best.face_id if best is not None else -1
        return (best.face_id, best.face_matched) if best is not None else (-1, False)

    def _build_ui_packet(
        self,
        frame: np.ndarray,
        timestamp: float,
        faces: Sequence[MatchedFace],
        context: Optional[Any] = None,
    ) -> UIFramePacket:
        ui_faces = [
            {
                "face_id": face.face_id,
                "bbox": list(face.bbox),
                "student_name": face.student_name,
                "face_matched": face.face_matched,
            }
            for face in faces
        ]
        frame_progress = None
        if context is not None and context.total_frames > 0:
            frame_progress = {
                "current_frame": int(context.frame_index),
                "total_frames": int(context.total_frames),
            }
        return UIFramePacket(
            frame=frame,
            faces=ui_faces,
            timestamp=timestamp,
            frame_progress=frame_progress,
        )

    def _build_feature_packet(
        self,
        frame: np.ndarray,
        timestamp: float,
        faces: Sequence[MatchedFace],
        owner_face_id: Any,
        owner_face_matched: bool,
    ) -> FeatureFramePacket:
        feature_faces = [
            {
                "face_id": face.face_id,
                "student_name": face.student_name,
                "face_roi": face.face_roi,
                "confidence": face.confidence,
                "face_matched": face.face_matched,
            }
            for face in faces
        ]
        return FeatureFramePacket(
            timestamp=timestamp,
            faces=feature_faces,
            owner_face_id=owner_face_id,
            frame=frame,
            face_matched=owner_face_matched,
        )

    def _emit_file_playback_ended(self) -> None:
        file_path = ""
        if self._active_source and self._active_source.get("type") == "file":
            file_path = str(self._active_source.get("file_path", ""))
        if not file_path:
            file_path = self.video_source.file_path or ""
        if self.ui_callback is not None:
            self.ui_callback({"type": "file_playback_ended", "file_path": file_path})

    @staticmethod
    def _callback_accepts_frame_progress(callback: Callable[..., Any]) -> bool:
        try:
            signature = inspect.signature(callback)
        except (TypeError, ValueError):
            return False
        params = list(signature.parameters.values())
        if any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in params):
            return True
        positional_params = [
            param for param in params
            if param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        return len(positional_params) >= 4

    def _prepare_file_read_timing(self) -> None:
        if not self._is_file_source_active():
            return
        fps = self._effective_file_fps()
        if fps <= 0:
            return
        if self._file_playback_started_at is None:
            self._file_playback_started_at = time.perf_counter()
            return
        expected_next_frame = int(
            max(0.0, time.perf_counter() - self._file_playback_started_at)
            * fps
            * self._playback_rate
        ) + 1
        if expected_next_frame > self.video_source.frame_index + 1:
            self.video_source.skip_to_frame(expected_next_frame)

    def _pace_file_playback(self, context: Any, frame_started_at: float) -> None:
        if not self._is_file_source_active():
            return
        fps = self._effective_file_fps(context.fps)
        if fps <= 0:
            return
        if self._file_playback_started_at is None:
            self._file_playback_started_at = frame_started_at
        frame_interval = 1.0 / max(fps * self._playback_rate, 1e-6)
        target_time = self._file_playback_started_at + max(0, context.frame_index - 1) * frame_interval
        now = time.perf_counter()
        remaining = target_time - now
        if remaining > 0:
            time.sleep(remaining)
            return
        lag_frames = int(abs(remaining) // frame_interval)
        if lag_frames >= 1:
            self.video_source.skip_to_frame(context.frame_index + lag_frames + 1)

    def _effective_file_fps(self, fps: Optional[float] = None) -> float:
        value = float(fps if fps is not None else self.video_source.fps)
        return value if value > 1e-3 else 25.0

    def _is_file_source_active(self) -> bool:
        return bool(self._active_source and self._active_source.get("type") == "file")


class PreprocessingCommandAdapter:
    def __init__(self, service: PreprocessingService):
        self.service = service

    def __call__(self, command: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.service.handle_command(command, params)
