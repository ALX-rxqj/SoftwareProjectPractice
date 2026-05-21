"""
Feature Extraction与Preprocessing集成演示

演示如何将Preprocessing输出的数据与Feature Extraction对接，
实现完整的从视频输入到特征输出的流程。

使用示例：
    # 从摄像头读取数据
    python -m src.feature_extraction.handoff_demo --camera 0
    
    # 从视频文件读取数据
    python -m src.feature_extraction.handoff_demo --video video.mp4
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Feature Extraction与Preprocessing集成演示")
    parser.add_argument("--camera", type=int, default=0, help="摄像头设备编号")
    parser.add_argument("--video", type=str, default="", help="本地视频文件路径")
    parser.add_argument("--duration", type=int, default=30, help="运行时长（秒）")
    parser.add_argument(
        "--enable-registration",
        action="store_true",
        help="是否进行人脸注册演示",
    )
    parser.add_argument(
        "--monitor-registered",
        action="store_true",
        help="是否仅监测已注册的人脸",
    )
    return parser


def _make_demo_frames() -> List[np.ndarray]:
    """生成演示用的虚拟帧。"""
    frames: List[np.ndarray] = []
    base = np.tile(np.arange(160, dtype=np.uint8), (160, 1))
    for shift in [0, 16, 32, 48]:
        shifted = np.roll(base, shift=shift, axis=1)
        frame = np.stack([shifted, shifted, shifted], axis=-1)
        frames.append(frame)
    return frames


def main() -> int:
    """主演示流程。"""
    args = build_parser().parse_args()
    
    # 添加项目根目录到Python路径
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # 导入模块
    try:
        from src.preprocessing import PreprocessingService
        from src.feature_extraction import FeatureExtractionService
    except ImportError as e:
        print(f"错误: 无法导入必需模块 - {e}")
        print(f"项目根目录: {project_root}")
        print(f"Python路径: {sys.path}")
        return 1
    # 项目根目录
    project_root = Path(__file__).resolve().parents[2]
    
    # 统计数据
    ui_count = 0
    feature_count = 0
    scoring_count = 0
    feature_packets = []
    scoring_outputs = []
    
    # ========== Preprocessing 回调 ==========
    def on_ui_packet(packet: Dict[str, Any]) -> None:
        """UI层数据包回调（从preprocessing）。"""
        nonlocal ui_count
        ui_count += 1
        packet_type = packet.get("type", "")
        faces_count = len(packet.get("faces", []))
        print(
            f"[PREP-UI] ts={packet['timestamp']:.3f} "
            f"faces={faces_count} "
            f"face_ids={[f.get('face_id') for f in packet.get('faces', [])]}"
        )
    
    def on_camera_list(camera_list: List[Dict[str, Any]]) -> None:
        """摄像头列表回调（从preprocessing）。"""
        print(f"[PREP-CAMERAS] 可用摄像头: {camera_list}")
    
    def on_log(message: str) -> None:
        """Preprocessing日志回调。"""
        print(f"[PREP-LOG] {message}")
    
    # ========== Feature Extraction 回调 ==========
    def on_scoring_result(output: Dict[str, Any]) -> None:
        """评分结果回调（从feature_extraction）。"""
        nonlocal scoring_count
        scoring_count += 1
        scoring_outputs.append(output)
        
        timestamp = output.get("timestamp", 0.0)
        face_id = output.get("face_id", "?")
        features = output.get("features", {})
        
        head_pose = features.get("head_pose", {})
        attention = features.get("attention_state", {})
        eye_state = features.get("eye_state", {})
        is_yawning = features.get("is_yawning", {})
        
        eye_text = "闭眼" if eye_state.get("value") == 1 else "睁眼"
        att_value = {0: "专注", 1: "不专注", 2: "偏离"}.get(
            attention.get("value"), "?"
        )
        yawn_text = "是" if is_yawning.get("value") else "否"
        
        print(
            f"[FEAT-OUT] ts={timestamp:.3f} "
            f"face_id={face_id} "
            f"pitch={head_pose.get('pitch', 0):.1f}° "
            f"yaw={head_pose.get('yaw', 0):.1f}° "
            f"roll={head_pose.get('roll', 0):.1f}° "
            f"eye={eye_text} "
            f"att={att_value} "
            f"yawn={yawn_text}"
        )
    
    def on_feature_packet(packet: Dict[str, Any]) -> None:
        """特征帧数据包回调（从preprocessing）。"""
        nonlocal feature_count
        feature_count += 1
        feature_packets.append(packet)
        
        timestamp = packet.get("timestamp", 0.0)
        faces_count = len(packet.get("faces", []))
        owner_face_id = packet.get("owner_face_id")
        face_matched = packet.get("face_matched", False)
        
        print(
            f"[PREP-FEAT] ts={timestamp:.3f} "
            f"owner_id={owner_face_id} "
            f"faces={faces_count} "
            f"matched={face_matched}"
        )
    
    def on_feature_log(message: str) -> None:
        """Feature Extraction日志回调。"""
        print(f"[FEAT-LOG] {message}")
    
    # ========== 初始化服务 ==========
    print("\n=== 初始化服务 ===")
    
    # 创建Feature Extraction Service
    feature_service = FeatureExtractionService(
        face_model_path=str(project_root / "src" / "feature_extraction" / "assets" / "face_detector.onnx"),
        mark_model_path=str(project_root / "src" / "feature_extraction" / "assets" / "face_landmarks.onnx"),
        scoring_callback=on_scoring_result,
        log_callback=on_feature_log,
    )
    print(f"✓ Feature Extraction Service 已初始化")
    
    # 创建Preprocessing Service，注册feature_extraction的回调
    preprocessing_service = PreprocessingService(
        ui_callback=on_ui_packet,
        feature_callback=feature_service.process_feature_packet,  # ← 关键对接点
        log_callback=on_log,
        camera_list_callback=on_camera_list,
    )
    print(f"✓ Preprocessing Service 已初始化")
    print(f"✓ Feature Callback已注册: {feature_service.process_feature_packet}")
    
    # ========== 人脸注册（可选） ==========
    if args.enable_registration:
        print("\n=== 人脸注册演示 ===")
        face_id = "demo_student_001"
        student_name = "演示学生"
        
        ack = preprocessing_service.register_face(
            student_name=student_name,
            frames=_make_demo_frames(),
            storage_type="temp",
            face_id=face_id,
        )
        print(f"[Register] {ack}")
        
        # 等待注册完成
        for _ in range(40):
            time.sleep(0.05)
        
        # 查询已注册人脸
        registry = preprocessing_service.query_face_registry()
        print(f"[Registry] {registry}")
        
        if args.monitor_registered:
            monitored_faces = [f["face_id"] for f in registry.get("faces", [])]
            print(f"[Monitored] 将监测: {monitored_faces}")
        else:
            monitored_faces = []
    else:
        monitored_faces = []
    
    # ========== 启动视频源 ==========
    print("\n=== 启动视频源 ===")
    try:
        if args.video:
            result = preprocessing_service.on_load_video(args.video)
            source_desc = f"视频文件: {args.video}"
        else:
            result = preprocessing_service.on_control_capture(
                device_id=args.camera,
                start=True,
                monitored_faces=monitored_faces,
            )
            source_desc = f"摄像头 #{args.camera}"
        
        if not result.get("success", False):
            print(f"✗ 启动失败: {result.get('msg')}")
            return 1
        
        print(f"✓ {source_desc} 已启动")
    except Exception as e:
        print(f"✗ 启动失败: {e}")
        return 1
    
    # ========== 处理循环 ==========
    print(f"\n=== 处理中（{args.duration}秒）===")
    print("Preprocessing流 -> Feature Extraction流 -> 评分系统\n")
    
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("\n（用户中断）")
    
    # ========== 停止处理 ==========
    print("\n=== 停止处理 ===")
    preprocessing_service.stop()
    print("✓ 已停止")
    
    # ========== 统计信息 ==========
    print("\n=== 统计信息 ===")
    print(f"Preprocessing UI包: {ui_count}")
    print(f"Preprocessing 特征包: {feature_count}")
    print(f"Feature Extraction 输出: {scoring_count}")
    
    feature_stats = feature_service.get_stats()
    print(f"\nFeature Extraction统计:")
    print(f"  - 接收的包: {feature_stats['packets_received']}")
    print(f"  - 处理成功: {feature_stats['packets_processed']}")
    print(f"  - 处理失败: {feature_stats['packets_failed']}")
    
    if scoring_outputs:
        print(f"\n最后一条特征提取结果示例:")
        last_output = scoring_outputs[-1]
        print(f"  - 时间戳: {last_output.get('timestamp', 0):.3f}")
        print(f"  - 人脸ID: {last_output.get('face_id')}")
        features = last_output.get('features', {})
        head_pose = features.get('head_pose', {})
        print(f"  - 头部姿态: "
              f"pitch={head_pose.get('pitch', 0):.1f}°, "
              f"yaw={head_pose.get('yaw', 0):.1f}°, "
              f"roll={head_pose.get('roll', 0):.1f}°")
    
    print("\n=== 演示完成 ===\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
