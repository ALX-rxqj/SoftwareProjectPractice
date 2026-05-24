"""
专注度评估器单元测试 — Focus Estimator Tests

测试 src/state_estimation/estimator.py 中 FocusEstimator 的所有评分维度：
- 头部姿态评分（角度→分数映射 + 置信度修正）
- 行为动作评分（四子维度加权求和 + 置信度修正）
- 表情评分（四状态映射 + 置信度插值）
- 人数评分（单人/无人/多人）
- D-S 证据融合（class vs exam 折扣系数差异）
- 完整 estimate() 流程
- 异常计数累积与阈值

运行方式:
    python -m pytest test/test_focus_estimator.py -v
"""

import math
import pytest

from src.state_estimation.contracts import (
    FeatureData, MonitorMode, WarnInfo,
    WARN_NO_FACE, WARN_MULTI_FACE, WARN_FACE_MISMATCH,
    WARN_LOW_EVIDENCE, WARN_HEAD_POSE,
    WARN_EYE_STATE, WARN_YAWNING,
)
from src.state_estimation.estimator import FocusEstimator


# ── 辅助函数 ────────────────────────────────────────────────

def _hd(pitch=0.0, yaw=0.0, roll=0.0, confidence=1.0):
    """快捷构造头部姿态字典"""
    return {"pitch": pitch, "yaw": yaw, "roll": roll, "confidence": confidence}


def _make_fd(head_pose=None, eye_state=None, looking=None,
             attention=None, distance=None, yawning=None,
             num_face=None, face_matched=True, face_id="f1"):
    """快捷构造 FeatureData"""
    return FeatureData(
        timestamp=0.0, face_id=face_id, face_matched=face_matched,
        head_pose=head_pose or _hd(),
        eye_state=eye_state or {"value": 0, "confidence": 1.0},
        is_looking_screen=looking or {"value": True, "confidence": 1.0},
        attention_state=attention or {"value": 0, "confidence": 1.0},
        face_distance_state=distance or {"value": 0, "confidence": 1.0},
        is_yawning=yawning or {"value": False, "confidence": 1.0},
        num_face_total=num_face or {"value": 1, "confidence": 1.0},
    )


# ============================================================
# 头部姿态评分测试
# ============================================================

class TestHeadPoseScoring:
    """头部姿态各角度基础评分 + 置信度修正"""

    def test_perfect_pose_full_score(self, estimator_class):
        """所有角度在正常范围、高置信度 → 接近 100"""
        fd = _make_fd(head_pose=_hd(pitch=0, yaw=0, roll=0, confidence=1.0))
        score, _ = estimator_class._score_head_pose(fd.head_pose)
        assert score == pytest.approx(100.0)

    def test_pitch_out_of_normal_range_drops(self, estimator_class):
        """pitch 超出正常范围但未到极限 → 分数线性下降"""
        fd = _make_fd(head_pose=_hd(pitch=45, yaw=0, roll=0, confidence=1.0))
        score, _ = estimator_class._score_head_pose(fd.head_pose)
        # pitch=45, normal_max=10, max_angle=90
        # pitch_score = 100 * (1 - (45-10)/(90-10)) = 100 * (1 - 35/80) = 56.25
        # 加权后: 0.4 * 56.25 + 0.4*100 + 0.2*100 = 22.5 + 40 + 20 = 82.5
        assert score < 90
        assert score > 60

    def test_yaw_at_limit_zero(self, estimator_class):
        """yaw 超出极限 90° → 该维度置零"""
        fd = _make_fd(head_pose=_hd(pitch=0, yaw=90, roll=0, confidence=1.0))
        score, _ = estimator_class._score_head_pose(fd.head_pose)
        # yaw_score=0, pitch=100, roll=100 → 0.4*100 + 0.4*0 + 0.2*100 = 60
        assert 55 < score < 65

    def test_negative_angle_out_of_range(self, estimator_class):
        """负角度超出正常范围但未到极限 → 线性下降"""
        fd = _make_fd(head_pose=_hd(pitch=-35, yaw=0, roll=0, confidence=1.0))
        score, _ = estimator_class._score_head_pose(fd.head_pose)
        # pitch=-35, normal_min=-15, max=90
        # (normal_min - angle)/(normal_min - (-90)) = (-15 - (-35))/(-15+90) = 20/75 = 0.267
        # pitch_score = 100*(1-0.267)=73.33
        # 0.4*73.33+0.4*100+0.2*100 = 29.33+40+20 = 89.33
        assert 85 < score < 95

    def test_negative_angle_beyond_limit_zero(self, estimator_class):
        """角度 <= -90 → 该维度置零"""
        fd = _make_fd(head_pose=_hd(pitch=-90, yaw=0, roll=0, confidence=1.0))
        score, _ = estimator_class._score_head_pose(fd.head_pose)
        # pitch=0, yaw=100, roll=100 → 0.4*0+0.4*100+0.2*100 = 60
        assert 55 < score < 65

    def test_medium_confidence_interpolates(self, estimator_class):
        """中等置信度(0.65)在原始分数和 0 之间插值"""
        fd_good = _make_fd(head_pose=_hd(confidence=1.0))
        score_high, _ = estimator_class._score_head_pose(fd_good.head_pose)

        fd_med = _make_fd(head_pose=_hd(confidence=0.65))
        score_med, _ = estimator_class._score_head_pose(fd_med.head_pose)

        # t = (0.65-0.5)/(0.8-0.5) = 0.5 → score_med = 100 * 0.5 = 50
        assert 0 < score_med < score_high

    def test_low_confidence_neutral(self, estimator_class):
        """低置信度(<0.5) → 分数置 50"""
        fd = _make_fd(head_pose=_hd(confidence=0.3))
        score, _ = estimator_class._score_head_pose(fd.head_pose)
        # 三个维度都置50，加权后还是50
        assert score == pytest.approx(50.0)

    def test_low_score_triggers_warn(self, estimator_class):
        """头部姿态评分 < 50 时触发告警"""
        fd = _make_fd(head_pose=_hd(pitch=80, yaw=80, roll=80, confidence=1.0))
        score, warn = estimator_class._score_head_pose(fd.head_pose)
        assert score < 50
        assert warn is not None
        assert warn.warn_type == WARN_HEAD_POSE


# ============================================================
# 行为动作评分测试
# ============================================================

class TestBehaviorScoring:
    """行为动作四子维度评分"""

    def test_all_good_behavior_full_score(self, estimator_class):
        """全部好状态 → 接近 100"""
        fd = _make_fd()
        score, _ = estimator_class._score_behavior(fd)
        assert score == pytest.approx(100.0)

    def test_eyes_closed_drops_eye_component(self, estimator_class):
        """闭眼 → eye_score 变为坏状态"""
        fd = _make_fd(eye_state={"value": 1, "confidence": 1.0})
        score, _ = estimator_class._score_behavior(fd)
        # eye=0, looking=100, yawning=100, distance=100
        # 0.35*0 + 0.35*100 + 0.1*100 + 0.2*100 = 65
        assert score == pytest.approx(65.0)

    def test_not_looking_screen_drops(self, estimator_class):
        """不看屏幕 → looking 组件下降"""
        fd = _make_fd(looking={"value": False, "confidence": 1.0})
        score, _ = estimator_class._score_behavior(fd)
        assert score == pytest.approx(65.0)

    def test_yawning_drops(self, estimator_class):
        """打哈欠 → yawning 组件下降"""
        fd = _make_fd(yawning={"value": True, "confidence": 1.0})
        score, _ = estimator_class._score_behavior(fd)
        assert score == pytest.approx(90.0)

    def test_abnormal_distance_drops(self, estimator_class):
        """距离异常 → distance 组件下降"""
        fd = _make_fd(distance={"value": 1, "confidence": 1.0})
        score, _ = estimator_class._score_behavior(fd)
        assert score == pytest.approx(80.0)

    def test_weighted_sum_formula(self, estimator_class):
        """验证加权求和公式: 0.35*eye + 0.35*looking + 0.1*yawning + 0.2*distance"""
        fd = _make_fd(
            eye_state={"value": 0, "confidence": 1.0},
            looking={"value": True, "confidence": 1.0},
            yawning={"value": False, "confidence": 1.0},
            distance={"value": 0, "confidence": 1.0},
        )
        score, _ = estimator_class._score_behavior(fd)
        assert score == pytest.approx(100.0)

    def test_behavior_medium_conf_interpolates(self, estimator_class):
        """中等置信度 → 在原分数和 50 之间插值"""
        fd = _make_fd(
            eye_state={"value": 1, "confidence": 0.65},
            looking={"value": True, "confidence": 1.0},
        )
        score, _ = estimator_class._score_behavior(fd)
        # eye: bad→0, conf=0.65: t=0.5, 50+(0-50)*0.5=25
        # total: 0.35*25 + 0.35*100 + 0.1*100 + 0.2*100 = 8.75+35+10+20 = 73.75
        assert 70 < score < 80

    def test_behavior_low_conf_neutral(self, estimator_class):
        """低置信度(<0.5) → 置 50"""
        fd = _make_fd(
            eye_state={"value": 1, "confidence": 0.3},
            looking={"value": False, "confidence": 0.3},
            yawning={"value": True, "confidence": 0.3},
            distance={"value": 1, "confidence": 0.3},
        )
        score, _ = estimator_class._score_behavior(fd)
        # 四个子维度全部低置信置50: 0.35*50+0.35*50+0.1*50+0.2*50 = 50
        assert score == pytest.approx(50.0)

    def test_low_behavior_triggers_warn(self, estimator_class):
        """行为评分 < 50 触发告警"""
        fd = _make_fd(
            eye_state={"value": 1, "confidence": 1.0},
            looking={"value": False, "confidence": 1.0},
            yawning={"value": True, "confidence": 1.0},
        )
        score, warn = estimator_class._score_behavior(fd)
        assert score < 50
        assert warn is not None
        assert warn.warn_type == WARN_EYE_STATE


# ============================================================
# 表情评分测试
# ============================================================

class TestExpressionScoring:
    """表情/注意力状态评分"""

    def test_focused_full_score(self, estimator_class):
        """专注状态 → 100"""
        score, _ = estimator_class._score_expression({"value": 0, "confidence": 1.0})
        assert score == pytest.approx(100.0)

    def test_distracted_score(self, estimator_class):
        """分心状态 → 60"""
        score, _ = estimator_class._score_expression({"value": 1, "confidence": 1.0})
        assert score == pytest.approx(60.0)

    def test_sleepy_score(self, estimator_class):
        """困倦状态 → 30"""
        score, _ = estimator_class._score_expression({"value": 2, "confidence": 1.0})
        assert score == pytest.approx(30.0)

    def test_absent_score(self, estimator_class):
        """离席状态 → 0"""
        score, _ = estimator_class._score_expression({"value": 3, "confidence": 1.0})
        assert score == pytest.approx(0.0)

    def test_medium_conf_interpolates_to_next_level(self, estimator_class):
        """中等置信度 → 在本级和下一级之间插值"""
        # 专注(100) → 分心(60), conf=0.65 (t=0.5): 60+(100-60)*0.5=80
        score, _ = estimator_class._score_expression({"value": 0, "confidence": 0.65})
        assert score == pytest.approx(80.0)

    def test_low_conf_neutral(self, estimator_class):
        """低置信度(<0.5) → 置 50"""
        score, _ = estimator_class._score_expression({"value": 0, "confidence": 0.3})
        assert score == pytest.approx(50.0)

    def test_absent_low_conf(self, estimator_class):
        """离席状态(0)中等置信度 → 0和0之间都是0"""
        score, _ = estimator_class._score_expression({"value": 3, "confidence": 0.65})
        assert score == pytest.approx(0.0)

    def test_low_expression_triggers_warn(self, estimator_class):
        """表情评分 < 50 触发告警"""
        score, warn = estimator_class._score_expression({"value": 2, "confidence": 1.0})
        assert score < 50
        assert warn is not None
        assert warn.warn_type == WARN_YAWNING


# ============================================================
# 人数评分测试
# ============================================================

class TestPeopleScoring:
    """人数评分（不使用置信度）"""

    def test_single_person_full_score(self, estimator_class):
        """单人 → 100，无告警"""
        score, warn = estimator_class._score_people(1)
        assert score == 100.0
        assert warn is None

    def test_no_person_zero_score(self, estimator_class):
        """无人 → 0，有告警"""
        score, warn = estimator_class._score_people(0)
        assert score == 0.0
        assert warn is not None
        assert warn.warn_type == WARN_NO_FACE

    def test_multi_person_zero_score(self, estimator_class):
        """多人 → 0，有告警"""
        score, warn = estimator_class._score_people(3)
        assert score == 0.0
        assert warn is not None
        assert warn.warn_type == WARN_MULTI_FACE


# ============================================================
# D-S 证据融合测试
# ============================================================

class TestEvidenceFusion:
    """Dempster-Shafer 证据理论融合"""

    def test_all_perfect_yields_high_evidence(self, estimator_class):
        """三源全满分 → 融合后接近 100"""
        result = estimator_class._fuse_evidence(100.0, 100.0, 100.0)
        # class: α=0.6 each → 1-(1-0.6)^3 = 1-0.064 = 0.936 → 93.6
        assert 90 < result < 100

    def test_mixed_inputs(self, estimator_class):
        """混合分数 → 融合后有折扣"""
        r1 = estimator_class._fuse_evidence(100.0, 50.0, 0.0)
        # α=0.6 each: product = (1-0.6)*(1-0.3)*(1-0) = 0.4*0.7*1 = 0.28
        # belief = 1-0.28 = 0.72 → 72
        assert 70 < r1 < 75

    def test_all_zero_yields_zero(self, estimator_class):
        """三源全零 → 融合为零"""
        result = estimator_class._fuse_evidence(0.0, 0.0, 0.0)
        assert result == pytest.approx(0.0)

    def test_class_vs_exam_differs(self, estimator_class, estimator_exam):
        """相同输入，EXAM 模式融合结果更低"""
        r_class = estimator_class._fuse_evidence(80.0, 80.0, 80.0)
        r_exam = estimator_exam._fuse_evidence(80.0, 80.0, 80.0)
        assert r_exam < r_class  # EXAM 折扣更重


# ============================================================
# 完整 estimate() 流程测试
# ============================================================

class TestFullEstimate:
    """estimate() 端到端流程"""

    def test_good_frame_high_score(self, estimator_class, sample_feature_data_good):
        """良好帧 → 高分，不强制置零"""
        scores, is_force_zero, is_over, warns = estimator_class.estimate(
            sample_feature_data_good
        )
        assert scores["final_focus"] > 70
        assert is_force_zero is False
        assert is_over is False

    def test_multi_face_force_zero(self, estimator_class, sample_feature_data_multi_face):
        """多人帧 → 强制置零"""
        scores, is_force_zero, is_over, warns = estimator_class.estimate(
            sample_feature_data_multi_face
        )
        assert scores["final_focus"] == 0.0
        assert is_force_zero is True
        assert any(w.warn_type == WARN_MULTI_FACE for w in warns)

    def test_face_mismatch_force_zero(self, estimator_class, sample_feature_data_mismatch):
        """人脸不匹配 → 强制置零"""
        scores, is_force_zero, is_over, warns = estimator_class.estimate(
            sample_feature_data_mismatch
        )
        assert scores["final_focus"] == 0.0
        assert is_force_zero is True
        assert any(w.warn_type == WARN_FACE_MISMATCH for w in warns)

    def test_no_face_force_zero(self, estimator_class, sample_feature_data_no_face):
        """无人脸 → 强制置零"""
        scores, is_force_zero, is_over, warns = estimator_class.estimate(
            sample_feature_data_no_face
        )
        assert scores["final_focus"] == 0.0
        assert is_force_zero is True
        assert any(w.warn_type == WARN_NO_FACE for w in warns)

    def test_returns_all_five_dimensions(self, estimator_class, sample_feature_data_good):
        """返回所有五个评分维度"""
        scores, _, _, _ = estimator_class.estimate(sample_feature_data_good)
        assert set(scores.keys()) == {
            "head_pose", "behavior", "expression", "evidence", "people", "final_focus"
        }

    def test_warns_collected_correctly(self, estimator_class, sample_feature_data_bad_pose):
        """低分场景收集对应告警"""
        _, _, _, warns = estimator_class.estimate(sample_feature_data_bad_pose)
        warn_types = {w.warn_type for w in warns}
        assert WARN_HEAD_POSE in warn_types


# ============================================================
# 异常计数与阈值测试
# ============================================================

class TestAbnormalCount:
    """人数异常累计与阈值"""

    def test_abnormal_count_increments(self, estimator_class, sample_feature_data_multi_face):
        """每次异常帧计数递增"""
        assert estimator_class.abnormal_count == 0
        estimator_class.estimate(sample_feature_data_multi_face)
        assert estimator_class.abnormal_count == 1
        estimator_class.estimate(sample_feature_data_multi_face)
        assert estimator_class.abnormal_count == 2

    def test_over_threshold_exam(self, estimator_exam, sample_feature_data_multi_face):
        """EXAM 模式: 200 帧异常后触发 is_over_threshold"""
        for _ in range(199):
            _, _, is_over, _ = estimator_exam.estimate(sample_feature_data_multi_face)
        assert is_over is False  # 第 199 帧尚未超阈值
        _, _, is_over, _ = estimator_exam.estimate(sample_feature_data_multi_face)
        assert is_over is True  # 第 200 帧触发

    def test_over_threshold_class(self, estimator_class, sample_feature_data_multi_face):
        """CLASS 模式: 500 帧异常后才触发（比 EXAM 更宽松）"""
        for _ in range(200):
            _, _, is_over, _ = estimator_class.estimate(sample_feature_data_multi_face)
        assert is_over is False  # CLASS 需 500 帧

    def test_reset_clears_count(self, estimator_class, sample_feature_data_multi_face):
        """reset() 清零异常计数"""
        estimator_class.estimate(sample_feature_data_multi_face)
        estimator_class.estimate(sample_feature_data_multi_face)
        assert estimator_class.abnormal_count == 2
        estimator_class.reset()
        assert estimator_class.abnormal_count == 0


# ============================================================
# 模式切换测试
# ============================================================

class TestModeSwitching:
    """监督模式切换"""

    def test_default_mode_is_class(self):
        """默认模式为 CLASS"""
        estimator = FocusEstimator()
        assert estimator.mode == MonitorMode.CLASS

    def test_set_mode_changes(self, estimator_class):
        """set_mode 切换模式"""
        estimator_class.set_mode(MonitorMode.EXAM)
        assert estimator_class.mode == MonitorMode.EXAM
