"""
界面接口管理器 - Interface Manager for Frontend
负责界面功能模块与后端模块（预处理、特征提取、状态估计）之间的所有交互

数据接口（接收后端数据）：
  - PRI-01: on_video_frame_received() - 接收视频帧和人脸坐标
  - PRI-03: on_camera_list_received() - 接收摄像头列表
  - SEI-01: on_focus_result_received() - 接收专注度评分结果

指令接口（发送控制指令）：
  - toggle_capture() - 启动/停止视频采集
  - load_video_file() - 加载本地视频文件
  - refresh_camera_list() - 获取摄像头列表
  - toggle_analysis() - 启动/停止专注度分析
  - start_new_session() - 创建新会话
  - stop_session() - 结束会话
  - switch_mode() - 监督模式切换
  - update_warn_threshold() - 告警阈值更新
"""

import time as _time
from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from ..database.database_service import database_service


class MonitorMode(Enum):
    CLASS = "class"
    EXAM = "exam"


@dataclass
class VideoFrameData:
    """PRI-01 数据结构"""
    frame: Any
    faces: list
    timestamp: float


@dataclass
class CameraInfo:
    """摄像头信息"""
    device_id: int
    device_name: str


@dataclass
class FocusResultData:
    """SEI-01 数据结构"""
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


class InterfaceManager:
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

        self._video_frame_callback: Optional[Callable] = None
        self._focus_result_callback: Optional[Callable] = None
        self._camera_list_callback: Optional[Callable] = None
        self._face_registration_frame_callback: Optional[Callable] = None

        self._preprocessing_callback: Optional[Callable] = None
        self._state_estimation_callback: Optional[Callable] = None
        self._database_callback: Optional[Callable] = None

        self._current_session_id: Optional[str] = None
        self._current_mode: MonitorMode = MonitorMode.CLASS
        self._warn_threshold: float = 60.0
        self._is_capture_running: bool = False
        self._is_analysis_running: bool = False
        self._current_device_id: int = 0

    def register_video_frame_callback(self, callback: Callable[[VideoFrameData], None]):
        """注册视频帧接收回调 - PRI-01"""
        self._video_frame_callback = callback

    def register_focus_result_callback(self, callback: Callable[[FocusResultData], None]):
        """注册专注度结果接收回调 - SEI-01"""
        self._focus_result_callback = callback

    def register_camera_list_callback(self, callback: Callable[[List[CameraInfo]], None]):
        """注册摄像头列表回调 - PRI-03"""
        self._camera_list_callback = callback

    def register_face_registration_frame_callback(self, callback: Callable[[Any, list, float], None]):
        """注册人脸注册专用帧回调"""
        self._face_registration_frame_callback = callback

    def clear_face_registration_frame_callback(self):
        """清除人脸注册专用帧回调"""
        self._face_registration_frame_callback = None

    def on_video_frame_received(self, frame: Any, faces: list, timestamp: float):
        """
        PRI-01: 接收预处理模块发送的视频帧数据
        调用时机：每帧处理后发送，用于画面渲染与标注

        Args:
            frame: BGR numpy array
            faces: list of {face_id:int, bbox:[x,y,w,h]}
            timestamp: float
        """
        if self._face_registration_frame_callback:
            self._face_registration_frame_callback(frame, faces, timestamp)
        if self._video_frame_callback:
            data = VideoFrameData(frame=frame, faces=faces, timestamp=timestamp)
            self._video_frame_callback(data)

    def on_camera_list_received(self, camera_list: List[Dict[str, Any]]):
        """
        PRI-03: 接收预处理模块发送的摄像头列表
        调用时机：启动程序时调用，预处理模块完成摄像头枚举后立即返回

        Args:
            camera_list: list of {device_id:int, device_name:str}
        """
        print(f"[InterfaceManager] 收到摄像头列表: {camera_list}")
        if self._camera_list_callback:
            cameras = [
                CameraInfo(device_id=c["device_id"], device_name=c["device_name"])
                for c in camera_list
            ]
            self._camera_list_callback(cameras)

    def on_focus_result_received(self, data: Dict[str, Any]):
        """
        SEI-01: 接收状态估计模块发送的专注度评分结果
        调用时机：每完成一次帧级评分计算后输出

        Args:
            data: dict containing:
                - timestamp: float
                - session_id: str
                - head_pose_score: float
                - behavior_score: float
                - expression_score: float
                - evidence_score: float
                - people_score: float
                - final_focus_score: float
                - is_force_zero: bool
                - warn_msg: {"type":str, "detail":str} or None
        """
        if self._focus_result_callback:
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

    def refresh_camera_list(self) -> Dict[str, Any]:
        """
        指令：获取摄像头列表
        路由：直接至预处理模块
        关联函数：refresh_camera_list -> on_query_cameras -> query_camera_list

        Returns:
            {success: bool, msg: str}
        """
        print(f"[InterfaceManager] 请求获取摄像头列表")

        if self._preprocessing_callback:
            return self._preprocessing_callback("query_cameras", {})

        return {"success": True, "msg": "摄像头列表请求已发送"}

    def toggle_capture(self, device_id: int, start: bool) -> Dict[str, Any]:
        """
        指令：启动/停止视频采集
        路由：转发至预处理模块
        关联函数：toggle_capture -> on_control_capture -> start_camera/stop_camera

        Args:
            device_id: int - 摄像头设备ID
            start: bool - True启动，False停止

        Returns:
            {success: bool, msg: str}
        """
        action = "启动" if start else "停止"
        print(f"[InterfaceManager] {action}视频采集, device_id={device_id}")

        self._is_capture_running = start
        if start:
            self._current_device_id = device_id

        if self._preprocessing_callback:
            result = self._preprocessing_callback("toggle_capture", {
                "device_id": device_id,
                "start": start
            })
            if not start:
                self.clear_face_registration_frame_callback()
            return result

        if not start:
            self.clear_face_registration_frame_callback()
        return {"success": True, "msg": f"{action}视频采集指令已发送"}

    def load_video_file(self, file_path: str) -> Dict[str, Any]:
        """
        指令：加载本地视频文件
        路由：转发至预处理模块
        关联函数：load_video_file -> on_load_video -> load_video

        Args:
            file_path: str - 视频文件路径

        Returns:
            {success: bool, msg: str}
        """
        print(f"[InterfaceManager] 加载本地视频文件: {file_path}")

        if self._preprocessing_callback:
            return self._preprocessing_callback("load_video", {
                "file_path": file_path
            })

        return {"success": True, "msg": "视频文件加载指令已发送"}

    def toggle_analysis(self, start: bool) -> Optional[Dict[str, Any]]:
        """
        指令：启动/停止专注度分析
        路由：直接至状态估计模块

        Args:
            start: bool - True启动，False停止

        Returns:
            启动时返回 {session_id: str}，停止时返回 {success: bool}
        """
        action = "启动" if start else "停止"
        print(f"[InterfaceManager] {action}专注度分析")

        self._is_analysis_running = start

        if start:
            session_id = self.start_new_session()
            return {"session_id": session_id}
        else:
            if self._current_session_id:
                self.stop_session(self._current_session_id)
            self._is_analysis_running = False
            return {"success": True}

    def start_new_session(self, student_id: str = None) -> str:
        """
        指令：创建新会话
        路由：直接至数据库模块（写 sessions 表）

        Args:
            student_id: 可选，被监控学生标识

        Returns:
            session_id: str
        """
        import uuid
        self._current_session_id = f"session_{uuid.uuid4().hex[:8]}"
        start_time = _time.time()
        mode_str = self._current_mode.value  # "class" or "exam"
        print(f"[InterfaceManager] 创建新会话: {self._current_session_id}")

        database_service.create_session({
            "session_id": self._current_session_id,
            "student_id": student_id,
            "mode": mode_str,
            "start_time": start_time,
        })

        if self._state_estimation_callback:
            self._state_estimation_callback("toggle_analysis", {
                "start": True,
                "session_id": self._current_session_id,
                "mode": mode_str,
            })

        return self._current_session_id

    def stop_session(self, session_id: str) -> Dict[str, Any]:
        """
        指令：结束会话
        路由：直接至数据库模块（UPDATE end_time + 聚合计算）和状态估计模块

        Args:
            session_id: str

        Returns:
            {success: bool}
        """
        print(f"[InterfaceManager] 结束会话: {session_id}")

        end_time = _time.time()

        # 先通知状态估计模块停止评分并 flush 数据
        if self._state_estimation_callback:
            result = self._state_estimation_callback("toggle_analysis", {
                "start": False,
                "session_id": session_id,
            })

        # 数据库模块更新 end_time + 聚合计算
        database_service.end_session(session_id, end_time)

        if session_id == self._current_session_id:
            self._current_session_id = None

        return {"success": True}

    def switch_mode(self, mode: str) -> Dict[str, Any]:
        """
        指令：监督模式切换
        路由：直接至状态估计模块
        关联函数：switch_mode -> on_mode_changed

        Args:
            mode: str - "class" 或 "exam"

        Returns:
            {success: bool}
        """
        if mode not in ["class", "exam"]:
            return {"success": False, "msg": f"无效的模式: {mode}"}

        self._current_mode = MonitorMode.CLASS if mode == "class" else MonitorMode.EXAM
        print(f"[InterfaceManager] 切换监督模式: {mode}")

        if self._state_estimation_callback:
            return self._state_estimation_callback("switch_mode", {
                "mode": mode
            })

        return {"success": True}

    def update_warn_threshold(self, threshold: float) -> Dict[str, Any]:
        """
        指令：告警阈值更新
        路由：直接至状态估计模块
        关联函数：update_warn_threshold -> on_threshold_changed

        Args:
            threshold: float [0, 100]

        Returns:
            {success: bool}
        """
        if not 0 <= threshold <= 100:
            return {"success": False, "msg": f"阈值必须在0-100之间: {threshold}"}

        self._warn_threshold = threshold
        print(f"[InterfaceManager] 更新告警阈值: {threshold}")

        if self._state_estimation_callback:
            return self._state_estimation_callback("update_threshold", {
                "threshold": threshold
            })

        return {"success": True}

    def register_face(self, name: str, frames: list, storage_type: str) -> Dict[str, Any]:
        """
        指令：注册人脸
        路由：直接至预处理模块

        Args:
            name: str - 学生姓名
            frames: List[np.ndarray] - 采集的人脸帧列表（原始BGR帧）
            storage_type: str - "local"（本地持久）或 "temp"（会话临时）

        Returns:
            {success: bool, face_id: str, msg: str}
        """
        if storage_type not in ["local", "temp"]:
            return {"success": False, "msg": f"无效的存储类型: {storage_type}"}

        face_id = f"temp_{name}" if storage_type == "temp" else name
        print(f"[InterfaceManager] 注册人脸: {name}, storage={storage_type}, "
              f"frames={len(frames)}, face_id={face_id}")

        if self._preprocessing_callback:
            return self._preprocessing_callback("register_face", {
                "student_name": name,
                "frames": frames,
                "storage_type": storage_type,
                "face_id": face_id,
            })

        return {"success": True, "face_id": face_id,
                "msg": f"人脸 {face_id} 注册指令已发送（预处理模块未连接）"}

    def set_preprocessing_callback(self, callback: Callable[[str, Dict], Optional[Dict]]):
        """设置预处理模块回调（用于指令下发）"""
        self._preprocessing_callback = callback

    def set_state_estimation_callback(self, callback: Callable[[str, Dict], Optional[Dict]]):
        """设置状态估计模块回调（用于指令下发）"""
        self._state_estimation_callback = callback

    def register_database_callback(self, callback: Callable[[str, Dict], Optional[List[Dict]]]):
        """注册数据库模块回调（用于查询指令下发）"""
        self._database_callback = callback

    def query_sessions(self, filter_params: dict) -> List[Dict[str, Any]]:
        """UII-01: 查询会话列表，转发至数据库模块"""
        if self._database_callback:
            result = self._database_callback("query_sessions", filter_params)
            if result is not None:
                return result
        return []

    @property
    def current_session_id(self) -> Optional[str]:
        return self._current_session_id

    @property
    def current_mode(self) -> MonitorMode:
        return self._current_mode

    @property
    def warn_threshold(self) -> float:
        return self._warn_threshold

    @property
    def is_capture_running(self) -> bool:
        return self._is_capture_running

    @property
    def is_analysis_running(self) -> bool:
        return self._is_analysis_running

    @property
    def current_device_id(self) -> int:
        return self._current_device_id


interface_manager = InterfaceManager()
