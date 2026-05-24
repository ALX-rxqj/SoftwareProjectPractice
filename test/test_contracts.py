"""
合约工具函数与数据结构测试 — Contracts & Data Structures

测试 src/state_estimation/contracts.py 中的：
- alert_priority() 优先级映射
- pick_highest_alert() 告警选取逻辑
- FocusResultData.to_dict() 序列化

运行方式:
    python -m pytest test/test_contracts.py -v
"""

import pytest

from src.state_estimation.contracts import (
    WARN_NO_FACE,
    WARN_MULTI_FACE,
    WARN_FACE_MISMATCH,
    WARN_LOW_EVIDENCE,
    WARN_LOW_HEAD_POSE,
    WARN_LOW_BEHAVIOR,
    WARN_LOW_EXPRESSION,
    alert_priority,
    pick_highest_alert,
    WarnInfo,
    FocusResultData,
    MonitorMode,
    SessionInfo,
    FeatureData,
)


# ── alert_priority ──────────────────────────────────────────

class TestAlertPriority:
    """告警优先级映射测试"""

    def test_no_face_priority(self):
        """无人脸告警优先级为 1（最高）"""
        assert alert_priority(WARN_NO_FACE) == 1

    def test_multi_face_priority(self):
        """多人脸告警优先级为 1（与无人脸同等最高）"""
        assert alert_priority(WARN_MULTI_FACE) == 1

    def test_face_mismatch_priority(self):
        """人脸不匹配优先级为 2"""
        assert alert_priority(WARN_FACE_MISMATCH) == 2

    def test_low_evidence_priority(self):
        """低证据评分优先级为 3"""
        assert alert_priority(WARN_LOW_EVIDENCE) == 3

    def test_unknown_type_returns_999(self):
        """未知告警类型返回最低优先级 999"""
        assert alert_priority("fake_type") == 999
        assert alert_priority("") == 999

    def test_all_known_types_ordered(self):
        """验证所有已知类型的优先级数值递增（越小优先级越高）"""
        types = [
            WARN_NO_FACE,
            WARN_MULTI_FACE,
            WARN_FACE_MISMATCH,
            WARN_LOW_EVIDENCE,
            WARN_LOW_HEAD_POSE,
            WARN_LOW_BEHAVIOR,
            WARN_LOW_EXPRESSION,
        ]
        priorities = [alert_priority(t) for t in types]
        assert priorities == sorted(priorities), "优先级应保持定义的数值顺序"


# ── pick_highest_alert ──────────────────────────────────────

class TestPickHighestAlert:
    """告警候选选取测试"""

    def test_empty_returns_none(self):
        """空元组返回 None"""
        assert pick_highest_alert(()) is None

    def test_single_returns_that(self):
        """单个候选直接返回"""
        warn = WarnInfo(warn_type=WARN_LOW_HEAD_POSE, detail="头部姿态评分过低")
        assert pick_highest_alert((warn,)) is warn

    def test_picks_highest_priority(self):
        """多个候选时返回优先级最高的"""
        low_pri = WarnInfo(warn_type=WARN_LOW_EXPRESSION, detail="表情评分过低")
        high_pri = WarnInfo(warn_type=WARN_NO_FACE, detail="画面中无人脸")
        result = pick_highest_alert((low_pri, high_pri))
        assert result.warn_type == WARN_NO_FACE

    def test_equal_priority_returns_first(self):
        """同等优先级返回第一个（稳定排序）"""
        w1 = WarnInfo(warn_type=WARN_NO_FACE, detail="first")
        w2 = WarnInfo(warn_type=WARN_MULTI_FACE, detail="second")
        result = pick_highest_alert((w1, w2))
        assert result.detail == "first"


# ── FocusResultData.to_dict ─────────────────────────────────

class TestFocusResultDataToDict:
    """FocusResultData 序列化测试"""

    def test_to_dict_with_warn(self):
        """有告警时 warn_info 包含最高优先级告警"""
        warn_low = WarnInfo(warn_type=WARN_NO_FACE, detail="无人脸")
        warn_high = WarnInfo(warn_type=WARN_LOW_BEHAVIOR, detail="行为低分")
        result = FocusResultData(
            timestamp=100.0,
            session_id="s1",
            head_pose_score=80.0,
            behavior_score=30.0,
            expression_score=70.0,
            evidence_score=60.0,
            people_score=0.0,
            final_focus_score=0.0,
            is_force_zero=True,
            is_over_threshold=False,
            warn_candidates=(warn_low, warn_high),
        )
        d = result.to_dict()
        assert d["warn_info"] is not None
        assert d["warn_info"]["type"] == WARN_NO_FACE  # 优先级最高
        assert d["warn_info"]["detail"] == "无人脸"

    def test_to_dict_without_warn(self):
        """无告警时 warn_info 为 None"""
        result = FocusResultData(
            timestamp=100.0,
            session_id="s1",
            head_pose_score=80.0,
            behavior_score=85.0,
            expression_score=70.0,
            evidence_score=78.0,
            people_score=100.0,
            final_focus_score=78.0,
            is_force_zero=False,
            is_over_threshold=False,
            warn_candidates=(),
        )
        d = result.to_dict()
        assert d["warn_info"] is None

    def test_to_dict_all_fields_present(self):
        """to_dict 输出包含所有预期字段"""
        result = FocusResultData(
            timestamp=100.0,
            session_id="s1",
            head_pose_score=1.0,
            behavior_score=2.0,
            expression_score=3.0,
            evidence_score=4.0,
            people_score=5.0,
            final_focus_score=6.0,
            is_force_zero=False,
            is_over_threshold=True,
            warn_candidates=(),
        )
        d = result.to_dict()
        expected_keys = {
            "timestamp", "session_id",
            "head_pose_score", "behavior_score", "expression_score",
            "evidence_score", "people_score", "final_focus_score",
            "is_force_zero", "is_over_threshold", "warn_info",
        }
        assert set(d.keys()) == expected_keys


# ── MonitorMode 枚举 ────────────────────────────────────────

class TestMonitorMode:
    """监督模式枚举测试"""

    def test_class_value(self):
        assert MonitorMode.CLASS.value == "class"

    def test_exam_value(self):
        assert MonitorMode.EXAM.value == "exam"


# ── SessionInfo 数据类 ──────────────────────────────────────

class TestSessionInfo:
    """SessionInfo 数据类测试"""

    def test_default_values(self):
        """默认值正确"""
        info = SessionInfo(session_id="s1", mode=MonitorMode.CLASS, start_time=100.0)
        assert info.session_id == "s1"
        assert info.mode == MonitorMode.CLASS
        assert info.start_time == 100.0
        assert info.end_time is None
        assert info.warn_threshold == 60.0
        assert info.is_running is True
        assert info.total_frames == 0
        assert info.abnormal_event_count == 0


# ── FeatureData 数据类 ──────────────────────────────────────

class TestFeatureData:
    """FeatureData 数据类测试"""

    def test_default_num_face_total(self):
        """num_face_total 默认值为 1"""
        fd = FeatureData(
            timestamp=0.0,
            face_id="f1",
            head_pose={"pitch": 0, "yaw": 0, "roll": 0, "confidence": 1},
            eye_state={"value": 0, "confidence": 1},
            is_looking_screen={"value": True, "confidence": 1},
            attention_state={"value": 0, "confidence": 1},
            face_distance_state={"value": 0, "confidence": 1},
            is_yawning={"value": False, "confidence": 1},
        )
        assert fd.num_face_total["value"] == 1
        assert fd.face_matched is True

    def test_frozen_prevents_mutation(self):
        """frozen=True 阻止修改"""
        fd = FeatureData(
            timestamp=0.0,
            face_id="f1",
            head_pose={"pitch": 0, "yaw": 0, "roll": 0, "confidence": 1},
            eye_state={"value": 0, "confidence": 1},
            is_looking_screen={"value": True, "confidence": 1},
            attention_state={"value": 0, "confidence": 1},
            face_distance_state={"value": 0, "confidence": 1},
            is_yawning={"value": False, "confidence": 1},
        )
        with pytest.raises(Exception):
            fd.timestamp = 999.0
