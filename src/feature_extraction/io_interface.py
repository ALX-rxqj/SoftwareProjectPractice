"""
输入/输出接口模块（轻量封装）

此模块只负责把外部输入转换为内部处理调用，并把处理结果按约定输出。
内部直接调用项目中已有的 `FaceDetector`, `MarkDetector`, `PoseEstimator` 等实现。

提供的主要函数：
- `IOInterface` 类：可复用的实例化封装，方法 `process(record, send_to_scoring)` 用于处理单条输入并回调输出。
- `process_batch(records, send_to_scoring, io)`：批量处理工具函数。

"""
from typing import Callable, Dict, List, Any, Optional
import numpy as np

from .face_detection import FaceDetector
from .mark_detection import MarkDetector
from .pose_estimation import PoseEstimator
from .utils import refine

# 为了复用 main 中的注意力/张嘴/闭眼等算法，安全导入这些函数
from .metrics import (
    _build_default_output,
    _build_prompt_output,
    _estimate_attention_state,
    _estimate_eye_state,
    _estimate_face_distance_state,
    _estimate_looking_screen,
    _estimate_yawning_state,
)


class IOInterface:
    """封装输入/输出调用的接口类。

    使用示例：
        io = IOInterface()
        io.process(record, send_to_scoring)
"""

    def __init__(self,
                 face_model_path: str = 'assets/face_detector.onnx',
                 mark_model_path: str = 'assets/face_landmarks.onnx'):
        self.face_detector = FaceDetector(face_model_path)
        self.mark_detector = MarkDetector(mark_model_path)
        self.pose_estimator: Optional[PoseEstimator] = None

    def _ensure_pose_estimator(self, frame: np.ndarray):
        h, w = frame.shape[0], frame.shape[1]
        if self.pose_estimator is None or self.pose_estimator.size != (h, w):
            # PoseEstimator 构造需要 (width, height) 参数
            self.pose_estimator = PoseEstimator(w, h)

    def _parse_marks(self, raw_marks: np.ndarray) -> np.ndarray:
        """把模型输出的关键点数组转换为 (68,2) 形式。

        这个处理尝试兼容常见的输出形状。
        """
        marks = np.array(raw_marks)
        if marks.ndim == 3 and marks.shape[0] == 1:
            marks = marks[0]
        if marks.ndim == 1:
            # 可能是 [136] 的扁平向量
            if marks.size == 136:
                marks = marks.reshape((68, 2))
            else:
                raise ValueError('无法识别的关键点形状: {}'.format(marks.shape))
        if marks.ndim == 2 and marks.shape[1] == 136:
            marks = marks.reshape((-1, 2))
        if marks.ndim == 2 and marks.shape[1] == 2:
            return marks.astype(np.float32)
        raise ValueError('无法识别的关键点形状: {}'.format(marks.shape))

    def process(self, record: Dict[str, Any], send_to_scoring: Callable[[Dict[str, Any]], None],
                mark_threshold: float = 0.5) -> None:
        """处理单条输入并通过 `send_to_scoring` 回调结果。

        输入 record 示例：
        {
            "timestamp": 12345.6,
            "faces": [{"face_id":1, "face_roi": face_img}, ...],
            "owner_face_id": 1,
            "frame": frame
        }

        """
        timestamp = float(record.get('timestamp', 0.0))
        faces = record.get('faces', []) or []
        owner_face_id = record.get('owner_face_id')  # 保持原始类型（串称下整数）
        frame = record.get('frame', None)
        face_matched = record.get('face_matched', False)

        if frame is None:
            # 没有原始帧时仍继续，但 pose_estimator 需要 frame 来构造相机参数
            frame = np.zeros((480, 640, 3), dtype=np.uint8)

        self._ensure_pose_estimator(frame)

        # 统计人脸数目
        num_face_total = len(faces)

        # 找到主人脸的 face_roi
        owner_face = None
        for f in faces:
            if f.get('face_id') == owner_face_id:
                owner_face = f
                break

        if owner_face is None:
            # 如果没有找到主人脸，返回空结果（可按需修改）
            output = _build_default_output(owner_face_id, face_matched=face_matched)
            output['timestamp'] = timestamp
            output['features']['num_face_total'] = {'value': num_face_total, 'confidence': 1.0}
            send_to_scoring(output)
            return

        face_roi = owner_face.get('face_roi')
        if face_roi is None:
            # 如果没有直接提供 face_roi，尝试用 bounding box 从 frame 裁剪
            bbox = owner_face.get('bbox') or owner_face.get('face_bbox')
            if bbox is not None and frame is not None:
                x1, y1, x2, y2 = map(int, bbox[:4])
                face_roi = frame[y1:y2, x1:x2].copy()
            else:
                # 兜底：把整个帧当作 face_roi
                face_roi = frame.copy()

        # 调用关键点检测
        try:
            raw_marks = self.mark_detector.detect([face_roi])
            marks = self._parse_marks(raw_marks)
        except Exception:
            # 若关键点失败，使用空占位
            marks = np.zeros((68, 2), dtype=np.float32)

        # 调用姿态估计
        try:
            pose = self.pose_estimator.solve(marks)
            head_pose = self.pose_estimator.get_head_pose_data(marks, pose=pose).get('head_pose', {})
        except Exception:
            head_pose = {'pitch': 0.0, 'yaw': 0.0, 'roll': 0.0, 'confidence': 0.0}

        # 使用 main.py 中的算法估计眼睛/注视/打哈欠等
        try:
            eye_state = _estimate_eye_state(marks)
        except Exception:
            eye_state = {'value': 0, 'confidence': 0.0}

        try:
            is_looking_screen = _estimate_looking_screen(head_pose, eye_state)
        except Exception:
            is_looking_screen = {'value': False, 'confidence': 0.0}

        face_distance_state = _estimate_face_distance_state(
            face_box=owner_face.get('bbox') or owner_face.get('face_bbox'),
            frame_shape=frame.shape,
            face_roi_shape=face_roi.shape,
        )

        # 使用 mouth aspect ratio 判断是否打哈欠，confidence 表示对该判断的把握度
        try:
            is_yawning = _estimate_yawning_state(marks)
        except Exception:
            is_yawning = {'value': False, 'confidence': 0.0}

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
            num_face_total,
            face_matched=face_matched,
        )

        send_to_scoring(output)


def process_batch(records: List[Dict[str, Any]], send_to_scoring: Callable[[Dict[str, Any]], None], io: Optional[IOInterface] = None):
    """批量处理接口列表。"""
    if io is None:
        io = IOInterface()
    for r in records:
        try:
            io.process(r, send_to_scoring)
        except Exception:
            # 单条出错时继续处理其余条目
            continue


__all__ = ['IOInterface', 'process_batch']
