"""
专注度评估器 - Focus Estimator

负责实现专注度评分算法。
评分维度：头部姿态 / 行为动作 / 表情 / 证据融合 / 人数
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .contracts import (
    FeatureData, MonitorMode, WarnInfo,
    WARN_NO_FACE, WARN_MULTI_FACE, WARN_FACE_MISMATCH,
    WARN_LOW_EVIDENCE, WARN_LOW_HEAD_POSE,
    WARN_LOW_BEHAVIOR, WARN_LOW_EXPRESSION,
    LOW_SCORE_THRESHOLD,
)

# ============================================================
# 专注度评分宏参数（可按需调整）
# ============================================================

# --- 头部姿态评分参数 ---
# 各维度权重（pitch=上下, yaw=左右, roll=歪头）
HEAD_POSE_WEIGHT_PITCH = 0.4
HEAD_POSE_WEIGHT_YAW = 0.4
HEAD_POSE_WEIGHT_ROLL = 0.2

# 正常偏转范围（满分区间），单位：度
HEAD_POSE_NORMAL_PITCH_MIN = -15  # pitch 正常范围下限
HEAD_POSE_NORMAL_PITCH_MAX = 10   # pitch 正常范围上限
HEAD_POSE_NORMAL_YAW_MIN = -12    # yaw 正常范围下限
HEAD_POSE_NORMAL_YAW_MAX = 12     # yaw 正常范围上限
HEAD_POSE_NORMAL_ROLL_MIN = -10   # roll 正常范围下限
HEAD_POSE_NORMAL_ROLL_MAX = 10    # roll 正常范围上限

# 角度极限（超出即置0）
HEAD_POSE_MAX_ANGLE = 90

# 分数上下限
HEAD_POSE_SCORE_MAX = 100.0
HEAD_POSE_SCORE_MIN = 0.0

# 置信度阈值
HEAD_POSE_CONF_HIGH = 0.8  # c >= 0.8 直接采用原分数
HEAD_POSE_CONF_LOW = 0.5   # 0.5 <= c < 0.8 在 [原分数, 0] 间线性插值

# --- 动作评分参数 ---
# 各维度权重
BEHAVIOR_WEIGHT_EYE = 0.35      # 睁眼闭眼权重
BEHAVIOR_WEIGHT_LOOKING = 0.35  # 注视屏幕权重
BEHAVIOR_WEIGHT_YAWNING = 0.1   # 打哈欠权重
BEHAVIOR_WEIGHT_DISTANCE = 0.2  # 人脸距离权重

# 好状态基准分
BEHAVIOR_SCORE_GOOD = 100.0
# 坏状态基准分（高置信度时）
BEHAVIOR_SCORE_BAD = 0.0
# 中间分（低置信度收敛点）
BEHAVIOR_SCORE_NEUTRAL = 50.0

# 置信度阈值
BEHAVIOR_CONF_HIGH = 0.8  # c >= 0.8 直接采用原分数
BEHAVIOR_CONF_LOW = 0.5   # 0.5 <= c < 0.8 在 [原分数, 50] 间线性插值

# --- 表情评分参数 ---
# 各注意力状态基准分
EXPRESSION_SCORE_FOCUSED = 100     # 专注
EXPRESSION_SCORE_DISTRACTED = 60   # 分心
EXPRESSION_SCORE_SLEEPY = 30       # 困倦
EXPRESSION_SCORE_ABSENT = 0        # 离席

# 下一级分数映射（用于置信度插值）
_EXPRESSION_NEXT_LEVEL = {
    0: EXPRESSION_SCORE_DISTRACTED,  # 专注 → 分心
    1: EXPRESSION_SCORE_SLEEPY,      # 分心 → 困倦
    2: EXPRESSION_SCORE_ABSENT,      # 困倦 → 离席
    3: EXPRESSION_SCORE_ABSENT,      # 离席无下级
}

# 置信度阈值
EXPRESSION_CONF_HIGH = 0.8  # c >= 0.8 直接采用原分数
EXPRESSION_CONF_LOW = 0.5   # 0.5 <= c < 0.8 在 [本级别, 下一级] 间线性插值

# --- 人数评分参数 ---
PEOPLE_SCORE_SINGLE = 100  # 单人满分
PEOPLE_SCORE_OTHER = 0     # 无人或多人

# --- 全局置信度参数 ---
GLOBAL_CONF_MIN = 0.5  # 置信度低于此值视为无效，该维度置50并告警

# --- 人数异常累计阈值 ---
# 整堂课人数异常帧数（_abnormal_count）超过此值则 is_over_threshold 置 True
FORCE_ZERO_THRESHOLD = {
    "class": 500,  # 网课：500帧异常触发
    "exam": 200,   # 考试：200帧异常触发（更严格）
}

# --- 证据理论融合参数 ---
# 三个证据源各自的折扣系数 α（0 < α <= 1，越小折扣越重）
# 考试模式 α 更低 → 融合更保守 → 更难拿高分
EVIDENCE_DISCOUNT_HEAD_POSE = {
    "class": 0.6,   # 网课：头部姿态折扣系数
    "exam": 0.5,    # 考试：更不信头姿（可能低头看题）
}
EVIDENCE_DISCOUNT_BEHAVIOR = {
    "class": 0.6,   # 网课：行为动作折扣系数
    "exam": 0.5,    # 考试：更不信动作
}
EVIDENCE_DISCOUNT_EXPRESSION = {
    "class": 0.6,   # 网课：表情折扣系数
    "exam": 0.6,    # 考试：表情同等对待
}


class FocusEstimator:
    """
    专注度评估器核心类

    评分维度：
    - head_pose: 头部姿态评分
    - behavior: 行为动作评分
    - expression: 表情评分
    - evidence: 证据理论融合评分（D-S 规则，三源折扣融合）
    - people: 人数项评分

    支持两种模式：
    - CLASS: 网课模式
    - EXAM: 考试模式（当前参数与CLASS一致，后续权重差异化）
    """

    def __init__(self, mode: MonitorMode = MonitorMode.CLASS):
        """初始化专注度评估器"""
        self.mode = mode
        self._abnormal_count = 0  # 人数异常帧计数（num_face_total != 1）

    def set_mode(self, mode: MonitorMode):
        """设置评估模式（CLASS / EXAM）"""
        self.mode = mode

    # ================================================================
    # 公开接口
    # ================================================================

    def estimate(
        self, feature_data: FeatureData, num_people: int = 1
    ) -> Tuple[Dict[str, float], bool, bool, Tuple[WarnInfo, ...]]:
        """
        计算一帧的专注度评分

        Args:
            feature_data: 特征数据（来自特征提取模块）
            num_people: 画面中的人数（兼容旧接口，优先使用 feature_data.num_face_total）

        Returns:
            scores: 各维度评分字典
            is_force_zero: 当前帧是否强制置0（人数异常）
            is_over_threshold: 累计异常次数是否超过阈值
            warn_candidates: 本帧触发的所有告警候选
        """
        # 优先从 FeatureData 中提取人数
        num_face_data = feature_data.num_face_total
        num_face = num_face_data.get("value", num_people) if num_face_data else num_people

        head_pose_score, head_pose_warn = self._score_head_pose(feature_data.head_pose)
        behavior_score, behavior_warn = self._score_behavior(feature_data)
        expression_score, expression_warn = self._score_expression(feature_data.attention_state)
        people_score, people_warn = self._score_people(num_face)

        # 证据理论融合（三源：头姿/动作/表情）
        evidence_score = self._fuse_evidence(
            head_pose_score, behavior_score, expression_score
        )

        # 专注度评分过低告警
        evidence_warn = None
        if evidence_score < LOW_SCORE_THRESHOLD:
            evidence_warn = WarnInfo(
                warn_type=WARN_LOW_EVIDENCE,
                detail=f"专注度评分过低: {evidence_score:.0f}",
            )

        # 人脸不匹配告警（与人数异常同等优先）
        face_mismatch_warn = None
        if not feature_data.face_matched:
            face_mismatch_warn = WarnInfo(
                warn_type=WARN_FACE_MISMATCH,
                detail="人脸不匹配",
            )

        # 最终专注度 = 人数开关 + 人脸匹配控制
        if people_score == PEOPLE_SCORE_SINGLE and not face_mismatch_warn:
            final_focus = evidence_score
            is_force_zero = False
        else:
            final_focus = 0.0
            is_force_zero = True
            self._abnormal_count += 1

        # 人数异常累计是否超过阈值
        mode_key = self.mode.value
        is_over_threshold = self._abnormal_count >= FORCE_ZERO_THRESHOLD[mode_key]

        # 收集所有告警候选
        warn_candidates: List[WarnInfo] = []
        if people_warn:
            warn_candidates.append(people_warn)
        if face_mismatch_warn:
            warn_candidates.append(face_mismatch_warn)
        if evidence_warn:
            warn_candidates.append(evidence_warn)
        if head_pose_warn:
            warn_candidates.append(head_pose_warn)
        if behavior_warn:
            warn_candidates.append(behavior_warn)
        if expression_warn:
            warn_candidates.append(expression_warn)

        scores = {
            "head_pose": head_pose_score,
            "behavior": behavior_score,
            "expression": expression_score,
            "evidence": evidence_score,
            "people": people_score,
            "final_focus": final_focus,
        }
        return scores, is_force_zero, is_over_threshold, tuple(warn_candidates)

    def reset(self):
        """重置评估器状态"""
        self._abnormal_count = 0

    @property
    def abnormal_count(self) -> int:
        """获取人数异常帧计数"""
        return self._abnormal_count

    # ================================================================
    # 证据理论融合
    # ================================================================

    def _fuse_evidence(
        self, head_score: float, behavior_score: float, expression_score: float
    ) -> float:
        """
        D-S 证据理论融合三源评分

        识别框架 Θ = {专注, 不专注}
        - m_i({专注}) = α × S_i / 100
        - m_i(Θ) = 1 - α × S_i / 100
        - m_i({不专注}) = 0（只提供正面证据）

        Dempster 组合：
        m({专注}) = 1 - Π(1 - α × S_i/100)
        evidence_score = m({专注}) × 100

        Args:
            head_score: 头部姿态评分 [0, 100]
            behavior_score: 动作评分 [0, 100]
            expression_score: 表情评分 [0, 100]

        Returns:
            evidence_score: 证据融合评分 [0, 100]
        """
        mode_key = self.mode.value  # "class" or "exam"
        scores = (head_score, behavior_score, expression_score)
        alphas = (
            EVIDENCE_DISCOUNT_HEAD_POSE[mode_key],
            EVIDENCE_DISCOUNT_BEHAVIOR[mode_key],
            EVIDENCE_DISCOUNT_EXPRESSION[mode_key],
        )
        product = 1.0
        for score, alpha in zip(scores, alphas):
            belief = alpha * score / 100.0
            product *= (1.0 - belief)  # 当前源"不同意专注"的概率
        belief_focused = 1.0 - product
        return belief_focused * 100.0

    # ================================================================
    # 头部姿态评分
    # ================================================================

    def _score_head_pose(self, head_pose: Dict) -> Tuple[float, Optional[WarnInfo]]:
        """
        头部姿态评分

        三个维度分别计算角度评分，用同一个置信度修正，
        最后加权求和。分数 < 50 时附加告警。
        """
        pitch = head_pose.get("pitch", 0.0)
        yaw = head_pose.get("yaw", 0.0)
        roll = head_pose.get("roll", 0.0)
        confidence = head_pose.get("confidence", 1.0)

        pitch_score = self._score_head_angle(
            pitch, HEAD_POSE_NORMAL_PITCH_MIN, HEAD_POSE_NORMAL_PITCH_MAX
        )
        pitch_score = self._apply_conf_head_pose(pitch_score, confidence)

        yaw_score = self._score_head_angle(
            yaw, HEAD_POSE_NORMAL_YAW_MIN, HEAD_POSE_NORMAL_YAW_MAX
        )
        yaw_score = self._apply_conf_head_pose(yaw_score, confidence)

        roll_score = self._score_head_angle(
            roll, HEAD_POSE_NORMAL_ROLL_MIN, HEAD_POSE_NORMAL_ROLL_MAX
        )
        roll_score = self._apply_conf_head_pose(roll_score, confidence)

        score = (
            HEAD_POSE_WEIGHT_PITCH * pitch_score
            + HEAD_POSE_WEIGHT_YAW * yaw_score
            + HEAD_POSE_WEIGHT_ROLL * roll_score
        )

        warn = None
        if score < LOW_SCORE_THRESHOLD:
            warn = WarnInfo(
                warn_type=WARN_LOW_HEAD_POSE,
                detail=f"头部姿态评分过低: {score:.0f}",
            )
        return score, warn

    def _score_head_angle(self, angle: float, normal_min: float, normal_max: float) -> float:
        """
        计算单个角度的基础评分

        正常范围内：100
        超出正常但在 ±90° 内：100 → 0 线性
        超过 ±90°：直接 0
        """
        if normal_min <= angle <= normal_max:
            return HEAD_POSE_SCORE_MAX

        if angle > normal_max:
            if angle >= HEAD_POSE_MAX_ANGLE:
                return HEAD_POSE_SCORE_MIN
            ratio = (angle - normal_max) / (HEAD_POSE_MAX_ANGLE - normal_max)
            return HEAD_POSE_SCORE_MAX * (1.0 - ratio)

        if angle <= -HEAD_POSE_MAX_ANGLE:
            return HEAD_POSE_SCORE_MIN
        ratio = (normal_min - angle) / (normal_min - (-HEAD_POSE_MAX_ANGLE))
        return HEAD_POSE_SCORE_MAX * (1.0 - ratio)

    def _apply_conf_head_pose(self, score: float, confidence: float) -> float:
        """
        头部姿态评分置信度修正

        c >= 0.8: 直接采用原分数
        0.5 <= c < 0.8: 在 [原分数, 0] 间线性插值
        c < 0.5: 置 50 并告警
        """
        if confidence >= HEAD_POSE_CONF_HIGH:
            return score
        if confidence < GLOBAL_CONF_MIN:
            return BEHAVIOR_SCORE_NEUTRAL
        t = (confidence - HEAD_POSE_CONF_LOW) / (HEAD_POSE_CONF_HIGH - HEAD_POSE_CONF_LOW)
        return score * t

    # ================================================================
    # 行为动作评分
    # ================================================================

    def _score_behavior(self, feature_data: FeatureData) -> Tuple[float, Optional[WarnInfo]]:
        """
        行为动作评分

        四个子维度各用各的置信度修正后加权求和。
        好状态: [50, 100], 坏状态: [0, 50]
        分数 < 50 时附加告警。
        """
        eye_state = feature_data.eye_state
        eye_value = eye_state.get("value", 0) if eye_state else 0
        eye_raw = BEHAVIOR_SCORE_GOOD if eye_value == 0 else BEHAVIOR_SCORE_BAD
        eye_score = self._apply_conf_behavior(eye_raw, eye_state.get("confidence", 1.0) if eye_state else 1.0)

        looking = feature_data.is_looking_screen
        looking_value = looking.get("value", True) if looking else True
        looking_raw = BEHAVIOR_SCORE_GOOD if looking_value else BEHAVIOR_SCORE_BAD
        looking_score = self._apply_conf_behavior(
            looking_raw, looking.get("confidence", 1.0) if looking else 1.0
        )

        yawning = feature_data.is_yawning
        yawning_value = yawning.get("value", False) if yawning else False
        yawning_raw = BEHAVIOR_SCORE_GOOD if not yawning_value else BEHAVIOR_SCORE_BAD
        yawning_score = self._apply_conf_behavior(
            yawning_raw, yawning.get("confidence", 1.0) if yawning else 1.0
        )

        distance = feature_data.face_distance_state
        distance_value = distance.get("value", 0) if distance else 0
        distance_raw = BEHAVIOR_SCORE_GOOD if distance_value == 0 else BEHAVIOR_SCORE_BAD
        distance_score = self._apply_conf_behavior(
            distance_raw, distance.get("confidence", 1.0) if distance else 1.0
        )

        score = (
            BEHAVIOR_WEIGHT_EYE * eye_score
            + BEHAVIOR_WEIGHT_LOOKING * looking_score
            + BEHAVIOR_WEIGHT_YAWNING * yawning_score
            + BEHAVIOR_WEIGHT_DISTANCE * distance_score
        )

        warn = None
        if score < LOW_SCORE_THRESHOLD:
            warn = WarnInfo(
                warn_type=WARN_LOW_BEHAVIOR,
                detail=f"行为动作评分过低: {score:.0f}",
            )
        return score, warn

    def _apply_conf_behavior(self, score: float, confidence: float) -> float:
        """
        行为动作评分置信度修正

        c >= 0.8: 直接采用原分数
        0.5 <= c < 0.8: 在 [原分数, 50] 间线性插值
        c < 0.5: 置 50 并告警
        """
        if confidence >= BEHAVIOR_CONF_HIGH:
            return score
        if confidence < GLOBAL_CONF_MIN:
            return BEHAVIOR_SCORE_NEUTRAL
        t = (confidence - BEHAVIOR_CONF_LOW) / (BEHAVIOR_CONF_HIGH - BEHAVIOR_CONF_LOW)
        return BEHAVIOR_SCORE_NEUTRAL + (score - BEHAVIOR_SCORE_NEUTRAL) * t

    # ================================================================
    # 表情评分
    # ================================================================

    def _score_expression(self, attention_state: Dict) -> Tuple[float, Optional[WarnInfo]]:
        """
        表情评分

        根据 attention_state.value 映射基准分，
        再用置信度向下一级插值。
        分数 < 50 时附加告警。
        """
        state_value = attention_state.get("value", 0) if attention_state else 0
        confidence = attention_state.get("confidence", 1.0) if attention_state else 1.0

        score_map = {
            0: EXPRESSION_SCORE_FOCUSED,
            1: EXPRESSION_SCORE_DISTRACTED,
            2: EXPRESSION_SCORE_SLEEPY,
            3: EXPRESSION_SCORE_ABSENT,
        }
        base_score = score_map.get(state_value, EXPRESSION_SCORE_FOCUSED)
        next_score = _EXPRESSION_NEXT_LEVEL.get(state_value, EXPRESSION_SCORE_ABSENT)

        score = self._apply_conf_expression(base_score, next_score, confidence)

        warn = None
        if score < LOW_SCORE_THRESHOLD:
            warn = WarnInfo(
                warn_type=WARN_LOW_EXPRESSION,
                detail=f"表情评分过低: {score:.0f}",
            )
        return score, warn

    def _apply_conf_expression(
        self, score: float, next_level: float, confidence: float
    ) -> float:
        """
        表情评分置信度修正

        c >= 0.8: 直接采用原分数
        0.5 <= c < 0.8: 在 [本级别, 下一级] 间线性插值
        c < 0.5: 置 50 并告警
        """
        if confidence >= EXPRESSION_CONF_HIGH:
            return score
        if confidence < GLOBAL_CONF_MIN:
            return BEHAVIOR_SCORE_NEUTRAL
        t = (confidence - EXPRESSION_CONF_LOW) / (EXPRESSION_CONF_HIGH - EXPRESSION_CONF_LOW)
        return next_level + (score - next_level) * t

    # ================================================================
    # 人数评分
    # ================================================================

    def _score_people(self, num_face: int) -> Tuple[float, Optional[WarnInfo]]:
        """
        人数评分

        1人=100，否则=0。不使用置信度。
        人数异常时附加告警。
        """
        if num_face == 1:
            return PEOPLE_SCORE_SINGLE, None

        if num_face == 0:
            warn = WarnInfo(warn_type=WARN_NO_FACE, detail="画面中无人脸")
        else:
            warn = WarnInfo(warn_type=WARN_MULTI_FACE, detail=f"画面中有{num_face}张人脸")
        return PEOPLE_SCORE_OTHER, warn
