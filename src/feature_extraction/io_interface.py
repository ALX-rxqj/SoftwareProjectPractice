"""
输入/输出接口模块（MediaPipe Face Landmarker 版）

此模块使用 MediaPipe Face Landmarker 替换原有的 ONNX 68 点模型链。
通过适配器将 MediaPipe 478 点输出转换为现有管线兼容的格式。

提供的主要类：
- `IOInterface`：处理单条输入并通过回调输出结果。
- `process_batch`：批量处理工具函数。
"""
import os as _os
from typing import Callable, Dict, List, Any, Optional

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .mediapipe_adapter import (
    mp_to_68_marks,
    mp_extract_head_pose,
    mp_get_face_bbox,
)
from .metrics import (
    _build_default_output,
    _build_prompt_output,
    _estimate_attention_state,
    _estimate_face_distance_state,
    _estimate_looking_screen,
    _estimate_yawning_state,
    EyeStateEstimator,
)

# 模型文件默认路径
_ASSETS_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', 'weights')
_DEFAULT_MP_MODEL = _os.path.join(_ASSETS_DIR, 'face_landmarker.task')


class IOInterface:
    """封装输入/输出调用的接口类。

    使用 MediaPipe Face Landmarker 进行人脸检测 + 关键点提取 + 头部姿态估计。

    使用示例：
        io = IOInterface()
        io.process(record, send_to_scoring)
    """

    def __init__(self,
                 mp_model_path: str = _DEFAULT_MP_MODEL,
                 num_faces: int = 1,
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5):
        mp_options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=mp_model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=num_faces,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=True,
        )
        self.mp_landmarker = vision.FaceLandmarker.create_from_options(mp_options)
        self.eye_estimator = EyeStateEstimator()

    def _process_frame(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """用 MediaPipe 处理单帧，返回中间结果字典。

        Returns:
            dict with keys: num_faces, marks, head_pose, face_bbox
            or None if no face detected.
        """
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.mp_landmarker.detect(mp_image)

        num_faces = len(result.face_landmarks)
        if num_faces == 0:
            return None

        landmarks = result.face_landmarks[0]
        transform = (
            result.facial_transformation_matrixes[0]
            if result.facial_transformation_matrixes
            else None
        )

        marks = mp_to_68_marks(landmarks, w, h)
        head_pose = mp_extract_head_pose(transform)
        face_bbox = mp_get_face_bbox(landmarks, w, h)

        return {
            "num_faces": num_faces,
            "marks": marks,
            "head_pose": head_pose,
            "face_bbox": face_bbox,
        }

    def process(self, record: Dict[str, Any],
                send_to_scoring: Callable[[Dict[str, Any]], None],
                mark_threshold: float = 0.5) -> None:
        """处理单条输入并通过 `send_to_scoring` 回调结果。

        输入 record：
        {
            "timestamp": float,
            "faces": [...],           # 可选，不再使用
            "owner_face_id": track_id,
            "original_frame": frame,  # 原始摄像头帧
            "face_matched": bool      # 可选，会被转发到输出
        }
        """
        timestamp = float(record.get('timestamp', 0.0))
        owner_face_id = record.get('owner_face_id')
        original_frame = record.get('original_frame', None)
        face_matched = record.get('face_matched', False)

        if original_frame is None:
            original_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        intermediate = self._process_frame(original_frame)

        if intermediate is not None:
            marks = intermediate["marks"]
            head_pose = intermediate["head_pose"]
            face_bbox = intermediate["face_bbox"]
            faces_from_preprocessing = record.get("faces", []) or []
            num_face_total = len(faces_from_preprocessing) if faces_from_preprocessing else intermediate["num_faces"]

            # 估计眼睛状态（自适应 EAR 基线）
            try:
                eye_state = self.eye_estimator.estimate(marks, face_id=owner_face_id)
            except Exception:
                eye_state = {'value': 0, 'confidence': 0.0}

            # 估计是否看屏幕
            try:
                is_looking_screen = _estimate_looking_screen(head_pose, eye_state)
            except Exception:
                is_looking_screen = {'value': False, 'confidence': 0.0}

            # 估计人脸距离状态
            face_distance_state = _estimate_face_distance_state(
                face_box=face_bbox,
                frame_shape=original_frame.shape,
            )

            # 估计打哈欠状态
            try:
                is_yawning = _estimate_yawning_state(marks, head_pose=head_pose)
            except Exception:
                is_yawning = {'value': False, 'confidence': 0.0}

            # 估计注意力状态
            attention_state = _estimate_attention_state(
                eye_state,
                is_looking_screen,
                face_distance_state,
                is_yawning,
                face_present=True,
            )

            output = _build_prompt_output(
                timestamp,
                owner_face_id,
                head_pose,
                eye_state,
                is_looking_screen,
                attention_state,
                face_distance_state,
                is_yawning,
                int(num_face_total),
                face_matched=face_matched,
            )
        else:
            output = _build_default_output(owner_face_id, face_matched=face_matched)
            output['timestamp'] = timestamp
            faces_count = len(record.get("faces", []) or [])
            output['features']['num_face_total'] = {
                'value': faces_count,
                'confidence': 0.0,
            }

        send_to_scoring(output)


def process_batch(records: List[Dict[str, Any]],
                  send_to_scoring: Callable[[Dict[str, Any]], None],
                  io: Optional[IOInterface] = None):
    """批量处理接口列表。"""
    if io is None:
        io = IOInterface()
    for r in records:
        try:
            io.process(r, send_to_scoring)
        except Exception:
            continue


__all__ = ['IOInterface', 'process_batch']
