"""
专注度评估器 - Focus Estimator

基于 D-S 证据理论的四源独立证据融合。
四个证据源（头部姿态 / 眼部状态 / 哈欠检测 / 人脸距离）
各自向 {不专注} 分配基本信任质量（mass），经 Dempster 组合后
输出专注度评分。每个源只提供正向证据（m({不专注})），
不确定时 mass 保留在 Θ。

识别框架 Θ = {专注, 不专注}
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .contracts import (
    FeatureData, MonitorMode, WarnInfo,
    WARN_NO_FACE, WARN_MULTI_FACE, WARN_FACE_MISMATCH,
    WARN_LOW_EVIDENCE, WARN_HEAD_POSE, WARN_EYE_STATE,
    WARN_YAWNING, WARN_DISTANCE,
    LOW_SCORE_THRESHOLD,
)

# ============================================================
# 宏参数（可按需调整）
# ============================================================

# --- 证据源折扣系数 α ---
# α ∈ (0, 1]，表示对该传感器的信任程度。
# 越小折扣越重 → 该源提供的 m({不专注}) 越弱。
EVIDENCE_DISCOUNT_HEAD_POSE = {"class": 0.8, "exam": 0.9}
EVIDENCE_DISCOUNT_EYE_STATE = {"class": 0.8, "exam": 0.7}
EVIDENCE_DISCOUNT_YAWNING   = {"class": 0.6, "exam": 0.6}
EVIDENCE_DISCOUNT_DISTANCE  = {"class": 0.4, "exam": 0.4}

# --- 头部姿态角度阈值（度） ---
# 各方向正常范围 + 极限角度（正常 → 极限 之间线性变化 ratio 0→1）
# class/exam 分开：考试时 yaw 更敏感（防左右张望），低头/仰头更宽容（看试卷/思考）
HEAD_POSE_NORMAL_YAW   = {"class": 12,  "exam": 5}    # yaw 正常范围
HEAD_POSE_NORMAL_ROLL  = 7                             # roll 正常范围 ±7°（通用）
HEAD_POSE_NORMAL_PITCH_UP  = {"class": -10, "exam": -15}  # pitch 仰头界限（< 值 → 不专注）
HEAD_POSE_NORMAL_PITCH_DOWN = 10                         # pitch 低头弃权下限（> 8° 弃权，通用）
HEAD_POSE_MAX_ANGLE = 40                                # 角度极限，超出即 ratio=1（通用）
HEAD_POSE_PITCH_DOWN_ABNORMAL = {"class": 15, "exam": 25}  # pitch 低头异常阈值（> 值 → 不专注）

# --- 反向 mass（特征报告"正常"但置信度偏低时）---
# conf [0, threshold] → mass [β, min]  低置信度 → 高反向 mass
# conf [threshold, 1] → mass [min, 0]  高置信度 → 低残留 mass
REVERSE_MASS_BETA = 0.2
REVERSE_MASS_MIN = 0.02
REVERSE_MASS_CONF_THRESHOLD = 0.5

# --- 时序平滑 ---
EMA_ALPHA = 0.3       # 指数移动平均系数（上升：防单帧噪声）
EMA_ALPHA_FALL = 0.7  # 指数移动平均系数（下降：快速恢复，不留幽灵残值）

# --- 人数异常累计阈值 ---
FORCE_ZERO_THRESHOLD = {
    "class": 500,
    "exam": 200,
}

# --- 时序低头检测（仅 class 模式） ---
# 用于区分低头写笔记/做题（周期性抬头）和低头玩手机（持续低头）
# pitch > 阈值 且 |yaw| ≤ 阈值 时计时器走表
# 间隙容忍：条件违反 ≤ 3 秒不计入复位，超过 3 秒清零
TEMPORAL_DOWN_PITCH_THRESHOLD = 8       # pitch 低头触发线（与 HEAD_POSE_NORMAL_PITCH_DOWN 一致）
TEMPORAL_DOWN_YAW_NORMAL = 8            # yaw 正常范围上限（与 HEAD_POSE_NORMAL_YAW["class"] 一致）
TEMPORAL_GAP_TOLERANCE_FRAMES = 90      # 间隙容忍帧数（3s @30fps）
TEMPORAL_T_MAX_FRAMES = 100             # 累计帧数阈值（30s @30fps）
TEMPORAL_STEP_FRAMES = 30              # 每步帧数（5s @30fps）
TEMPORAL_STEP_MASS = 0.1                # 每步增加 mass 量
TEMPORAL_MAX_MASS = 0.6                 # 时序 mass 上限

# --- 人数评分 ---
PEOPLE_SCORE_SINGLE = 100.0
PEOPLE_SCORE_OTHER  = 0.0

# --- 单源 mass 告警阈值 ---
# 某源 m({不专注}) ≥ 此值时单独告警
MASS_WARN_THRESHOLD = 0.5


class FocusEstimator:
    """
    专注度评估器核心类

    评分流程：
    1. 四源各自计算 m({不专注})（原始 mass）
    2. EMA 时序平滑
    3. Dempster 组合：m_combined({不专注}) = 1 - Π(1 - m_i)
    4. evidence_score = (1 - m_combined) × 100
    5. people gate 得到 final_focus
    """

    def __init__(self, mode: MonitorMode = MonitorMode.CLASS):
        self.mode = mode
        self._abnormal_count = 0
        self._smoothed: Dict[str, float] = {}
        self._smoothed_spatial = 0.0
        self._down_frames = 0
        self._gap_frames = 0

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
        计算一帧的专注度评分。

        Returns:
            scores: 各维度评分字典
            is_force_zero: 当前帧是否因人数异常强制置0
            is_over_threshold: 累计异常是否超过阈值
            warn_candidates: 本帧触发的所有告警候选
        """
        mode_key = self.mode.value

        # 1. 人数评分（独立于证据融合）
        num_face_data = feature_data.num_face_total
        num_face = num_face_data.get("value", num_people) if num_face_data else num_people
        people_score, people_warn = self._score_people(num_face)

        # 2. 四源各自计算 m({不专注})
        # head_pose 拆分：spatial（yaw/roll/pitch 即时） + temporal（持续低头检测）
        spatial_mass = self._head_pose_mass(feature_data.head_pose, mode_key)
        temporal_mass = self._compute_temporal_mass(feature_data.head_pose, mode_key)
        head_pose_raw = max(spatial_mass, temporal_mass)

        raw_masses = {
            "head_pose": head_pose_raw,
            "eye":       self._binary_mass(feature_data.eye_state, EVIDENCE_DISCOUNT_EYE_STATE[mode_key], conf_remap=True),
            "yawn":      self._binary_mass(feature_data.is_yawning, EVIDENCE_DISCOUNT_YAWNING[mode_key]),
            "distance":  self._binary_mass(feature_data.face_distance_state, EVIDENCE_DISCOUNT_DISTANCE[mode_key]),
        }

        # 3. EMA 时序平滑（非对称：慢升快降）
        # 上升用低 α 防单帧噪声，下降用高 α 快速恢复到正常
        # head_pose 的 spatial 部分走 EMA，temporal 部分绕过 EMA
        if not self._smoothed:
            self._smoothed = raw_masses.copy()
            self._smoothed_spatial = spatial_mass
        else:
            # spatial head_pose
            if spatial_mass > self._smoothed_spatial:
                self._smoothed_spatial = (
                    EMA_ALPHA * spatial_mass + (1.0 - EMA_ALPHA) * self._smoothed_spatial
                )
            else:
                self._smoothed_spatial = (
                    EMA_ALPHA_FALL * spatial_mass + (1.0 - EMA_ALPHA_FALL) * self._smoothed_spatial
                )
            self._smoothed["head_pose"] = max(self._smoothed_spatial, temporal_mass)
            # eye / yawn / distance
            for key in ("eye", "yawn", "distance"):
                if raw_masses[key] > self._smoothed[key]:
                    self._smoothed[key] = (
                        EMA_ALPHA * raw_masses[key] + (1.0 - EMA_ALPHA) * self._smoothed[key]
                    )
                else:
                    self._smoothed[key] = (
                        EMA_ALPHA_FALL * raw_masses[key] + (1.0 - EMA_ALPHA_FALL) * self._smoothed[key]
                    )

        # 4. Dempster 组合：m_combined({不专注}) = 1 - Π(1 - m_i)
        mass_not_focused = self._fuse_evidence([
            self._smoothed["head_pose"],
            self._smoothed["eye"],
            self._smoothed["yawn"],
            self._smoothed["distance"],
        ])
        evidence_score = (1.0 - mass_not_focused) * 100.0

        # 5. 人脸匹配告警
        face_mismatch_warn = None
        if not feature_data.face_matched:
            face_mismatch_warn = WarnInfo(
                warn_type=WARN_FACE_MISMATCH, detail="人脸不匹配"
            )

        # 6. 人数门控 → 最终专注度
        if people_score == PEOPLE_SCORE_SINGLE and not face_mismatch_warn:
            final_focus = evidence_score
            is_force_zero = False
        else:
            final_focus = 0.0
            is_force_zero = True
            self._abnormal_count += 1

        is_over_threshold = self._abnormal_count >= FORCE_ZERO_THRESHOLD[mode_key]

        # 7. 告警收集
        warn_candidates: List[WarnInfo] = []
        if people_warn:
            warn_candidates.append(people_warn)
        if face_mismatch_warn:
            warn_candidates.append(face_mismatch_warn)
        if evidence_score < LOW_SCORE_THRESHOLD:
            warn_candidates.append(WarnInfo(
                warn_type=WARN_LOW_EVIDENCE,
                detail=f"专注度评分过低: {evidence_score:.0f}",
            ))
        # 单源告警
        if self._smoothed["head_pose"] >= MASS_WARN_THRESHOLD:
            warn_candidates.append(WarnInfo(
                warn_type=WARN_HEAD_POSE,
                detail=f"头部姿态异常: {self._smoothed['head_pose']:.2f}",
            ))
        if self._smoothed["eye"] >= MASS_WARN_THRESHOLD:
            warn_candidates.append(WarnInfo(
                warn_type=WARN_EYE_STATE,
                detail=f"眼部异常: {self._smoothed['eye']:.2f}",
            ))
        if self._smoothed["yawn"] >= MASS_WARN_THRESHOLD:
            warn_candidates.append(WarnInfo(
                warn_type=WARN_YAWNING,
                detail=f"哈欠异常: {self._smoothed['yawn']:.2f}",
            ))
        if self._smoothed["distance"] >= MASS_WARN_THRESHOLD:
            warn_candidates.append(WarnInfo(
                warn_type=WARN_DISTANCE,
                detail=f"距离异常: {self._smoothed['distance']:.2f}",
            ))

        # 8. 构建输出
        scores = {
            # 四源风险分（smoothed m({NF}) × 100）
            "head_pose": self._smoothed["head_pose"] * 100.0,
            "eye":       self._smoothed["eye"] * 100.0,
            "yawn":      self._smoothed["yawn"] * 100.0,
            "distance":  self._smoothed["distance"] * 100.0,
            # 四源原始风险分（raw m({NF}) × 100，调试用）
            "head_pose_raw": raw_masses["head_pose"] * 100.0,
            "head_pose_spatial": spatial_mass * 100.0,
            "head_pose_temporal": temporal_mass * 100.0,
            "eye_raw":       raw_masses["eye"] * 100.0,
            "yawn_raw":      raw_masses["yawn"] * 100.0,
            "distance_raw":  raw_masses["distance"] * 100.0,
            # 融合结果
            "mass_not_focused": mass_not_focused,
            "evidence":  evidence_score,
            "people":    people_score,
            "final_focus": final_focus,
            # 时序低头计时器状态（调试用）
            "temporal_down_frames": self._down_frames,
            "temporal_gap_frames": self._gap_frames,
        }
        return scores, is_force_zero, is_over_threshold, tuple(warn_candidates)

    def reset(self):
        """重置评估器状态"""
        self._abnormal_count = 0
        self._smoothed.clear()
        self._smoothed_spatial = 0.0
        self._down_frames = 0
        self._gap_frames = 0

    @property
    def abnormal_count(self) -> int:
        return self._abnormal_count

    # ================================================================
    # 证据理论融合
    # ================================================================

    def _fuse_evidence(self, masses: List[float]) -> float:
        """
        Dempster 组合：计算组合后 m({不专注})。

        每个源只有两个 focal elements: {不专注} 和 Θ。
        由于 {不专注} ∩ Θ ≠ ∅，冲突因子 K = 0。

        m_combined({不专注}) = 1 - Π(1 - m_i)
        """
        product = 1.0
        for m in masses:
            product *= (1.0 - m)
        return 1.0 - product

    # ================================================================
    # 头部姿态 → m({不专注})
    # ================================================================

    def _head_pose_mass(self, head_pose: Dict, mode_key: str) -> float:
        """
        从头部姿态角度计算 m({不专注})。

        yaw/roll 超出正常范围 → m({不专注}) = α × ratio × conf
        pitch < 仰头界限 → 同上
        pitch > 低头异常阈值 → 同上
        pitch 在低头弃权区 → 返回 0（mass 留在 Θ）

        class/exam 模式使用不同的 yaw、仰头、低头异常阈值。

        多个方向同时偏离时取 max（同源内部不累加）。
        """
        yaw   = abs(head_pose.get("yaw", 0.0))
        pitch = head_pose.get("pitch", 0.0)
        roll  = abs(head_pose.get("roll", 0.0))
        confidence = head_pose.get("confidence", 1.0)
        alpha = EVIDENCE_DISCOUNT_HEAD_POSE[mode_key]

        candidates: List[float] = []

        # yaw: 左右偏头
        yaw_normal = HEAD_POSE_NORMAL_YAW[mode_key]
        if yaw > yaw_normal:
            ratio = min(1.0, (yaw - yaw_normal)
                        / (HEAD_POSE_MAX_ANGLE - yaw_normal))
            candidates.append(alpha * ratio * confidence)

        # roll: 歪头
        if roll > HEAD_POSE_NORMAL_ROLL:
            ratio = min(1.0, (roll - HEAD_POSE_NORMAL_ROLL)
                        / (HEAD_POSE_MAX_ANGLE - HEAD_POSE_NORMAL_ROLL))
            candidates.append(alpha * ratio * confidence)

        # pitch < 仰头界限 → 仰头
        pitch_up_normal = HEAD_POSE_NORMAL_PITCH_UP[mode_key]
        if pitch < pitch_up_normal:
            ratio = min(1.0, (pitch_up_normal - pitch)
                        / (pitch_up_normal - (-HEAD_POSE_MAX_ANGLE)))
            candidates.append(alpha * ratio * confidence)

        # pitch > 低头异常阈值 → 低头异常
        pitch_down_abnormal = HEAD_POSE_PITCH_DOWN_ABNORMAL[mode_key]
        if pitch > pitch_down_abnormal:
            ratio = min(1.0, (pitch - pitch_down_abnormal)
                        / (HEAD_POSE_MAX_ANGLE - pitch_down_abnormal))
            candidates.append(alpha * ratio * confidence)

        if not candidates:
            return 0.0
        return min(max(candidates), 1.0)

    # ================================================================
    # 二值特征 → m({不专注})
    # ================================================================

    def _binary_mass(self, feature_dict: Optional[Dict], alpha: float,
                     conf_remap: bool = False) -> float:
        """
        从二值/离散特征计算 m({不专注})。

        eye_state:     value=1 (闭眼) → 异常
        is_yawning:    value=True      → 异常
        face_distance: value≠0         → 异常

        异常时：m({不专注}) = α × effective_conf
          - conf_remap=False: effective_conf = confidence（直接使用原始置信度）
          - conf_remap=True:  分段线性重映射（用于眼部传感器）
              conf ∈ [0, 0.3] → effective ∈ [0, 0.5]
              conf ∈ [0.3, 1] → effective ∈ [0.5, 1]
        正常且 confidence < REVERSE_MASS_CONF_THRESHOLD：
                  m({不专注}) = REVERSE_MASS_BETA × (1 - confidence)
        """
        if not feature_dict:
            return 0.0

        value = feature_dict.get("value", 0)
        confidence = feature_dict.get("confidence", 1.0)

        is_abnormal: bool
        if isinstance(value, bool):
            is_abnormal = value
        elif isinstance(value, (int, float)):
            is_abnormal = (value != 0)
        else:
            is_abnormal = False

        if is_abnormal:
            if conf_remap:
                if confidence <= 0.3:
                    effective_conf = confidence * (0.5 / 0.3)
                else:
                    effective_conf = 0.5 + (confidence - 0.3) * (0.5 / 0.7)
            else:
                effective_conf = confidence
            return alpha * effective_conf
        # 正常分支：统一反向 mass 映射（连续，无硬截断）
        # conf [0, threshold] → mass [β, min]   传感器不太信自己 → 反向 mass 较高
        # conf [threshold, 1] → mass [min, 0]   传感器确信正常   → 微量残留 mass
        if confidence <= REVERSE_MASS_CONF_THRESHOLD:
            ratio = 1.0 - confidence / REVERSE_MASS_CONF_THRESHOLD
            mass = REVERSE_MASS_MIN + (REVERSE_MASS_BETA - REVERSE_MASS_MIN) * ratio
        else:
            ratio = (1.0 - confidence) / (1.0 - REVERSE_MASS_CONF_THRESHOLD)
            mass = REVERSE_MASS_MIN * ratio
        return alpha * mass

    # ================================================================
    # 时序低头检测 → m({不专注})
    # ================================================================

    def _compute_temporal_mass(self, head_pose: Dict, mode_key: str) -> float:
        """
        基于持续低头时长的 m({不专注})，仅 class 模式生效。

        exam 模式返回 0，计时器不运作。

        计时规则：
        - pitch > 8° 且 |yaw| ≤ 8° → 计时器走表
        - 条件违反 ≤ 90 帧（3s）→ 计时器暂停不重置
        - 条件违反 > 90 帧 → 计时器清零
        - 累计 ≥ 900 帧（30s）后开始产出 mass
        - 之后每 150 帧（5s）+0.1，上限 0.6
        """
        if mode_key != "class":
            return 0.0

        pitch = head_pose.get("pitch", 0.0)
        yaw = abs(head_pose.get("yaw", 0.0))
        confidence = head_pose.get("confidence", 1.0)

        condition_met = (
            pitch > TEMPORAL_DOWN_PITCH_THRESHOLD
            and yaw <= TEMPORAL_DOWN_YAW_NORMAL
        )

        if condition_met:
            self._down_frames += 1
            self._gap_frames = 0
        else:
            self._gap_frames += 1
            if self._gap_frames > TEMPORAL_GAP_TOLERANCE_FRAMES:
                self._down_frames = 0

        if self._down_frames < TEMPORAL_T_MAX_FRAMES:
            return 0.0

        excess = self._down_frames - TEMPORAL_T_MAX_FRAMES
        penalty = min(TEMPORAL_MAX_MASS,
                      (excess / TEMPORAL_STEP_FRAMES) * TEMPORAL_STEP_MASS)
        alpha = EVIDENCE_DISCOUNT_HEAD_POSE[mode_key]
        return alpha * penalty * confidence

    # ================================================================
    # 人数评分
    # ================================================================

    def _score_people(self, num_face: int) -> Tuple[float, Optional[WarnInfo]]:
        """人数评分：1人=100，否则=0"""
        if num_face == 1:
            return PEOPLE_SCORE_SINGLE, None
        if num_face == 0:
            return PEOPLE_SCORE_OTHER, WarnInfo(
                warn_type=WARN_NO_FACE, detail="画面中无人脸"
            )
        return PEOPLE_SCORE_OTHER, WarnInfo(
            warn_type=WARN_MULTI_FACE, detail=f"画面中有{num_face}张人脸"
        )
