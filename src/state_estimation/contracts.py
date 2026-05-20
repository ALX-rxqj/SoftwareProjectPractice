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
from typing import Any, Dict, Optional, Tuple


class MonitorMode(Enum):
    """
    监督模式枚举

    CLASS: 网课模式 - 常规网课监控，评分策略相对宽松
    EXAM: 考试模式 - 考试场景监控，评分策略更严格
    """
    CLASS = "class"
    EXAM = "exam"


# --- 告警类型常量 ---
WARN_NO_FACE = "no_face"
WARN_MULTI_FACE = "multi_face"
WARN_LOW_EVIDENCE = "low_evidence"
WARN_LOW_HEAD_POSE = "low_head_pose"
WARN_LOW_BEHAVIOR = "low_behavior"
WARN_LOW_EXPRESSION = "low_expression"

# 告警优先级映射 — 数值越小优先级越高
_ALERT_PRIORITY = {
    WARN_NO_FACE: 1,
    WARN_MULTI_FACE: 1,  # 人数异常同一优先级
    WARN_LOW_EVIDENCE: 2,
    WARN_LOW_HEAD_POSE: 3,
    WARN_LOW_BEHAVIOR: 4,
    WARN_LOW_EXPRESSION: 5,
}

# 降采样窗口占比阈值
ANOMALY_RATIO_THRESHOLD = 0.5

# 低分告警阈值
LOW_SCORE_THRESHOLD = 50.0


def alert_priority(warn_type: str) -> int:
    """返回告警类型优先级（数值越小越高），未知类型返回999"""
    return _ALERT_PRIORITY.get(warn_type, 999)


def pick_highest_alert(candidates: Tuple[WarnInfo, ...]) -> Optional[WarnInfo]:
    """从候选告警中按优先级选出最高的"""
    if not candidates:
        return None
    best = candidates[0]
    best_pri = alert_priority(best.warn_type)
    for c in candidates[1:]:
        pri = alert_priority(c.warn_type)
        if pri < best_pri:
            best = c
            best_pri = pri
    return best


@dataclass(frozen=True)
class WarnInfo:
    """
    告警信息数据结构

    Attributes:
        warn_type: 告警类型（no_face, multi_face, low_evidence, low_head_pose, low_behavior, low_expression）
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
        is_over_threshold: 人数异常累计次数是否超过阈值
        warn_candidates: 本帧触发的所有告警候选（按优先级排列，空元组表示无告警）
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
    is_over_threshold: bool = False
    warn_candidates: Tuple[WarnInfo, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，便于序列化传输"""
        primary = pick_highest_alert(self.warn_candidates)
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
            "is_over_threshold": self.is_over_threshold,
            "warn_info": {
                "type": primary.warn_type,
                "detail": primary.detail,
            } if primary else None,
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
        num_face_total: 画面人脸总数 {value: int, confidence}
    """
    timestamp: float
    face_id: int
    head_pose: Dict[str, Any]
    eye_state: Dict[str, Any]
    is_looking_screen: Dict[str, Any]
    attention_state: Dict[str, Any]
    face_distance_state: Dict[str, Any]
    is_yawning: Dict[str, Any]
    num_face_total: Dict[str, Any] = field(default_factory=lambda: {"value": 1, "confidence": 1.0})
