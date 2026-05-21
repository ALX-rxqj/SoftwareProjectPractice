"""
降采样器 - Downsampler

将逐帧评分结果（~30fps）按固定时间窗口压缩为每窗1条输出，
降低数据库存储量和界面数据压力，同时保留分数走向趋势。

方法：告警占比 + 均值帧选取
- 窗口内按告警类型独立统计占比
- 任一类型占比 >= 0.5 则触发告警，多类型触发时按优先级取最高者
- 全异常窗口取第一帧
- 触发告警时在获胜类型帧中选 final_focus 最接近均值的帧
- 无告警时在正常帧中选 final_focus 最接近均值的帧
- UI/DB 共用同一输出帧
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from .contracts import (
    FocusResultData, WarnInfo,
    ANOMALY_RATIO_THRESHOLD, alert_priority,
)

# --- 降采样宏参数 ---
DOWNSAMPLE_WINDOW_SECONDS = 1.0  # 时间窗口长度（秒）


class Downsampler:
    """
    时间窗降采样器

    用法：
        ds = Downsampler()
        for frame in frames:
            out = ds.add_frame(frame)
            if out:
                send_to_ui(out)      # 同时也是 DB 帧
        final = ds.flush()
        if final:
            send_to_ui(final)        # 同时也是 DB 帧
    """

    def __init__(self, window_seconds: float = DOWNSAMPLE_WINDOW_SECONDS):
        self._window_seconds = window_seconds
        self._buffer: List[FocusResultData] = []
        self._output_frame: Optional[FocusResultData] = None

    def add_frame(self, result: FocusResultData) -> Optional[FocusResultData]:
        """
        添加一帧评分结果。

        若缓冲区累计时间 ≥ 窗口长度，触发降采样输出。
        """
        self._buffer.append(result)

        if len(self._buffer) >= 2:
            window_duration = result.timestamp - self._buffer[0].timestamp
            if window_duration >= self._window_seconds:
                return self._emit_window()
        return None

    def flush(self) -> Optional[FocusResultData]:
        """强制输出当前缓冲区（用于会话结束时清空残余帧）"""
        if self._buffer:
            return self._emit_window()
        return None

    def reset(self):
        """清空缓冲区（用于会话切换）"""
        self._buffer.clear()
        self._output_frame = None

    def get_output_frame(self) -> Optional[FocusResultData]:
        """获取当前窗口的输出帧（消费式，取后即清），UI 和 DB 共用"""
        result = self._output_frame
        self._output_frame = None
        return result

    # ================================================================
    # 窗口处理逻辑
    # ================================================================

    def _emit_window(self) -> Optional[FocusResultData]:
        """处理当前窗口并返回降采样结果"""
        if not self._buffer:
            return None

        total = len(self._buffer)

        # 按告警类型独立统计帧数
        type_counts: Dict[str, int] = defaultdict(int)
        type_frames: Dict[str, List[FocusResultData]] = defaultdict(list)
        normal_frames: List[FocusResultData] = []
        anomaly_frames: List[FocusResultData] = []

        for f in self._buffer:
            if f.is_force_zero:
                anomaly_frames.append(f)
            else:
                normal_frames.append(f)

            seen_types: set = set()
            for w in f.warn_candidates:
                if w.warn_type not in seen_types:
                    type_counts[w.warn_type] += 1
                    type_frames[w.warn_type].append(f)
                    seen_types.add(w.warn_type)

        # 找出所有占比 >= 阈值的告警类型
        triggered_types: List[str] = []
        for warn_type, count in type_counts.items():
            if count / total >= ANOMALY_RATIO_THRESHOLD:
                triggered_types.append(warn_type)

        if triggered_types:
            # 按优先级选最高者
            winner_type = min(triggered_types, key=lambda t: alert_priority(t))
            winner_frames = type_frames[winner_type]

            if anomaly_frames and len(anomaly_frames) == total:
                # 全异常窗口：取第一帧
                output = anomaly_frames[0]
            else:
                # 在获胜类型帧中选 final_focus 最接近均值的帧
                output = self._pick_closest_to_mean(winner_frames)
        else:
            # 无告警触发：在正常帧中选最接近均值的帧
            if normal_frames:
                output = self._pick_closest_to_mean(normal_frames)
            else:
                # 理论上不会走到这里（全异常窗口必定有人数告警触发）
                output = self._buffer[0]

        # 组装输出帧：warn_candidates 仅包含获胜告警
        winner_warn = self._resolve_winner_warn(output, triggered_types)
        output = FocusResultData(
            timestamp=output.timestamp,
            session_id=output.session_id,
            head_pose_score=output.head_pose_score,
            behavior_score=output.behavior_score,
            expression_score=output.expression_score,
            evidence_score=output.evidence_score,
            people_score=output.people_score,
            final_focus_score=output.final_focus_score,
            is_force_zero=output.is_force_zero,
            is_over_threshold=output.is_over_threshold,
            warn_candidates=(winner_warn,) if winner_warn else (),
        )

        self._output_frame = output
        self._buffer.clear()
        return output

    def _pick_closest_to_mean(
        self, frames: List[FocusResultData]
    ) -> FocusResultData:
        """在帧列表中选 final_focus_score 最接近均值的帧"""
        mean_focus = sum(f.final_focus_score for f in frames) / len(frames)
        return min(frames, key=lambda f: abs(f.final_focus_score - mean_focus))

    def _resolve_winner_warn(
        self,
        output_frame: FocusResultData,
        triggered_types: List[str],
    ) -> Optional[WarnInfo]:
        """
        从输出帧的候选告警中选出与触发类型匹配的 WarnInfo。

        在输出帧的 warn_candidates 中找优先级最高且属于触发类型的告警。
        使用输出帧的实际分数（而非触发时的分数）生成 detail。
        """
        if not triggered_types:
            return None

        winner_type = min(triggered_types, key=lambda t: alert_priority(t))

        # 优先从输出帧的候选告警中匹配
        for w in output_frame.warn_candidates:
            if w.warn_type == winner_type:
                return w

        return None
