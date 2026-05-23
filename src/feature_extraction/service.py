"""
Feature Extraction Service - 与Preprocessing的数据对接层

本模块通过service类接收来自preprocessing的数据包(FeatureFramePacket)，
并调用IOInterface进行特征提取和分析。

主要功能：
- 接收preprocessing发送的feature callback数据
- 数据格式验证和适配
- 调用IOInterface进行处理
- 向下游评分系统发送结果

使用示例：
    # 1. 创建service实例
    service = FeatureExtractionService(
        face_model_path='assets/face_detector.onnx',
        mark_model_path='assets/face_landmarks.onnx',
        scoring_callback=on_scoring_result
    )
    
    # 2. 从preprocessing接收数据并处理
    service.process_feature_packet(feature_packet_dict)
    
    # 3. 在preprocessing中注册回调
    preprocessing_service = PreprocessingService(
        feature_callback=service.process_feature_packet
    )
"""

import os as _os
from typing import Callable, Dict, Any, Optional
import logging

from .io_interface import IOInterface

# 模型文件默认路径（相对于本模块的 assets/ 子目录）
_ASSETS_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'assets')

# 类型别名
ScoringCallback = Callable[[Dict[str, Any]], None]
LogCallback = Callable[[str], None]
# state callback: full feature_extraction output dict -> None
StateCallback = Callable[[Dict[str, Any]], None]


class FeatureExtractionService:
    """特征提取服务类，接收并处理来自preprocessing的数据包。

    attributes:
        io_interface: IOInterface实例，用于处理单条输入
        scoring_callback: 向下游评分系统发送结果的回调函数
        log_callback: 日志输出回调函数
    """

    def __init__(
        self,
        mp_model_path: str = _os.path.join(
            _os.path.dirname(_os.path.abspath(__file__)),
            '..', '..', 'weights', 'face_landmarker.task'
        ),
        scoring_callback: Optional[ScoringCallback] = None,
        log_callback: Optional[LogCallback] = None,
        state_callback: Optional[StateCallback] = None,
    ):
        """初始化特征提取service。

        Args:
            mp_model_path: MediaPipe Face Landmarker 模型路径
            scoring_callback: 评分系统回调函数，接收处理结果
            log_callback: 日志回调函数
        """
        self.io_interface = IOInterface(mp_model_path=mp_model_path)
        self.scoring_callback = scoring_callback or self._default_scoring_callback
        self.log_callback = log_callback or (lambda msg: None)
        # 可选的状态估计回调（接收 FEI-01 格式的数据）
        self.state_callback = state_callback
        self.stats = {
            'packets_received': 0,
            'packets_processed': 0,
            'packets_failed': 0,
        }
    
    def _default_scoring_callback(self, output: Dict[str, Any]) -> None:
        """默认的评分回调函数（占位）。"""
        pass
    
    def process_feature_packet(self, packet: Dict[str, Any]) -> None:
        """处理来自preprocessing的单条特征帧数据包。
        
        这是feature_callback的回调函数实现，接收来自PreprocessingService
        的FeatureFramePacket转换后的字典。
        
        Args:
            packet: 特征帧数据包字典，包含：
                - timestamp: float - 帧时间戳
                - faces: List[Dict] - 检测到的人脸列表，每个包含:
                    - face_id: 人脸ID
                    - student_name: 学生名字
                    - face_roi: np.ndarray - 裁剪的人脸区域
                    - confidence: 置信度
                    - face_matched: 是否匹配
                - owner_face_id: 主人脸ID
                - frame: np.ndarray - 原始帧
                - face_matched: bool - 是否匹配（可选）
        """
        self.stats['packets_received'] += 1
        
        try:
            # 验证必需字段
            if not isinstance(packet, dict):
                raise ValueError('packet必须是字典类型')
            
            required_fields = ['timestamp', 'faces', 'owner_face_id', 'frame']
            for field in required_fields:
                if field not in packet:
                    raise ValueError(f'缺少必需字段: {field}')
            
            # 验证faces列表
            faces = packet.get('faces', [])
            if not isinstance(faces, list):
                raise ValueError('faces必须是列表类型')
            
            # 为faces列表中的每个人脸提取必需字段
            for face in faces:
                if 'face_id' not in face or 'face_roi' not in face:
                    raise ValueError('faces列表中的每个元素必须包含face_id和face_roi')
            
            # 记录日志
            self._log_packet_info(packet)
            
            # 构造一个 wrapper，在调用 scoring 回调的同时把 FEI-01 格式数据发送给状态估计模块
            def _send_wrapper(output: Dict[str, Any]) -> None:
                if isinstance(output, dict):
                    output.setdefault('face_matched', bool(packet.get('face_matched', False)))

                # 先回调评分/下游，输出保持完整结构：timestamp / face_id / face_matched / features
                try:
                    self.scoring_callback(output)
                except Exception:
                    # 保持容错，不阻塞后续处理
                    self.log_callback('scoring_callback 处理失败')

                # 同步发送给状态估计（转发完整输出字典，由状态估计模块自行解析 features）
                try:
                    if self.state_callback and isinstance(output, dict):
                        # face_matched 已在 output 中保留，状态估计模块仅需要提取 features
                        self.state_callback(output)
                except Exception:
                    self.log_callback('向状态估计转发时发生错误')

            self.io_interface.process(
                record=packet,
                send_to_scoring=_send_wrapper
            )
            
            self.stats['packets_processed'] += 1
            
        except Exception as e:
            self.stats['packets_failed'] += 1
            error_msg = f'处理特征包失败: {str(e)}'
            self.log_callback(error_msg)
            # 不抛出异常，只记录日志，允许继续处理其他包
    
    def _log_packet_info(self, packet: Dict[str, Any]) -> None:
        """记录数据包信息。"""
        timestamp = packet.get('timestamp', 0.0)
        faces_count = len(packet.get('faces', []))
        owner_face_id = packet.get('owner_face_id')
        face_matched = packet.get('face_matched', False)
        
        msg = (
            f'特征包接收: ts={timestamp:.3f}, '
            f'faces={faces_count}, '
            f'owner_id={owner_face_id}, '
            f'matched={face_matched}'
        )
        self.log_callback(msg)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息。
        
        Returns:
            包含处理统计的字典
        """
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """重置统计计数。"""
        for key in self.stats:
            if isinstance(self.stats[key], int):
                self.stats[key] = 0
