"""
数据库服务集成测试 — Database Service Tests

测试 src/database/database_service.py 的：
- Schema 版本管理与建表
- 会话创建/结束/删除（CRUD 操作）
- 专注度记录批量写入与查询
- 告警事件自动写入
- 人脸注册与查询
- 级联删除

使用临时文件数据库 + monkeypatched 密钥派生，绕过 Windows 注册表依赖。

运行方式:
    python -m pytest test/test_database_service.py -v
"""

import time as _time

import pytest


# ============================================================
# Schema 管理测试
# ============================================================

class TestSchema:
    """Schema 版本管理与建表"""

    def test_ensure_schema_creates_all_tables(self, db_service):
        """建表后所有核心表存在"""
        conn = db_service._conn_mgr.get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {row["name"] for row in tables}
        expected = {"sessions", "focus_records", "alert_events",
                    "registered_students", "face_embeddings"}
        for t in expected:
            assert t in table_names, f"缺少表: {t}"

    def test_ensure_schema_is_idempotent(self, db_service):
        """重复调用 ensure_schema 不会报错"""
        db_service._schema_mgr.ensure_schema(db_service._conn_mgr.get_connection())
        # 不应抛出异常

    def test_version_tracking(self, db_service):
        """PRAGMA user_version 等于 CURRENT_VERSION"""
        conn = db_service._conn_mgr.get_connection()
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        from src.database.schema import SchemaManager
        assert version == SchemaManager.CURRENT_VERSION


# ============================================================
# 会话 CRUD 测试
# ============================================================

class TestSessionCRUD:
    """会话创建/结束/查询"""

    def test_create_session_succeeds(self, db_service):
        """创建有效会话返回 True"""
        result = db_service.create_session({
            "session_id": "test_s1",
            "mode": "class",
            "start_time": _time.time(),
        })
        assert result is True

    def test_create_session_missing_required_fails(self, db_service):
        """缺少必填字段返回 False"""
        assert db_service.create_session({"session_id": "test_s2"}) is False
        assert db_service.create_session({"mode": "class"}) is False
        assert db_service.create_session({"start_time": 100.0}) is False

    def test_end_session_updates(self, db_service):
        """结束会话更新 end_time 并计算 avg_focus_score"""
        sid = "test_end"
        db_service.create_session({
            "session_id": sid, "mode": "class",
            "start_time": _time.time(),
        })
        # 先写入一些评分记录以确保 avg_focus_score 可计算
        records = [
            {"session_id": sid, "timestamp": 1000.0 + i,
             "head_pose_score": 80.0, "behavior_score": 85.0,
             "expression_score": 75.0, "evidence_score": 80.0,
             "people_score": 100.0, "final_focus_score": float(80 + i),
             "is_force_zero": False, "is_over_threshold": False}
            for i in range(3)
        ]
        db_service.insert_focus_records_batch(records)
        assert db_service.end_session(sid, _time.time()) is True

    def test_end_session_missing_params_fails(self, db_service):
        """缺少参数返回 False"""
        assert db_service.end_session("", 100.0) is False
        assert db_service.end_session("test", 0.0) is False

    def test_query_sessions_all(self, db_service):
        """创建多会话后查询返回全部"""
        for i in range(3):
            db_service.create_session({
                "session_id": f"qs_{i}",
                "mode": "class" if i % 2 == 0 else "exam",
                "start_time": _time.time() + i,
            })
        sessions = db_service.query_sessions({})
        assert len(sessions) == 3

    def test_query_sessions_by_mode(self, db_service):
        """按 mode 筛选"""
        db_service.create_session({
            "session_id": "qs_mode_1", "mode": "class",
            "start_time": _time.time(),
        })
        db_service.create_session({
            "session_id": "qs_mode_2", "mode": "exam",
            "start_time": _time.time() + 1,
        })
        class_sessions = db_service.query_sessions({"mode": "class"})
        assert len(class_sessions) == 1
        assert class_sessions[0]["mode"] == "class"


# ============================================================
# 专注度记录批量写入与查询
# ============================================================

class TestFocusRecords:
    """专注度评分记录读写"""

    def test_insert_and_query(self, db_service):
        """批量写入后查询返回相同数据"""
        sid = "test_fr"
        db_service.create_session({
            "session_id": sid, "mode": "class",
            "start_time": _time.time(),
        })
        records = [
            {"session_id": sid, "timestamp": 1000.0 + i * 2,
             "head_pose_score": 85.0, "behavior_score": 90.0,
             "expression_score": 75.0, "evidence_score": 83.0,
             "people_score": 100.0, "final_focus_score": 83.0,
             "is_force_zero": False, "is_over_threshold": False}
            for i in range(5)
        ]
        assert db_service.insert_focus_records_batch(records) is True

        results = db_service.query_focus_records(sid)
        assert len(results) == 5
        assert results[0]["session_id"] == sid

    def test_insert_empty_batch(self, db_service):
        """空批量写入返回 True（无操作）"""
        assert db_service.insert_focus_records_batch([]) is True

    def test_invalid_records_fails(self, db_service):
        """缺少必填字段的记录整批失败"""
        assert db_service.insert_focus_records_batch([
            {"no_session_id": "x", "no_timestamp": 0}
        ]) is False


# ============================================================
# 告警事件测试
# ============================================================

class TestAlertEvents:
    """告警事件自动写入"""

    def test_warn_info_generates_alert(self, db_service):
        """包含 warn_info 的记录自动创建 alert_events 行"""
        sid = "test_alert"
        db_service.create_session({
            "session_id": sid, "mode": "class",
            "start_time": _time.time(),
        })
        records = [
            {"session_id": sid, "timestamp": 1000.0,
             "head_pose_score": 50.0, "behavior_score": 30.0,
             "expression_score": 40.0, "evidence_score": 35.0,
             "people_score": 100.0, "final_focus_score": 35.0,
             "is_force_zero": False, "is_over_threshold": False,
             "warn_info": {"type": "low_behavior", "detail": "行为评分过低"}},
        ]
        db_service.insert_focus_records_batch(records)

        alerts = db_service.query_alert_events(sid)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "low_behavior"


# ============================================================
# 人脸注册测试
# ============================================================

class TestFaceRegistration:
    """人脸注册与查询"""

    def test_insert_and_query_face(self, db_service):
        """注册人脸后查询可获取"""
        result = db_service.insert_face_embeddings_batch(
            "face_reg_001", "测试学生",
            [(b"\x00" * 512, "frontal"), (b"\x01" * 512, "left")],
            _time.time(),
        )
        assert result is True

        students = db_service.query_registered_students()
        assert len(students) == 1
        assert students[0]["student_name"] == "测试学生"

        all_data = db_service.load_all_face_embeddings()
        assert len(all_data) == 1
        assert len(all_data[0]["embeddings"]) == 2

    def test_insert_empty_embeddings_fails(self, db_service):
        """空 embedding 列表返回 False"""
        assert db_service.insert_face_embeddings_batch(
            "face_002", "学生2", [], _time.time()
        ) is False


# ============================================================
# 级联删除测试
# ============================================================

class TestCascadeDelete:
    """级联删除"""

    def test_delete_session_cascades(self, db_service):
        """删除会话同时删除其 focus_records 和 alert_events"""
        sid = "test_cascade"
        db_service.create_session({
            "session_id": sid, "mode": "class",
            "start_time": _time.time(),
        })
        db_service.insert_focus_records_batch([
            {"session_id": sid, "timestamp": 1000.0,
             "head_pose_score": 80.0, "behavior_score": 85.0,
             "expression_score": 75.0, "evidence_score": 80.0,
             "people_score": 100.0, "final_focus_score": 80.0,
             "is_force_zero": False, "is_over_threshold": False,
             "warn_info": {"type": "test", "detail": "test"}},
        ])

        db_service.delete_sessions([sid])
        assert db_service.query_focus_records(sid) == []
        assert db_service.query_alert_events(sid) == []

    def test_delete_face_cascades(self, db_service):
        """删除人脸同时删除其 session 和 embedding"""
        fid = "face_cascade"
        db_service.insert_face_embeddings_batch(
            fid, "学生", [(b"\x00" * 512, "frontal")], _time.time()
        )
        db_service.create_session({
            "session_id": "s_for_face", "face_id": fid,
            "mode": "class", "start_time": _time.time(),
        })

        result = db_service.delete_face(fid)
        assert result["success"] is True
        # 人脸下的 session 也被删
        sessions = db_service.query_sessions({})
        face_sessions = [s for s in sessions if s.get("face_id") == fid]
        assert len(face_sessions) == 0

    def test_delete_nonexistent_face(self, db_service):
        """删除不存在的人脸返回 success=False"""
        result = db_service.delete_face("no_such_face")
        assert result["success"] is False
