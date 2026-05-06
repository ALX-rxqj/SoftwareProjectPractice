from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from src.preprocessing.service import PreprocessingService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run preprocessing module demo")
    parser.add_argument("--camera", type=int, default=0, help="Camera device id")
    parser.add_argument("--video", type=str, default="", help="Local video file path")
    parser.add_argument("--duration", type=int, default=10, help="Run duration in seconds")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    yolo_config_dir = project_root / ".ultralytics"
    yolo_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(yolo_config_dir)

    ui_count = 0
    feature_count = 0

    def on_video_frame_received(frame, faces, timestamp):
        nonlocal ui_count
        ui_count += 1
        print(f"[UI] ts={timestamp:.3f} faces={len(faces)}")

    def on_frame_received(data):
        nonlocal feature_count
        feature_count += 1
        print(
            f"[Feature] ts={data['timestamp']:.3f} "
            f"owner_face_id={data['owner_face_id']} faces={len(data['faces'])}"
        )

    def on_camera_list_received(camera_list):
        print(f"[CameraList] devices={len(camera_list)} {camera_list}")

    service = PreprocessingService(
        log_callback=lambda message: print(f"[Log] {message}"),
        video_frame_callback=on_video_frame_received,
        frame_received_callback=on_frame_received,
        camera_list_callback=on_camera_list_received,
    )

    try:
        service.on_query_cameras()
        if args.video:
            result = service.on_load_video(args.video)
        else:
            result = service.on_control_capture(device_id=args.camera, start=True)

        print("[Start]", result)
        if not result.get("success", False):
            return 1

        time.sleep(max(args.duration, 1))
        print("[Status]", service.get_status())
        return 0
    except KeyboardInterrupt:
        print("\n[Stop] Interrupted by user")
        return 0
    finally:
        print("[Stop]", service.on_control_capture(device_id=args.camera, start=False))
        print(f"[Summary] ui_packets={ui_count}, feature_packets={feature_count}")


if __name__ == "__main__":
    sys.exit(main())
