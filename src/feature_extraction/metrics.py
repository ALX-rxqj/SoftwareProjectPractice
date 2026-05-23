"""

此模块提供：
- `_clip01`, `_distance`, `_eye_aspect_ratio`, `_compute_ear`, `_mouth_aspect_ratio`,
- `_estimate_eye_state`, `_estimate_looking_screen`, `_estimate_face_distance_state`,
- `_estimate_attention_state`, `_build_default_output`, `_build_prompt_output`

"""
import time
from collections import deque
import numpy as np


def _clip01(value):
    return float(np.clip(value, 0.0, 1.0))


def _distance(p1, p2):
    return float(np.linalg.norm(p1 - p2))


def _eye_aspect_ratio(eye_points):
    vertical = _distance(eye_points[1], eye_points[5]) + _distance(eye_points[2], eye_points[4])
    horizontal = max(_distance(eye_points[0], eye_points[3]), 1e-6)
    return vertical / (2.0 * horizontal)


def _compute_ear(marks):
    left_ear = _eye_aspect_ratio(marks[36:42])
    right_ear = _eye_aspect_ratio(marks[42:48])
    ear = (left_ear + right_ear) / 2.0
    return {
        "left": left_ear,
        "right": right_ear,
        "value": ear,
    }


def _mouth_aspect_ratio(marks):
    mouth_width = max(_distance(marks[48], marks[54]), 1e-6)

    outer_open = (
        _distance(marks[51], marks[57])
        + _distance(marks[50], marks[58])
        + _distance(marks[52], marks[56])
    ) / (3.0 * mouth_width)

    inner_open = (
        _distance(marks[61], marks[67])
        + _distance(marks[62], marks[66])
        + _distance(marks[63], marks[65])
    ) / (3.0 * mouth_width)

    return 0.4 * outer_open + 0.6 * inner_open


def _estimate_eye_state(marks):
    ear = _compute_ear(marks)["value"]

    # 调整阈值：降低敏感度，减少误判
    # 原值：closed_score = (0.26 - ear) / 0.10，阈值 >= 0.35
    # 新值：使用更宽松的标准
    closed_score = _clip01((0.20 - ear) / 0.12)
    if closed_score >= 0.25:
        return {"value": 1, "confidence": closed_score}
    return {"value": 0, "confidence": _clip01(1.0 - closed_score)}


class EyeStateEstimator:
    """Adaptive eye state estimator using personal EAR baseline.

    Instead of a hardcoded EAR threshold, this class maintains a rolling
    history of recent EAR values and computes a per-person "normal open-eye"
    baseline (P85 percentile). Eye state is classified based on the ratio of
    current EAR to baseline, making it robust across different eye shapes.

    Warmup: first 30 frames use the hardcoded fallback threshold.
    Guard: only frames with ratio >= 0.60 are added to history to prevent
           baseline drift during prolonged eye closure.
    Person switch: changing face_id triggers automatic reset.
    """

    HISTORY_SIZE = 90
    BASELINE_PERCENTILE = 85
    WARMUP_FRAMES = 30
    CLOSED_RATIO = 0.50
    UPDATE_GUARD_RATIO = 0.60
    MIN_BASELINE = 0.10

    def __init__(self):
        self._history = deque(maxlen=self.HISTORY_SIZE)
        self._baseline = None
        self._baseline_frame_count = 0
        self._current_face_id = None

    def reset(self):
        self._history.clear()
        self._baseline = None
        self._baseline_frame_count = 0
        self._current_face_id = None

    def estimate(self, marks, face_id=None):
        ear = _compute_ear(marks)["value"]

        if face_id is not None and face_id != self._current_face_id:
            self.reset()
            self._current_face_id = face_id

        if self._baseline_frame_count < self.WARMUP_FRAMES:
            self._history.append(ear)
            self._baseline_frame_count += 1
            return _estimate_eye_state(marks)

        self._baseline = max(
            float(np.percentile(list(self._history), self.BASELINE_PERCENTILE)),
            self.MIN_BASELINE,
        )

        ratio = ear / self._baseline

        if ratio < self.CLOSED_RATIO:
            closed_score = _clip01((self.CLOSED_RATIO - ratio) / (self.CLOSED_RATIO * 0.6))
            result = {"value": 1, "confidence": max(0.25, closed_score)}
        else:
            open_margin = ratio - self.CLOSED_RATIO
            confidence = _clip01(0.4 + open_margin / (1.0 - self.CLOSED_RATIO) * 0.6)
            result = {"value": 0, "confidence": confidence}

        if ratio >= self.UPDATE_GUARD_RATIO:
            self._history.append(ear)

        return result


def _estimate_looking_screen(head_pose, eye_state):
    if eye_state["value"] == 1:
        return {"value": False, "confidence": _clip01(eye_state["confidence"]) }

    yaw = abs(head_pose["yaw"])
    pitch = abs(head_pose["pitch"])
    roll = abs(head_pose["roll"])

    yaw_score = _clip01(1.0 - yaw / 25.0)
    pitch_score = _clip01(1.0 - pitch / 20.0)
    roll_score = _clip01(1.0 - roll / 20.0)
    gaze_score = _clip01(0.6 * yaw_score + 0.3 * pitch_score + 0.1 * roll_score)
    confidence = _clip01(0.75 * gaze_score + 0.25 * eye_state["confidence"])
    return {"value": confidence >= 0.55, "confidence": confidence}


def _estimate_face_distance_state(face_box=None, frame_shape=None, face_roi_shape=None):
    """基于人脸框大小估计距离状态。

    0 = 正常距离, 1 = 太远, 2 = 太近
    """
    area = None
    if face_box is not None and len(face_box) >= 4:
        x1, y1, x2, y2 = [float(v) for v in face_box[:4]]
        area = max((x2 - x1) * (y2 - y1), 1.0)
    elif face_roi_shape is not None and len(face_roi_shape) >= 2:
        area = max(float(face_roi_shape[0] * face_roi_shape[1]), 1.0)

    if area is None:
        return {"value": 0, "confidence": 0.0}

    if frame_shape is not None and len(frame_shape) >= 2:
        frame_area = max(float(frame_shape[0] * frame_shape[1]), 1.0)
    else:
        frame_area = max(area * 8.0, 1.0)

    ratio = area / frame_area
    if ratio < 0.10:
        confidence = _clip01((0.10 - ratio) / 0.10)
        return {"value": 1, "confidence": confidence}
    if ratio > 0.22:
        confidence = _clip01((ratio - 0.22) / 0.18)
        return {"value": 2, "confidence": confidence}

    confidence = _clip01(1.0 - abs(ratio - 0.12) / 0.12)
    return {"value": 0, "confidence": confidence}


def _estimate_attention_state(eye_state, is_looking_screen, face_distance_state, is_yawning, face_present=True):
    """根据眼睛、注视、打哈欠和距离状态估计注意力状态。

    0 = 专注, 1 = 分心, 2 = 困倦, 3 = 缺席
    """
    if not face_present:
        return {"value": 3, "confidence": 1.0}

    if eye_state["value"] == 1 or is_yawning.get("value", False):
        confidence = _clip01(max(eye_state.get("confidence", 0.0), is_yawning.get("confidence", 0.0)))
        return {"value": 2, "confidence": confidence}

    if face_distance_state["value"] in (1, 2) or not is_looking_screen.get("value", False):
        confidence = _clip01(max(
            is_looking_screen.get("confidence", 0.0),
            face_distance_state.get("confidence", 0.0),
        ))
        return {"value": 1, "confidence": confidence}

    confidence = _clip01(0.5 * is_looking_screen.get("confidence", 0.0) + 0.5 * eye_state.get("confidence", 0.0))
    return {"value": 0, "confidence": confidence}


def _estimate_yawning_state(marks, head_pose=None, eye_state=None, threshold=0.30, margin=0.10):
    """估计是否打哈欠，以及该判断的可信度。

    value: bool，是否打哈欠
    confidence: float，对当前判定结果的把握度。
    
    - 张嘴且眼睛闭合时置信度最高（0.80-0.95）
    - 单纯张嘴时置信度较低（0.70-0.75）
    - 侧脸时自动禁用判别，避免误判。
    """
    # 侧脸检测：如果yaw角度 > 30度，说明是侧脸，禁用打哈欠检测
    if head_pose is not None and "yaw" in head_pose:
        yaw = abs(head_pose.get("yaw", 0))
        if yaw > 30:  # 侧脸角度过大，不判别
            return {"value": False, "confidence": 0.0}
    
    mar = _mouth_aspect_ratio(marks)
    value = bool(mar >= threshold)
    
    if value:
        # 张嘴时的置信度计算
        relative_conf = _clip01((mar - threshold) / max(margin, 1e-6))
        
        # 检查眼睛是否闭合
        eyes_closed = eye_state is not None and eye_state.get("value") == 1
        
        if eyes_closed:
            # 张嘴且眼睛闭合：置信度范围 0.80-0.95（真正的打哈欠）
            confidence = _clip01(0.80 + 0.15 * relative_conf)
        else:
            # 只张嘴（眼睛睁着）：置信度范围 0.70-0.75（可能是说话）
            confidence = _clip01(0.70 + 0.05 * relative_conf)
    else:
        # 没张嘴时：置信度范围 0.3-0.7
        relative_conf = _clip01((threshold - mar) / max(margin * 2, 1e-6))
        confidence = _clip01(0.3 + 0.4 * relative_conf)
    
    return {"value": value, "confidence": confidence}


def _build_default_output(face_id, face_matched=None):
    return {
        "timestamp": time.time(),
        "face_id": face_id,
        "face_matched": face_matched if face_matched is not None else False,
        "features": {
            "head_pose": {
                "pitch": 0.0,
                "yaw": 0.0,
                "roll": 0.0,
                "confidence": 0.0,
            },
            "eye_state": {"value": 0, "confidence": 0.0},
            "is_looking_screen": {"value": False, "confidence": 0.0},
            "attention_state": {"value": 3, "confidence": 1.0},
            "face_distance_state": {"value": 0, "confidence": 0.0},
            "is_yawning": {"value": False, "confidence": 0.0},
            "num_face_total": {"value": 0, "confidence": 0.0},
        },
    }


def _build_prompt_output(timestamp, face_id, head_pose, eye_state, is_looking_screen, attention_state,
                         face_distance_state, is_yawning, num_face_total, face_matched=None):
    return {
        "timestamp": float(timestamp),
        "face_id": face_id,
        "face_matched": face_matched if face_matched is not None else False,
        "features": {
            "head_pose": head_pose,
            "eye_state": eye_state,
            "is_looking_screen": is_looking_screen,
            "attention_state": attention_state,
            "face_distance_state": face_distance_state,
            "is_yawning": is_yawning,
            "num_face_total": {
                "value": int(num_face_total),
                "confidence": _clip01(1.0 if num_face_total > 0 else 0.0),
            },
        },
    }


__all__ = [
    '_clip01', '_distance', '_eye_aspect_ratio', '_compute_ear', '_mouth_aspect_ratio',
    '_estimate_eye_state', '_estimate_looking_screen', '_estimate_face_distance_state',
    '_estimate_attention_state', '_estimate_yawning_state', '_build_default_output', '_build_prompt_output',
    'EyeStateEstimator',
]
