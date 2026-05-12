"""数据库模块 — SQLite 持久化层

提供:
- ConnectionManager:     数据库连接管理（单例）
- SchemaManager:         Schema 版本管理（单例）
- DatabaseService:       命令路由 + 查询服务（单例）
- DatabaseCommandAdapter: InterfaceManager 回调适配器
- 12 个 @dataclass:       业务表数据结构
"""

from .connection import ConnectionManager, connection_manager
from .schema import (
    SchemaManager,
    schema_manager,
    PreprocessingFrameRecord,
    FaceDetectionRecord,
    FaceImageIndexRecord,
    AbnormalFrameRecord,
    FrameFeatureRecord,
    HeadPoseScoreRecord,
    BehaviorScoreRecord,
    ExpressionScoreRecord,
    PeopleCountScoreRecord,
    FocusScoreRecord,
    SessionInfoRecord,
    AlarmEventRecord,
)
from .database_service import DatabaseService, database_service
from .command_adapter import DatabaseCommandAdapter

__all__ = [
    # 连接管理
    "ConnectionManager",
    "connection_manager",
    # Schema 管理
    "SchemaManager",
    "schema_manager",
    # 表结构 @dataclass
    "PreprocessingFrameRecord",
    "FaceDetectionRecord",
    "FaceImageIndexRecord",
    "AbnormalFrameRecord",
    "FrameFeatureRecord",
    "HeadPoseScoreRecord",
    "BehaviorScoreRecord",
    "ExpressionScoreRecord",
    "PeopleCountScoreRecord",
    "FocusScoreRecord",
    "SessionInfoRecord",
    "AlarmEventRecord",
    # 服务层
    "DatabaseService",
    "database_service",
    "DatabaseCommandAdapter",
]
