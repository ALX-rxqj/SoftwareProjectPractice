"""
专注度评估器 - Focus Estimator

负责实现专注度评分算法框架。
具体评分算法待实现。
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from .contracts import FeatureData, MonitorMode, WarnInfo


class FocusEstimator:
    """
    专注度评估器核心类（框架）
    
    评分维度：
    - head_pose: 头部姿态评分
    - behavior: 行为动作评分
    - expression: 表情评分
    - evidence: 证据理论融合评分
    - people: 人数项评分
    
    支持两种模式：
    - CLASS: 网课模式
    - EXAM: 考试模式
    """

    def __init__(self, mode: MonitorMode = MonitorMode.CLASS):
        """
        初始化专注度评估器
        
        Args:
            mode: 监督模式，默认为CLASS模式
        """
        self.mode = mode
        self._abnormal_count = 0

    def set_mode(self, mode: MonitorMode):
        """
        设置评估模式
        
        Args:
            mode: 监督模式（CLASS/EXAM）
        """
        self.mode = mode

    def estimate(self, feature_data: FeatureData, num_people: int = 1) -> Tuple[Dict[str, float], bool, Optional[WarnInfo]]:
        """
        计算专注度评分（待实现）
        
        Args:
            feature_data: 特征数据（来自特征提取模块）
            num_people: 画面中的人数
        
        Returns:
            scores: 各维度评分字典
            is_force_zero: 是否强制置0
            warn_info: 告警信息（可选）
        """
        # TODO: 实现专注度评分算法
        scores = {
            "head_pose": 0.0,
            "behavior": 0.0,
            "expression": 0.0,
            "evidence": 0.0,
            "people": 0.0,
            "final_focus": 0.0,
        }
        return scores, False, None

    def reset(self):
        """重置评估器状态"""
        self._abnormal_count = 0
