from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List

import numpy as np

from .service import PreprocessingService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preprocessing handoff demo")
    parser.add_argument("--camera", type=int, default=0, help="Camera device id")
    parser.add_argument("--video", type=str, default="", help="Local video file path")
    parser.add_argument("--duration", type=int, default=10, help="Run duration in seconds")
    parser.add_argument("--register-name", type=str, default="Alice", help="Demo student name")
    parser.add_argument(
        "--storage-type",
        type=str,
        choices=["temp", "local"],
        default="temp",
        help="Registration storage type",
    )
    parser.add_argument(
        "--enable-registration",
        action="store_true",
        help="Run register_face and query_face_registry before capture",
    )
    parser.add_argument(
        "--monitor-registered",
        action="store_true",
        help="Use query_face_registry result as monitored_faces for capture",
    )
    parser.add_argument(
        "--real-registration",
        action="store_true",
        help="Use actual frame-based registration logic instead of demo mock embeddings",
    )
    return parser


def _make_demo_frames() -> List[np.ndarray]:
    frames: List[np.ndarray] = []
    base = np.tile(np.arange(160, dtype=np.uint8), (160, 1))
    for shift in [0, 16, 32, 48]:
        shifted = np.roll(base, shift=shift, axis=1)
        frame = np.stack([shifted, shifted, shifted], axis=-1)
        frames.append(frame)
    return frames


def main() -> int:
    args = build_parser().parse_args()

    project_root = Path(__file__).resolve().parents[2]
    yolo_config_dir = project_root / ".ultralytics"
    yolo_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(yolo_config_dir)

    ui_count = 0
    feature_count = 0
    registration_results = []
    queried_faces = []

    def on_ui_packet(packet):
        nonlocal ui_count
        packet_type = packet.get("type", "")
        if packet_type == "face_registration_result":
            registration_results.append(packet)
            print(f"[PRI-04] {packet}")
            return
        ui_count += 1
        print(
            f"[PRI-01] ts={packet['timestamp']:.3f} "
            f"faces={len(packet['faces'])} "
            f"ids={[face.get('face_id') for face in packet['faces']]}"
        )

    def on_feature_packet(packet):
        nonlocal feature_count
        feature_count += 1
        print(
            f"[PRI-02] ts={packet['timestamp']:.3f} "
            f"owner_face_id={packet['owner_face_id']} "
            f"face_matched={packet['face_matched']} "
            f"faces={len(packet['faces'])}"
        )

    def on_camera_list(camera_list):
        print(f"[PRI-03] camera_list={camera_list}")

    service = PreprocessingService(
        ui_callback=on_ui_packet,
        feature_callback=on_feature_packet,
        camera_list_callback=on_camera_list,
        log_callback=lambda message: print(f"[Log] {message}"),
    )

    if args.storage_type == "local":
        service.set_face_embedding_writer(lambda face_id, student_name, embeddings: True)
    if not args.real_registration:
        service._extract_embeddings_from_frames = lambda frames: [
            (np.linspace(0, 1, 512, dtype=np.float32), "frontal"),
            (np.linspace(1, 0, 512, dtype=np.float32), "left"),
            (np.roll(np.linspace(0, 1, 512, dtype=np.float32), 16), "right"),
            (np.roll(np.linspace(0, 1, 512, dtype=np.float32), 32), "down"),
        ]

    try:
        service.on_query_cameras()

        monitored_faces = []
        if args.enable_registration:
            face_id = f"{args.storage_type}_demo_001"
            ack = service.register_face(
                student_name=args.register_name,
                frames=_make_demo_frames(),
                storage_type=args.storage_type,
                face_id=face_id,
            )
            print("[Register ACK]", ack)

            for _ in range(40):
                if registration_results:
                    break
                time.sleep(0.05)

            registry_result = service.query_face_registry()
            queried_faces = registry_result.get("faces", [])
            print("[Registry]", registry_result)

            if args.monitor_registered:
                monitored_faces = [face["face_id"] for face in queried_faces]
                print("[Monitored Faces]", monitored_faces)

        if args.video:
            result = service.on_load_video(args.video)
        else:
            result = service.on_control_capture(
                device_id=args.camera,
                start=True,
                monitored_faces=monitored_faces,
            )

        print("[Start]", result)
        if not result.get("success", False):
            return 1

        time.sleep(max(args.duration, 1))
        print("[Status]", service.get_status())
        return 0
    except RuntimeError as exc:
        print("[Error]", str(exc))
        return 1
    except KeyboardInterrupt:
        print("\n[Stop] Interrupted by user")
        return 0
    finally:
        if not args.video:
            print("[Stop]", service.on_control_capture(device_id=args.camera, start=False))
        else:
            print("[Stop]", service.stop())
        print(
            f"[Summary] ui_packets={ui_count}, feature_packets={feature_count}, "
            f"registration_results={len(registration_results)}, registry_faces={len(queried_faces)}"
        )


if __name__ == "__main__":
    sys.exit(main())
