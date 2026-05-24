"""数据库表结构定义 + Schema 版本管理

包含 4 张核心表的 @dataclass 结构，以及 SchemaManager 单例用于建表和版本管理。
"""

from sqlcipher3 import dbapi2 as sqlite3
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
    face_id: Optional[str] = None
    end_time: Optional[float] = None
    avg_focus_score: Optional[float] = None
    abnormal_event_count: int = 0
    video_source_type: str = "camera"
    file_name: Optional[str] = None


# ============================================================
# 表 2: 专注度评分记录表 focus_records
# ============================================================
@dataclass
class FocusRecord:
    session_id: str
    timestamp: float
    head_pose_score: float = 0.0
    eye_score: float = 0.0
    yawn_score: float = 0.0
    distance_score: float = 0.0
    behavior_score: float = 0.0
    expression_score: float = 0.0
    evidence_score: float = 0.0
    people_score: float = 0.0
    final_focus_score: float = 0.0
    is_force_zero: bool = False
    is_over_threshold: bool = False
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
# 表 4: 已注册人脸表 registered_faces
# ============================================================
@dataclass
class RegisteredStudent:
    face_id: str
    student_name: str
    registered_at: float


@dataclass
class FaceEmbedding:
    face_id: str
    embedding: bytes
    pose_type: Optional[str] = None
    id: Optional[int] = None


# ============================================================
# Schema 版本管理
# ============================================================
class SchemaManager:
    """数据库 Schema 版本管理器（单例）"""

    _instance: Optional["SchemaManager"] = None
    CURRENT_VERSION: int = 6

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
            """
            CREATE TABLE IF NOT EXISTS registered_faces (
                face_id       TEXT PRIMARY KEY,
                student_name  TEXT NOT NULL,
                created_at    REAL NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_registered_faces_name
                ON registered_faces(student_name)
            """,
        ],
        2: [
            "DROP TABLE IF EXISTS registered_faces",
            "DROP INDEX IF EXISTS idx_registered_faces_name",
            """
            CREATE TABLE IF NOT EXISTS registered_students (
                face_id       TEXT PRIMARY KEY,
                student_name  TEXT NOT NULL,
                registered_at REAL NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                face_id     TEXT NOT NULL,
                embedding   BLOB NOT NULL,
                pose_type   TEXT,
                FOREIGN KEY (face_id) REFERENCES registered_students(face_id) ON DELETE CASCADE
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_face_embeddings_face_id ON face_embeddings(face_id)",
        ],
        3: [
            "DROP TABLE IF EXISTS sessions",
            "DROP INDEX IF EXISTS idx_sessions_student_id",
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id      TEXT PRIMARY KEY,
                face_id         TEXT,
                mode            TEXT NOT NULL CHECK(mode IN ('class', 'exam')),
                start_time      REAL NOT NULL,
                end_time        REAL,
                avg_focus_score REAL,
                abnormal_event_count INTEGER DEFAULT 0,
                FOREIGN KEY (face_id) REFERENCES registered_students(face_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_mode ON sessions(mode)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_face_id ON sessions(face_id)",
        ],
        4: [
            "ALTER TABLE focus_records ADD COLUMN is_over_threshold INTEGER DEFAULT 0",
        ],
        5: [
            "ALTER TABLE sessions ADD COLUMN video_source_type TEXT NOT NULL DEFAULT 'camera'",
            "ALTER TABLE sessions ADD COLUMN file_name TEXT DEFAULT NULL",
        ],
        6: [
            "ALTER TABLE focus_records ADD COLUMN eye_score REAL DEFAULT 0.0",
            "ALTER TABLE focus_records ADD COLUMN yawn_score REAL DEFAULT 0.0",
            "ALTER TABLE focus_records ADD COLUMN distance_score REAL DEFAULT 0.0",
        ],
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
        """执行建表与索引创建（幂等），通过 PRAGMA user_version 管理版本

        Args:
            connection: sqlite3.Connection，由 ConnectionManager 提供
        """
        cursor = connection.cursor()
        db_version = cursor.execute("PRAGMA user_version").fetchone()[0]
        target_version = SchemaManager.CURRENT_VERSION

        if db_version >= target_version:
            print(f"[SchemaManager] Schema v{db_version} 已是最新，无需迁移")
            return

        print(f"[SchemaManager] 数据库版本 v{db_version} → v{target_version}，开始迁移...")
        for version in range(db_version + 1, target_version + 1):
            statements = self._DDL.get(version, [])
            for stmt in statements:
                try:
                    cursor.execute(stmt)
                except sqlite3.Error as e:
                    print(f"[SchemaManager] DDL 执行失败 (v{version}): {e}\n  SQL: {stmt[:100]}...")
                    raise
            cursor.execute(f"PRAGMA user_version = {version}")
        connection.commit()
        print(f"[SchemaManager] Schema v{target_version} 就绪")


schema_manager = SchemaManager()
