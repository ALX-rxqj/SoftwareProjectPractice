from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np

from .contracts import FrameContext


class VideoSource:
    def __init__(self):
        self._capture: Optional[cv2.VideoCapture] = None
        self._source_name = "unopened"
        self._source_type = "unopened"
        self._file_path: Optional[str] = None
        self._frame_index = 0
        self._total_frames = 0
        self._fps = 0.0
        self._reached_end = False

    @property
    def is_opened(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def source_type(self) -> str:
        return self._source_type

    @property
    def file_path(self) -> Optional[str]:
        return self._file_path

    @property
    def frame_index(self) -> int:
        return self._frame_index

    @property
    def total_frames(self) -> int:
        return self._total_frames

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def reached_end(self) -> bool:
        return self._reached_end

    def open_camera(self, device_id: int = 0) -> None:
        self.close()
        self._capture = cv2.VideoCapture(device_id, cv2.CAP_DSHOW)
        self._source_name = f"camera:{device_id}"
        self._source_type = "camera"
        self._file_path = None
        self._frame_index = 0
        self._total_frames = 0
        self._fps = float(self._capture.get(cv2.CAP_PROP_FPS) or 0.0)
        self._reached_end = False
        if not self.is_opened:
            raise RuntimeError(f"Unable to open camera device {device_id}")

    def open_file(self, file_path: Union[str, Path]) -> None:
        self.close()
        path = Path(file_path)
        self._capture = cv2.VideoCapture(str(path))
        self._source_name = f"file:{path.name}"
        self._source_type = "file"
        self._file_path = str(path)
        self._frame_index = 0
        self._total_frames = int(self._capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self._fps = float(self._capture.get(cv2.CAP_PROP_FPS) or 0.0)
        self._reached_end = False
        if not self.is_opened:
            raise RuntimeError(f"Unable to open video file: {path}")

    def read(self) -> Optional[FrameContext]:
        if not self.is_opened:
            return None

        ok, frame = self._capture.read()
        if not ok or frame is None:
            self._reached_end = self._source_type == "file"
            return None

        self._frame_index += 1
        self._reached_end = False
        return FrameContext(
            frame=frame,
            timestamp=time.time(),
            source_name=self._source_name,
            frame_index=self._frame_index,
            total_frames=self._total_frames,
            fps=self._fps,
            file_path=self._file_path,
        )

    def skip_to_frame(self, next_frame_index: int) -> None:
        if not self.is_opened or self._source_type != "file":
            return
        bounded_index = max(1, next_frame_index)
        if self._total_frames > 0 and bounded_index > self._total_frames:
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, self._total_frames)
            self._frame_index = self._total_frames
            self._reached_end = False
            return
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, bounded_index - 1)
        self._frame_index = bounded_index - 1
        self._reached_end = False

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._source_name = "unopened"
        self._source_type = "unopened"
        self._file_path = None
        self._frame_index = 0
        self._total_frames = 0
        self._fps = 0.0
        self._reached_end = False

    def __enter__(self) -> "VideoSource":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
