"""
状态估计模块数据结构定义 - Data Contracts for State Estimation Module

定义本模块使用的核心数据结构，包括：
1. FocusResultData - SEI-01接口：专注度评分结果
2. MonitorMode - 监督模式枚举
3. SessionInfo - 会话信息
4. WarnInfo - 告警信息
5. FeatureData - 特征数据（来自特征提取模块）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class MonitorMode(Enum):
    """
    监督模式枚举
    
    CLASS: 网课模式 - 常规网课监控，评分策略相对宽松
    EXAM: 考试模式 - 考试场景监控，评分策略更严格
    """
    CLASS = "class"
    EXAM = "exam"


@dataclass(frozen=True)
class WarnInfo:
    """
    告警信息数据结构

    Attributes:
        warn_type: 告警类型（低分告警、离席、多人、姿态异常、行为异常、表情异常）
        detail: 告警详情描述
    """
    warn_type: str
    detail: str


@dataclass(frozen=True)
class FocusResultData:
    """
    SEI-01接口数据结构：专注度评分结果
    
    调用时机：每完成一次帧级评分计算后输出
    
    Attributes:
        timestamp: 当前帧时间戳
        session_id: 当前会话ID
        head_pose_score: 头部姿态综合分 [0, 100]
        behavior_score: 行为动作综合分 [0, 100]
        expression_score: 表情综合分 [0, 100]
        evidence_score: 证据理论融合评分 [0, 100]
        people_score: 人数项评分 [0, 100]
        final_focus_score: 最终专注度评分 [0, 100]
        is_force_zero: 是否因累计异常强制置0
        warn_msg: 告警信息（可选）
    """
    timestamp: float
    session_id: str
    head_pose_score: float
    behavior_score: float
    expression_score: float
    evidence_score: float
    people_score: float
    final_focus_score: float
    is_force_zero: bool
    warn_msg: Optional[WarnInfo] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，便于序列化传输"""
        return {
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "head_pose_score": self.head_pose_score,
            "behavior_score": self.behavior_score,
            "expression_score": self.expression_score,
            "evidence_score": self.evidence_score,
            "people_score": self.people_score,
            "final_focus_score": self.final_focus_score,
            "is_force_zero": self.is_force_zero,
            "warn_info": {
                "type": self.warn_msg.warn_type,
                "detail": self.warn_msg.detail,
            } if self.warn_msg else None,
        }


@dataclass
class SessionInfo:
    """
    会话信息数据结构
    
    Attributes:
        session_id: 会话唯一标识
        mode: 监督模式（class/exam）
        start_time: 会话开始时间戳
        end_time: 会话结束时间戳（未结束时为None）
        warn_threshold: 告警阈值 [0, 100]
        is_running: 会话是否正在运行
        total_frames: 处理的总帧数
        abnormal_event_count: 异常事件计数
    """
    session_id: str
    mode: MonitorMode
    start_time: float
    end_time: Optional[float] = None
    warn_threshold: float = 60.0
    is_running: bool = True
    total_frames: int = 0
    abnormal_event_count: int = 0


@dataclass(frozen=True)
class FeatureData:
    """
    特征数据结构（来自特征提取模块，对应 FEI-01 接口）

    仅当 owner_face_id != -1 时，特征提取模块才通过
    on_features_extracted() 发送本数据；无人脸时不发送。

    每个子特征均为 {"value": ..., "confidence": float} 结构，
    其中 head_pose 特殊，为 {pitch, yaw, roll, confidence}。

    Attributes:
        timestamp: 帧时间戳
        face_id: 人脸ID（对应 owner_face_id）
        head_pose: 头部姿态 {pitch, yaw, roll, confidence}
        eye_state: 眼部状态 {value: int(0=open,1=closed), confidence}
        is_looking_screen: 注视屏幕 {value: bool, confidence}
        attention_state: 注意力状态 {value: int(0=focused,1=distracted,2=sleepy,3=absent), confidence}
        face_distance_state: 人脸距离 {value: int(0=normal,1=too_far,2=too_close), confidence}
        is_yawning: 哈欠检测 {value: bool, confidence}
    """
    timestamp: float
    face_id: int
    head_pose: Dict[str, Any]
    eye_state: Dict[str, Any]
    is_looking_screen: Dict[str, Any]
    attention_state: Dict[str, Any]
    face_distance_state: Dict[str, Any]
    is_yawning: Dict[str, Any]


@dataclass
class EstimationStats:
    """
    状态估计统计信息
    
    Attributes:
        total_frames_processed: 处理的总帧数
        avg_focus_score: 平均专注度评分
        total_abnormal_events: 异常事件总数
        current_session_id: 当前会话ID（如有）
    """
    total_frames_processed: int = 0
    avg_focus_score: float = 0.0
    total_abnormal_events: int = 0
    current_session_id: Optional[str] = None
