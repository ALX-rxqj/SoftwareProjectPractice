"""数据库表结构定义 + Schema 版本管理

包含 3 张核心表的 @dataclass 结构，以及 SchemaManager 单例用于建表和版本管理。
"""

import sqlite3
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 表 1: 会话信息表 sessions
# ============================================================
@dataclass
class SessionRecord:
    session_id: str
    mode: str  # "class" | "exam"
    start_time: float
    student_id: Optional[str] = None
    end_time: Optional[float] = None
    avg_focus_score: Optional[float] = None
    abnormal_event_count: int = 0


# ============================================================
# 表 2: 专注度评分记录表 focus_records
# ============================================================
@dataclass
class FocusRecord:
    session_id: str
    timestamp: float
    head_pose_score: float = 0.0
    behavior_score: float = 0.0
    expression_score: float = 0.0
    evidence_score: float = 0.0
    people_score: float = 0.0
    final_focus_score: float = 0.0
    is_force_zero: bool = False
    id: Optional[int] = None
    date: str = ""
    time: str = ""


# ============================================================
# 表 3: 告警事件记录表 alert_events
# ============================================================
@dataclass
class AlertEventRecord:
    session_id: str
    timestamp: float
    alert_type: str
    detail: str = ""
    frame_timestamp: Optional[float] = None
    id: Optional[int] = None


# ============================================================
# Schema 版本管理
# ============================================================
class SchemaManager:
    """数据库 Schema 版本管理器（单例）"""

    _instance: Optional["SchemaManager"] = None
    CURRENT_VERSION: int = 1

    _DDL = {
        1: [
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id      TEXT PRIMARY KEY,
                student_id      TEXT,
                mode            TEXT NOT NULL CHECK(mode IN ('class', 'exam')),
                start_time      REAL NOT NULL,
                end_time        REAL,
                avg_focus_score REAL,
                abnormal_event_count INTEGER DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS focus_records (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                timestamp       REAL NOT NULL,
                date            TEXT NOT NULL,
                time            TEXT NOT NULL,
                head_pose_score REAL,
                behavior_score  REAL,
                expression_score REAL,
                evidence_score  REAL,
                people_score    REAL,
                final_focus_score REAL,
                is_force_zero   INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS alert_events (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                timestamp       REAL NOT NULL,
                alert_type      TEXT NOT NULL,
                detail          TEXT,
                frame_timestamp REAL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_start_time
                ON sessions(start_time)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_mode
                ON sessions(mode)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_student_id
                ON sessions(student_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_focus_records_session_time
                ON focus_records(session_id, timestamp)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_alert_events_session
                ON alert_events(session_id)
            """,
        ]
    }

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

    def ensure_schema(self, connection: sqlite3.Connection) -> None:
        """执行建表与索引创建（幂等）

        Args:
            connection: sqlite3.Connection，由 ConnectionManager 提供
        """
        statements = self._DDL.get(SchemaManager.CURRENT_VERSION, [])
        cursor = connection.cursor()
        for stmt in statements:
            try:
                cursor.execute(stmt)
            except sqlite3.Error as e:
                print(f"[SchemaManager] DDL 执行失败: {e}\n  SQL: {stmt[:100]}...")
                raise
        connection.commit()
        print(f"[SchemaManager] Schema v{SchemaManager.CURRENT_VERSION} 就绪")


schema_manager = SchemaManager()
