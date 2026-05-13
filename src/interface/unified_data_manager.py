"""
统一数据管理器 - Unified Data Manager
通过单一参数控制数据来源（模拟数据/真实数据）

功能：
  1. 统一管理视频帧数据和专注度评分数据
  2. 通过 data_source 参数一键切换数据源
  3. 提供回调机制供UI模块注册
  4. MOCK模式委托 mock_data_manager 生成模拟数据
  5. REAL模式通过 interface_manager 调用真实预处理模块
  6. 统一管理摄像头列表
"""

from typing import Callable, Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

from .interface_manager import interface_manager
from .mock_data_manager import mock_data_manager


class DataSource(Enum):
    MOCK = "mock"
    REAL = "real"


@dataclass
class VideoFrameData:
    frame: Any
    faces: list
    timestamp: float


@dataclass
class FocusResultData:
    timestamp: float
    session_id: str
    head_pose_score: float
    behavior_score: float
    expression_score: float
    evidence_score: float
    people_score: float
    final_focus_score: float
    is_force_zero: bool
    warn_msg: Optional[Dict[str, str]] = None


@dataclass
class CameraInfo:
    device_id: int
    device_name: str


class UnifiedDataManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 各模块独立数据源控制
        self._preprocessing_source: DataSource = DataSource.REAL
        self._state_estimation_source: DataSource = DataSource.MOCK
        self._database_source: DataSource = DataSource.MOCK

        self._video_frame_callback: Optional[Callable[[VideoFrameData], None]] = None
        self._focus_result_callback: Optional[Callable[[FocusResultData], None]] = None
        self._camera_list_callback: Optional[Callable[[List[CameraInfo]], None]] = None

        self._current_session_id: Optional[str] = None
        self._warn_threshold: float = 60.0

        self._preprocessing_service = None
        self._state_estimation_service = None

        self._setup_interface_manager_integration()

    # ──────────────────── 各模块数据源属性 ────────────────────

    @property
    def preprocessing_source(self) -> DataSource:
        return self._preprocessing_source

    @preprocessing_source.setter
    def preprocessing_source(self, source: DataSource):
        self._preprocessing_source = source
        print(f"[UnifiedDataManager] 预处理模块数据源切换为: {source.value}")

    @property
    def state_estimation_source(self) -> DataSource:
        return self._state_estimation_source

    @state_estimation_source.setter
    def state_estimation_source(self, source: DataSource):
        self._state_estimation_source = source
        print(f"[UnifiedDataManager] 状态估计模块数据源切换为: {source.value}")

    @property
    def database_source(self) -> DataSource:
        return self._database_source

    @database_source.setter
    def database_source(self, source: DataSource):
        self._database_source = source
        print(f"[UnifiedDataManager] 数据库模块数据源切换为: {source.value}")

    # ──────────────────── 向后兼容：全局 data_source 属性 ────────────────────

    @property
    def data_source(self) -> DataSource:
        return self._preprocessing_source

    @data_source.setter
    def data_source(self, source: DataSource):
        self._preprocessing_source = source
        self._state_estimation_source = source
        self._database_source = source
        print(f"[UnifiedDataManager] 全局数据来源已切换为: {source.value}")

    def set_data_source_by_name(self, name: str):
        if name.lower() == "mock":
            self.data_source = DataSource.MOCK
        elif name.lower() == "real":
            self.data_source = DataSource.REAL
        else:
            raise ValueError(f"无效的数据来源: {name}")

    def set_module_source(self, module: str, name: str):
        source = DataSource.MOCK if name.lower() == "mock" else DataSource.REAL
        if module == "preprocessing":
            self.preprocessing_source = source
        elif module == "state_estimation":
            self.state_estimation_source = source
        elif module == "database":
            self.database_source = source
        else:
            raise ValueError(f"无效的模块名: {module}")

    # ──────────────────── interface_manager 集成 ────────────────────

    def _setup_interface_manager_integration(self):
        interface_manager.register_video_frame_callback(self._on_interface_video_frame)
        interface_manager.register_focus_result_callback(self._on_interface_focus_result)
        interface_manager.register_camera_list_callback(self._on_interface_camera_list)

    def _on_interface_video_frame(self, data):
        if self._video_frame_callback:
            video_data = VideoFrameData(
                frame=data.frame,
                faces=data.faces,
                timestamp=data.timestamp
            )
            self._video_frame_callback(video_data)

    def _on_interface_focus_result(self, data):
        if self._focus_result_callback:
            focus_data = FocusResultData(
                timestamp=data.timestamp,
                session_id=data.session_id,
                head_pose_score=data.head_pose_score,
                behavior_score=data.behavior_score,
                expression_score=data.expression_score,
                evidence_score=data.evidence_score,
                people_score=data.people_score,
                final_focus_score=data.final_focus_score,
                is_force_zero=data.is_force_zero,
                warn_msg=data.warn_msg
            )
            self._focus_result_callback(focus_data)

    def _on_interface_camera_list(self, cameras):
        if self._camera_list_callback:
            camera_info_list = [
                CameraInfo(device_id=c.device_id, device_name=c.device_name)
                for c in cameras
            ]
            self._camera_list_callback(camera_info_list)

    # ──────────────────── 回调注册 ────────────────────

    def register_video_frame_callback(self, callback: Callable[[VideoFrameData], None]):
        self._video_frame_callback = callback

    def register_focus_result_callback(self, callback: Callable[[FocusResultData], None]):
        self._focus_result_callback = callback

    def register_camera_list_callback(self, callback: Callable[[List[CameraInfo]], None]):
        self._camera_list_callback = callback

    # ──────────────────── 实时数据（委托 mock_data_manager） ────────────────────

    def generate_realtime_scores(self) -> Dict[str, Any]:
        """获取实时评分数据（供UI直接调用）"""
        if self._state_estimation_source == DataSource.REAL:
            return {}
        return mock_data_manager.generate_realtime_scores()

    def generate_focus_result_dict(self) -> Dict[str, Any]:
        """获取完整的专注度结果字典"""
        if self._state_estimation_source == DataSource.REAL:
            return {}
        return mock_data_manager.generate_focus_result()

    def push_video_frame(self, frame: Any = None, faces: list = None, timestamp: float = None):
        """推送视频帧数据"""
        if self._preprocessing_source == DataSource.REAL:
            if frame is not None and faces is not None:
                data = VideoFrameData(frame=frame, faces=faces,
                                      timestamp=timestamp or 0.0)
                if self._video_frame_callback:
                    self._video_frame_callback(data)
        else:
            mock = mock_data_manager.generate_video_frame_data()
            if self._video_frame_callback and mock:
                data = VideoFrameData(
                    frame=mock.get("frame"),
                    faces=mock.get("faces", []),
                    timestamp=mock.get("timestamp", 0.0)
                )
                self._video_frame_callback(data)

    def push_focus_result(self, data: Optional[Dict] = None):
        """推送专注度结果数据"""
        if self._state_estimation_source == DataSource.REAL:
            if data is not None and self._focus_result_callback:
                result = FocusResultData(
                    timestamp=data.get("timestamp", 0.0),
                    session_id=data.get("session_id", ""),
                    head_pose_score=data.get("head_pose_score", 0.0),
                    behavior_score=data.get("behavior_score", 0.0),
                    expression_score=data.get("expression_score", 0.0),
                    evidence_score=data.get("evidence_score", 0.0),
                    people_score=data.get("people_score", 0.0),
                    final_focus_score=data.get("final_focus_score", 0.0),
                    is_force_zero=data.get("is_force_zero", False),
                    warn_msg=data.get("warn_info")
                )
                self._focus_result_callback(result)
        else:
            mock = mock_data_manager.generate_focus_result()
            if self._focus_result_callback and mock:
                result = FocusResultData(
                    timestamp=mock.get("timestamp", 0.0),
                    session_id=mock.get("session_id", ""),
                    head_pose_score=mock.get("head_pose_score", 0.0),
                    behavior_score=mock.get("behavior_score", 0.0),
                    expression_score=mock.get("expression_score", 0.0),
                    evidence_score=mock.get("evidence_score", 0.0),
                    people_score=mock.get("people_score", 0.0),
                    final_focus_score=mock.get("final_focus_score", 0.0),
                    is_force_zero=mock.get("is_force_zero", False),
                    warn_msg=mock.get("warn_info")
                )
                self._focus_result_callback(result)

    def push_camera_list(self, camera_list: List[Dict[str, Any]]):
        cameras = [
            CameraInfo(device_id=c["device_id"], device_name=c["device_name"])
            for c in camera_list
        ]
        if self._camera_list_callback:
            self._camera_list_callback(cameras)

    # ──────────────────── 历史数据（委托 mock_data_manager） ────────────────────

    def generate_face_ids(self) -> List[str]:
        if self._database_source == DataSource.REAL:
            return []
        return mock_data_manager.generate_face_ids()

    def generate_records(self, face_id: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        if self._database_source == DataSource.REAL:
            return []
        return mock_data_manager.generate_records(face_id, count)

    def generate_sessions(self, face_id: str) -> List[Dict[str, Any]]:
        if self._database_source == DataSource.REAL:
            return []
        return mock_data_manager.generate_sessions(face_id)

    def generate_all_sessions(self) -> List[Dict[str, Any]]:
        if self._database_source == DataSource.REAL:
            return []

        all_sessions = []
        for face_id in mock_data_manager.generate_face_ids():
            sessions = mock_data_manager.generate_sessions(face_id)
            for session in sessions:
                session["face_id"] = face_id
                all_sessions.append(session)

        all_sessions.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        print(f"[UnifiedDataManager] 获取全部会话记录: {len(all_sessions)} 条")
        return all_sessions

    def query_sessions(self, filter_params: dict) -> List[Dict[str, Any]]:
        """UII-01: 按筛选条件查询会话列表

        Args:
            filter_params: start_date, end_date, mode, focus_min, focus_max,
                           abnormal_min, abnormal_max

        Returns:
            筛选后的会话列表
        """
        if self._database_source == DataSource.REAL:
            return interface_manager.query_sessions(filter_params)

        all_sessions = self.generate_all_sessions()
        filtered = []
        for session in all_sessions:
            session_date = session.get("start_time", "").split(" ")[0]
            session_mode = session.get("mode", "")
            session_focus = session.get("avg_focus_score", 0)
            session_abnormal = session.get("abnormal_event_count", 0)

            if filter_params.get("start_date") and session_date < filter_params["start_date"]:
                continue
            if filter_params.get("end_date") and session_date > filter_params["end_date"]:
                continue
            if filter_params.get("mode") and session_mode != filter_params["mode"]:
                continue

            focus_min = filter_params.get("focus_min", 0)
            focus_max = filter_params.get("focus_max", 100)
            if session_focus < focus_min or session_focus > focus_max:
                continue

            abnormal_min = filter_params.get("abnormal_min", 0)
            abnormal_max = filter_params.get("abnormal_max", 100)
            if session_abnormal < abnormal_min or session_abnormal > abnormal_max:
                continue

            filtered.append(session)

        return filtered

    def generate_records_by_session(self, session_id: str, start_time: str, end_time: str) -> List[Dict[str, Any]]:
        print(f"[UnifiedDataManager] 查询会话记录: session_id={session_id}")

        if self._database_source == DataSource.MOCK:
            all_records = self.generate_records_for_session(session_id, start_time, end_time)
            print(f"[UnifiedDataManager] 筛选结果: {len(all_records)} 条记录")
            return all_records
        else:
            return []

    def generate_records_for_session(self, session_id: str, start_time: str = "", end_time: str = "") -> List[Dict[str, Any]]:
        if self._database_source == DataSource.REAL:
            return []

        if start_time and end_time:
            return mock_data_manager.generate_records_with_session_id(
                session_id, start_time, end_time
            )
        return []

    def generate_alarm_events(self, session_id: str) -> List[Dict[str, Any]]:
        if self._database_source == DataSource.REAL:
            return []
        return mock_data_manager.generate_alarm_events(session_id)

    # ──────────────────── 摄像头列表 ────────────────────

    def request_camera_list(self):
        if self._preprocessing_source == DataSource.MOCK:
            mock_cameras_data = mock_data_manager.generate_camera_list()
            mock_cameras = [
                CameraInfo(device_id=c["device_id"], device_name=c["device_name"])
                for c in mock_cameras_data
            ]
            if self._camera_list_callback:
                self._camera_list_callback(mock_cameras)
            return mock_cameras
        else:
            return interface_manager.refresh_camera_list()

    # ──────────────────── 控制指令 ────────────────────

    def toggle_capture(self, device_id: int, start: bool) -> Dict[str, Any]:
        action = "启动" if start else "停止"
        print(f"[UnifiedDataManager] {action}视频采集, device_id={device_id}")

        if self._preprocessing_source == DataSource.REAL:
            return interface_manager.toggle_capture(device_id, start)

        return {"success": True, "msg": f"{action}视频采集指令已发送"}

    def toggle_analysis(self, start: bool) -> Optional[Dict[str, Any]]:
        action = "启动" if start else "停止"
        print(f"[UnifiedDataManager] {action}专注度分析")

        if self._state_estimation_source == DataSource.REAL:
            return interface_manager.toggle_analysis(start)

        if start:
            import uuid
            self._current_session_id = f"session_{uuid.uuid4().hex[:8]}"
            print(f"[UnifiedDataManager] 创建新会话: {self._current_session_id}")
            return {"session_id": self._current_session_id}
        else:
            if self._current_session_id:
                print(f"[UnifiedDataManager] 结束会话: {self._current_session_id}")
                self._current_session_id = None
            return {"success": True}

    def switch_mode(self, mode: str) -> Dict[str, Any]:
        if mode not in ["class", "exam"]:
            return {"success": False, "msg": f"无效的模式: {mode}"}

        print(f"[UnifiedDataManager] 切换监督模式: {mode}")

        if self._state_estimation_source == DataSource.REAL:
            return interface_manager.switch_mode(mode)

        return {"success": True}

    def update_warn_threshold(self, threshold: float) -> Dict[str, Any]:
        if not 0 <= threshold <= 100:
            return {"success": False, "msg": f"阈值必须在0-100之间: {threshold}"}

        self._warn_threshold = threshold
        mock_data_manager.configure_score("final_focus", base_value=int(threshold))
        print(f"[UnifiedDataManager] 更新告警阈值: {threshold}")

        if self._state_estimation_source == DataSource.REAL:
            return interface_manager.update_warn_threshold(threshold)

        return {"success": True}

    def refresh_camera_list(self) -> Dict[str, Any]:
        print(f"[UnifiedDataManager] 刷新摄像头列表")
        if self._preprocessing_source == DataSource.REAL:
            return interface_manager.refresh_camera_list()
        return self.request_camera_list()

    # ──────────────────── 真实后端初始化 ────────────────────

    def initialize_real_backend(self) -> bool:
        """
        初始化真实预处理后端，将 PreprocessingService 接入 interface_manager。

        Returns:
            True 表示初始化成功
        """
        try:
            from ..preprocessing.service import (
                PreprocessingService,
                PreprocessingCommandAdapter,
            )

            service = PreprocessingService(
                video_frame_callback=self._on_preprocessing_video_frame,
                camera_list_callback=self._on_preprocessing_camera_list,
                log_callback=lambda msg: print(f"[Preprocessing] {msg}"),
            )

            adapter = PreprocessingCommandAdapter(service)
            interface_manager.set_preprocessing_callback(adapter)
            self._preprocessing_service = service

            print("[UnifiedDataManager] 真实预处理后端已初始化")
            return True
        except ImportError as e:
            print(f"[UnifiedDataManager] 预处理模块导入失败（可能缺少依赖）: {e}")
            return False
        except Exception as e:
            print(f"[UnifiedDataManager] 预处理模块初始化失败: {e}")
            return False

    def _on_preprocessing_video_frame(self, frame, faces, timestamp):
        """预处理模块视频帧回调 -> 转发至 InterfaceManager"""
        interface_manager.on_video_frame_received(frame, faces, timestamp)

    def _on_preprocessing_camera_list(self, camera_list):
        """预处理模块摄像头列表回调 -> 转发至 InterfaceManager"""
        interface_manager.on_camera_list_received(camera_list)

    @property
    def preprocessing_service(self):
        return self._preprocessing_service

    @property
    def state_estimation_service(self):
        return self._state_estimation_service

    def initialize_state_estimation_backend(self) -> bool:
        """初始化真实状态估计后端，将 StateEstimationService 接入 interface_manager。

        Returns:
            True 表示初始化成功
        """
        try:
            from ..state_estimation.service import StateEstimationService

            service = StateEstimationService()
            service.set_log_callback(lambda msg: print(msg))

            # 桥接：contracts.FocusResultData → dict → interface_manager
            service.set_focus_result_callback(
                lambda result: interface_manager.on_focus_result_received(
                    result.to_dict()
                )
            )

            adapter = StateEstimationCommandAdapter(service)
            interface_manager.set_state_estimation_callback(adapter)

            self._state_estimation_service = service
            self._state_estimation_source = DataSource.REAL

            print("[UnifiedDataManager] 真实状态估计后端已初始化")
            return True
        except ImportError as e:
            print(f"[UnifiedDataManager] 状态估计模块导入失败（可能缺少依赖）: {e}")
            return False
        except Exception as e:
            print(f"[UnifiedDataManager] 状态估计模块初始化失败: {e}")
            return False

    def clear_cache(self):
        mock_data_manager.clear_cache()
        print("[UnifiedDataManager] 缓存已清除")


class StateEstimationCommandAdapter:
    """将 StateEstimationService 适配为 InterfaceManager 所需的回调格式

    镜像 PreprocessingCommandAdapter 的设计模式。
    """

    def __init__(self, service):
        self.service = service

    def __call__(self, command: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.service.handle_command(command, params)


unified_data_manager = UnifiedDataManager()
