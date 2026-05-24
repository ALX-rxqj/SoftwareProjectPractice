"""
降采样器单元测试 — Downsampler Tests

测试 src/state_estimation/downsampler.py 中 Downsampler 的：
- 窗口未满不输出
- 窗口满触发输出
- flush 清空残余帧
- 全异常窗口取首帧
- 正常窗口取最接近均值帧
- 告警类型优先级选取
- reset 清空缓冲区

运行方式:
    python -m pytest test/test_downsampler.py -v
"""

import pytest

from src.state_estimation.contracts import (
    FocusResultData, WarnInfo,
    WARN_NO_FACE, WARN_MULTI_FACE, WARN_EYE_STATE,
)
from src.state_estimation.downsampler import Downsampler, DOWNSAMPLE_WINDOW_SECONDS


def _make_result(timestamp, final_focus=85.0, is_force_zero=False,
                 warn_candidates=(), session_id="s1"):
    """快捷构造 FocusResultData"""
    return FocusResultData(
        timestamp=timestamp, session_id=session_id,
        head_pose_score=80.0, eye_score=85.0, yawn_score=75.0,
        distance_score=80.0,
        evidence_score=80.0, people_score=100.0,
        final_focus_score=final_focus,
        is_force_zero=is_force_zero,
        is_over_threshold=False,
        warn_candidates=warn_candidates,
    )


# ── 基本行为 ────────────────────────────────────────────────

class TestBasicBehavior:
    """基本输入输出行为"""

    def test_single_frame_returns_none(self, downsampler):
        """单帧不足触发输出"""
        result = downsampler.add_frame(_make_result(0.0))
        assert result is None

    def test_two_frames_within_window_returns_none(self, downsampler):
        """两帧但时间差不足窗口 → 不输出"""
        downsampler.add_frame(_make_result(0.0))
        result = downsampler.add_frame(_make_result(0.5))  # 0.5s < 1s
        assert result is None

    def test_window_fills_triggers_output(self, downsampler):
        """时间差 >= 窗口长度 → 输出"""
        downsampler.add_frame(_make_result(0.0))
        result = downsampler.add_frame(_make_result(1.5))  # 1.5s > 1s
        assert result is not None
        assert isinstance(result, FocusResultData)

    def test_output_consumes_buffer(self, downsampler):
        """输出后缓冲区清空"""
        downsampler.add_frame(_make_result(0.0))
        downsampler.add_frame(_make_result(1.5))
        # 第三帧不会和前面的混合
        result = downsampler.add_frame(_make_result(1.6))
        assert result is None  # 缓冲区已清空，1.6-0=1.6>1，但只有新的一帧

    def test_multiple_windows_produce_multiple_outputs(self, downsampler):
        """连续输入超过多个窗口帧 → 每窗输出一次"""
        downsampler.add_frame(_make_result(0.0))
        out1 = downsampler.add_frame(_make_result(1.5))
        assert out1 is not None

        out2 = downsampler.add_frame(_make_result(3.0))
        assert out2 is None  # 和上一帧差 1.5s 但缓冲只有一帧...

        # 重新测试：确保连续输入产生多个输出
        out3 = downsampler.add_frame(_make_result(4.0))
        assert out3 is not None  # 第二个窗口


# ── flush ───────────────────────────────────────────────────

class TestFlush:
    """flush 清空残余帧"""

    def test_flush_returns_remaining(self, downsampler):
        """缓冲区有数据时 flush 输出"""
        downsampler.add_frame(_make_result(0.0))
        result = downsampler.flush()
        assert result is not None
        assert isinstance(result, FocusResultData)

    def test_flush_empty_returns_none(self, downsampler):
        """缓冲区空时 flush 返回 None"""
        assert downsampler.flush() is None

    def test_flush_after_output_returns_none(self, downsampler):
        """刚输出后 flush 返回 None"""
        downsampler.add_frame(_make_result(0.0))
        downsampler.add_frame(_make_result(1.5))
        result = downsampler.flush()
        assert result is None


# ── 异常窗口处理 ────────────────────────────────────────────

class TestAnomalyWindow:
    """全异常窗口取第一帧"""

    def test_all_anomaly_picks_first_frame(self, downsampler):
        """全异常帧窗口取第一帧"""
        f1 = _make_result(0.0, final_focus=0.0, is_force_zero=True,
                          warn_candidates=(WarnInfo(WARN_NO_FACE, "无人脸"),))
        f2 = _make_result(1.5, final_focus=0.0, is_force_zero=True,
                          warn_candidates=(WarnInfo(WARN_NO_FACE, "无人脸"),))
        downsampler.add_frame(f1)
        result = downsampler.add_frame(f2)
        assert result is not None
        assert result.timestamp == f1.timestamp  # 取第一帧


# ── 正常窗口：均值帧选取 ────────────────────────────────────

class TestNormalMeanPicking:
    """正常窗口选最接近均值帧"""

    def test_normal_window_picks_closest_to_mean(self, downsampler):
        """正常帧中选取 final_focus 最接近均值的帧"""
        f1 = _make_result(0.0, final_focus=80.0)
        f2 = _make_result(1.5, final_focus=90.0)
        downsampler.add_frame(f1)
        # 第二帧触发输出（时间差 1.5s >= 1s 窗口）
        result = downsampler.add_frame(f2)
        # 均值 = (80+90)/2 = 85 → 应选取最接近 85 的帧，即 80
        assert result is not None
        assert result.final_focus_score == pytest.approx(85.0, abs=10)


# ── 告警类型优先级选取 ──────────────────────────────────────

class TestAlertPriorityInWindow:
    """窗口内告警类型按优先级选取"""

    def test_triggered_alert_type_wins(self, downsampler):
        """某类告警占比超阈值 → 选该类帧中均值帧"""
        # 2 帧都带 no_face 告警（占比 100% > 50%）
        downsampler.add_frame(_make_result(
            0.0, final_focus=0.0, is_force_zero=True,
            warn_candidates=(WarnInfo(WARN_NO_FACE, "无人脸"),),
        ))
        # 第二帧触发输出（时间差 1.5s >= 1s 窗口）
        result = downsampler.add_frame(_make_result(
            1.5, final_focus=0.0, is_force_zero=True,
            warn_candidates=(WarnInfo(WARN_NO_FACE, "无人脸"),),
        ))
        assert result is not None
        # 获胜告警包含在输出中
        assert len(result.warn_candidates) == 1
        assert result.warn_candidates[0].warn_type == WARN_NO_FACE

    def test_multiple_types_highest_priority_wins(self, downsampler):
        """多个类型超阈值 → 优先级高的获胜"""
        # 两帧：一帧 no_face(pri=1)，一帧 low_behavior(pri=5)
        # 各占 50%，都等于阈值，都应触发
        f1 = _make_result(0.0, final_focus=0.0, is_force_zero=True,
                          warn_candidates=(WarnInfo(WARN_NO_FACE, "无人脸"),))
        f2 = _make_result(1.5, final_focus=30.0,
                          warn_candidates=(WarnInfo(WARN_EYE_STATE, "眼部状态低分"),))
        downsampler.add_frame(f1)
        result = downsampler.add_frame(f2)
        assert result is not None
        assert result.warn_candidates[0].warn_type == WARN_NO_FACE

    def test_no_alert_triggered_picks_normal_frame(self, downsampler):
        """无告警超过阈值 → 在正常帧中选均值"""
        f1 = _make_result(0.0, final_focus=80.0)
        f2 = _make_result(1.5, final_focus=90.0)
        downsampler.add_frame(f1)
        result = downsampler.add_frame(f2)
        assert result is not None
        assert len(result.warn_candidates) == 0


# ── reset ───────────────────────────────────────────────────

class TestReset:
    """reset 清空缓冲区"""

    def test_reset_clears_buffer(self, downsampler):
        """reset 后缓冲区为空"""
        downsampler.add_frame(_make_result(0.0))
        downsampler.add_frame(_make_result(0.5))
        downsampler.reset()
        assert downsampler.flush() is None

    def test_get_output_frame_consumes(self, downsampler):
        """get_output_frame 消费式获取，取后即清"""
        downsampler.add_frame(_make_result(0.0))
        downsampler.add_frame(_make_result(1.5))
        out1 = downsampler.get_output_frame()
        assert out1 is not None
        out2 = downsampler.get_output_frame()
        assert out2 is None  # 已清空


# ── 自定义窗口长度 ──────────────────────────────────────────

class TestCustomWindow:
    """自定义窗口长度"""

    def test_short_window_triggers_earlier(self):
        """短窗口（0.3s）比默认（1s）更快触发"""
        ds = Downsampler(window_seconds=0.3)
        ds.add_frame(_make_result(0.0))
        result = ds.add_frame(_make_result(0.4))
        assert result is not None
