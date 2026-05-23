"""MediaPipe Face Landmarker → 68-point iBUG 格式适配器。

将 MediaPipe 478 点输出转换为现有管线能识别的格式：
- 合成 68 点关键点数组（像素坐标）
- 从 4x4 变换矩阵提取头部姿态
- 从 landmarks 计算人脸边界框
"""
import numpy as np


# ---------------------------------------------------------------------------
# MediaPipe 478 点 → 68 点 (iBUG) 索引映射
# ---------------------------------------------------------------------------
# MediaPipe Face Landmarker 拓扑参考:
#   https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/face_landmarker.md
#
# 映射策略：
#   - 眼部 (36-47) 和嘴部 (48-67)：精确选取，保证 EAR/MAR 计算正确
#   - 下巴/眉/鼻 (0-35)：近似映射（MediaPipe 的拓扑与 iBUG 不完全对应，
#     选取几何上最接近的点；这些索引不参与关键指标计算）

MP_FACE_OVAL = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
]

MP_68_MAP = [
    # ---- 下巴轮廓 (0-16): 从 Face Oval 36 点中等距采样 17 点 ----
    10,    # 0
    338,   # 1
    332,   # 2
    284,   # 3
    251,   # 4
    389,   # 5
    356,   # 6
    454,   # 7  下巴底
    323,   # 8
    288,   # 9
    365,   # 10
    378,   # 11
    400,   # 12
    152,   # 13
    176,   # 14
    150,   # 15
    172,   # 16
    # ---- 左眉 (17-21) ----
    55,    # 17  左眉左端
    107,   # 18
    66,    # 19
    105,   # 20
    70,    # 21  左眉右端（近鼻）
    # ---- 右眉 (22-26) ----
    300,   # 22  右眉左端（近鼻）
    334,   # 23
    296,   # 24
    336,   # 25
    285,   # 26  右眉右端
    # ---- 鼻梁 (27-30) ----
    168,   # 27
    6,     # 28
    197,   # 29
    195,   # 30
    # ---- 鼻尖 (31-35) ----
    5,     # 31
    4,     # 32  鼻尖
    1,     # 33
    98,    # 34
    327,   # 35
    # ---- 左眼 (36-41): 外眼角→上睑→内眼角→下睑→外眼角 ----
    33,    # 36  外眼角
    160,   # 37  上睑外侧
    158,   # 38  上睑内侧
    133,   # 39  内眼角
    153,   # 40  下睑内侧
    144,   # 41  下睑外侧
    # ---- 右眼 (42-47): 外眼角→上睑→内眼角→下睑→外眼角 ----
    263,   # 42  外眼角
    386,   # 43  上睑外侧
    385,   # 44  上睑内侧
    362,   # 45  内眼角
    373,   # 46  下睑内侧
    374,   # 47  下睑外侧
    # ---- 嘴外轮廓 (48-59): 顺时针从左侧嘴角 ----
    61,    # 48  左嘴角
    40,    # 49
    37,    # 50
    0,     # 51  上唇中点
    267,   # 52
    270,   # 53
    291,   # 54  右嘴角
    321,   # 55
    314,   # 56
    17,    # 57  下唇中点
    84,    # 58
    82,    # 59
    # ---- 嘴内轮廓 (60-67): 顺时针从左侧 ----
    78,    # 60
    81,    # 61
    13,    # 62
    311,   # 63
    308,   # 64
    402,   # 65
    14,    # 66
    178,   # 67
]

assert len(MP_68_MAP) == 68, f"MP_68_MAP must have 68 entries, got {len(MP_68_MAP)}"


def mp_to_68_marks(landmarks, img_w: int, img_h: int) -> np.ndarray:
    """将 MediaPipe NormalizedLandmark 列表转为 (68, 2) 像素坐标数组。

    Args:
        landmarks: 478 个 NormalizedLandmark 的列表（MediaPipe 输出）
        img_w: 图像宽度（像素）
        img_h: 图像高度（像素）

    Returns:
        np.ndarray, shape (68, 2), dtype float32, 像素坐标
    """
    marks = np.zeros((68, 2), dtype=np.float32)
    for i68, mp_idx in enumerate(MP_68_MAP):
        lm = landmarks[mp_idx]
        marks[i68, 0] = lm.x * img_w
        marks[i68, 1] = lm.y * img_h
    return marks


def mp_extract_head_pose(transform_matrix) -> dict:
    """从 MediaPipe 4x4 面部变换矩阵提取头部姿态角度。

    Args:
        transform_matrix: shape (4, 4) 的 numpy 数组，
                         来自 FaceLandmarkerResult.facial_transformation_matrixes[i]

    Returns:
        dict: {"pitch": float, "yaw": float, "roll": float, "confidence": float}
    """
    if transform_matrix is None:
        return {"pitch": 0.0, "yaw": 0.0, "roll": 0.0, "confidence": 0.0}

    R = np.array(transform_matrix[0:3, 0:3], dtype=np.float64)

    sy = np.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
    singular = sy < 1e-6

    if not singular:
        pitch = np.arctan2(R[2, 1], R[2, 2])
        yaw = np.arctan2(-R[2, 0], sy)
        roll = np.arctan2(R[1, 0], R[0, 0])
    else:
        pitch = np.arctan2(-R[1, 2], R[1, 1])
        yaw = np.arctan2(-R[2, 0], sy)
        roll = 0.0

    pitch_deg = float(np.degrees(pitch))
    yaw_deg = float(np.degrees(yaw))
    roll_deg = float(np.degrees(roll))

    angle_magnitude = np.sqrt(pitch_deg ** 2 + yaw_deg ** 2 + roll_deg ** 2)
    confidence = float(np.clip(1.0 - angle_magnitude / 90.0, 0.0, 1.0))

    return {"pitch": pitch_deg, "yaw": yaw_deg, "roll": roll_deg, "confidence": confidence}


def mp_get_face_bbox(landmarks, img_w: int, img_h: int,
                     margin: float = 0.05) -> np.ndarray:
    """从 MediaPipe landmarks 计算紧密人脸边界框。

    Args:
        landmarks: 478 个 NormalizedLandmark 的列表
        img_w: 图像宽度
        img_h: 图像高度
        margin: 边距比例（默认 0.05）

    Returns:
        np.ndarray: [x1, y1, x2, y2] 像素坐标
    """
    xs = [lm.x for lm in landmarks]
    ys = [lm.y for lm in landmarks]

    x_min = max(0.0, min(xs) - margin)
    y_min = max(0.0, min(ys) - margin)
    x_max = min(1.0, max(xs) + margin)
    y_max = min(1.0, max(ys) + margin)

    return np.array([
        x_min * img_w,
        y_min * img_h,
        x_max * img_w,
        y_max * img_h,
    ], dtype=np.float32)
