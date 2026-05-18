from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


class PreprocessingDatabaseBackend:
    """Direct SQLite backend for preprocessing-only face registry access."""

    def __init__(self, db_path: str | None = None):
        self.db_path = Path(db_path) if db_path else self._default_db_path()
        self._connection: Optional[sqlite3.Connection] = None

    @staticmethod
    def _default_db_path() -> Path:
        env_path = os.environ.get("CLASS_MONITOR_DB_PATH")
        if env_path:
            return Path(env_path)
        return Path.home() / ".class_monitor" / "data.db"

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(self.db_path), check_same_thread=False, timeout=5.0
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._ensure_schema()

    def is_ready(self) -> bool:
        return self._connection is not None

    def _ensure_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self.initialize()
        return self._connection

    def _ensure_schema(self) -> None:
        conn = self._ensure_connection()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS registered_students (
                face_id       TEXT PRIMARY KEY,
                student_name  TEXT NOT NULL,
                registered_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS face_embeddings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                face_id     TEXT NOT NULL,
                embedding   BLOB NOT NULL,
                pose_type   TEXT,
                FOREIGN KEY (face_id) REFERENCES registered_students(face_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_face_embeddings_face_id
                ON face_embeddings(face_id);
            """
        )
        conn.commit()

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
