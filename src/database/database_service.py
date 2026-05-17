"""数据库服务层（单例）

命令路由中心，接收来自 InterfaceManager 的查询指令并分发到对应的处理方法。
提供 6 个核心方法：create_session, end_session, insert_focus_records_batch,
query_sessions, query_focus_records, query_alert_events。
"""

import sqlite3
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

    def handle_command(self, command: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """命令路由：兼容 DatabaseCommandAdapter 的回调接口"""
        handler = self._command_handlers.get(command)
        if handler is not None:
            return handler(params)
        print(f"[DatabaseService] 未知命令: {command}")
        return None

    # ────────────────── 会话管理 ──────────────────

    def create_session(self, session: Dict[str, Any]) -> bool:
        """创建会话记录（界面模块调用）

        Args:
            session: {"session_id": str, "student_id": str|None,
                       "mode": "class"|"exam", "start_time": float}
        """
        sql = ("INSERT INTO sessions (session_id, student_id, mode, start_time) "
               "VALUES (?, ?, ?, ?)")
        try:
            conn = self._conn_mgr.get_connection()
            conn.execute(sql, (
                session["session_id"],
                session.get("student_id"),
                session["mode"],
                session["start_time"],
            ))
            conn.commit()
            print(f"[DatabaseService] 会话已创建: {session['session_id']}")
            return True
        except sqlite3.Error as e:
            print(f"[DatabaseService] 创建会话失败: {e}")
            return False

    def end_session(self, session_id: str, end_time: float) -> bool:
        """结束会话，同时通过 SQL 聚合计算 avg_focus_score 和 abnormal_event_count

        Args:
            session_id: 会话标识
            end_time: 结束时间戳
        """
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
        try:
            conn = self._conn_mgr.get_connection()
            conn.execute(sql, (end_time, session_id, session_id, session_id))
            conn.commit()
            print(f"[DatabaseService] 会话已结束: {session_id}")
            return True
        except sqlite3.Error as e:
            print(f"[DatabaseService] 结束会话失败: {e}")
            return False

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

        focus_sql = """
            INSERT INTO focus_records (
                session_id, timestamp, date, time,
                head_pose_score, behavior_score, expression_score,
                evidence_score, people_score, final_focus_score, is_force_zero
            ) VALUES (
                ?, ?,
                strftime('%Y-%m-%d', ?, 'unixepoch'),
                strftime('%H:%M:%S', ?, 'unixepoch'),
                ?, ?, ?, ?, ?, ?, ?
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
            ))
            warn = r.get("warn_info")
            if warn:
                alert_rows.append((
                    r["session_id"], ts,
                    warn.get("type", ""),
                    warn.get("detail", ""),
                    ts,
                ))

        last_error = None
        for attempt in range(3):
            try:
                conn = self._conn_mgr.get_connection()
                conn.execute("BEGIN")
                if focus_rows:
                    conn.executemany(focus_sql, focus_rows)
                if alert_rows:
                    conn.executemany(alert_sql, alert_rows)
                conn.commit()
                print(f"[DatabaseService] 批量写入: {len(focus_rows)} 条评分, {len(alert_rows)} 条告警")
                return True
            except sqlite3.Error as e:
                last_error = e
                print(f"[DatabaseService] 批量写入失败 (第{attempt+1}次): {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass
                if attempt < 2:
                    time.sleep(0.1)

        print(f"[DatabaseService] 批量写入最终失败，数据已丢弃（应有快照兜底）")
        return False

    # ────────────────── 查询 ──────────────────

    def query_sessions(self, filter_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """DBI-01: 按筛选条件查询会话列表"""
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
        sql = "SELECT * FROM alert_events WHERE session_id = ? ORDER BY timestamp ASC"
        try:
            conn = self._conn_mgr.get_connection()
            rows = conn.execute(sql, (session_id,)).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"[DatabaseService] 查询告警事件失败: {e}")
            return []

    def shutdown(self) -> None:
        """关闭数据库连接"""
        self._conn_mgr.close()
        print("[DatabaseService] 数据库服务已关闭")


database_service = DatabaseService()
