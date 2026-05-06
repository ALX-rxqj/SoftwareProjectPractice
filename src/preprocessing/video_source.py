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
        self._frame_index = 0

    @property
    def is_opened(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    @property
    def source_name(self) -> str:
        return self._source_name

    def open_camera(self, device_id: int = 0) -> None:
        self.close()
        self._capture = cv2.VideoCapture(device_id, cv2.CAP_DSHOW)
        self._source_name = f"camera:{device_id}"
        self._frame_index = 0
        if not self.is_opened:
            raise RuntimeError(f"Unable to open camera device {device_id}")

    def open_file(self, file_path: Union[str, Path]) -> None:
        self.close()
        path = Path(file_path)
        self._capture = cv2.VideoCapture(str(path))
        self._source_name = f"file:{path.name}"
        self._frame_index = 0
        if not self.is_opened:
            raise RuntimeError(f"Unable to open video file: {path}")

    def read(self) -> Optional[FrameContext]:
        if not self.is_opened:
            return None

        ok, frame = self._capture.read()
        if not ok or frame is None:
            return None

        self._frame_index += 1
        return FrameContext(
            frame=frame,
            timestamp=time.time(),
            source_name=self._source_name,
            frame_index=self._frame_index,
        )

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._source_name = "unopened"
        self._frame_index = 0

    def __enter__(self) -> "VideoSource":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
