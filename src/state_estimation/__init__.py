"""
状态估计模块 - State Estimation Module

本模块负责：
1. 接收特征提取模块的 FEI-01 格式数据
2. 基于 D-S 证据理论计算专注度评分（四源独立证据融合）
3. 管理分析会话的生命周期
4. 支持网课模式(class)和考试模式(exam)两种评分策略
5. 通过SEI-01接口向界面模块输出专注度评分结果

证据源：
- head_pose: 头部姿态（yaw/roll/仰头→不专注证据，低头→弃权）
- eye_state: 眼部状态（闭眼→不专注证据）
- is_yawning: 哈欠检测（打哈欠→不专注证据）
- face_distance: 人脸距离（异常距离→不专注证据）

对外公开接口（StateEstimationService.on_* 系列）：
- on_features_extracted: 接收特征提取模块的 FEI-01 数据
- on_control_capture: 启动/停止视频采集（转发预处理模块）
- on_load_video: 加载本地视频文件（转发预处理模块）
- on_control_analysis: 启动/停止专注度分析
- on_session_init: 创建新会话
- on_session_end: 结束会话
- on_mode_changed: 切换监督模式
- on_threshold_changed: 更新告警阈值
- on_query_cameras: 获取摄像头列表（转发预处理模块）
- on_query_sessions: 查询会话列表（按筛选条件）
- on_query_records: 查询专注度评分记录（按会话ID）

模块结构：
- contracts.py: 数据结构定义（FocusResultData等）
- estimator.py: 专注度估计算法核心（D-S 证据理论）
- session_manager.py: 会话生命周期管理
- service.py: 对外服务接口（指令处理与通信）
- downsampler.py: 1秒窗口降采样

导出对象：
- StateEstimationService: 对外服务入口
- FocusResultData: 专注度评分结果数据结构
- MonitorMode: 监督模式枚举
"""

from .contracts import FeatureData, FocusResultData, MonitorMode, SessionInfo, WarnInfo
from .service import StateEstimationService

__all__ = [
    "StateEstimationService",
    "FeatureData",
    "FocusResultData",
    "MonitorMode",
    "SessionInfo",
    "WarnInfo",
]
