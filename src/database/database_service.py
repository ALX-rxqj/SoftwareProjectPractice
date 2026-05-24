"""数据库服务层（单例）

命令路由中心，接收来自 InterfaceManager 的查询指令并分发到对应的处理方法。
提供 6 个核心方法：create_session, end_session, insert_focus_records_batch,
query_sessions, query_focus_records, query_alert_events。
"""

from sqlcipher3 import dbapi2 as sqlite3
import time
from typing import Any, Dict, List, Optional

from .connection import ConnectionManager, connection_manager
from .schema import SchemaManager, schema_manager


class DatabaseService:
    """数据库服务（单例）—— 命令路由 + 数据访问"""

    _instance: Optional["DatabaseService"] = None

    def __new__(cls) -> "DatabaseService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._conn_mgr: ConnectionManager = connection_manager
        self._schema_mgr: SchemaManager = schema_manager
        self._command_handlers: Dict[str, callable] = {
            "query_sessions": self._query_sessions_handler,
            "query_focus_records": self._query_records_handler,
        }

    def initialize(self, db_path: str) -> None:
        """初始化数据库连接并校验 schema"""
        self._conn_mgr.initialize(db_path)
        self._schema_mgr.ensure_schema(self._conn_mgr.get_connection())
        print(f"[DatabaseService] 数据库初始化完成: {db_path}")

    def _retry_write(self, operation, op_name: str) -> bool:
        """执行写操作的事务重试（3 次，100ms 退避）

        operation: callable(conn) -> None（在 BEGIN..COMMIT 事务中执行）
        返回 True 表示成功，False 表示 3 次重试均失败。
        """
        last_error = None
        for attempt in range(3):
            try:
                conn = self._conn_mgr.get_connection()
                conn.execute("BEGIN")
                operation(conn)
                conn.commit()
                return True
            except sqlite3.Error as e:
                last_error = e
                print(f"[DatabaseService] {op_name} 失败 (第{attempt+1}次): {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass
                if attempt < 2:
                    time.sleep(0.1)
        print(f"[DatabaseService] {op_name} 最终失败: {last_error}")
        return False

    def handle_command(self, command: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """命令路由：兼容 DatabaseCommandAdapter 的回调接口"""
        handler = self._command_handlers.get(command)
        if handler is not None:
            return handler(params)
        print(f"[DatabaseService] 未知命令: {command}")
        return []

    # ────────────────── 人脸注册（新架构：主子表） ──────────────────

    def insert_face_embeddings_batch(
        self, face_id: str, student_name: str,
        embeddings: List[tuple], registered_at: float,
    ) -> bool:
        """写入注册学生及其特征向量（预处理模块通过回调调用，storage_type='local' 时）

        Args:
            face_id: 人脸标识（UI 生成的 UUID）
            student_name: 学生姓名
            embeddings: [(embedding_blob: bytes, pose_type: str), ...]
            registered_at: 注册时间戳

        Returns:
            True 表示写入成功
        """
        if not face_id or not student_name or not embeddings:
            print(f"[DatabaseService] insert_face_embeddings_batch 缺少必填字段")
            return False

        student_sql = ("INSERT OR REPLACE INTO registered_students "
                       "(face_id, student_name, registered_at) VALUES (?, ?, ?)")
        embedding_sql = ("INSERT INTO face_embeddings "
                         "(face_id, embedding, pose_type) VALUES (?, ?, ?)")

        def _do(conn):
            conn.execute(student_sql, (face_id, student_name, registered_at))
            if embeddings:
                conn.executemany(embedding_sql, [
                    (face_id, emb, pose) for emb, pose in embeddings
                ])

        if not self._retry_write(_do, "人脸注册"):
            return False
        print(f"[DatabaseService] 已注册人脸: {face_id} ({student_name}), "
              f"{len(embeddings)} 个特征向量")
        return True

    def query_registered_students(self) -> List[Dict[str, Any]]:
        """查询所有已注册学生（仅主表，不含 embedding）"""
        sql = "SELECT * FROM registered_students ORDER BY student_name"
        try:
            conn = self._conn_mgr.get_connection()
            rows = conn.execute(sql).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"[DatabaseService] 查询已注册学生失败: {e}")
            return []

    def load_all_face_embeddings(self) -> List[Dict[str, Any]]:
        """程序启动时加载全部持久人脸的完整数据（含所有 embedding）

        Returns: [
            {"face_id": str, "student_name": str, "registered_at": float,
             "embeddings": [{"embedding": bytes, "pose_type": str}, ...]},
            ...
        ]
        """
        sql = """
            SELECT s.face_id, s.student_name, s.registered_at,
                   e.embedding, e.pose_type
            FROM registered_students s
            LEFT JOIN face_embeddings e ON s.face_id = e.face_id
            ORDER BY s.student_name
        """
        try:
            conn = self._conn_mgr.get_connection()
            rows = conn.execute(sql).fetchall()
            result: Dict[str, dict] = {}
            for row in rows:
                fid = row["face_id"]
                if fid not in result:
                    result[fid] = {
                        "face_id": fid,
                        "student_name": row["student_name"],
                        "registered_at": row["registered_at"],
                        "embeddings": [],
                    }
                if row["embedding"] is not None:
                    result[fid]["embeddings"].append({
                        "embedding": row["embedding"],
                        "pose_type": row["pose_type"],
                    })
            return list(result.values())
        except sqlite3.Error as e:
            print(f"[DatabaseService] 加载人脸特征向量失败: {e}")
            return []

    def query_registered_faces(self) -> List[Dict[str, Any]]:
        """查询所有已注册人脸（兼容旧接口，转调 registered_students）"""
        return self.query_registered_students()

    # ────────────────── 会话管理 ──────────────────

    def create_session(self, session: Dict[str, Any]) -> bool:
        """创建会话记录（界面模块调用）

        Args:
            session: {"session_id": str, "face_id": str|None,
                       "mode": "class"|"exam", "start_time": float}
        """
        required = ["session_id", "mode", "start_time"]
        missing = [k for k in required if k not in session or session[k] is None]
        if missing:
            print(f"[DatabaseService] create_session 缺少必填字段: {missing}")
            return False

        sql = ("INSERT INTO sessions (session_id, face_id, mode, start_time, "
               "video_source_type, file_name) "
               "VALUES (?, ?, ?, ?, ?, ?)")

        def _do(conn):
            conn.execute(sql, (
                session["session_id"],
                session.get("face_id"),
                session["mode"],
                session["start_time"],
                session.get("video_source_type", "camera"),
                session.get("file_name"),
            ))

        if not self._retry_write(_do, "创建会话"):
            return False
        print(f"[DatabaseService] 会话已创建: {session['session_id']}")
        return True

    def end_session(self, session_id: str, end_time: float) -> bool:
        """结束会话，同时通过 SQL 聚合计算 avg_focus_score 和 abnormal_event_count

        Args:
            session_id: 会话标识
            end_time: 结束时间戳
        """
        if not session_id or not end_time:
            print(f"[DatabaseService] end_session 缺少必填字段: "
                  f"session_id={session_id!r}, end_time={end_time!r}")
            return False

        sql = """
            UPDATE sessions SET
                end_time = ?,
                avg_focus_score = (
                    SELECT AVG(final_focus_score) FROM focus_records
                    WHERE session_id = ?
                ),
                abnormal_event_count = (
                    SELECT COUNT(*) FROM alert_events
                    WHERE session_id = ?
                )
            WHERE session_id = ?
        """

        def _do(conn):
            conn.execute(sql, (end_time, session_id, session_id, session_id))

        if not self._retry_write(_do, "结束会话"):
            return False
        print(f"[DatabaseService] 会话已结束: {session_id}")
        return True

    # ────────────────── 评分记录批量写入 ──────────────────

    def insert_focus_records_batch(self, records: List[Dict[str, Any]]) -> bool:
        """批量写入专注度评分记录 + 告警事件（状态估计模块通过回调调用）

        Args:
            records: [{
                "session_id": str, "timestamp": float,
                "head_pose_score": float, "behavior_score": float,
                "expression_score": float, "evidence_score": float,
                "people_score": float, "final_focus_score": float,
                "is_force_zero": bool,
                "warn_info": {"type": str, "detail": str} | None
            }, ...]

        Returns:
            True 表示写入成功
        """
        if not records:
            return True

        # 校验每条记录必填字段
        invalid = [i for i, r in enumerate(records) if not r.get("session_id") or not r.get("timestamp")]
        if invalid:
            print(f"[DatabaseService] 批量写入校验失败: 第{invalid}条缺少 session_id 或 timestamp")
            return False

        focus_sql = """
            INSERT INTO focus_records (
                session_id, timestamp, date, time,
                head_pose_score, behavior_score, expression_score,
                evidence_score, people_score, final_focus_score, is_force_zero,
                is_over_threshold
            ) VALUES (
                ?, ?,
                strftime('%Y-%m-%d', ?, 'unixepoch'),
                strftime('%H:%M:%S', ?, 'unixepoch'),
                ?, ?, ?, ?, ?, ?, ?, ?
            )
        """
        alert_sql = """
            INSERT INTO alert_events (session_id, timestamp, alert_type, detail, frame_timestamp)
            VALUES (?, ?, ?, ?, ?)
        """

        focus_rows = []
        alert_rows = []

        for r in records:
            ts = r["timestamp"]
            focus_rows.append((
                r["session_id"], ts, ts, ts,
                r.get("head_pose_score", 0.0),
                r.get("behavior_score", 0.0),
                r.get("expression_score", 0.0),
                r.get("evidence_score", 0.0),
                r.get("people_score", 0.0),
                r.get("final_focus_score", 0.0),
                1 if r.get("is_force_zero", False) else 0,
                1 if r.get("is_over_threshold", False) else 0,
            ))
            warn = r.get("warn_info")
            if warn:
                alert_rows.append((
                    r["session_id"], ts,
                    warn.get("type", ""),
                    warn.get("detail", ""),
                    ts,
                ))


        def _do(conn):
            if focus_rows:
                conn.executemany(focus_sql, focus_rows)
            if alert_rows:
                conn.executemany(alert_sql, alert_rows)

        if not self._retry_write(_do, "批量写入"):
            return False
        # 大批量写入后执行 WAL checkpoint，确保数据持久化到主数据库
        if len(focus_rows) >= 100 or len(alert_rows) >= 50:
            try:
                conn = self._conn_mgr.get_connection()
                conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except sqlite3.Error:
                pass
        print(f"[DatabaseService] 批量写入: {len(focus_rows)} 条评分, {len(alert_rows)} 条告警")
        return True

    # ────────────────── 查询 ──────────────────

    def query_sessions(self, filter_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """DBI-01: 按筛选条件查询会话列表"""
        if filter_params is None:
            print("[DatabaseService] query_sessions 参数不能为 None")
            return []
        return self._query_sessions_handler(filter_params)

    def _query_sessions_handler(self, filter_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """会话查询的内部实现"""
        conditions = []
        values = []

        start_date = filter_params.get("start_date")
        if start_date:
            conditions.append("start_time >= ?")
            values.append(start_date)

        end_date = filter_params.get("end_date")
        if end_date:
            conditions.append("start_time <= ?")
            values.append(end_date)

        mode = filter_params.get("mode")
        if mode:
            conditions.append("mode = ?")
            values.append(mode)

        focus_min = filter_params.get("focus_min")
        if focus_min is not None:
            conditions.append("(avg_focus_score IS NULL OR avg_focus_score >= ?)")
            values.append(focus_min)

        focus_max = filter_params.get("focus_max")
        if focus_max is not None:
            conditions.append("(avg_focus_score IS NULL OR avg_focus_score <= ?)")
            values.append(focus_max)

        abnormal_min = filter_params.get("abnormal_min")
        if abnormal_min is not None:
            conditions.append("abnormal_event_count >= ?")
            values.append(abnormal_min)

        abnormal_max = filter_params.get("abnormal_max")
        if abnormal_max is not None:
            conditions.append("abnormal_event_count <= ?")
            values.append(abnormal_max)

        face_id = filter_params.get("face_id")
        if face_id:
            conditions.append("face_id = ?")
            values.append(face_id)

        video_source_type = filter_params.get("video_source_type")
        if video_source_type:
            conditions.append("video_source_type = ?")
            values.append(video_source_type)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM sessions{where} ORDER BY start_time DESC"

        try:
            conn = self._conn_mgr.get_connection()
            rows = conn.execute(sql, values).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"[DatabaseService] 查询会话失败: {e}")
            return []

    def query_focus_records(self, session_id: str) -> List[Dict[str, Any]]:
        """查询指定会话的专注度评分记录（界面模块调用）"""
        if not session_id:
            print("[DatabaseService] query_focus_records: session_id 不能为空")
            return []
        return self._query_records_handler({"session_id": session_id})

    def _query_records_handler(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        session_id = params.get("session_id", "")
        sql = "SELECT * FROM focus_records WHERE session_id = ? ORDER BY timestamp ASC"
        try:
            conn = self._conn_mgr.get_connection()
            rows = conn.execute(sql, (session_id,)).fetchall()
            records = []
            for row in rows:
                d = dict(row)
                d["is_force_zero"] = bool(d.get("is_force_zero", 0))
                records.append(d)
            return records
        except sqlite3.Error as e:
            print(f"[DatabaseService] 查询评分记录失败: {e}")
            return []

    def query_alert_events(self, session_id: str) -> List[Dict[str, Any]]:
        """查询指定会话的告警事件（预留，当前 UI 未使用）"""
        if not session_id:
            print("[DatabaseService] query_alert_events: session_id 不能为空")
            return []
        sql = "SELECT * FROM alert_events WHERE session_id = ? ORDER BY timestamp ASC"
        try:
            conn = self._conn_mgr.get_connection()
            rows = conn.execute(sql, (session_id,)).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"[DatabaseService] 查询告警事件失败: {e}")
            return []

    def delete_sessions(self, session_ids: List[str]) -> Dict[str, Any]:
        """批量删除会话及关联数据（CASCADE 自动删除 focus_records + alert_events）

        Args:
            session_ids: 要删除的会话 ID 列表

        Returns:
            {"deleted_count": N, "total": M}
        """
        if not session_ids:
            return {"deleted_count": 0, "total": 0}

        sql = "DELETE FROM sessions WHERE session_id = ?"
        total = len(session_ids)
        deleted_count = 0

        try:
            conn = self._conn_mgr.get_connection()
            conn.execute("BEGIN")
            for sid in session_ids:
                cursor = conn.execute(sql, (sid,))
                deleted_count += cursor.rowcount
            conn.commit()
            print(f"[DatabaseService] 已删除 {deleted_count}/{total} 条会话")
        except sqlite3.Error as e:
            print(f"[DatabaseService] 删除会话失败: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            deleted_count = 0
            return {"deleted_count": deleted_count, "total": total}

        return {"deleted_count": deleted_count, "total": total}

    def delete_face(self, face_id: str) -> Dict[str, Any]:
        """级联删除已注册人脸：删人脸 → CASCADE 删 embeddings + sessions + focus_records + alert_events"""
        if not face_id:
            return {"success": False, "deleted_face_id": "", "msg": "face_id 为空"}

        try:
            conn = self._conn_mgr.get_connection()
            conn.execute("BEGIN")
            conn.execute("DELETE FROM sessions WHERE face_id = ?", (face_id,))
            cursor = conn.execute(
                "DELETE FROM registered_students WHERE face_id = ?",
                (face_id,),
            )
            deleted = cursor.rowcount
            conn.commit()
            if deleted:
                print(f"[DatabaseService] 已删除人脸: {face_id}")
                return {"success": True, "deleted_face_id": face_id}
            else:
                print(f"[DatabaseService] 未找到人脸: {face_id}")
                return {"success": False, "deleted_face_id": face_id,
                        "msg": f"未找到 face_id={face_id}"}
        except sqlite3.Error as e:
            print(f"[DatabaseService] 删除人脸失败: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            return {"success": False, "deleted_face_id": face_id, "msg": str(e)}

    def shutdown(self) -> None:
        """关闭数据库连接"""
        self._conn_mgr.close()
        print("[DatabaseService] 数据库服务已关闭")

database_service = DatabaseService()
