"""MediaPipe vs ONNX 眼睛关键点对比验证脚本。

同时运行 MediaPipe Face Landmarker 和 ONNX 68点模型，
在同一帧上绘制两者的眼睛关键点，方便对比精度差异。

MediaPipe: 绿色 — 478个密集关键点中提取的眼部轮廓
ONNX 68pt: 黄色 — 原有 6 点眼部轮廓

使用方法：
    python test/visualize_compare_models.py

按 ESC 退出，按 S 切换单模型显示。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from feature_extraction.face_detection import FaceDetector
from feature_extraction.mark_detection import MarkDetector
from feature_extraction.utils import refine
from feature_extraction.metrics import _compute_ear

# ---- MediaPipe 眼部关键点索引 (Face Landmarker 478点) ----
# 参考: https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/face_landmarker.md
MP_LEFT_EYE_CONTOUR = [
    33, 246, 161, 160, 159, 158, 157, 173,  # 上眼睑: 外眼角→内眼角
    133, 155, 154, 153, 145, 144, 163, 7,     # 下眼睑: 内眼角→外眼角
]
MP_RIGHT_EYE_CONTOUR = [
    362, 398, 384, 385, 386, 387, 388, 466,  # 上眼睑: 内眼角→外眼角
    263, 249, 390, 373, 374, 380, 381, 382,  # 下眼睑: 外眼角→内眼角
]
# MediaPipe 6点简化版（用于 EAR 计算，对应 iBUG 的 6 点格式）
MP_LEFT_EYE_6 = [33, 160, 158, 133, 153, 144]    # 外角, 上中左, 上中右, 内角, 下中左, 下中右
MP_RIGHT_EYE_6 = [362, 385, 387, 263, 373, 380]  # 内角, 上中左, 上中右, 外角, 下中左, 下中右

MP_COLOR = (0, 255, 128)   # 绿色 - MediaPipe
ONNX_COLOR = (0, 255, 255)  # 黄色 - ONNX 68pt
TEXT_COLOR = (255, 255, 255)


def draw_eye_from_landmarks(frame, landmarks, indices, color, label, offset_y=0):
    """从 MediaPipe NormalizedLandmark 列表绘制眼部轮廓。"""
    h, w = frame.shape[:2]
    pts = []
    for idx in indices:
        lm = landmarks[idx]
        px, py = int(lm.x * w), int(lm.y * h)
        pts.append((px, py))
        cv2.circle(frame, (px, py), 2, color, -1)

    # 绘制轮廓连线
    for i in range(len(pts)):
        cv2.line(frame, pts[i], pts[(i + 1) % len(pts)], color, 1)

    return pts


def draw_onnx_eye_landmarks(frame, marks, color):
    """从 ONNX 68点模型绘制左右眼 6 点轮廓。"""
    left_idx = list(range(36, 42))
    right_idx = list(range(42, 48))

    for idx in left_idx + right_idx:
        pt = tuple(marks[idx].astype(int))
        c = color if idx < 42 else (color[0], color[1] - 60, color[2])
        cv2.circle(frame, pt, 3, c, -1)

    # 左眼连线
    for i in range(6):
        p1 = tuple(marks[left_idx[i]].astype(int))
        p2 = tuple(marks[left_idx[(i + 1) % 6]].astype(int))
        cv2.line(frame, p1, p2, color, 1)
    # 右眼连线
    for i in range(6):
        p1 = tuple(marks[right_idx[i]].astype(int))
        p2 = tuple(marks[right_idx[(i + 1) % 6]].astype(int))
        cv2.line(frame, p1, p2, (color[0], color[1] - 60, color[2]), 1)


def compute_mp_ear(landmarks, img_w, img_h):
    """用 MediaPipe 关键点计算 EAR。"""
    def get_pt(idx):
        lm = landmarks[idx]
        return np.array([lm.x * img_w, lm.y * img_h])

    def ear_six(pts_indices):
        pts = [get_pt(i) for i in pts_indices]
        v1 = np.linalg.norm(pts[1] - pts[5])
        v2 = np.linalg.norm(pts[2] - pts[4])
        h = max(np.linalg.norm(pts[0] - pts[3]), 1e-6)
        return (v1 + v2) / (2.0 * h)

    left = ear_six(MP_LEFT_EYE_6)
    right = ear_six(MP_RIGHT_EYE_6)
    return {"left": left, "right": right, "value": (left + right) / 2.0}


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    assets_dir = os.path.join(project_root, "src", "feature_extraction", "assets")
    weights_dir = os.path.join(project_root, "weights")

    # ---- 初始化 ONNX 模型 ----
    face_detector = FaceDetector(os.path.join(assets_dir, "face_detector.onnx"))
    mark_detector = MarkDetector(os.path.join(assets_dir, "face_landmarks.onnx"))

    # ---- 初始化 MediaPipe Face Landmarker ----
    mp_options = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(
            model_asset_path=os.path.join(weights_dir, "face_landmarker.task")
        ),
        running_mode=vision.RunningMode.IMAGE,
        num_faces=1,
    )
    mp_landmarker = vision.FaceLandmarker.create_from_options(mp_options)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"摄像头: {frame_width}x{frame_height}")
    print("MediaPipe 绿色 | ONNX 黄色 | 按 S 切换模式 | ESC 退出")

    show_mode = 0  # 0=both, 1=MediaPipe only, 2=ONNX only

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 2)
        h, w = frame.shape[:2]
        t_start = time.time()

        # ==== MediaPipe 处理 ====
        if show_mode in (0, 1):
            mp_frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=mp_frame_rgb)
            mp_result = mp_landmarker.detect(mp_image)

            if len(mp_result.face_landmarks) > 0:
                landmarks = mp_result.face_landmarks[0]
                draw_eye_from_landmarks(frame, landmarks, MP_LEFT_EYE_CONTOUR, MP_COLOR, "MP Left")
                draw_eye_from_landmarks(frame, landmarks, MP_RIGHT_EYE_CONTOUR, MP_COLOR, "MP Right")
                mp_ear = compute_mp_ear(landmarks, w, h)
            else:
                mp_ear = None

        # ==== ONNX 处理 ====
        if show_mode in (0, 2):
            faces, _ = face_detector.detect(frame, 0.7)
            onnx_ear = None

            if len(faces) > 0:
                face = refine(faces, w, h, 0.15)[0]
                x1, y1, x2, y2 = face[:4].astype(int)
                try:
                    patch = frame[y1:y2, x1:x2]
                    marks = mark_detector.detect([patch])[0].reshape([68, 2])
                    marks *= (x2 - x1)
                    marks[:, 0] += x1
                    marks[:, 1] += y1

                    draw_onnx_eye_landmarks(frame, marks, ONNX_COLOR)
                    onnx_ear = _compute_ear(marks)
                    # 画人脸框
                    cv2.rectangle(frame, (x1, y1), (x2, y2), ONNX_COLOR, 1)
                except Exception:
                    pass

        # ==== 信息面板 ====
        t_elapsed = (time.time() - t_start) * 1000

        overlay = frame.copy()
        panel_h = 145
        cv2.rectangle(overlay, (5, 30), (340, 30 + panel_h), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.55, frame, 0.45, 0)

        y = 55
        cv2.putText(frame, f"Inference: {t_elapsed:.1f}ms", (15, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, TEXT_COLOR)
        y += 22

        if mp_ear:
            cv2.putText(frame, f"MP   L:{mp_ear['left']:.4f} R:{mp_ear['right']:.4f} Avg:{mp_ear['value']:.4f}",
                        (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, MP_COLOR)
        else:
            cv2.putText(frame, "MP   No face", (15, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 100, 100))
        y += 22

        if onnx_ear:
            cv2.putText(frame, f"ONNX L:{onnx_ear['left']:.4f} R:{onnx_ear['right']:.4f} Avg:{onnx_ear['value']:.4f}",
                        (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, ONNX_COLOR)
        else:
            cv2.putText(frame, "ONNX No face", (15, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 100, 100))
        y += 22

        mode_text = ["Both", "MediaPipe only", "ONNX only"][show_mode]
        cv2.putText(frame, f"Mode: {mode_text} (press S to switch)", (15, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, TEXT_COLOR)

        cv2.imshow("Model Comparison - MediaPipe(green) vs ONNX(yellow)", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            break
        elif key == ord('s') or key == ord('S'):
            show_mode = (show_mode + 1) % 3

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
