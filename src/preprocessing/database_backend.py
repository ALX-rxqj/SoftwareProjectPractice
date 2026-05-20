from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.database.connection import connection_manager
from src.database.schema import schema_manager
from sqlcipher3 import dbapi2 as sqlite3


class PreprocessingDatabaseBackend:
    """预处理模块人脸注册数据访问，复用 ConnectionManager 的加密连接"""

    def __init__(self, db_path: str | None = None):
        self.db_path = Path(db_path) if db_path else self._default_db_path()

    @staticmethod
    def _default_db_path() -> Path:
        env_path = os.environ.get("CLASS_MONITOR_DB_PATH")
        if env_path:
            return Path(env_path)
        return Path.home() / ".class_monitor" / "data.db"

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not connection_manager.is_connected:
            connection_manager.initialize(str(self.db_path))
        conn = connection_manager.get_connection()
        schema_manager.ensure_schema(conn)

    def is_ready(self) -> bool:
        return connection_manager.is_connected

    def _ensure_connection(self) -> sqlite3.Connection:
        if not connection_manager.is_connected:
            self.initialize()
        return connection_manager.get_connection()

    def insert_face_embeddings_batch(
        self,
        face_id: str,
        student_name: str,
        embeddings: Sequence[Tuple[bytes, str]],
        registered_at: float | None = None,
    ) -> bool:
        if not face_id or not student_name or not embeddings:
            return False

        conn = self._ensure_connection()
        registered_at = registered_at or time.time()
        try:
            conn.execute("BEGIN")
            conn.execute(
                "INSERT OR REPLACE INTO registered_students (face_id, student_name, registered_at) VALUES (?, ?, ?)",
                (face_id, student_name, registered_at),
            )
            conn.execute("DELETE FROM face_embeddings WHERE face_id = ?", (face_id,))
            conn.executemany(
                "INSERT INTO face_embeddings (face_id, embedding, pose_type) VALUES (?, ?, ?)",
                [(face_id, embedding, pose_type) for embedding, pose_type in embeddings],
            )
            conn.commit()
            return True
        except sqlite3.Error:
            try:
                conn.rollback()
            except Exception:
                pass
            return False

    def load_all_face_embeddings(self) -> List[Dict[str, Any]]:
        conn = self._ensure_connection()
        sql = """
            SELECT s.face_id, s.student_name, s.registered_at,
                   e.embedding, e.pose_type
            FROM registered_students s
            LEFT JOIN face_embeddings e ON s.face_id = e.face_id
            ORDER BY s.student_name
        """
        rows = conn.execute(sql).fetchall()
        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            face_id = row["face_id"]
            if face_id not in result:
                result[face_id] = {
                    "face_id": face_id,
                    "student_name": row["student_name"],
                    "registered_at": row["registered_at"],
                    "embeddings": [],
                }
            if row["embedding"] is not None:
                result[face_id]["embeddings"].append(
                    {"embedding": row["embedding"], "pose_type": row["pose_type"]}
                )
        return list(result.values())
