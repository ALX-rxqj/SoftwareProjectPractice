"""人脸头部姿态估计演示代码。

主要分为三步：
1. 在视频帧中检测并裁剪人脸。
2. 对人脸图像进行关键点检测。
3. 通过 PnP 求解头部姿态。
演示中使用的模型文件可以在 `assets/` 目录下找到

"""
from argparse import ArgumentParser
import time
import os

import cv2
import numpy as np
from types import SimpleNamespace

from .face_detection import FaceDetector
from .mark_detection import MarkDetector
from .pose_estimation import PoseEstimator
from .utils import refine
from .metrics import (
    _build_default_output,
    _build_prompt_output,
    _estimate_attention_state,
    _estimate_face_distance_state,
    _estimate_looking_screen,
    _estimate_yawning_state,
    _mouth_aspect_ratio,
    EyeStateEstimator,
)

# 当作为模块被导入时，提供一个默认的 args，避免在导入时解析命令行参数
args = SimpleNamespace(video=None, cam=0, face_id=0)


def _module_startup_prints():
    print(__doc__)
    print("OpenCV version: {}".format(cv2.__version__))


def send_to_scoring(output):
    """下游评分系统的回调占位函数。"""
    _ = output


# Helper functions moved to `metrics.py` and imported above for clarity.


def run():
    # 在开始估计前，先做一些初始化工作。
    
    # 获取模型文件的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(script_dir, "assets")

    # 初始化视频源，来源可以是摄像头或视频文件。
    video_src = args.cam if args.video is None else args.video
    cap = cv2.VideoCapture(video_src)
    print(f"Video source: {video_src}")

    # 获取帧尺寸，后续检测器会用到。
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 初始化人脸检测器。
    face_detector = FaceDetector(os.path.join(assets_dir, "face_detector.onnx"))

    # 初始化关键点检测器。
    mark_detector = MarkDetector(os.path.join(assets_dir, "face_landmarks.onnx"))

    # 初始化姿态估计器。
    pose_estimator = PoseEstimator(frame_width, frame_height)

    # 初始化眼睛状态估计器（自适应 EAR 基线）。
    eye_estimator = EyeStateEstimator()

    # 使用计时器统计性能。
    tm = cv2.TickMeter()
    output = _build_default_output(args.face_id)
    frame_count = 0
    mar = 0.0

    # 接下来开始逐帧处理
    while True:

        # 读取一帧
        frame_got, frame = cap.read()
        if frame_got is False:
            break

        # 如果来源是摄像头，则翻转为镜像效果
        if video_src == 0:
            frame = cv2.flip(frame, 2)

        # 第一步：从当前帧中检测人脸
        faces, _ = face_detector.detect(frame, 0.7)
        num_face_total = len(faces)

        # 是否检测到有效人脸
        if len(faces) > 0:
            tm.start()

            # 第二步：检测关键点。裁剪人脸区域后送入关键点检测器
            # 演示中只使用第一张人脸
            face = refine(faces, frame_width, frame_height, 0.15)[0]
            x1, y1, x2, y2 = face[:4].astype(int)
            patch = frame[y1:y2, x1:x2]

            # 执行关键点检测
            marks = mark_detector.detect([patch])[0].reshape([68, 2])

            # 将局部人脸区域中的坐标转换回整张图像坐标
            marks *= (x2 - x1)
            marks[:, 0] += x1
            marks[:, 1] += y1

            # 第三步：利用 68 个关键点估计头部姿态
            pose = pose_estimator.solve(marks)
            head_pose = pose_estimator.get_head_pose_data(marks, pose)["head_pose"]
            eye_state = eye_estimator.estimate(marks, face_id=args.face_id)
            is_looking_screen = _estimate_looking_screen(head_pose, eye_state)
            face_distance_state = _estimate_face_distance_state(
                face_box=face[:4],
                frame_shape=frame.shape,
            )
            is_yawning = _estimate_yawning_state(marks, head_pose=head_pose, eye_state=eye_state)
            attention_state = _estimate_attention_state(
                eye_state,
                is_looking_screen,
                face_distance_state,
                is_yawning,
                face_present=True,
            )

            output = _build_prompt_output(
                time.time(),
                int(args.face_id),
                head_pose,
                eye_state,
                is_looking_screen,
                attention_state,
                face_distance_state,
                is_yawning,
                int(num_face_total),
            )

            tm.stop()

            # 完成处理后，最直观的方式是在画面中实时绘制姿态结果

            # 是否显示姿态标注
            pose_estimator.visualize(frame, pose, color=(0, 255, 0))

            # 是否显示坐标轴
            # pose_estimator.draw_axes(frame, pose)

            # 是否显示关键点
            # mark_detector.visualize(frame, marks, color=(0, 255, 0))

            # 是否显示人脸框
            # face_detector.visualize(frame, faces)

        else:
            output = _build_default_output(args.face_id)
            output["features"]["num_face_total"] = {
                "value": int(num_face_total),
                "confidence": float(np.clip(1.0 if num_face_total > 0 else 0.0, 0.0, 1.0)),
            }

        send_to_scoring(output)

        # 在屏幕上绘制关键数值
        hp = output["features"]["head_pose"]
        eye = output["features"]["eye_state"]
        look = output["features"]["is_looking_screen"]
        attention = output["features"]["attention_state"]
        face_distance = output["features"]["face_distance_state"]
        yawning = output["features"]["is_yawning"]
        num_face_total_output = output["features"]["num_face_total"]
        eye_text = "Closed" if eye["value"] == 1 else "Open"
        look_text = "Looking" if look["value"] else "Not looking"
        cv2.rectangle(frame, (0, 30), (360, 182), (0, 0, 0), cv2.FILLED)
        cv2.putText(frame, f"Pitch: {hp['pitch']:.2f}", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))
        cv2.putText(frame, f"Yaw:   {hp['yaw']:.2f}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))
        cv2.putText(frame, f"Roll:  {hp['roll']:.2f}", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))
        cv2.putText(frame, f"Conf:  {hp['confidence']:.2f}", (10, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))
        cv2.putText(frame, f"Eye:   {eye_text} ({eye['confidence']:.2f})", (10, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))
        cv2.putText(frame, f"Look:  {look_text} ({look['confidence']:.2f})", (10, 150),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))
        cv2.putText(frame, f"Att:   {attention['value']} ({attention['confidence']:.2f})", (10, 170),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))
        cv2.putText(frame, f"Dist:  {face_distance['value']} ({face_distance['confidence']:.2f})", (190, 130),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))
        cv2.putText(frame, f"Yawn:  {int(yawning['value'])} ({yawning['confidence']:.2f})", (190, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))
        cv2.putText(frame, f"Faces: {num_face_total_output['value']} ({num_face_total_output['confidence']:.2f})", (190, 170),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))

        # 每 30 帧打印一次轻量级结构化输出。
        frame_count += 1
        if frame_count % 30 == 0:
            print({
                **output,
                "features": {
                    **output["features"],
                    "mar": mar,
                },
            })

        # 在屏幕上绘制 FPS
        cv2.rectangle(frame, (0, 0), (90, 30), (0, 0, 0), cv2.FILLED)
        cv2.putText(frame, f"FPS: {tm.getFPS():.0f}", (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))

        # 显示预览窗口
        cv2.imshow("Preview", frame)
        if cv2.waitKey(1) == 27:
            break


if __name__ == '__main__':
    # 解析用户输入参数，运行时才会执行
    parser = ArgumentParser()
    parser.add_argument("--video", type=str, default=None,
                        help="待处理的视频文件。")
    parser.add_argument("--cam", type=int, default=0,
                        help="摄像头编号。")
    parser.add_argument("--face-id", type=int, default=0,
                        help="输出中使用的主人脸 ID。")
    args = parser.parse_args()
    _module_startup_prints()
    run()
