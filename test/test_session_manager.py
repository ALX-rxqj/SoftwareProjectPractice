"""
会话管理器单元测试 — Session Manager Tests

测试 src/state_estimation/session_manager.py 中 SessionManager 的：
- 创建/结束/删除会话
- 自动结束前一会话
- 告警阈值校验
- 活跃/所有会话过滤
- 会话统计更新与摘要
- 会话时长计算

运行方式:
    python -m pytest test/test_session_manager.py -v
"""

import time as _time

import pytest

from src.state_estimation.contracts import MonitorMode


# ── 会话创建 ────────────────────────────────────────────────

class TestSessionCreation:
    """会话创建测试"""

    def test_create_session_returns_id(self, session_manager):
        """创建会话返回非空 ID"""
        sid = session_manager.create_session()
        assert sid is not None
        assert len(sid) > 0
        assert sid.startswith("session_")

    def test_create_session_sets_current(self, session_manager):
        """创建后 current_session 存在"""
        session_manager.create_session()
        assert session_manager.current_session is not None
        assert session_manager.current_session_id is not None

    def test_create_session_with_custom_mode(self, session_manager):
        """可指定 EXAM 模式"""
        sid = session_manager.create_session(mode=MonitorMode.EXAM)
        info = session_manager.get_session(sid)
        assert info.mode == MonitorMode.EXAM

    def test_create_session_with_threshold(self, session_manager):
        """可指定自定义告警阈值"""
        sid = session_manager.create_session(warn_threshold=80.0)
        info = session_manager.get_session(sid)
        assert info.warn_threshold == 80.0

    def test_default_threshold_is_60(self, session_manager):
        """默认告警阈值为 60"""
        sid = session_manager.create_session()
        info = session_manager.get_session(sid)
        assert info.warn_threshold == 60.0

    def test_create_second_auto_ends_first(self, session_manager):
        """创建第二个会话时自动结束第一个"""
        sid1 = session_manager.create_session()
        info1 = session_manager.get_session(sid1)
        assert info1.is_running is True

        sid2 = session_manager.create_session()
        # 第一个已被自动结束
        info1 = session_manager.get_session(sid1)
        assert info1.is_running is False
        assert info1.end_time is not None

        # 第二个是当前活跃的
        info2 = session_manager.get_session(sid2)
        assert info2.is_running is True


# ── 会话结束 ────────────────────────────────────────────────

class TestSessionEnding:
    """会话结束测试"""

    def test_end_session_sets_end_time(self, session_manager):
        """结束会话设置 end_time 并标记 is_running=False"""
        sid = session_manager.create_session()
        result = session_manager.end_session(sid)
        assert result is True
        info = session_manager.get_session(sid)
        assert info.is_running is False
        assert info.end_time is not None

    def test_end_session_clears_current(self, session_manager):
        """结束当前会话后 current_session 为 None"""
        sid = session_manager.create_session()
        session_manager.end_session(sid)
        assert session_manager.current_session is None

    def test_end_nonexistent_raises(self, session_manager):
        """结束不存在的会话抛出 ValueError"""
        with pytest.raises(ValueError, match="会话不存在"):
            session_manager.end_session("fake_id")

    def test_end_already_ended_does_not_raise(self, session_manager):
        """结束已结束的会话不会报错（end_time 被更新为新的时间）"""
        sid = session_manager.create_session()
        session_manager.end_session(sid)
        # 第二次结束不应报错
        result = session_manager.end_session(sid)
        assert result is True


# ── 会话查询 ────────────────────────────────────────────────

class TestSessionQuery:
    """会话查询测试"""

    def test_get_session_returns_none_for_missing(self, session_manager):
        """查询不存在的会话返回 None"""
        assert session_manager.get_session("fake") is None

    def test_get_session_returns_info_for_existing(self, session_manager):
        """查询存在的会话返回 SessionInfo"""
        sid = session_manager.create_session()
        info = session_manager.get_session(sid)
        assert info is not None
        assert info.session_id == sid

    def test_get_all_sessions_includes_ended(self, session_manager):
        """已结束的会话仍出现在 get_all_sessions 中"""
        sid = session_manager.create_session()
        session_manager.end_session(sid)
        all_s = session_manager.get_all_sessions()
        assert sid in all_s

    def test_get_active_sessions_excludes_ended(self, session_manager):
        """已结束的会话不在 get_active_sessions 中"""
        sid1 = session_manager.create_session()
        sid2 = session_manager.create_session()  # 这会结束 sid1
        active = session_manager.get_active_sessions()
        assert sid1 not in active
        assert sid2 in active

    def test_has_active_session(self, session_manager):
        """has_active_session 反映当前状态"""
        assert session_manager.has_active_session() is False
        session_manager.create_session()
        assert session_manager.has_active_session() is True
        session_manager.end_session(session_manager.current_session_id)
        assert session_manager.has_active_session() is False


# ── 会话删除 ────────────────────────────────────────────────

class TestSessionDeletion:
    """会话删除测试"""

    def test_delete_session_removes(self, session_manager):
        """删除后 get_session 返回 None"""
        sid = session_manager.create_session()
        session_manager.delete_session(sid)
        assert session_manager.get_session(sid) is None

    def test_delete_current_clears_current_id(self, session_manager):
        """删除当前会话清除 current_session_id"""
        sid = session_manager.create_session()
        session_manager.delete_session(sid)
        assert session_manager.current_session_id is None

    def test_delete_nonexistent_returns_false(self, session_manager):
        """删除不存在的会话返回 False"""
        assert session_manager.delete_session("fake") is False

    def test_clear_sessions_removes_all(self, session_manager):
        """clear_sessions() 清空所有会话"""
        session_manager.create_session()
        session_manager.create_session()
        session_manager.clear_sessions()
        assert len(session_manager.get_all_sessions()) == 0
        assert session_manager.current_session_id is None


# ── 告警阈值 ────────────────────────────────────────────────

class TestWarnThreshold:
    """告警阈值测试"""

    def test_set_valid_threshold(self, session_manager):
        """设置 [0, 100] 内的阈值成功"""
        sid = session_manager.create_session()
        assert session_manager.set_warn_threshold(sid, 80.0) is True
        info = session_manager.get_session(sid)
        assert info.warn_threshold == 80.0

    def test_set_boundary_values(self, session_manager):
        """边界值 0 和 100 有效"""
        sid = session_manager.create_session()
        assert session_manager.set_warn_threshold(sid, 0.0) is True
        assert session_manager.set_warn_threshold(sid, 100.0) is True

    def test_set_below_zero_raises(self, session_manager):
        """< 0 抛出 ValueError"""
        sid = session_manager.create_session()
        with pytest.raises(ValueError):
            session_manager.set_warn_threshold(sid, -1.0)

    def test_set_above_100_raises(self, session_manager):
        """> 100 抛出 ValueError"""
        sid = session_manager.create_session()
        with pytest.raises(ValueError):
            session_manager.set_warn_threshold(sid, 101.0)

    def test_set_on_nonexistent_returns_false(self, session_manager):
        """不存在的会话返回 False"""
        assert session_manager.set_warn_threshold("fake", 50.0) is False


# ── 会话统计 ────────────────────────────────────────────────

class TestSessionStats:
    """会话统计更新与摘要"""

    def test_update_stats_accumulates(self, session_manager):
        """统计信息累加"""
        sid = session_manager.create_session()
        session_manager.update_session_stats(sid, frames_processed=10, abnormal_events=2)
        session_manager.update_session_stats(sid, frames_processed=5, abnormal_events=1)
        info = session_manager.get_session(sid)
        assert info.total_frames == 15
        assert info.abnormal_event_count == 3

    def test_update_nonexistent_no_error(self, session_manager):
        """更新不存在的会话不会报错"""
        session_manager.update_session_stats("fake", 10, 2)

    def test_get_session_summary_all_fields(self, session_manager):
        """会话摘要包含所有预期字段"""
        sid = session_manager.create_session(mode=MonitorMode.EXAM, warn_threshold=70.0)
        summary = session_manager.get_session_summary(sid)
        expected = {"session_id", "mode", "start_time", "end_time",
                    "duration", "warn_threshold", "is_running",
                    "total_frames", "abnormal_event_count"}
        assert set(summary.keys()) == expected
        assert summary["session_id"] == sid
        assert summary["mode"] == "exam"
        assert summary["warn_threshold"] == 70.0
        assert summary["is_running"] is True
        assert summary["total_frames"] == 0

    def test_summary_nonexistent_returns_none(self, session_manager):
        """不存在的会话摘要返回 None"""
        assert session_manager.get_session_summary("fake") is None


# ── 会话时长 ────────────────────────────────────────────────

class TestSessionDuration:
    """会话时长计算"""

    def test_duration_for_nonexistent_returns_none(self, session_manager):
        """不存在的会话返回 None"""
        assert session_manager.get_session_duration("fake") is None

    def test_duration_for_running_session(self, session_manager):
        """运行中的会话时长 = now - start_time"""
        sid = session_manager.create_session()
        dur = session_manager.get_session_duration(sid)
        assert dur is not None
        assert dur >= 0

    def test_duration_for_ended_session(self, session_manager):
        """已结束会话时长 = end_time - start_time"""
        sid = session_manager.create_session()
        session_manager.end_session(sid)
        dur = session_manager.get_session_duration(sid)
        assert dur is not None
        assert dur >= 0


# ── adopt_session ───────────────────────────────────────────

class TestAdoptSession:
    """接管已存在会话"""

    def test_adopt_session_uses_given_id(self, session_manager):
        """接管使用传入的 ID 而非自动生成"""
        sid = session_manager.adopt_session("my_session_id", mode=MonitorMode.EXAM)
        assert sid == "my_session_id"
        info = session_manager.get_session("my_session_id")
        assert info.mode == MonitorMode.EXAM

    def test_adopt_session_clears_previous(self, session_manager):
        """接管前结束前一会话"""
        sid1 = session_manager.create_session()
        session_manager.adopt_session("new_session")
        info = session_manager.get_session(sid1)
        assert info.is_running is False
