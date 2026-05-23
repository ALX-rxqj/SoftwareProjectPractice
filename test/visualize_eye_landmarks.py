"""眼睛关键点可视化验证脚本。

打开摄像头，检测人脸并绘制眼睛区域的 12 个关键点（左眼 36-41，右眼 42-47），
同时显示 EAR 值和睁眼/闭眼判定结果。

使用方法：
    python test/visualize_eye_landmarks.py

按 ESC 退出。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import cv2
import numpy as np

from feature_extraction.face_detection import FaceDetector
from feature_extraction.mark_detection import MarkDetector
from feature_extraction.utils import refine
from feature_extraction.metrics import _compute_ear, _eye_aspect_ratio

# 颜色定义
LEFT_EYE_COLOR = (0, 255, 255)   # 黄色 - 左眼
RIGHT_EYE_COLOR = (0, 255, 128)  # 绿色 - 右眼
HIGHLIGHT_COLOR = (0, 0, 255)    # 红色 - 当前点高亮

LEFT_EYE_IDX = list(range(36, 42))   # 左眼 6 个点
RIGHT_EYE_IDX = list(range(42, 48))  # 右眼 6 个点


def draw_eye_landmarks(frame, marks):
    """在帧上绘制眼睛关键点及连线。"""
    h, w = frame.shape[:2]

    # 绘制左眼轮廓
    for i in range(6):
        p1 = tuple(marks[LEFT_EYE_IDX[i]].astype(int))
        p2 = tuple(marks[LEFT_EYE_IDX[(i + 1) % 6]].astype(int))
        cv2.line(frame, p1, p2, LEFT_EYE_COLOR, 2)
        cv2.circle(frame, p1, 3, LEFT_EYE_COLOR, -1)

    # 绘制右眼轮廓
    for i in range(6):
        p1 = tuple(marks[RIGHT_EYE_IDX[i]].astype(int))
        p2 = tuple(marks[RIGHT_EYE_IDX[(i + 1) % 6]].astype(int))
        cv2.line(frame, p1, p2, RIGHT_EYE_COLOR, 2)
        cv2.circle(frame, p1, 3, RIGHT_EYE_COLOR, -1)

    # 在眼睛关键点旁边标注索引
    for idx in LEFT_EYE_IDX + RIGHT_EYE_IDX:
        pt = tuple(marks[idx].astype(int))
        color = LEFT_EYE_COLOR if idx < 42 else RIGHT_EYE_COLOR
        cv2.putText(frame, str(idx), (pt[0] + 5, pt[1] - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)


def draw_ear_info(frame, ear_data, eye_state_label):
    """在帧上绘制 EAR 数值面板。"""
    left_ear = ear_data["left"]
    right_ear = ear_data["right"]
    avg_ear = ear_data["value"]

    # 半透明背景面板
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 30), (250, 130), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)

    cv2.putText(frame, f"Left EAR:  {left_ear:.4f}", (20, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0))
    cv2.putText(frame, f"Right EAR: {right_ear:.4f}", (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 128))
    cv2.putText(frame, f"Avg EAR:  {avg_ear:.4f}", (20, 105),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255))
    cv2.putText(frame, f"State: {eye_state_label}", (20, 128),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0) if "Open" in eye_state_label else (0, 0, 255))

    return frame


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    assets_dir = os.path.join(project_root, "src", "feature_extraction", "assets")

    face_detector = FaceDetector(os.path.join(assets_dir, "face_detector.onnx"))
    mark_detector = MarkDetector(os.path.join(assets_dir, "face_landmarks.onnx"))

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"摄像头分辨率: {frame_width}x{frame_height}")
    print("按 ESC 退出")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 2)

        faces, _ = face_detector.detect(frame, 0.7)

        if len(faces) > 0:
            face = refine(faces, frame_width, frame_height, 0.15)[0]
            x1, y1, x2, y2 = face[:4].astype(int)

            try:
                patch = frame[y1:y2, x1:x2]
                marks = mark_detector.detect([patch])[0].reshape([68, 2])
                marks *= (x2 - x1)
                marks[:, 0] += x1
                marks[:, 1] += y1

                # 在人脸框内显示人脸框
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 1)

                # 绘制眼睛关键点
                draw_eye_landmarks(frame, marks)

                # 计算 EAR
                ear_data = _compute_ear(marks)
                avg_ear = ear_data["value"]

                # 睁眼/闭眼判定
                if avg_ear < 0.17:
                    eye_label = "Closed"
                elif avg_ear < 0.22:
                    eye_label = f"Open (borderline)"
                else:
                    eye_label = "Open"

                frame = draw_ear_info(frame, ear_data, eye_label)

            except Exception as e:
                cv2.putText(frame, f"Error: {e}", (20, 250),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255))

        else:
            cv2.putText(frame, "No face detected", (20, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255))

        cv2.imshow("Eye Landmarks Verification", frame)
        if cv2.waitKey(1) == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
