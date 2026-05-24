"""
状态估计服务 - State Estimation Service

对外服务接口，负责：
1. 接收并处理界面模块发送的指令
2. 转发指令到预处理模块（如摄像头控制）
3. 接收特征提取模块的数据
4. 计算专注度评分并通过SEI-01接口输出到界面模块
5. 管理会话生命周期

对外公开接口：
  指令类（on_* 系列，供界面模块直接调用）：
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
  数据类（供其他模块调用）：
  - on_features_extracted: 接收特征提取模块的 FEI-01 数据
  - on_feature_received: 直接接收 FeatureData（内部/兼容）
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from .contracts import FeatureData, FocusResultData, MonitorMode
from .downsampler import Downsampler
from .estimator import FocusEstimator
from .session_manager import SessionManager

# 类型定义
CommandCallback = Callable[[str, Dict[str, Any]], Optional[Dict[str, Any]]]
FocusResultCallback = Callable[[FocusResultData], None]
LogCallback = Callable[[str], None]


class StateEstimationService:
    """
    状态估计服务核心类

    作为模块对外的统一入口，处理所有指令和数据流转。
    界面模块通过 on_* 系列公开方法调用本模块功能。
    """

    def __init__(self):
        """初始化状态估计服务"""
        # 管理器和评估器
        self._session_manager = SessionManager()
        self._estimator = FocusEstimator()
        self._downsampler = Downsampler()

        # 回调函数
        self._preprocessing_callback: Optional[CommandCallback] = None
        self._focus_result_callback: Optional[FocusResultCallback] = None
        self._log_callback: Optional[LogCallback] = None

        # 运行状态
        self._is_running = False
        self._is_processing = False
        self._processing_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 模拟特征数据（用于测试，后续应从特征提取模块接收）
        self._mock_feature_enabled = False

        # 模拟评分记录缓存（用于 on_query_records 的 MOCK 模式）
        self._mock_records_cache: Dict[str, List[Dict[str, Any]]] = {}

        # 数据库写入
        self._db_buffer: List[Dict[str, Any]] = []
        self._write_callback: Optional[Callable[[List[Dict[str, Any]]], Any]] = None

        # 快照
        self._snapshot_dir = "snapshots"
        self._snapshot_timer: Optional[threading.Timer] = None

    # ==================== 回调注册 ====================

    def set_preprocessing_callback(self, callback: CommandCallback):
        """
        设置预处理模块回调

        当指令需要转发到预处理模块时（如摄像头控制、视频加载），
        通过此回调将指令及参数传递给预处理模块执行。

        Args:
            callback: 预处理模块指令处理回调
        """
        self._preprocessing_callback = callback
        self._log(f"预处理模块回调已设置")

    def set_focus_result_callback(self, callback: FocusResultCallback):
        """
        设置专注度结果回调（SEI-01接口）

        每完成一次帧级评分计算后，通过此回调将 FocusResultData
        推送给界面模块。

        Args:
            callback: 专注度结果接收回调
        """
        self._focus_result_callback = callback
        self._log(f"专注度结果回调已设置")

    def set_log_callback(self, callback: LogCallback):
        """
        设置日志回调

        Args:
            callback: 日志输出回调
        """
        self._log_callback = callback

    def set_record_writer(self, callback: Callable[[List[Dict[str, Any]]], Any]):
        """设置数据库写回调，由 UnifiedDataManager 注入"""
        self._write_callback = callback
        self._log("数据库写回调已设置")

    # ================================================================
    # 对外公开接口（on_* 系列）
    # 界面模块通过这些方法调用本模块功能。
    # 每个方法对应表中的一个指令条目。
    # ================================================================

    # --- 转发类指令（路由至预处理模块） ---

    def on_control_capture(self, device_id: int, start: bool) -> Dict[str, Any]:
        """
        启动/停止视频采集（转发预处理模块）

        路由：界面模块 → 状态估计模块 → 预处理模块
        最终由预处理模块执行 start_camera / stop_camera。

        Args:
            device_id: 摄像头设备ID
            start: True=启动采集, False=停止采集

        Returns:
            {"success": bool, "msg": str}
        """
        self._log(f"on_control_capture: device_id={device_id}, start={start}")
        params = {"device_id": device_id, "start": start}
        if self._preprocessing_callback:
            result = self._preprocessing_callback("toggle_capture", params)
            if result:
                return result
        return {"success": True, "msg": "视频采集指令已转发"}

    def on_load_video(self, file_path: str) -> Dict[str, Any]:
        """
        加载本地视频文件（转发预处理模块）

        路由：界面模块 → 状态估计模块 → 预处理模块
        最终由预处理模块执行 load_video。

        Args:
            file_path: 本地视频文件路径

        Returns:
            {"success": bool, "msg": str}
        """
        self._log(f"on_load_video: file_path={file_path}")
        params = {"file_path": file_path}
        if self._preprocessing_callback:
            result = self._preprocessing_callback("load_video", params)
            if result:
                return result
        return {"success": True, "msg": "视频加载指令已转发"}

    def on_query_cameras(self) -> Dict[str, Any]:
        """
        获取摄像头列表（转发预处理模块）

        路由：界面模块 → 状态估计模块 → 预处理模块
        最终由预处理模块执行 query_camera_list。
        异步返回，通过数据接口 PRI-03 回调 camera_list 至界面模块。

        Returns:
            {"success": bool, "cameras": list}
        """
        self._log("on_query_cameras: 查询摄像头列表")
        params: Dict[str, Any] = {}
        if self._preprocessing_callback:
            result = self._preprocessing_callback("query_cameras", params)
            if result and result.get("success"):
                return result
        # 预处理模块未注册时返回空列表
        return {"success": True, "cameras": []}

    # --- 本模块处理类指令 ---

    def on_control_analysis(self, start: bool, session_id: str = "",
                            mode: str = "") -> Dict[str, Any]:
        """
        启动/停止专注度分析

        由状态估计模块直接处理，控制评分计算的启停。
        启动时若传入 session_id 则复用，否则自动创建。

        Args:
            start: True=启动分析, False=停止分析
            session_id: 外部传入的会话ID（可选，由 interface_manager 生成）
            mode: 监督模式（可选）

        Returns:
            启动时: {"session_id": str}
            停止时: {"success": bool}
        """
        self._log(f"on_control_analysis: start={start}, session_id={session_id}, mode={mode}")

        if start:
            # 启动分析：使用传入的 session_id 或自动创建
            self._estimator.reset()
            if session_id:
                monitor_mode = MonitorMode.EXAM if mode.lower() == "exam" else MonitorMode.CLASS
                self._session_manager.adopt_session(session_id, monitor_mode)
                self._estimator.set_mode(monitor_mode)
            else:
                session_id = self._session_manager.create_session()
            self._start_processing()
            return {"session_id": session_id}
        else:
            # 停止分析：停止处理线程并结束会话
            self._stop_processing()
            if session_id:
                self._session_manager.end_session(session_id)
            elif self._session_manager.current_session_id:
                self._session_manager.end_session(self._session_manager.current_session_id)
            self._estimator.reset()
            return {"success": True}

    def on_session_init(self) -> Dict[str, Any]:
        """
        创建新会话

        在开始分析前调用，返回新创建的会话ID。
        默认使用 CLASS 模式和告警阈值 60.0。

        Returns:
            {"success": bool, "session_id": str}
        """
        self._log("on_session_init: 创建新会话")
        session_id = self._session_manager.create_session(
            mode=MonitorMode.CLASS,
            warn_threshold=60.0,
        )
        return {"success": True, "session_id": session_id}

    def on_session_end(self, session_id: str) -> Dict[str, Any]:
        """
        结束会话

        停止分析并保存会话记录。

        Args:
            session_id: 要结束的会话ID

        Returns:
            {"success": bool}
        """
        self._log(f"on_session_end: session_id={session_id}")

        if not session_id:
            return {"success": False, "msg": "session_id 不能为空"}

        try:
            success = self._session_manager.end_session(session_id)
            self._cancel_snapshot_timer()
            self._flush_db_buffer()
            return {"success": success}
        except ValueError as e:
            return {"success": False, "msg": str(e)}

    def on_mode_changed(self, mode: str) -> Dict[str, Any]:
        """
        切换监督模式

        在 CLASS（网课）和 EXAM（考试）两种评分策略之间切换。
        切换后影响后续所有帧的专注度评分计算。

        Args:
            mode: "class" 或 "exam"

        Returns:
            {"success": bool}
        """
        self._log(f"on_mode_changed: mode={mode}")
        mode_lower = mode.lower()

        if mode_lower not in ["class", "exam"]:
            return {"success": False, "msg": f"无效的模式: {mode}，有效值为 'class' 或 'exam'"}

        new_mode = MonitorMode.CLASS if mode_lower == "class" else MonitorMode.EXAM
        self._estimator.set_mode(new_mode)

        # 如果有活动会话，同步更新会话记录中的模式
        if self._session_manager.current_session:
            self._session_manager.current_session.mode = new_mode

        return {"success": True}

    def on_threshold_changed(self, threshold: float) -> Dict[str, Any]:
        """
        更新告警阈值

        调整告警灵敏度，当专注度评分低于该阈值时触发告警。

        Args:
            threshold: 告警阈值，取值范围 [0, 100]

        Returns:
            {"success": bool}
        """
        self._log(f"on_threshold_changed: threshold={threshold}")

        if not (0.0 <= threshold <= 100.0):
            return {"success": False, "msg": f"阈值必须在0-100之间，当前值: {threshold}"}

        # 更新当前会话的告警阈值
        if self._session_manager.current_session_id:
            self._session_manager.set_warn_threshold(
                self._session_manager.current_session_id, threshold
            )

        return {"success": True}

    # --- 数据查询类指令 ---

    def on_query_sessions(
        self,
        start_date: str = "",
        end_date: str = "",
        mode: str = "",
        focus_min: int = 0,
        focus_max: int = 100,
        abnormal_min: int = 0,
        abnormal_max: int = 999,
    ) -> List[Dict[str, Any]]:
        """
        查询会话列表（按筛选条件）

        数据查询模式下，用户设置筛选条件后查询匹配的会话信息。
        MOCK 模式：从本地会话管理器中筛选。
        REAL 模式：经状态估计模块中转至数据库模块查询。

        Args:
            start_date: 开始日期筛选 "YYYY-MM-DD"
            end_date: 结束日期筛选 "YYYY-MM-DD"
            mode: 监督模式筛选 "class" / "exam" / ""（不限）
            focus_min: 专注度评分下限 [0, 100]
            focus_max: 专注度评分上限 [0, 100]
            abnormal_min: 异常事件数下限
            abnormal_max: 异常事件数上限

        Returns:
            list[dict]: 会话信息列表，每个元素包含会话摘要字段
        """
        self._log(
            f"on_query_sessions: start_date={start_date}, end_date={end_date}, "
            f"mode={mode}, focus_min={focus_min}, focus_max={focus_max}, "
            f"abnormal_min={abnormal_min}, abnormal_max={abnormal_max}"
        )

        # MOCK 模式：从本地会话管理器获取所有会话并筛选
        all_sessions = self._session_manager.get_all_sessions()
        result: List[Dict[str, Any]] = []

        for session_id, session in all_sessions.items():
            summary = self._session_manager.get_session_summary(session_id)
            if not summary:
                continue

            # 模式筛选
            if mode and summary.get("mode", "") != mode:
                continue

            # 异常事件数范围筛选
            abnormal_count = summary.get("abnormal_event_count", 0)
            if abnormal_count < abnormal_min or abnormal_count > abnormal_max:
                continue

            # 专注度评分范围筛选（MOCK 模式下生成模拟平均分）
            mock_avg_score = random.uniform(focus_min, focus_max) if focus_min < focus_max else 50.0
            summary["avg_focus_score"] = round(mock_avg_score, 1)
            result.append(summary)

        self._log(f"on_query_sessions: 返回 {len(result)} 条会话记录")
        return result

    def on_query_records(
        self,
        session_id: str,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, Any]]:
        """
        查询专注度评分记录（按会话ID）

        用户点击会话记录后，跳转详情页查询该会话时间范围内的
        所有专注度评分记录。
        MOCK 模式：按 session_id 生成模拟评分记录。
        REAL 模式：经状态估计模块中转至数据库模块查询。

        Args:
            session_id: 目标会话ID
            start_time: 时间范围起始 "YYYY-MM-DD HH:MM:SS"
            end_time: 时间范围结束 "YYYY-MM-DD HH:MM:SS"

        Returns:
            list[dict]: 专注度评分记录列表，每条包含各维度评分及时间戳
        """
        self._log(
            f"on_query_records: session_id={session_id}, "
            f"start_time={start_time}, end_time={end_time}"
        )

        if not session_id:
            self._log("on_query_records: session_id 为空，返回空列表")
            return []

        # 检查会话是否存在
        session = self._session_manager.get_session(session_id)
        if not session:
            self._log(f"on_query_records: 会话 {session_id} 不存在，返回模拟数据")

        # MOCK 模式：生成模拟评分记录
        # 模拟约30秒的数据（按30fps约900条，为减少数据量这里生成~60条）
        records = self._generate_mock_records(session_id)
        self._log(f"on_query_records: 返回 {len(records)} 条评分记录")
        return records

    def _generate_mock_records(self, session_id: str) -> List[Dict[str, Any]]:
        """
        生成模拟专注度评分记录（MOCK 模式）

        为指定会话生成一组模拟的逐帧评分记录，
        模拟正常课堂场景下学生的专注度波动。

        Args:
            session_id: 会话ID

        Returns:
            list[dict]: 模拟评分记录列表
        """
        import math

        records: List[Dict[str, Any]] = []
        base_time = time.time() - 60  # 模拟最近60秒的数据
        record_count = 60  # 生成60条记录

        for i in range(record_count):
            t = base_time + i  # 每秒一条

            # 模拟正常的专注度波动（以75分为中心，正弦波动 ±15）
            base_score = 75.0 + 15.0 * math.sin(i * 0.3)
            noise = random.uniform(-5, 5)
            final_score = max(0.0, min(100.0, base_score + noise))

            record = {
                "timestamp": t,
                "session_id": session_id,
                "head_pose_score": round(max(0.0, min(100.0, final_score + random.uniform(-8, 8))), 1),
                "eye_score": round(max(0.0, min(100.0, final_score + random.uniform(-5, 5))), 1),
                "yawn_score": round(max(0.0, min(100.0, final_score + random.uniform(-10, 10))), 1),
                "distance_score": round(max(0.0, min(100.0, final_score + random.uniform(-6, 6))), 1),
                "evidence_score": round(max(0.0, min(100.0, final_score + random.uniform(-3, 3))), 1),
                "people_score": round(random.uniform(85, 100), 1),
                "final_focus_score": round(final_score, 1),
                "is_force_zero": random.random() < 0.03,  # 3%概率强制置零
                "is_over_threshold": False,  # MOCK 模式默认未超阈值
                "warn_info": (
                    {
                        "type": "low_score",
                        "detail": "专注度评分过低",
                    }
                    if final_score < 50
                    else None
                ),
            }
            records.append(record)

        return records

    # ================================================================
    # 通用指令分发接口（兼容旧调用方式）
    # 界面模块应优先使用上述 on_* 公开方法。
    # ================================================================

    def handle_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理外部指令（通用分发入口）

        兼容旧有调用方式。新代码请直接调用对应的 on_* 方法。

        Args:
            command: 指令名称
            params: 指令参数字典

        Returns:
            指令执行结果
        """
        self._log(f"收到指令: {command}, 参数: {params}")

        command_handlers = {
            # 转发类指令
            "toggle_capture": lambda p: self.on_control_capture(
                device_id=p.get("device_id", 0),
                start=p.get("start", False),
            ),
            "load_video_file": lambda p: self.on_load_video(
                file_path=p.get("file_path", ""),
            ),
            "load_video": lambda p: self.on_load_video(
                file_path=p.get("file_path", ""),
            ),
            "refresh_camera_list": lambda p: self.on_query_cameras(),
            "query_cameras": lambda p: self.on_query_cameras(),
            # 本模块处理类指令
            "toggle_analysis": lambda p: self.on_control_analysis(
                start=p.get("start", False),
                session_id=p.get("session_id", ""),
                mode=p.get("mode", ""),
            ),
            "start_new_session": lambda p: self.on_session_init(),
            "start_session": lambda p: self.on_session_init(),
            "stop_session": lambda p: self.on_session_end(
                session_id=p.get("session_id", ""),
            ),
            "switch_mode": lambda p: self.on_mode_changed(
                mode=p.get("mode", ""),
            ),
            "update_warn_threshold": lambda p: self.on_threshold_changed(
                threshold=p.get("threshold", 60.0),
            ),
            "update_threshold": lambda p: self.on_threshold_changed(
                threshold=p.get("threshold", 60.0),
            ),
            # 查询类指令
            "query_sessions": lambda p: {
                "success": True,
                "data": self.on_query_sessions(
                    start_date=p.get("start_date", ""),
                    end_date=p.get("end_date", ""),
                    mode=p.get("mode", ""),
                    focus_min=p.get("focus_min", 0),
                    focus_max=p.get("focus_max", 100),
                    abnormal_min=p.get("abnormal_min", 0),
                    abnormal_max=p.get("abnormal_max", 999),
                ),
            },
            "query_records": lambda p: {
                "success": True,
                "data": self.on_query_records(
                    session_id=p.get("session_id", ""),
                    start_time=p.get("start_time", ""),
                    end_time=p.get("end_time", ""),
                ),
            },
        }

        handler = command_handlers.get(command)
        if handler:
            try:
                result = handler(params)
                return result if result else {"success": True, "msg": f"指令 {command} 已执行"}
            except Exception as e:
                self._log(f"指令执行失败 {command}: {str(e)}")
                return {"success": False, "msg": str(e)}
        else:
            return {"success": False, "msg": f"不支持的指令: {command}"}

    # ================================================================
    # 数据接收接口（供特征提取模块调用）
    # ================================================================

    def on_features_extracted(self, feature_output: Dict[str, Any]):
        """
        接收特征提取模块的完整输出字典（FEI-01 接口）

        输入字典格式（来自 feature_extraction service）：
        {
            "timestamp": float,
            "face_id": str,
            "face_matched": bool,
            "features": {
                "head_pose": {pitch, yaw, roll, confidence},
                "eye_state": {value: int(0=open,1=closed), confidence},
                "is_looking_screen": {value: bool, confidence},
                "attention_state": {value: int(0=focused,1=distracted,2=sleepy,3=absent), confidence},
                "face_distance_state": {value: int(0=normal,1=too_far,2=too_close), confidence},
                "is_yawning": {value: bool, confidence},
                "num_face_total": {value: int, confidence}
            }
        }

        本方法将完整输出字典转换为内部 FeatureData，
        然后进入统一的评分管线处理。

        Args:
            feature_output: 特征提取模块输出的完整字典
        """
        timestamp = float(feature_output.get("timestamp", time.time()))
        face_id = str(feature_output.get("face_id", "-1"))
        face_matched = bool(feature_output.get("face_matched", False))
        features = feature_output.get("features", {}) if isinstance(feature_output, dict) else {}

        # 调试：打印 FEI-01 原始输入数据
        self._debug_fei01_input(feature_output, features)

        # 将输出字典转换为内部 FeatureData
        feature_data = FeatureData(
            timestamp=timestamp,
            face_id=face_id,
            head_pose=features.get("head_pose", {}),
            eye_state=features.get("eye_state", {}),
            is_looking_screen=features.get("is_looking_screen", {}),
            attention_state=features.get("attention_state", {}),
            face_distance_state=features.get("face_distance_state", {}),
            is_yawning=features.get("is_yawning", {}),
            num_face_total=features.get("num_face_total", {"value": 1, "confidence": 1.0}),
            face_matched=face_matched,
        )
        # 进入统一的评分处理管线
        self.on_feature_received(feature_data)

    def on_feature_received(self, feature_data: FeatureData):
        """
        接收并处理一帧特征数据（内部评分管线入口）

        处理流程：
        1. 检查是否处于分析状态
        2. 调用评估器计算各维度评分
        3. 构建 FocusResultData
        4. 送入降采样器（1秒时间窗），窗满时通过 SEI-01 推送
        5. 更新会话统计信息（所有帧均统计）

        Args:
            feature_data: 特征数据
        """
        if not self._is_processing:
            return

        # 计算专注度评分
        session_id = self._session_manager.current_session_id or "unknown"

        # 调试：打印 FeatureData 各字段值
        self._debug_feature_data(feature_data)

        # 使用评估器计算评分（人数从 feature_data.num_face_total 提取）
        scores, is_force_zero, is_over_threshold, warn_candidates = self._estimator.estimate(feature_data)

        # 调试：打印评分结果
        self._debug_scores(scores, is_force_zero, is_over_threshold, warn_candidates)

        # 构建专注度结果
        result = FocusResultData(
            timestamp=feature_data.timestamp,
            session_id=session_id,
            head_pose_score=scores.get("head_pose", 0.0),
            eye_score=scores.get("eye", 0.0),
            yawn_score=scores.get("yawn", 0.0),
            distance_score=scores.get("distance", 0.0),
            evidence_score=scores.get("evidence", 0.0),
            people_score=scores.get("people", 0.0),
            final_focus_score=scores.get("final_focus", 0.0),
            is_force_zero=is_force_zero,
            is_over_threshold=is_over_threshold,
            warn_candidates=warn_candidates,
        )

        # 降采样：窗口满时才输出，否则缓存
        downsampled = self._downsampler.add_frame(result)
        if downsampled is not None:
            self._dispatch_focus_result(downsampled)
            # UI/DB 共用同一输出帧
            self._db_buffer.append(downsampled.to_dict())

        # 更新会话统计（所有帧都统计，不经过降采样）
        if session_id:
            self._session_manager.update_session_stats(
                session_id,
                frames_processed=1,
                abnormal_events=1 if warn_candidates else 0
            )

    def _dispatch_focus_result(self, result: FocusResultData):
        """
        发送专注度结果到界面模块（SEI-01接口）

        Args:
            result: 专注度评分结果
        """
        if self._focus_result_callback:
            try:
                self._focus_result_callback(result)
            except Exception as e:
                self._log(f"发送专注度结果失败: {str(e)}")

    # ================================================================
    # 处理线程管理
    # ================================================================

    def _start_processing(self):
        """启动专注度处理线程"""
        if self._is_processing:
            return

        self._is_processing = True
        self._stop_event.clear()
        self._processing_thread = threading.Thread(
            target=self._processing_loop,
            name="StateEstimationProcessing",
            daemon=True
        )
        self._processing_thread.start()
        # 首次 5 分钟后开始定期刷库
        self._snapshot_timer = threading.Timer(300, self._schedule_periodic_flush)
        self._snapshot_timer.daemon = True
        self._snapshot_timer.start()
        self._log("专注度分析已启动")

    def _stop_processing(self):
        """停止专注度处理线程"""
        if not self._is_processing:
            return

        self._is_processing = False
        self._stop_event.set()
        self._cancel_snapshot_timer()

        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=2.0)

        # 降采样器输出残余帧
        remaining = self._downsampler.flush()
        if remaining:
            self._dispatch_focus_result(remaining)
            self._db_buffer.append(remaining.to_dict())

        # 刷库
        self._flush_db_buffer()

        self._log("专注度分析已停止")

    def _processing_loop(self):
        """
        专注度处理主循环

        模拟模式下，定期生成符合 FEI-01 格式的模拟特征数据
        并通过 on_features_extracted 送入评分管线。
        实际应用中，由特征提取模块主动调用 on_features_extracted。
        """
        while not self._stop_event.is_set():
            if self._mock_feature_enabled:
                # 生成完整输出字典并送入管线
                feature_output = self._generate_mock_features()
                self.on_features_extracted(feature_output)

            # 控制处理频率（约30fps）
            time.sleep(1.0 / 30.0)

    def _generate_mock_features(self) -> Dict[str, Any]:
        """
        生成与 feature_extraction 输出格式一致的模拟字典（用于测试）

        严格按照特征提取模块的真实数据格式生成（FEI-01接口）：
        顶层包含 timestamp / face_id / face_matched / features，
        其中各子特征遵循 {value, confidence} 结构，
        head_pose 为 {pitch, yaw, roll, confidence}。

        Returns:
            完整输出字典，与 feature_extraction service 输出一致
        """
        timestamp = time.time()
        face_id = "face_001"  # 模拟单人场景，face_id 为字符串
        face_matched = random.random() > 0.05  # 5% 概率不匹配

        # 注意力状态离散值
        attention_value = random.choices([0, 1, 2, 3], weights=[0.80, 0.12, 0.05, 0.03])[0]

        # 人脸距离状态离散值
        distance_value = random.choices([0, 1, 2], weights=[0.88, 0.08, 0.04])[0]

        # 模拟人数 — 90%单人，5%无人，5%多人
        people_rand = random.random()
        if people_rand < 0.05:
            num_face_value = 0  # 无人
        elif people_rand < 0.10:
            num_face_value = random.randint(2, 3)  # 多人
        else:
            num_face_value = 1  # 单人

        features = {
            # 头部姿态 — {pitch, yaw, roll, confidence}
            "head_pose": {
                "pitch": random.uniform(-30.0, 30.0),
                "yaw": random.uniform(-45.0, 45.0),
                "roll": random.uniform(-20.0, 20.0),
                "confidence": random.uniform(0.85, 1.0),
            },
            # 眼部状态 — {value: 0=open / 1=closed, confidence}
            "eye_state": {
                "value": 1 if random.random() < 0.03 else 0,
                "confidence": random.uniform(0.9, 1.0),
            },
            # 注视屏幕 — {value: bool, confidence}
            "is_looking_screen": {
                "value": random.random() > 0.08,
                "confidence": random.uniform(0.8, 1.0),
            },
            # 注意力状态 — {value: 0=focused / 1=distracted / 2=sleepy / 3=absent, confidence}
            "attention_state": {
                "value": attention_value,
                "confidence": random.uniform(0.75, 1.0),
            },
            # 人脸距离 — {value: 0=normal / 1=too_far / 2=too_close, confidence}
            "face_distance_state": {
                "value": distance_value,
                "confidence": random.uniform(0.85, 1.0),
            },
            # 哈欠检测 — {value: bool, confidence}
            "is_yawning": {
                "value": random.random() < 0.03,
                "confidence": random.uniform(0.85, 1.0),
            },
            # 画面人脸总数 — {value: int, confidence}
            "num_face_total": {
                "value": num_face_value,
                "confidence": random.uniform(0.9, 1.0),
            },
        }

        return {
            "timestamp": timestamp,
            "face_id": face_id,
            "face_matched": face_matched,
            "features": features,
        }

    def _generate_mock_feature_data(self) -> FeatureData:
        """
        生成模拟 FeatureData（内部使用）

        Returns:
            模拟的 FeatureData
        """
        feature_output = self._generate_mock_features()
        features = feature_output.get("features", {})
        return FeatureData(
            timestamp=float(feature_output.get("timestamp", time.time())),
            face_id=feature_output.get("face_id", "face_001"),
            head_pose=features.get("head_pose", {}),
            eye_state=features.get("eye_state", {}),
            is_looking_screen=features.get("is_looking_screen", {}),
            attention_state=features.get("attention_state", {}),
            face_distance_state=features.get("face_distance_state", {}),
            is_yawning=features.get("is_yawning", {}),
            num_face_total=features.get("num_face_total", {"value": 1, "confidence": 1.0}),
            face_matched=bool(feature_output.get("face_matched", True)),
        )

    # ================================================================
    # 调试方法
    # ================================================================

    @staticmethod
    def _debug_fei01_input(feature_output: Dict[str, Any], features: Dict[str, Any]):
        """打印 FEI-01 原始输入字典的关键字段值"""
        hp = features.get("head_pose", {})
        eye = features.get("eye_state", {})
        look = features.get("is_looking_screen", {})
        attn = features.get("attention_state", {})
        dist = features.get("face_distance_state", {})
        yawn = features.get("is_yawning", {})
        nface = features.get("num_face_total", {})

        attn_labels = {0: "focused", 1: "distracted", 2: "sleepy", 3: "absent"}
        dist_labels = {0: "normal", 1: "too_far", 2: "too_close"}

        lines = [
            "=" * 60,
            "[DEBUG] FEI-01 原始输入数据",
            f"  timestamp    : {feature_output.get('timestamp', 'N/A')}",
            f"  face_id      : {feature_output.get('face_id', 'N/A')}",
            f"  face_matched : {feature_output.get('face_matched', 'N/A')}",
            "  --- features ---",
            f"  head_pose         : pitch={hp.get('pitch', '?'):.2f}, yaw={hp.get('yaw', '?'):.2f}, roll={hp.get('roll', '?'):.2f}, conf={hp.get('confidence', '?'):.3f}",
            f"  eye_state         : value={eye.get('value', '?')} (0=open/1=closed), conf={eye.get('confidence', '?'):.3f}",
            f"  is_looking_screen : value={look.get('value', '?')}, conf={look.get('confidence', '?'):.3f}",
            f"  attention_state   : value={attn.get('value', '?')} ({attn_labels.get(attn.get('value', -1), '?')}), conf={attn.get('confidence', '?'):.3f}",
            f"  face_distance     : value={dist.get('value', '?')} ({dist_labels.get(dist.get('value', -1), '?')}), conf={dist.get('confidence', '?'):.3f}",
            f"  is_yawning        : value={yawn.get('value', '?')}, conf={yawn.get('confidence', '?'):.3f}",
            f"  num_face_total    : value={nface.get('value', '?')}, conf={nface.get('confidence', '?'):.3f}",
            "=" * 60,
        ]
        for line in lines:
            print(line)

    @staticmethod
    def _debug_feature_data(fd: FeatureData):
        """打印 FeatureData 各字段的详细值"""
        hp = fd.head_pose
        eye = fd.eye_state
        look = fd.is_looking_screen
        attn = fd.attention_state
        dist = fd.face_distance_state
        yawn = fd.is_yawning
        nface = fd.num_face_total

        attn_labels = {0: "focused", 1: "distracted", 2: "sleepy", 3: "absent"}
        dist_labels = {0: "normal", 1: "too_far", 2: "too_close"}

        lines = [
            "-" * 40,
            "[DEBUG] FeatureData 输入值",
            f"  timestamp          : {fd.timestamp}",
            f"  face_id            : {fd.face_id}",
            f"  face_matched       : {fd.face_matched}",
            f"  head_pose          : pitch={hp.get('pitch', 0):.2f}, yaw={hp.get('yaw', 0):.2f}, roll={hp.get('roll', 0):.2f}, conf={hp.get('confidence', 0):.3f}",
            f"  eye_state          : value={eye.get('value', 0)}, conf={eye.get('confidence', 0):.3f}",
            f"  is_looking_screen  : value={look.get('value', 0)}, conf={look.get('confidence', 0):.3f}",
            f"  attention_state    : value={attn.get('value', 0)}({attn_labels.get(attn.get('value', -1), '?')}), conf={attn.get('confidence', 0):.3f}",
            f"  face_distance_state: value={dist.get('value', 0)}({dist_labels.get(dist.get('value', -1), '?')}), conf={dist.get('confidence', 0):.3f}",
            f"  is_yawning         : value={yawn.get('value', 0)}, conf={yawn.get('confidence', 0):.3f}",
            f"  num_face_total     : value={nface.get('value', 0)}, conf={nface.get('confidence', 0):.3f}",
            "-" * 40,
        ]
        for line in lines:
            print(line)

    @staticmethod
    def _debug_scores(scores: dict, is_force_zero: bool, is_over_threshold: bool, warn_candidates: tuple):
        """打印评分结果（四源 DS 证据融合）"""
        m_nf = scores.get("mass_not_focused", 0.0)
        active_sources = [
            name for name in ("head_pose", "eye", "yawn", "distance")
            if scores.get(name, 0.0) > 0.1
        ]

        lines = [
            "-" * 56,
            "[DEBUG] DS 证据融合评分结果",
            "  --- 四源风险分 (m({NF}) x 100, smoothed) ---",
            f"  head_pose : {scores.get('head_pose', 0):5.1f}  (raw: {scores.get('head_pose_raw', 0):5.1f})  spatial: {scores.get('head_pose_spatial', 0):5.1f}  temporal: {scores.get('head_pose_temporal', 0):5.1f}",
            f"  eye       : {scores.get('eye', 0):5.1f}  (raw: {scores.get('eye_raw', 0):5.1f})",
            f"  yawn      : {scores.get('yawn', 0):5.1f}  (raw: {scores.get('yawn_raw', 0):5.1f})",
            f"  distance  : {scores.get('distance', 0):5.1f}  (raw: {scores.get('distance_raw', 0):5.1f})",
            f"  --- 低头计时器 (class only) ---",
            f"  down_frames : {scores.get('temporal_down_frames', 0):.0f} / 900  (≈{scores.get('temporal_down_frames', 0) / 30:.0f}s / 30s)",
            f"  gap_frames  : {scores.get('temporal_gap_frames', 0):.0f} / 90   (≈{scores.get('temporal_gap_frames', 0) / 30:.1f}s / 3s)",
            "  --- 融合结果 ---",
            f"  m({{NF}}) combined : {m_nf:.4f}",
            f"  evidence   : {scores.get('evidence', 0):.1f}  (= (1 - m(NF)) x 100)",
            f"  people     : {scores.get('people', 0):.0f}",
            f"  final_focus: {scores.get('final_focus', 0):.1f}",
            f"  active sources    : {active_sources if active_sources else 'none'}",
            f"  is_force_zero     : {is_force_zero}",
            f"  is_over_threshold : {is_over_threshold}",
            f"  warn_candidates   : {[w.warn_type for w in warn_candidates] if warn_candidates else 'none'}",
            "-" * 56,
        ]
        for line in lines:
            print(line)

    # ================================================================
    # 状态查询
    # ================================================================

    def get_status(self) -> Dict[str, Any]:
        """
        获取服务状态

        Returns:
            状态信息字典
        """
        session = self._session_manager.current_session
        return {
            "is_running": self._is_running,
            "is_processing": self._is_processing,
            "current_session_id": self._session_manager.current_session_id,
            "current_mode": session.mode.value if session else None,
            "warn_threshold": session.warn_threshold if session else 60.0,
            "total_sessions": len(self._session_manager.get_all_sessions()),
        }

    def get_session_summary(self, session_id: Optional[str] = None) -> Optional[Dict]:
        """
        获取会话摘要

        Args:
            session_id: 会话ID，默认为当前会话

        Returns:
            会话摘要字典
        """
        target_session_id = session_id or self._session_manager.current_session_id
        if not target_session_id:
            return None
        return self._session_manager.get_session_summary(target_session_id)

    # ================================================================
    # 服务生命周期
    # ================================================================

    def _flush_db_buffer(self):
        """将缓冲的评分记录批量写入数据库，失败时存 JSON 兜底"""
        session_id = self._session_manager.current_session_id
        if not self._write_callback or not session_id:
            return
        os.makedirs(self._snapshot_dir, exist_ok=True)
        path = os.path.join(self._snapshot_dir, f"{session_id}.json")

        # Step 1: 先处理上次失败残留的 JSON
        pending = self._load_pending_json(path)
        if pending:
            try:
                self._write_callback(pending)
                self._log(f"已补写 {len(pending)} 条待重试记录到数据库")
                self._delete_pending_json(path)
            except Exception as e:
                self._log(f"补写失败: {e}，合并当前 buffer 到 JSON")
                pending.extend(self._db_buffer)
                self._save_pending_json(path, pending)
                self._db_buffer.clear()
                return

        # Step 2: 写当前 buffer
        if self._db_buffer:
            try:
                self._write_callback(list(self._db_buffer))
                self._log(f"已写入 {len(self._db_buffer)} 条评分记录到数据库")
            except Exception as e:
                self._log(f"数据库写入失败: {e}")
                self._save_pending_json(path, list(self._db_buffer))
            finally:
                self._db_buffer.clear()

    def _schedule_periodic_flush(self):
        """每 5 分钟执行一次：刷库 + 重新调度"""
        self._flush_db_buffer()
        if self._is_processing:
            self._snapshot_timer = threading.Timer(300, self._schedule_periodic_flush)
            self._snapshot_timer.daemon = True
            self._snapshot_timer.start()

    def _load_pending_json(self, path: str):
        """加载待重试的 JSON 数据"""
        try:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self._log(f"加载待重试快照失败: {e}")
        return None

    def _save_pending_json(self, path: str, records):
        """保存失败数据到 JSON 等待下次重试"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self._log(f"快照写入失败: {e}")

    def _delete_pending_json(self, path: str):
        """补写成功后删除 JSON 文件"""
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError as e:
            self._log(f"快照删除失败: {e}")

    def _cancel_snapshot_timer(self):
        if self._snapshot_timer is not None:
            self._snapshot_timer.cancel()
            self._snapshot_timer = None

    def _log(self, message: str):
        """输出日志"""
        if self._log_callback:
            self._log_callback(f"[StateEstimationService] {message}")
        else:
            print(f"[StateEstimationService] {message}")

    def start(self):
        """启动服务"""
        self._is_running = True
        self._log("状态估计服务已启动")

    def stop(self):
        """停止服务"""
        self._stop_processing()
        self._is_running = False
        self._log("状态估计服务已停止")

    def reset(self):
        """重置服务状态"""
        self._stop_processing()
        self._session_manager.clear_sessions()
        self._estimator.reset()
        self._downsampler.reset()
        self._mock_records_cache.clear()
        self._db_buffer.clear()
        self._log("状态估计服务已重置")
