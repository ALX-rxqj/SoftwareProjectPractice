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

import time as _time
import threading
from typing import Callable, Dict, Any, List, Optional
from enum import Enum

from PyQt5.QtCore import QTimer

from .interface_manager import interface_manager, VideoFrameData, FocusResultData, CameraInfo
from .mock_data_manager import mock_data_manager
from .data_access_provider import DataAccessProvider
from ..database.database_service import database_service


class DataSource(Enum):
    MOCK = "mock"
    REAL = "real"


__all__ = ["VideoFrameData", "FocusResultData", "CameraInfo"]


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
        self._state_estimation_source: DataSource = DataSource.REAL
        self._database_source: DataSource = DataSource.REAL

        self._video_frame_callback: Optional[Callable[[VideoFrameData], None]] = None
        self._focus_result_callback: Optional[Callable[[FocusResultData], None]] = None
        self._camera_list_callback: Optional[Callable[[List[CameraInfo]], None]] = None

        self._current_session_id: Optional[str] = None
        self._warn_threshold: float = 60.0
        self._mock_capture_running: bool = False

        self._preprocessing_service = None
        self._state_estimation_service = None
        self._feature_extraction_service = None

        self._mock_video_timer: Optional[QTimer] = None
        self._mock_focus_timer: Optional[QTimer] = None

        self._init_result: Dict[str, Any] = {"done": True, "success": True}

        self._data_access = DataAccessProvider(
            get_db_source=lambda: self._database_source,
            DataSource=DataSource,
        )

        self._setup_interface_manager_integration()

    def initialize_database(self, db_path: str = None) -> bool:
        return self._data_access.initialize_database(db_path)

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

    @property
    def is_capture_running(self) -> bool:
        """采集是否正在运行（MOCK/REAL 统一）"""
        if self._preprocessing_source == DataSource.REAL:
            return interface_manager.is_capture_running
        return self._mock_capture_running

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
        interface_manager.register_database_callback(self._on_interface_database_command)

    def _on_interface_database_command(self, command: str, params: dict):
        if command == "create_session":
            return database_service.create_session(params)
        elif command == "end_session":
            return database_service.end_session(
                params["session_id"], params["end_time"]
            )
        elif command == "query_sessions":
            return database_service.query_sessions(params)
        return None

    def _on_interface_video_frame(self, data):
        if self._video_frame_callback:
            video_data = VideoFrameData(
                frame=data.frame,
                faces=data.faces,
                timestamp=data.timestamp,
                frame_progress=data.frame_progress,
            )
            self._video_frame_callback(video_data)

    def _on_interface_focus_result(self, data):
        if self._focus_result_callback:
            focus_data = FocusResultData(
                timestamp=data.timestamp,
                session_id=data.session_id,
                head_pose_score=data.head_pose_score,
                eye_score=data.eye_score,
                yawn_score=data.yawn_score,
                distance_score=data.distance_score,
                behavior_score=data.behavior_score,
                expression_score=data.expression_score,
                evidence_score=data.evidence_score,
                people_score=data.people_score,
                final_focus_score=data.final_focus_score,
                is_force_zero=data.is_force_zero,
                is_over_threshold=data.is_over_threshold,
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

    def register_face_registration_frame_callback(self, callback):
        """注册人脸注册专用帧回调（转发到 interface_manager）"""
        interface_manager.register_face_registration_frame_callback(callback)

    def register_face_registration_result_callback(self, callback):
        """注册人脸注册异步结果回调（转发到 interface_manager）"""
        interface_manager.register_face_registration_result_callback(callback)

    def clear_face_registration_frame_callback(self):
        """清除人脸注册帧回调"""
        interface_manager.clear_face_registration_frame_callback()

    def clear_face_registration_result_callback(self):
        """清除人脸注册结果回调"""
        interface_manager.clear_face_registration_result_callback()

    def register_file_playback_ended_callback(self, callback):
        """注册文件播放完成回调（转发到 interface_manager）"""
        interface_manager.register_file_playback_ended_callback(callback)

    def register_face(self, name: str, frames: list, storage_type: str) -> Dict[str, Any]:
        """注册人脸。MOCK 模式下不支持。"""
        if self._preprocessing_source == DataSource.MOCK:
            return {"success": False, "msg": "模拟模式下不支持人脸注册"}
        return interface_manager.register_face(name, frames, storage_type)

    # ──────────────────── 实时数据（委托 mock_data_manager） ────────────────────

    def _generate_realtime_scores(self) -> Dict[str, Any]:
        """获取实时评分数据（内部方法，Mock timer 使用）"""
        if self._state_estimation_source == DataSource.REAL:
            return {}
        return mock_data_manager.generate_realtime_scores()

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
                    timestamp=mock.get("timestamp", 0.0),
                    frame_progress=mock.get("frame_progress"),
                )
                self._video_frame_callback(data)

                # Mock 文件模式：检测播放结束
                if mock.get("file_ended"):
                    file_name = mock_data_manager.current_file_name or ""
                    interface_manager.on_file_playback_ended(file_name)

    @staticmethod
    def _make_focus_result(data: dict) -> FocusResultData:
        return FocusResultData(
            timestamp=data.get("timestamp", 0.0),
            session_id=data.get("session_id", ""),
            head_pose_score=data.get("head_pose_score", 0.0),
            eye_score=data.get("eye_score", 0.0),
            yawn_score=data.get("yawn_score", 0.0),
            distance_score=data.get("distance_score", 0.0),
            behavior_score=data.get("behavior_score", 0.0),
            expression_score=data.get("expression_score", 0.0),
            evidence_score=data.get("evidence_score", 0.0),
            people_score=data.get("people_score", 0.0),
            final_focus_score=data.get("final_focus_score", 0.0),
            is_force_zero=data.get("is_force_zero", False),
            is_over_threshold=data.get("is_over_threshold", False),
            warn_msg=data.get("warn_info"),
        )

    def push_focus_result(self, data: Optional[Dict] = None):
        """推送专注度结果数据"""
        source_dict = None
        if self._state_estimation_source == DataSource.REAL:
            source_dict = data
        else:
            source_dict = mock_data_manager.generate_focus_result()

        if source_dict is not None and self._focus_result_callback:
            self._focus_result_callback(self._make_focus_result(source_dict))

    def push_camera_list(self, camera_list: List[Dict[str, Any]]):
        cameras = [
            CameraInfo(device_id=c["device_id"], device_name=c["device_name"])
            for c in camera_list
        ]
        if self._camera_list_callback:
            self._camera_list_callback(cameras)

    # ──────────────────── 历史数据（委托 mock_data_manager） ────────────────────

    def generate_face_ids(self) -> List[str]:
        return self._data_access.generate_face_ids()

    def generate_face_ids_with_details(self) -> List[Dict[str, Any]]:
        return self._data_access.generate_face_ids_with_details()

    def delete_face(self, face_id: str) -> Dict[str, Any]:
        return self._data_access.delete_face(face_id)

    def generate_records(self, face_id: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._data_access.generate_records(face_id, count)

    def generate_sessions(self, face_id: str) -> List[Dict[str, Any]]:
        return self._data_access.generate_sessions(face_id)

    def generate_all_sessions(self) -> List[Dict[str, Any]]:
        return self._data_access.generate_all_sessions()

    def query_sessions(self, filter_params: dict) -> List[Dict[str, Any]]:
        return self._data_access.query_sessions(filter_params)

    def generate_records_by_session(self, session_id: str, start_time: str, end_time: str) -> List[Dict[str, Any]]:
        return self._data_access.generate_records_by_session(session_id, start_time, end_time)

    def generate_records_for_session(self, session_id: str, start_time: str = "", end_time: str = "") -> List[Dict[str, Any]]:
        return self._data_access.generate_records_for_session(session_id, start_time, end_time)

    def generate_alarm_events(self, session_id: str) -> List[Dict[str, Any]]:
        return self._data_access.generate_alarm_events(session_id)

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

    def toggle_capture(
        self, device_id: int, start: bool,
        monitored_faces: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        action = "启动" if start else "停止"
        print(f"[UnifiedDataManager] {action}视频采集, device_id={device_id}")

        if self._preprocessing_source == DataSource.REAL:
            return interface_manager.toggle_capture(device_id, start, monitored_faces)

        # MOCK 路径
        self._mock_capture_running = start
        if start:
            self._start_mock_video_timer()
        else:
            self._stop_mock_video_timer()
        return {"success": True, "msg": f"{action}视频采集指令已发送"}

    def load_video_file(self, file_path: str) -> Dict[str, Any]:
        """加载本地视频文件并开始播放

        REAL 路径：转发至 interface_manager → 预处理模块
        MOCK 路径：启动 mock 视频定时器
        """
        print(f"[UnifiedDataManager] 加载本地视频文件: {file_path}")

        if self._preprocessing_source == DataSource.REAL:
            return interface_manager.load_video_file(file_path)

        # MOCK 路径
        self._mock_capture_running = True
        mock_data_manager.set_file_mode(file_path)
        self._start_mock_video_timer()
        return {"success": True, "msg": f"视频文件加载指令已发送"}

    def stop_capture(self) -> Dict[str, Any]:
        """统一停止视频采集（摄像头/文件）"""
        print(f"[UnifiedDataManager] 停止视频采集")

        if self._preprocessing_source == DataSource.REAL:
            return interface_manager.stop_capture()

        # MOCK 路径
        self._mock_capture_running = False
        mock_data_manager.set_file_mode(None)
        self._stop_mock_video_timer()
        return {"success": True, "msg": "采集已停止"}

    def _start_mock_video_timer(self):
        if self._mock_video_timer is not None:
            return
        self._mock_video_timer = QTimer()
        self._mock_video_timer.timeout.connect(lambda: self.push_video_frame())
        self._mock_video_timer.start(33)
        print("[UnifiedDataManager] Mock 视频帧定时器已启动")

    def _stop_mock_video_timer(self):
        if self._mock_video_timer is None:
            return
        self._mock_video_timer.stop()
        self._mock_video_timer = None
        print("[UnifiedDataManager] Mock 视频帧定时器已停止")

    def toggle_analysis(self, start: bool, face_id: str = None,
                        video_source_type: str = "camera",
                        file_name: str = None) -> Optional[Dict[str, Any]]:
        action = "启动" if start else "停止"
        print(f"[UnifiedDataManager] {action}专注度分析")

        if self._state_estimation_source == DataSource.REAL:
            return interface_manager.toggle_analysis(
                start, face_id=face_id,
                video_source_type=video_source_type,
                file_name=file_name,
            )

        # MOCK 路径
        if start:
            import uuid
            self._current_session_id = f"session_{uuid.uuid4().hex[:8]}"
            print(f"[UnifiedDataManager] 创建新会话: {self._current_session_id}")
            self._start_mock_focus_timer()
            return {"session_id": self._current_session_id}
        else:
            self._stop_mock_focus_timer()
            if self._current_session_id:
                print(f"[UnifiedDataManager] 结束会话: {self._current_session_id}")
                self._current_session_id = None
            return {"success": True}

    def _start_mock_focus_timer(self):
        if self._mock_focus_timer is not None:
            return
        self._mock_focus_timer = QTimer()
        self._mock_focus_timer.timeout.connect(lambda: self.push_focus_result())
        self._mock_focus_timer.start(1000)
        print("[UnifiedDataManager] Mock 专注度评分定时器已启动")

    def _stop_mock_focus_timer(self):
        if self._mock_focus_timer is None:
            return
        self._mock_focus_timer.stop()
        self._mock_focus_timer = None
        print("[UnifiedDataManager] Mock 专注度评分定时器已停止")

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

    # ──────────────────── 统一初始化入口 ────────────────────

    def initialize_all_backends(
        self,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> bool:
        """统一初始化入口。根据各模块的 data_source 决定初始化策略。

        - preprocessing_source == REAL → 后台线程加载 PreprocessingService
        - preprocessing_source == MOCK → 安装 Mock 适配器
        - state_estimation_source == REAL → 同步加载 StateEstimationService（失败返回 False）
        - state_estimation_source == MOCK → 安装 Mock 适配器

        REAL 路径失败直接返回 False，不静默降级。
        """
        # 预处理模块
        if self._preprocessing_source == DataSource.MOCK:
            self._install_mock_preprocessing_adapter()
        else:
            # REAL：启动后台线程加载模型
            self._init_result = {"done": False, "success": False}
            thread = threading.Thread(
                target=self._init_preprocessing_thread,
                args=(progress_callback,),
                daemon=True,
            )
            thread.start()

        # 状态估计模块（同步，轻量）
        if self._state_estimation_source == DataSource.REAL:
            if not self._init_state_estimation_backend():
                return False
        else:
            self._install_mock_state_estimation_adapter()

        return True

    def _install_mock_preprocessing_adapter(self):
        """安装 Mock 预处理适配器到 interface_manager"""
        interface_manager.set_preprocessing_callback(
            lambda cmd, params: print(
                f"[UnifiedDataManager] 预处理指令(MOCK): {cmd}, params: {params}"
            ) or {"success": True, "msg": "mock"}
        )
        print("[UnifiedDataManager] Mock 预处理适配器已安装")

    def _install_mock_state_estimation_adapter(self):
        """安装 Mock 状态估计适配器到 interface_manager"""
        interface_manager.set_state_estimation_callback(
            lambda cmd, params: print(
                f"[UnifiedDataManager] 状态估计指令(MOCK): {cmd}, params: {params}"
            ) or {"success": True, "msg": "mock"}
        )
        print("[UnifiedDataManager] Mock 状态估计适配器已安装")

    def _init_preprocessing_thread(self, progress_callback):
        """后台线程：加载真实预处理后端"""
        try:
            success = self._init_real_preprocessing_backend(progress_callback)
            self._init_result["done"] = True
            self._init_result["success"] = success
            if not success:
                print("[UnifiedDataManager] 预处理模块初始化失败（后台线程）")
        except Exception as e:
            self._init_result["done"] = True
            self._init_result["success"] = False
            self._init_result["message"] = str(e)
            print(f"[UnifiedDataManager] 预处理模块初始化异常: {e}")

    def _init_real_preprocessing_backend(
        self,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> bool:
        """加载 PreprocessingService 并注入到 interface_manager"""
        try:
            from ..preprocessing.service import (
                PreprocessingService,
                PreprocessingCommandAdapter,
            )

            service = PreprocessingService(
                ui_callback=self._on_preprocessing_ui_packet,
                camera_list_callback=self._on_preprocessing_camera_list,
                log_callback=lambda msg: print(f"[Preprocessing] {msg}"),
                progress_callback=progress_callback,
            )

            if hasattr(service, "set_face_embedding_writer"):
                service.set_face_embedding_writer(
                    lambda face_id, student_name, embeddings:
                        database_service.insert_face_embeddings_batch(
                            face_id, student_name, embeddings, _time.time()
                        )
                )
                print("[UnifiedDataManager] 数据库人脸写回调已注入预处理模块")

            adapter = PreprocessingCommandAdapter(service)
            interface_manager.set_preprocessing_callback(adapter)
            self._preprocessing_service = service

            # 若特征提取模块已就绪，接上回调
            if self._feature_extraction_service is not None:
                service.feature_callback = (
                    self._feature_extraction_service.process_feature_packet
                )
                print("[UnifiedDataManager] 预处理→特征提取回调已接上（预处理侧）")

            print("[UnifiedDataManager] 真实预处理后端已初始化")
            return True
        except ImportError as e:
            print(f"[UnifiedDataManager] 预处理模块导入失败（可能缺少依赖）: {e}")
            return False
        except Exception as e:
            print(f"[UnifiedDataManager] 预处理模块初始化失败: {e}")
            return False

    @property
    def init_done(self) -> bool:
        """后台初始化是否完成"""
        return self._init_result.get("done", True)

    @property
    def init_success(self) -> bool:
        """后台初始化是否成功"""
        return self._init_result.get("success", True)

    def _on_preprocessing_ui_packet(self, packet: dict):
        ptype = packet.get("type", "")
        if ptype == "face_registration_result":
            interface_manager.on_face_registration_result(packet)
        elif ptype == "file_playback_ended":
            interface_manager.on_file_playback_ended(
                packet.get("file_path", "")
            )
        else:
            interface_manager.on_video_frame_received(
                packet.get("frame"), packet.get("faces", []), packet.get("timestamp", 0.0),
                frame_progress=packet.get("frame_progress"),
            )

    def _on_preprocessing_video_frame(self, frame, faces, timestamp):
        interface_manager.on_video_frame_received(frame, faces, timestamp)

    def _on_preprocessing_camera_list(self, camera_list):
        interface_manager.on_camera_list_received(camera_list)

    @property
    def preprocessing_service(self):
        return self._preprocessing_service

    @property
    def state_estimation_service(self):
        return self._state_estimation_service

    def _init_state_estimation_backend(self) -> bool:
        """初始化真实状态估计后端（内部方法，由 initialize_all_backends 调用）"""
        try:
            from ..state_estimation.service import StateEstimationService

            service = StateEstimationService()
            service.set_log_callback(lambda msg: print(msg))

            service.set_focus_result_callback(
                lambda result: interface_manager.on_focus_result_received(
                    result.to_dict()
                )
            )

            if hasattr(service, "set_record_writer"):
                service.set_record_writer(
                    lambda records: database_service.insert_focus_records_batch(records)
                )
                print("[UnifiedDataManager] 数据库写回调已注入状态估计模块")
            else:
                print("[UnifiedDataManager] 警告: StateEstimationService 未实现 set_record_writer，"
                      "会话结束后评分数据不会持久化")

            adapter = StateEstimationCommandAdapter(service)
            interface_manager.set_state_estimation_callback(adapter)

            self._state_estimation_service = service
            self._state_estimation_source = DataSource.REAL

            # 特征提取模块作为可选中间层，依赖缺失时状态估计仍可运行
            self._init_feature_extraction(service)

            print("[UnifiedDataManager] 真实状态估计后端已初始化")
            return True
        except ImportError as e:
            print(f"[UnifiedDataManager] 状态估计模块导入失败（可能缺少依赖）: {e}")
            return False
        except Exception as e:
            print(f"[UnifiedDataManager] 状态估计模块初始化失败: {e}")
            return False

    def _init_feature_extraction(self, se_service) -> None:
        """尝试初始化特征提取模块并接入状态估计（可选，依赖缺失时降级）"""
        try:
            from ..feature_extraction.service import FeatureExtractionService

            fe_service = FeatureExtractionService(
                state_callback=se_service.on_features_extracted,
                log_callback=lambda msg: print(f"[FeatureExtraction] {msg}"),
            )
            self._feature_extraction_service = fe_service
            print("[UnifiedDataManager] 特征提取模块已初始化并接入状态估计")

            # 若预处理后端已就绪，立即接上
            if self._preprocessing_service is not None:
                self._preprocessing_service.feature_callback = (
                    fe_service.process_feature_packet
                )
                print("[UnifiedDataManager] 预处理→特征提取回调已接上")
        except ImportError as e:
            print(f"[UnifiedDataManager] 特征提取模块不可用（缺少依赖: {e}），"
                  "状态估计将使用内部模拟数据")
        except Exception as e:
            print(f"[UnifiedDataManager] 特征提取模块初始化失败: {e}，"
                  "状态估计将使用内部模拟数据")

    def delete_sessions(self, session_ids: List[str]) -> Dict[str, Any]:
        return self._data_access.delete_sessions(session_ids)

    def clear_cache(self):
        self._data_access.clear_cache()


class StateEstimationCommandAdapter:
    """将 StateEstimationService 适配为 InterfaceManager 所需的回调格式"""

    def __init__(self, service):
        self.service = service

    def __call__(self, command: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.service.handle_command(command, params)


unified_data_manager = UnifiedDataManager()
