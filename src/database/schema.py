"""数据库表结构定义 + Schema 版本管理

包含 12 张业务表的 @dataclass 结构，以及 SchemaManager 单例用于版本管理。
"""

from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 表 1: 预处理帧记录表
# ============================================================
@dataclass
class PreprocessingFrameRecord:
    id: Optional[int] = None
    timestamp: float = 0.0
    frame_index: int = 0
    video_source_type: str = ""
    frame_path: Optional[str] = None
    frame_status: str = "valid"
    anomaly_type: Optional[str] = None
    has_face: bool = False
    main_face_id: Optional[int] = None


# ============================================================
# 表 2: 人脸检测结果记录表
# ============================================================
@dataclass
class FaceDetectionRecord:
    id: Optional[int] = None
    timestamp: float = 0.0
    frame_index: int = 0
    face_id: int = 0
    bbox_x: int = 0
    bbox_y: int = 0
    bbox_w: int = 0
    bbox_h: int = 0
    is_main_face: bool = False
    face_count: int = 0


# ============================================================
# 表 3: 人脸图像索引表
# ============================================================
@dataclass
class FaceImageIndexRecord:
    id: Optional[int] = None
    timestamp: float = 0.0
    frame_index: int = 0
    face_id: int = 0
    image_path: Optional[str] = None
    image_width: int = 0
    image_height: int = 0
    color_format: str = ""


# ============================================================
# 表 4: 异常帧过滤记录表
# ============================================================
@dataclass
class AbnormalFrameRecord:
    id: Optional[int] = None
    timestamp: float = 0.0
    frame_index: int = 0
    anomaly_type: str = ""
    handle_method: str = ""
    log_description: str = ""


# ============================================================
# 表 5: 帧特征记录表
# ============================================================
@dataclass
class FrameFeatureRecord:
    id: Optional[int] = None
    session_id: str = ""
    frame_index: int = 0
    timestamp: float = 0.0
    face_id: int = 0
    head_pitch: float = 0.0
    head_yaw: float = 0.0
    head_roll: float = 0.0
    eye_state: str = ""
    expression_type: str = ""
    is_head_down: bool = False
    is_yawning: bool = False
    body_state: str = ""
    body_tilt: str = ""
    person_count: int = 0
    confidence: float = 0.0


# ============================================================
# 表 6: 头部姿态评分记录表
# ============================================================
@dataclass
class HeadPoseScoreRecord:
    id: Optional[int] = None
    timestamp: float = 0.0
    pitch_score: float = 0.0
    yaw_score: float = 0.0
    roll_score: float = 0.0
    weighted_average: float = 0.0


# ============================================================
# 表 7: 行为动作评分记录表
# ============================================================
@dataclass
class BehaviorScoreRecord:
    id: Optional[int] = None
    timestamp: float = 0.0
    eye_score: float = 0.0
    yawning_score: float = 0.0
    body_state_score: float = 0.0
    body_tilt_score: float = 0.0
    behavior_composite_score: float = 0.0


# ============================================================
# 表 8: 表情评分记录表
# ============================================================
@dataclass
class ExpressionScoreRecord:
    id: Optional[int] = None
    timestamp: float = 0.0
    expression_type: str = ""
    expression_composite_score: float = 0.0


# ============================================================
# 表 9: 人数评分记录表
# ============================================================
@dataclass
class PeopleCountScoreRecord:
    id: Optional[int] = None
    session_id: str = ""
    timestamp: float = 0.0
    face_count: int = 0
    people_score: float = 0.0
    cumulative_zero_count: int = 0


# ============================================================
# 表 10: 专注度评分记录表（当前 UI 查询使用）
# ============================================================
@dataclass
class FocusScoreRecord:
    id: Optional[int] = None
    session_id: str = ""
    timestamp: float = 0.0
    head_pose_score: float = 0.0
    behavior_score: float = 0.0
    expression_score: float = 0.0
    evidence_score: float = 0.0
    people_score: float = 0.0
    final_focus_score: float = 0.0
    is_force_zero: bool = False


# ============================================================
# 表 11: 会话信息表（当前 UI 查询使用）
# ============================================================
@dataclass
class SessionInfoRecord:
    id: Optional[int] = None
    session_id: str = ""
    start_time: str = ""
    end_time: str = ""
    mode: str = ""
    avg_focus_score: float = 0.0
    abnormal_event_count: int = 0


# ============================================================
# 表 12: 告警事件记录表
# ============================================================
@dataclass
class AlarmEventRecord:
    id: Optional[int] = None
    session_id: str = ""
    trigger_timestamp: float = 0.0
    alarm_type: str = ""
    alarm_detail: str = ""
    related_frame_timestamp: Optional[float] = None


# ============================================================
# Schema 版本管理
# ============================================================
class SchemaManager:
    """数据库 Schema 版本管理器（单例）"""

    _instance: Optional["SchemaManager"] = None
    CURRENT_VERSION: int = 0

    def __new__(cls) -> "SchemaManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

    def get_version(self) -> int:
        """返回当前 schema 版本号"""
        return SchemaManager.CURRENT_VERSION

    def ensure_schema(self) -> None:
        """Stub: 校验或初始化数据库表结构
        当前为占位实现，设计确定后实现建表与迁移逻辑。
        """
        print(f"[SchemaManager] Schema 校验 stub (v{SchemaManager.CURRENT_VERSION})")


schema_manager = SchemaManager()
