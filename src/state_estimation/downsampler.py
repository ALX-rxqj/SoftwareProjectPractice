"""
降采样器 - Downsampler

将逐帧评分结果（~30fps）按固定时间窗口压缩为每窗1条输出，
降低数据库存储量和界面数据压力，同时保留分数走向趋势。

方法：窗口均值 + 异常直通
- 正常帧：选取窗口内 final_focus 最接近均值的帧
- 全异常窗口：取第一帧异常帧
- 连续异常检测：窗内连续≥N帧异常时，标记告警
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .contracts import FocusResultData, WarnInfo

# --- 降采样宏参数 ---
DOWNSAMPLE_WINDOW_SECONDS = 1.0  # 时间窗口长度（秒）
ANOMALY_CONSECUTIVE_THRESHOLD = 5  # 连续异常帧数阈值（窗口内连续≥此值触发告警）


class Downsampler:
    """
    时间窗降采样器

    用法：
        ds = Downsampler()
        for frame in frames:
            out = ds.add_frame(frame)
            if out:
                send_to_ui(out)
        final = ds.flush()
        if final:
            send_to_ui(final)
    """

    def __init__(
        self,
        window_seconds: float = DOWNSAMPLE_WINDOW_SECONDS,
        consecutive_threshold: int = ANOMALY_CONSECUTIVE_THRESHOLD,
    ):
        self._window_seconds = window_seconds
        self._consecutive_threshold = consecutive_threshold
        self._buffer: List[FocusResultData] = []

    def add_frame(self, result: FocusResultData) -> Optional[FocusResultData]:
        """
        添加一帧评分结果。

        若缓冲区累计时间 ≥ 窗口长度，触发降采样输出。

        Args:
            result: 单帧评分结果

        Returns:
            降采样后的结果（窗口满时），否则 None
        """
        self._buffer.append(result)

        # 检查窗口是否已满
        if len(self._buffer) >= 2:
            window_duration = result.timestamp - self._buffer[0].timestamp
            if window_duration >= self._window_seconds:
                return self._emit_window()
        return None

    def flush(self) -> Optional[FocusResultData]:
        """
        强制输出当前缓冲区（用于会话结束时清空残余帧）。

        Returns:
            降采样后的结果，缓冲区为空时返回 None
        """
        if self._buffer:
            return self._emit_window()
        return None

    def reset(self):
        """清空缓冲区（用于会话切换）"""
        self._buffer.clear()

    # ================================================================
    # 窗口处理逻辑
    # ================================================================

    def _emit_window(self) -> Optional[FocusResultData]:
        """处理当前窗口并返回降采样结果"""
        if not self._buffer:
            return None

        # 分离正常帧和异常帧
        normal_frames = [f for f in self._buffer if not f.is_force_zero]
        anomaly_frames = [f for f in self._buffer if f.is_force_zero]

        if normal_frames:
            output = self._pick_from_normal(normal_frames, anomaly_frames)
        else:
            output = self._pick_from_all_anomaly(anomaly_frames)

        self._buffer.clear()
        return output

    def _pick_from_normal(
        self,
        normal_frames: List[FocusResultData],
        anomaly_frames: List[FocusResultData],
    ) -> FocusResultData:
        """
        有正常帧时：
        1. 计算 normal 帧的 final_focus 均值
        2. 选最接近均值的那一帧作为输出
        3. 检查连续异常帧数是否触发告警
        """
        # 计算 final_focus 均值
        mean_focus = sum(f.final_focus_score for f in normal_frames) / len(normal_frames)

        # 选最接近均值的帧
        closest = min(normal_frames, key=lambda f: abs(f.final_focus_score - mean_focus))

        # 连续异常检测
        has_consecutive, anomaly_type = self._check_consecutive_anomaly(anomaly_frames)
        if has_consecutive and anomaly_type:
            # 覆盖 warn_info 为窗口内的人数异常类型
            return FocusResultData(
                timestamp=closest.timestamp,
                session_id=closest.session_id,
                head_pose_score=closest.head_pose_score,
                behavior_score=closest.behavior_score,
                expression_score=closest.expression_score,
                evidence_score=closest.evidence_score,
                people_score=closest.people_score,
                final_focus_score=closest.final_focus_score,
                is_force_zero=closest.is_force_zero,
                is_over_threshold=closest.is_over_threshold,
                warn_msg=anomaly_type,
            )
        else:
            # 无连续异常，warn_info 置空
            if closest.warn_msg is not None:
                return FocusResultData(
                    timestamp=closest.timestamp,
                    session_id=closest.session_id,
                    head_pose_score=closest.head_pose_score,
                    behavior_score=closest.behavior_score,
                    expression_score=closest.expression_score,
                    evidence_score=closest.evidence_score,
                    people_score=closest.people_score,
                    final_focus_score=closest.final_focus_score,
                    is_force_zero=closest.is_force_zero,
                    is_over_threshold=closest.is_over_threshold,
                    warn_msg=None,
                )
            return closest

    def _pick_from_all_anomaly(
        self, anomaly_frames: List[FocusResultData]
    ) -> FocusResultData:
        """全异常窗口：取第一帧，保留其原有 warn_info"""
        return anomaly_frames[0]

    # ================================================================
    # 连续异常判断
    # ================================================================

    def _check_consecutive_anomaly(
        self, anomaly_frames: List[FocusResultData]
    ) -> Tuple[bool, Optional[WarnInfo]]:
        """
        检测窗口内是否存在连续 ≥ consecutive_threshold 帧异常。

        将窗口帧按时间顺序扫描，找到最长连续异常序列。
        若长度 ≥ 阈值，返回异常类型（按占比高的；占比相同取先出现）。

        Args:
            anomaly_frames: 窗口内所有异常帧（可能不连续）

        Returns:
            (是否触发, 异常告警类型或 None)
        """
        if not anomaly_frames:
            return False, None

        # 将全部帧按时间戳排序，扫描最长连续异常段
        all_sorted = sorted(self._buffer, key=lambda f: f.timestamp)

        max_anomaly_run = 0
        best_anomaly_segment: List[FocusResultData] = []

        current_run = 0
        current_segment: List[FocusResultData] = []

        for frame in all_sorted:
            if frame.is_force_zero:
                current_run += 1
                current_segment.append(frame)
                if current_run > max_anomaly_run:
                    max_anomaly_run = current_run
                    best_anomaly_segment = list(current_segment)
            else:
                current_run = 0
                current_segment.clear()

        if max_anomaly_run < self._consecutive_threshold:
            return False, None

        # 取最长连续异常段，按人数异常类型占比决定类型
        anomaly_type = self._pick_anomaly_type(best_anomaly_segment)
        return True, anomaly_type

    def _pick_anomaly_type(
        self, anomaly_segment: List[FocusResultData]
    ) -> Optional[WarnInfo]:
        """
        从一段连续异常帧中，按比例选出告警类型。

        - 占比高的获胜
        - 占比相同取先出现（帧顺序已按时间戳排好）
        """
        no_face_count = 0
        multi_face_count = 0
        first_no_face: Optional[FocusResultData] = None
        first_multi_face: Optional[FocusResultData] = None

        for f in anomaly_segment:
            w = f.warn_msg
            if w is None:
                continue
            if w.warn_type == "no_face":
                no_face_count += 1
                if first_no_face is None:
                    first_no_face = f
            elif w.warn_type == "multi_face":
                multi_face_count += 1
                if first_multi_face is None:
                    first_multi_face = f

        if no_face_count == 0 and multi_face_count == 0:
            return None
        if no_face_count > multi_face_count:
            return first_no_face.warn_msg if first_no_face else None
        if multi_face_count > no_face_count:
            return first_multi_face.warn_msg if first_multi_face else None
        # 占比相同：取先出现
        first = anomaly_segment[0]
        for f in anomaly_segment:
            if f.warn_msg is not None:
                first = f
                break
        # 直接在已排序段中找 warn_msg 不为空的第一个
        for f in anomaly_segment:
            if f.warn_msg is not None:
                return f.warn_msg
        return None


# ================================================================
# 数据库部分（暂不实现——数据库表结构尚未确定）
# ================================================================
# 数据库降采样规则：
# 1. 窗口内统计异常帧占比
# 2. 异常占比 ≥ 0.5 → 存入窗口内第一个异常帧
# 3. 异常占比 < 0.5 → 存入规则与 UI 一致（normal 中选最接近均值的帧）
#
# 方法签名（预留）：
#   def _db_pick_frame(self, normal_frames, anomaly_frames) -> FocusResultData:
#       ...
#
# 待数据库模块就绪后实现。
