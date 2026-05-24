"""
状态估计服务集成测试 — State Estimation Service Tests

测试 src/state_estimation/service.py 中 StateEstimationService 的：
- 会话管理 API（on_session_init, on_control_analysis, on_session_end）
- 模式切换（on_mode_changed）
- 阈值更新（on_threshold_changed）
- 数据流：FeatureData → FocusResultData → downsampler → callback
- handle_command 路由分发
- 状态查询

技术要点：monkeypatch _start_processing/_stop_processing 为 no-op，
直接控制 _is_processing 进行同步测试，避免 daemon 线程带来的不稳定。

运行方式:
    python -m pytest test/test_state_estimation_service.py -v
"""

import time as _time

import pytest

from src.state_estimation.contracts import (
    FeatureData, FocusResultData, MonitorMode,
    WarnInfo, WARN_NO_FACE,
)
from src.state_estimation.service import StateEstimationService


@pytest.fixture
def se_service():
    """创建 StateEstimationService 实例"""
    return StateEstimationService()


def _make_good_fd():
    """构造一个好的 FeatureData"""
    return FeatureData(
        timestamp=_time.time(),
        face_id="f1",
        face_matched=True,
        head_pose={"pitch": 0.0, "yaw": 0.0, "roll": 0.0, "confidence": 1.0},
        eye_state={"value": 0, "confidence": 1.0},
        is_looking_screen={"value": True, "confidence": 1.0},
        attention_state={"value": 0, "confidence": 1.0},
        face_distance_state={"value": 0, "confidence": 1.0},
        is_yawning={"value": False, "confidence": 1.0},
        num_face_total={"value": 1, "confidence": 1.0},
    )


# ============================================================
# 会话管理 API
# ============================================================

class TestSessionAPI:
    """on_session_init / on_control_analysis / on_session_end"""

    def test_session_init_returns_id(self, se_service):
        """创建会话返回有效的 session_id"""
        result = se_service.on_session_init()
        assert result["success"] is True
        assert result["session_id"].startswith("session_")

    def test_control_analysis_start_adopts_given_id(self, se_service, monkeypatch):
        """启动分析且传入 session_id 时复用该 ID"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        result = se_service.on_control_analysis(
            start=True, session_id="my_custom_id", mode="exam"
        )
        assert result["session_id"] == "my_custom_id"
        assert se_service._session_manager.current_session_id == "my_custom_id"

    def test_control_analysis_start_auto_creates(self, se_service, monkeypatch):
        """启动分析不传 session_id 时自动创建"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        result = se_service.on_control_analysis(start=True)
        assert result["session_id"].startswith("session_")

    def test_control_analysis_stop(self, se_service, monkeypatch):
        """停止分析结束会话"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        monkeypatch.setattr(se_service, "_stop_processing", lambda: None)
        monkeypatch.setattr(se_service, "_flush_db_buffer", lambda: None)
        monkeypatch.setattr(se_service, "_cancel_snapshot_timer", lambda: None)
        sid = se_service.on_control_analysis(start=True)["session_id"]
        result = se_service.on_control_analysis(start=False, session_id=sid)
        assert result["success"] is True

    def test_session_end_requires_id(self, se_service):
        """on_session_end 空 ID 返回失败"""
        result = se_service.on_session_end("")
        assert result["success"] is False


# ============================================================
# 模式切换
# ============================================================

class TestModeSwitch:
    """on_mode_changed"""

    def test_switch_to_exam(self, se_service, monkeypatch):
        """切换到 EXAM 模式成功"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        se_service.on_control_analysis(start=True, session_id="mode_test")
        result = se_service.on_mode_changed("exam")
        assert result["success"] is True
        assert se_service._estimator.mode == MonitorMode.EXAM

    def test_switch_to_class(self, se_service, monkeypatch):
        """切换到 CLASS 模式成功"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        se_service.on_control_analysis(start=True, session_id="mode_test", mode="exam")
        result = se_service.on_mode_changed("class")
        assert result["success"] is True
        assert se_service._estimator.mode == MonitorMode.CLASS

    def test_invalid_mode_rejected(self, se_service):
        """无效模式返回 success=False"""
        result = se_service.on_mode_changed("invalid_mode")
        assert result["success"] is False

    def test_case_insensitive(self, se_service, monkeypatch):
        """模式名称大小写不敏感"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        se_service.on_control_analysis(start=True, session_id="case_test")
        assert se_service.on_mode_changed("EXAM")["success"] is True
        assert se_service._estimator.mode == MonitorMode.EXAM


# ============================================================
# 告警阈值
# ============================================================

class TestThreshold:
    """on_threshold_changed"""

    def test_update_threshold_on_active_session(self, se_service, monkeypatch):
        """有活跃会话时更新阈值"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        se_service.on_control_analysis(start=True, session_id="thr_test")
        result = se_service.on_threshold_changed(80.0)
        assert result["success"] is True
        info = se_service._session_manager.current_session
        assert info.warn_threshold == 80.0

    def test_threshold_out_of_range(self, se_service):
        """超范围阈值拒绝"""
        assert se_service.on_threshold_changed(-1.0)["success"] is False
        assert se_service.on_threshold_changed(101.0)["success"] is False

    def test_threshold_boundary_valid(self, se_service, monkeypatch):
        """边界值 0 和 100 有效"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        se_service.on_control_analysis(start=True, session_id="thr_boundary")
        assert se_service.on_threshold_changed(0.0)["success"] is True
        assert se_service.on_threshold_changed(100.0)["success"] is True


# ============================================================
# 数据流：特征数据 → 评分
# ============================================================

class TestDataFlow:
    """on_feature_received 数据流"""

    def test_ignored_when_not_processing(self, se_service):
        """未启动分析时忽略特征数据"""
        fd = _make_good_fd()
        # 设置回调来验证是否被调用
        received = []
        se_service.set_focus_result_callback(lambda r: received.append(r))
        se_service.on_feature_received(fd)
        assert len(received) == 0  # is_processing == False

    def test_received_computes_score(self, se_service, monkeypatch):
        """处理中时计算评分并通过降采样器"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        se_service.on_control_analysis(start=True, session_id="flow_test")
        se_service._is_processing = True  # 绕过线程直接设置

        received = []
        se_service.set_focus_result_callback(lambda r: received.append(r))

        # 发两帧时间跨超过 1 秒，触发降采样输出
        fd1 = _make_good_fd()
        fd1 = FeatureData(
            timestamp=1000.0, face_id="f1", face_matched=True,
            head_pose={"pitch": 0.0, "yaw": 0.0, "roll": 0.0, "confidence": 1.0},
            eye_state={"value": 0, "confidence": 1.0},
            is_looking_screen={"value": True, "confidence": 1.0},
            attention_state={"value": 0, "confidence": 1.0},
            face_distance_state={"value": 0, "confidence": 1.0},
            is_yawning={"value": False, "confidence": 1.0},
            num_face_total={"value": 1, "confidence": 1.0},
        )
        fd2 = FeatureData(
            timestamp=1002.0, face_id="f1", face_matched=True,
            head_pose={"pitch": 0.0, "yaw": 0.0, "roll": 0.0, "confidence": 1.0},
            eye_state={"value": 0, "confidence": 1.0},
            is_looking_screen={"value": True, "confidence": 1.0},
            attention_state={"value": 0, "confidence": 1.0},
            face_distance_state={"value": 0, "confidence": 1.0},
            is_yawning={"value": False, "confidence": 1.0},
            num_face_total={"value": 1, "confidence": 1.0},
        )

        se_service.on_feature_received(fd1)
        # 第一帧不触发输出（窗口时间差不足）
        se_service.on_feature_received(fd2)
        # 两帧时间差 2s >= 1s → 触发降采样输出
        assert len(received) >= 1

    def test_force_zero_frame(self, se_service, monkeypatch):
        """多人帧 → 强制置零"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        se_service.on_control_analysis(start=True, session_id="force_test")
        se_service._is_processing = True

        received = []
        se_service.set_focus_result_callback(lambda r: received.append(r))

        fd = FeatureData(
            timestamp=1000.0, face_id="f1", face_matched=True,
            head_pose={"pitch": 0.0, "yaw": 0.0, "roll": 0.0, "confidence": 1.0},
            eye_state={"value": 0, "confidence": 1.0},
            is_looking_screen={"value": True, "confidence": 1.0},
            attention_state={"value": 0, "confidence": 1.0},
            face_distance_state={"value": 0, "confidence": 1.0},
            is_yawning={"value": False, "confidence": 1.0},
            num_face_total={"value": 3, "confidence": 1.0},
        )
        se_service.on_feature_received(fd)
        # 用 flush 触发输出
        remaining = se_service._downsampler.flush()
        if remaining:
            se_service._dispatch_focus_result(remaining)
        assert len(received) >= 1
        # 最终分数为 0
        assert received[0].final_focus_score == 0.0


# ============================================================
# handle_command 路由
# ============================================================

class TestCommandRouting:
    """handle_command 指令分发"""

    def test_known_command_success(self, se_service):
        """已知指令返回 success=True"""
        result = se_service.handle_command("start_new_session", {})
        assert result["success"] is True
        assert "session_id" in result

    def test_unknown_command_fails(self, se_service):
        """未知指令返回 success=False"""
        result = se_service.handle_command("nonexistent_cmd", {})
        assert result["success"] is False

    def test_toggle_analysis_start(self, se_service, monkeypatch):
        """toggle_analysis start 创建会话"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        result = se_service.handle_command("toggle_analysis", {
            "start": True, "session_id": "cmd_test", "mode": "class"
        })
        assert result["session_id"] == "cmd_test"


# ============================================================
# 状态查询
# ============================================================

class TestStatus:
    """get_status / get_session_summary"""

    def test_initial_status(self, se_service):
        """初始状态"""
        status = se_service.get_status()
        assert status["is_running"] is False
        assert status["is_processing"] is False
        assert status["current_session_id"] is None
        assert status["total_sessions"] == 0

    def test_status_after_session(self, se_service, monkeypatch):
        """创建会话后状态更新"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        se_service.on_control_analysis(start=True, session_id="status_test")
        status = se_service.get_status()
        assert status["current_session_id"] == "status_test"
        assert status["total_sessions"] == 1

    def test_session_summary(self, se_service, monkeypatch):
        """get_session_summary 返回会话摘要"""
        monkeypatch.setattr(se_service, "_start_processing", lambda: None)
        sid = se_service.on_control_analysis(start=True)["session_id"]
        summary = se_service.get_session_summary(sid)
        assert summary is not None
        assert summary["session_id"] == sid
