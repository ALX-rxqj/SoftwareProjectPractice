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
        
        完全按照main.py的逻辑处理原始帧：
        1. 从原始帧中检测人脸
        2. 提取关键点
        3. 计算所有特征

        输入 record 示例（注意：faces列表不再被使用）：
        {
            "timestamp": 12345.6,
            "faces": [...],           # 可选，不被使用
            "owner_face_id": track_id,
            "original_frame": frame,  # 原始摄像头帧
            "face_matched": True      # 可选，会被转发到输出
        }

        """
        timestamp = float(record.get('timestamp', 0.0))
        owner_face_id = record.get('owner_face_id')
        original_frame = record.get('original_frame', None)
        face_matched = record.get('face_matched', False)

        # 使用原始帧作为处理帧
        if original_frame is None:
            original_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # 初始化PoseEstimator
        self._ensure_pose_estimator(original_frame)

        # 第一步：从原始帧中检测人脸
        faces, _ = self.face_detector.detect(original_frame, 0.7)
        num_face_total = len(faces)

        # 是否检测到有效人脸
        if len(faces) > 0:
            # 第二步：选择主人脸并检测关键点
            frame_height, frame_width = original_frame.shape[0], original_frame.shape[1]
            face = refine(faces, frame_width, frame_height, 0.15)[0]
            x1, y1, x2, y2 = face[:4].astype(int)
            
            try:
                # 从原始帧中裁剪人脸区域
                patch = original_frame[y1:y2, x1:x2]
                
                # 执行关键点检测
                marks = self.mark_detector.detect([patch])[0].reshape([68, 2])
                
                # 将局部人脸区域中的坐标转换回整张图像坐标
                marks[:, 0] += x1
                marks[:, 1] += y1
            except Exception:
                marks = np.zeros((68, 2), dtype=np.float32)

            # 第三步：利用68个关键点估计头部姿态
            try:
                pose = self.pose_estimator.solve(marks)
                head_pose = self.pose_estimator.get_head_pose_data(marks, pose)["head_pose"]
            except Exception:
                head_pose = {'pitch': 0.0, 'yaw': 0.0, 'roll': 0.0, 'confidence': 0.0}

            # 估计眼睛状态
            try:
                eye_state = _estimate_eye_state(marks)
            except Exception:
                eye_state = {'value': 0, 'confidence': 0.0}

            # 估计是否看屏幕
            try:
                is_looking_screen = _estimate_looking_screen(head_pose, eye_state)
            except Exception:
                is_looking_screen = {'value': False, 'confidence': 0.0}

            # 估计人脸距离状态
            face_distance_state = _estimate_face_distance_state(
                face_box=face[:4],
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
            # 没有检测到人脸，返回默认输出
            output = _build_default_output(owner_face_id, face_matched=face_matched)
            output['timestamp'] = timestamp
            output['features']['num_face_total'] = {
                'value': int(num_face_total),
                'confidence': float(np.clip(1.0 if num_face_total > 0 else 0.0, 0.0, 1.0)),
            }

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
