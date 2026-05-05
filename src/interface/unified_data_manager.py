"""
统一数据管理器 - Unified Data Manager
通过单一参数控制数据来源（模拟数据/真实数据）

功能：
  1. 统一管理视频帧数据和专注度评分数据
  2. 通过 data_source 参数一键切换数据源
  3. 提供回调机制供UI模块注册
  4. 封装模拟数据生成和真实数据接收逻辑
  5. 符合数据库设计的模拟数据结构
  6. 统一管理摄像头列表
"""

from typing import Callable, Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass
import random
import uuid


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
class MockSession:
    session_id: str
    start_time: str
    end_time: str
    mode: str
    avg_focus_score: float
    abnormal_event_count: int


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

        self._data_source: DataSource = DataSource.MOCK

        self._video_frame_callback: Optional[Callable[[VideoFrameData], None]] = None
        self._focus_result_callback: Optional[Callable[[FocusResultData], None]] = None
        self._camera_list_callback: Optional[Callable[[List[CameraInfo]], None]] = None

        self._preprocessing_callback: Optional[Callable[[str, Dict], Optional[Dict]]] = None
        self._state_estimation_callback: Optional[Callable[[str, Dict], Optional[Dict]]] = None

        self._current_session_id: Optional[str] = None
        self._warn_threshold: float = 60.0

        self._mock_score_configs = {
            "head_pose": {"base": 88, "min": 60, "max": 100, "variation": 8, "weight": 0.2},
            "behavior": {"base": 92, "min": 70, "max": 100, "variation": 10, "weight": 0.3},
            "expression": {"base": 85, "min": 60, "max": 100, "variation": 10, "weight": 0.25},
            "evidence": {"base": 90, "min": 70, "max": 100, "variation": 5, "weight": 0.15},
            "people": {"base": 95, "min": 80, "max": 100, "variation": 3, "weight": 0.1},
        }

        self._mock_face_ids = [f"STU_2024{i:03d}" for i in range(1, 9)]
        self._mock_records_cache: Dict[str, List[Dict]] = {}
        self._mock_sessions_cache: Dict[str, List[MockSession]] = {}

        self._mock_cameras = [
            CameraInfo(device_id=0, device_name="Integrated Camera"),
            CameraInfo(device_id=1, device_name="USB Camera HD"),
            CameraInfo(device_id=2, device_name="Webcam Pro 3000"),
        ]

    @property
    def data_source(self) -> DataSource:
        """当前数据来源"""
        return self._data_source

    @data_source.setter
    def data_source(self, source: DataSource):
        """设置数据来源"""
        self._data_source = source
        print(f"[UnifiedDataManager] 数据来源已切换为: {source.value}")

    def set_data_source_by_name(self, name: str):
        """通过名称设置数据来源"""
        if name.lower() == "mock":
            self.data_source = DataSource.MOCK
        elif name.lower() == "real":
            self.data_source = DataSource.REAL
        else:
            raise ValueError(f"无效的数据来源: {name}")

    def register_video_frame_callback(self, callback: Callable[[VideoFrameData], None]):
        """注册视频帧回调"""
        self._video_frame_callback = callback

    def register_focus_result_callback(self, callback: Callable[[FocusResultData], None]):
        """注册专注度结果回调"""
        self._focus_result_callback = callback

    def register_camera_list_callback(self, callback: Callable[[List[CameraInfo]], None]):
        """注册摄像头列表回调"""
        self._camera_list_callback = callback

    def set_preprocessing_callback(self, callback: Callable[[str, Dict], Optional[Dict]]):
        """设置预处理模块回调"""
        self._preprocessing_callback = callback

    def set_state_estimation_callback(self, callback: Callable[[str, Dict], Optional[Dict]]):
        """设置状态估计模块回调"""
        self._state_estimation_callback = callback

    def _generate_mock_scores(self) -> Dict[str, float]:
        """生成模拟评分数据（五个维度）"""
        scores = {}
        total_weight = 0.0
        weighted_sum = 0.0

        for key, config in self._mock_score_configs.items():
            variation = random.randint(-config["variation"], config["variation"])
            value = config["base"] + variation
            value = max(config["min"], min(config["max"], value))
            scores[key] = value
            weighted_sum += value * config["weight"]
            total_weight += config["weight"]

        scores["final_focus"] = weighted_sum / total_weight if total_weight > 0 else 0.0
        return {k: int(v) if isinstance(v, float) and v.is_integer() else v for k, v in scores.items()}

    def _generate_session_id(self) -> str:
        """生成会话ID"""
        return f"session_{uuid.uuid4().hex[:8]}"

    def _generate_session(self, face_id: str, date: str, time: str) -> MockSession:
        """生成模拟会话信息"""
        session_id = self._generate_session_id()

        start_hour = int(time.split(":")[0])
        start_minute = int(time.split(":")[1])
        duration_minutes = random.randint(45, 90)

        end_minute = start_minute + duration_minutes
        end_hour = start_hour + end_minute // 60
        end_minute = end_minute % 60

        avg_focus = random.uniform(70.0, 95.0)

        return MockSession(
            session_id=session_id,
            start_time=f"{date} {time}",
            end_time=f"{date} {end_hour:02d}:{end_minute:02d}:00",
            mode=random.choice(["网课模式", "考试模式"]),
            avg_focus_score=avg_focus,
            abnormal_event_count=random.randint(0, 5)
        )

    def _generate_mock_focus_result(self) -> FocusResultData:
        """生成模拟的专注度结果数据"""
        scores = self._generate_mock_scores()

        warn_msg = None
        if scores["final_focus"] < self._warn_threshold and random.random() < 0.3:
            warn_types = [
                {"type": "低分告警", "detail": "专注度低于阈值"},
                {"type": "行为异常", "detail": "检测到走神行为"},
                {"type": "表情异常", "detail": "检测到困倦表情"},
                {"type": "离席", "detail": "检测到离开座位"},
                {"type": "多人", "detail": "检测到多人出现"},
                {"type": "姿态异常", "detail": "头部姿态异常"},
            ]
            warn_msg = random.choice(warn_types)

        return FocusResultData(
            timestamp=random.uniform(0, 1000),
            session_id=self._current_session_id or "mock_session",
            head_pose_score=scores.get("head_pose", 85),
            behavior_score=scores.get("behavior", 85),
            expression_score=scores.get("expression", 85),
            evidence_score=scores.get("evidence", 85),
            people_score=scores.get("people", 90),
            final_focus_score=scores.get("final_focus", 85.0),
            is_force_zero=False,
            warn_msg=warn_msg
        )

    def _generate_mock_video_frame(self) -> VideoFrameData:
        """生成模拟的视频帧数据"""
        num_faces = random.randint(1, 3)
        faces = []

        for i in range(num_faces):
            faces.append({
                "face_id": i + 1,
                "bbox": [
                    random.randint(10, 200),
                    random.randint(10, 150),
                    random.randint(80, 120),
                    random.randint(80, 120)
                ],
                "is_main_face": (i == 0)
            })

        return VideoFrameData(
            frame=None,
            faces=faces,
            timestamp=random.uniform(0, 1000)
        )

    def request_camera_list(self):
        """请求摄像头列表"""
        if self._data_source == DataSource.MOCK:
            camera_list = self._mock_cameras
            if self._camera_list_callback:
                self._camera_list_callback(camera_list)
            return camera_list
        else:
            if self._state_estimation_callback:
                self._state_estimation_callback("query_cameras", {})

    def push_video_frame(self, frame: Any = None, faces: list = None, timestamp: float = None):
        """
        推送视频帧数据

        真实数据模式：接收后端发送的真实数据
        模拟数据模式：生成并推送模拟数据
        """
        if self._data_source == DataSource.REAL:
            if frame is not None and faces is not None:
                data = VideoFrameData(
                    frame=frame,
                    faces=faces,
                    timestamp=timestamp or random.uniform(0, 1000)
                )
                if self._video_frame_callback:
                    self._video_frame_callback(data)
        else:
            data = self._generate_mock_video_frame()
            if self._video_frame_callback:
                self._video_frame_callback(data)

    def push_focus_result(self, data: Optional[Dict] = None):
        """
        推送专注度结果数据

        真实数据模式：接收后端发送的真实数据
        模拟数据模式：生成并推送模拟数据
        """
        if self._data_source == DataSource.REAL:
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
            result = self._generate_mock_focus_result()
            if self._focus_result_callback:
                self._focus_result_callback(result)

    def push_camera_list(self, camera_list: List[Dict[str, Any]]):
        """
        推送摄像头列表（由后端调用）
        """
        cameras = [
            CameraInfo(device_id=c["device_id"], device_name=c["device_name"])
            for c in camera_list
        ]
        if self._camera_list_callback:
            self._camera_list_callback(cameras)

    def generate_realtime_scores(self) -> Dict[str, Any]:
        """获取实时评分数据（供UI直接调用）"""
        if self._data_source == DataSource.REAL:
            return {}
        return self._generate_mock_scores()

    def generate_focus_result_dict(self) -> Dict[str, Any]:
        """获取完整的专注度结果字典"""
        if self._data_source == DataSource.REAL:
            return {}

        result = self._generate_mock_focus_result()
        return {
            "timestamp": result.timestamp,
            "session_id": result.session_id,
            "head_pose_score": result.head_pose_score,
            "behavior_score": result.behavior_score,
            "expression_score": result.expression_score,
            "evidence_score": result.evidence_score,
            "people_score": result.people_score,
            "final_focus_score": result.final_focus_score,
            "is_force_zero": result.is_force_zero,
            "warn_info": result.warn_msg
        }

    def generate_face_ids(self) -> List[str]:
        """生成模拟学生ID列表"""
        return self._mock_face_ids.copy()

    def generate_records(self, face_id: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        生成模拟历史记录（符合专注度评分记录表结构）

        Args:
            face_id: 学生ID
            count: 记录数量（默认随机5-15条）

        Returns:
            list: 历史记录列表，每条记录包含：
                - session_id: 会话ID（直接标识）
                - timestamp: 时间戳
                - date: 日期
                - time: 时间
                - head_pose_score: 头部姿态综合分
                - behavior_score: 行为动作综合分
                - expression_score: 表情综合分
                - evidence_score: 证据理论融合评分
                - people_score: 人数项评分
                - final_focus_score: 最终专注度评分
                - is_force_zero: 是否因累计异常强制置0
        """
        if face_id not in self._mock_records_cache or count is not None:
            records = []
            record_count = count or random.randint(5, 15)

            sessions_created = {}

            for _ in range(record_count):
                day = random.randint(20, 29)
                hour = random.randint(9, 16)
                minute = random.randint(0, 59)

                date = f"2026-04-{day:02d}"
                time = f"{hour:02d}:{minute:02d}:00"

                session_key = f"{date}_{hour}"
                if session_key not in sessions_created:
                    session = self._generate_session(face_id, date, time)
                    sessions_created[session_key] = session
                else:
                    session = sessions_created[session_key]

                scores = self._generate_mock_scores()

                record = {
                    "session_id": session.session_id,
                    "timestamp": random.uniform(0, 3600),
                    "date": date,
                    "time": time,
                    "head_pose_score": scores.get("head_pose", 85),
                    "behavior_score": scores.get("behavior", 85),
                    "expression_score": scores.get("expression", 85),
                    "evidence_score": scores.get("evidence", 85),
                    "people_score": scores.get("people", 90),
                    "final_focus_score": scores.get("final_focus", 85.0),
                    "is_force_zero": False,
                    "focus_score": scores.get("final_focus", 85.0),
                }
                records.append(record)

            records.sort(key=lambda x: (x["date"], x["time"]), reverse=True)
            self._mock_records_cache[face_id] = records

        return self._mock_records_cache.get(face_id, [])

    def generate_sessions(self, face_id: str) -> List[Dict[str, Any]]:
        """
        生成会话列表（符合会话信息表结构）

        Args:
            face_id: 学生ID

        Returns:
            list: 会话列表
        """
        if face_id not in self._mock_sessions_cache:
            sessions = []
            session_ids = set()

            for day in range(20, 30):
                if random.random() > 0.3:
                    date = f"2026-04-{day:02d}"
                    hour = random.randint(9, 16)
                    minute = random.randint(0, 30)
                    time = f"{hour:02d}:{minute:02d}:00"

                    session = self._generate_session(face_id, date, time)
                    if session.session_id not in session_ids:
                        session_ids.add(session.session_id)
                        sessions.append(session)

            sessions.sort(key=lambda x: x.start_time, reverse=True)
            self._mock_sessions_cache[face_id] = sessions

        return [
            {
                "session_id": s.session_id,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "mode": s.mode,
                "avg_focus_score": s.avg_focus_score,
                "abnormal_event_count": s.abnormal_event_count
            }
            for s in self._mock_sessions_cache.get(face_id, [])
        ]

    def generate_alarm_events(self, session_id: str) -> List[Dict[str, Any]]:
        """
        生成告警事件记录（符合告警事件记录表结构）

        Args:
            session_id: 会话ID

        Returns:
            list: 告警事件列表
        """
        alarm_types = [
            {"type": "低分告警", "detail": "专注度低于阈值"},
            {"type": "离席", "detail": "检测到离开座位超过30秒"},
            {"type": "多人", "detail": "画面中检测到多人"},
            {"type": "姿态异常", "detail": "头部持续低倾超过15秒"},
        ]

        event_count = random.randint(0, 3)
        events = []

        for i in range(event_count):
            events.append({
                "session_id": session_id,
                "timestamp": random.uniform(0, 3600),
                "alarm_type": random.choice(alarm_types)["type"],
                "detail": random.choice(alarm_types)["detail"],
                "frame_timestamp": random.uniform(0, 3600)
            })

        events.sort(key=lambda x: x["timestamp"])
        return events

    def toggle_capture(self, device_id: int, start: bool) -> Dict[str, Any]:
        """启动/停止视频采集"""
        action = "启动" if start else "停止"
        print(f"[UnifiedDataManager] {action}视频采集, device_id={device_id}")

        if self._preprocessing_callback:
            return self._preprocessing_callback("toggle_capture", {
                "device_id": device_id,
                "start": start
            })

        return {"success": True, "msg": f"{action}视频采集指令已发送"}

    def toggle_analysis(self, start: bool) -> Optional[Dict[str, Any]]:
        """启动/停止专注度分析"""
        action = "启动" if start else "停止"
        print(f"[UnifiedDataManager] {action}专注度分析")

        if start:
            session_id = self._create_session()
            return {"session_id": session_id}
        else:
            if self._current_session_id:
                self._end_session(self._current_session_id)
            return {"success": True}

    def _create_session(self) -> str:
        """创建新会话"""
        self._current_session_id = self._generate_session_id()
        print(f"[UnifiedDataManager] 创建新会话: {self._current_session_id}")

        if self._state_estimation_callback:
            self._state_estimation_callback("start_session", {
                "session_id": self._current_session_id
            })

        return self._current_session_id

    def _end_session(self, session_id: str) -> Dict[str, Any]:
        """结束会话"""
        print(f"[UnifiedDataManager] 结束会话: {session_id}")

        if self._state_estimation_callback:
            result = self._state_estimation_callback("stop_session", {
                "session_id": session_id
            })
            if result:
                return result

        if session_id == self._current_session_id:
            self._current_session_id = None

        return {"success": True}

    def switch_mode(self, mode: str) -> Dict[str, Any]:
        """切换监督模式"""
        if mode not in ["class", "exam"]:
            return {"success": False, "msg": f"无效的模式: {mode}"}

        print(f"[UnifiedDataManager] 切换监督模式: {mode}")

        if self._state_estimation_callback:
            return self._state_estimation_callback("switch_mode", {"mode": mode})

        return {"success": True}

    def update_warn_threshold(self, threshold: float) -> Dict[str, Any]:
        """更新告警阈值"""
        if not 0 <= threshold <= 100:
            return {"success": False, "msg": f"阈值必须在0-100之间: {threshold}"}

        self._warn_threshold = threshold
        print(f"[UnifiedDataManager] 更新告警阈值: {threshold}")

        if self._state_estimation_callback:
            return self._state_estimation_callback("update_threshold", {"threshold": threshold})

        return {"success": True}

    def clear_cache(self):
        """清除缓存"""
        self._mock_records_cache.clear()
        self._mock_sessions_cache.clear()
        print("[UnifiedDataManager] 缓存已清除")


unified_data_manager = UnifiedDataManager()
