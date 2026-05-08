from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import cv2

from .pipeline import PipelineConfig, PreprocessingPipeline
from .video_source import VideoSource


CommandCallback = Callable[[str, Dict[str, Any]], Optional[Dict[str, Any]]]
PacketCallback = Callable[[Dict[str, Any]], None]
LogCallback = Callable[[str], None]
VideoFrameCallback = Callable[[Any, List[Dict[str, Any]], float], None]
FrameReceivedCallback = Callable[[Dict[str, Any]], None]
CameraListCallback = Callable[[List[Dict[str, Any]]], None]


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
    ):
        self.ui_callback = ui_callback
        self.feature_callback = feature_callback
        self.log_callback = log_callback or (lambda message: None)
        self.video_frame_callback = video_frame_callback
        self.frame_received_callback = frame_received_callback
        self.camera_list_callback = camera_list_callback
        self.pipeline = PreprocessingPipeline(config=config, logger=self.log_callback)
        self.video_source = VideoSource()
        self._stop_event = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._active_source: Optional[Dict[str, Any]] = None

    def handle_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if command == "toggle_capture":
            return self.on_control_capture(
                device_id=int(params.get("device_id", 0)),
                start=bool(params.get("start", False)),
            )
        if command == "load_video":
            return self.on_load_video(file_path=params.get("file_path"))
        if command == "query_cameras":
            return self.on_query_cameras()
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

    def on_control_capture(self, device_id: int, start: bool) -> Dict[str, Any]:
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
        }

    def _start_worker(self) -> None:
        self._stop_event.clear()
        self.pipeline.reset()
        self._worker = threading.Thread(target=self._run_loop, name="PreprocessingWorker", daemon=True)
        self._worker.start()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            context = self.video_source.read()
            if context is None:
                time.sleep(0.02)
                if self._active_source and self._active_source.get("type") == "file":
                    break
                continue

            result = self.pipeline.process(context)
            if result is None:
                continue

            ui_packet = result["ui"].to_dict()
            feature_packet = result["feature"].to_dict()
            self._dispatch_ui_packet(ui_packet)
            self._dispatch_feature_packet(feature_packet)

        self.video_source.close()

    def _dispatch_ui_packet(self, ui_packet: Dict[str, Any]) -> None:
        if self.ui_callback is not None:
            self.ui_callback(ui_packet)
        if self.video_frame_callback is not None:
            self.video_frame_callback(ui_packet["frame"], ui_packet["faces"], ui_packet["timestamp"])

    def _dispatch_feature_packet(self, feature_packet: Dict[str, Any]) -> None:
        if self.feature_callback is not None:
            self.feature_callback(feature_packet)
        if self.frame_received_callback is not None:
            self.frame_received_callback(feature_packet)


class PreprocessingCommandAdapter:
    def __init__(self, service: PreprocessingService):
        self.service = service

    def __call__(self, command: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.service.handle_command(command, params)
