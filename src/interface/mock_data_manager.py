"""
模拟数据管理器 - Mock Data Manager
统一管理所有界面模块的模拟数据生成与控制

功能：
  1. 集中管理所有模拟数据配置（基础值、波动范围等）
  2. 统一的开关控制（全局/分模块）
  3. 提供可配置的模拟数据生成器
  4. 模拟后端接口响应
  5. 符合数据库设计的模拟数据结构
"""

import random
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ScoreConfig:
    """评分模拟配置"""
    base_value: int
    min_value: int
    max_value: int
    variation_range: int
    weight: float


@dataclass
class MockSession:
    """模拟会话信息（对应会话信息表）"""
    session_id: str
    start_time: str
    end_time: str
    mode: str
    avg_focus_score: float
    abnormal_event_count: int


@dataclass
class MockFocusRecord:
    """模拟专注度评分记录（对应专注度评分记录表）"""
    session_id: str
    timestamp: float
    head_pose_score: float
    behavior_score: float
    expression_score: float
    evidence_score: float
    people_score: float
    final_focus_score: float
    is_force_zero: bool
    is_over_threshold: bool
    date: str
    time: str


class MockDataManager:
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

        self._global_enabled = True

        self._score_configs = {
            "head_pose": ScoreConfig(88, 60, 100, 8, 0.2),
            "behavior": ScoreConfig(92, 70, 100, 10, 0.3),
            "expression": ScoreConfig(85, 60, 100, 10, 0.25),
            "evidence": ScoreConfig(90, 70, 100, 5, 0.15),
            "people": ScoreConfig(95, 80, 100, 3, 0.1),
        }

        self._simulated_face_ids = [
            f"STU_2024{i:03d}" for i in range(1, 9)
        ]

        self._simulated_sessions: Dict[str, MockSession] = {}
        self._simulated_records: Dict[str, List[MockFocusRecord]] = {}

    @property
    def is_enabled(self) -> bool:
        return self._global_enabled

    def set_global_enabled(self, enabled: bool):
        """全局开关：启用/禁用所有模拟数据"""
        self._global_enabled = enabled
        print(f"[MockDataManager] 全局模拟数据 {'启用' if enabled else '禁用'}")

    def configure_score(self, key: str, **kwargs):
        """配置评分模拟参数"""
        if key in self._score_configs:
            config = self._score_configs[key]
            if 'base_value' in kwargs:
                config.base_value = kwargs['base_value']
            if 'min_value' in kwargs:
                config.min_value = kwargs['min_value']
            if 'max_value' in kwargs:
                config.max_value = kwargs['max_value']
            if 'variation_range' in kwargs:
                config.variation_range = kwargs['variation_range']
            if 'weight' in kwargs:
                config.weight = kwargs['weight']
            print(f"[MockDataManager] 配置 {key}: {config}")

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
            mode=random.choice(["class", "exam"]),
            avg_focus_score=avg_focus,
            abnormal_event_count=random.randint(0, 5)
        )

    def generate_realtime_scores(self) -> Dict[str, Any]:
        """
        生成实时评分数据（模拟状态估计模块输出）

        Returns:
            dict: 包含各维度评分和最终专注度
        """
        if not self._global_enabled:
            return {}

        scores = {}
        total_weight = 0.0
        weighted_sum = 0.0

        for key, config in self._score_configs.items():
            variation = random.randint(-config.variation_range, config.variation_range)
            value = config.base_value + variation
            value = max(config.min_value, min(config.max_value, value))
            scores[key] = value
            weighted_sum += value * config.weight
            total_weight += config.weight

        scores["final_focus"] = weighted_sum / total_weight if total_weight > 0 else 0.0

        return {k: int(v) if isinstance(v, float) and v.is_integer() else v for k, v in scores.items()}

    def generate_focus_result(self, session_id: str = "test_session") -> Dict[str, Any]:
        """
        生成符合SEI-01接口格式的专注度结果数据

        Returns:
            dict: 完整的专注度评分结果
        """
        if not self._global_enabled:
            return {}

        scores = self.generate_realtime_scores()

        return {
            "timestamp": random.uniform(0, 1000),
            "session_id": session_id,
            "head_pose_score": scores.get("head_pose", 85),
            "behavior_score": scores.get("behavior", 85),
            "expression_score": scores.get("expression", 85),
            "evidence_score": scores.get("evidence", 85),
            "people_score": scores.get("people", 90),
            "final_focus_score": scores.get("final_focus", 85.0),
            "is_force_zero": False,
            "is_over_threshold": False,
            "warn_info": self._generate_warn_msg(scores.get("final_focus", 85.0))
        }

    def _generate_warn_msg(self, focus_score: float) -> Optional[Dict[str, str]]:
        """根据专注度分数生成随机告警消息"""
        if focus_score < 60 and random.random() < 0.3:
            warn_types = [
                {"type": "低分告警", "detail": "专注度低于阈值"},
                {"type": "行为异常", "detail": "检测到走神行为"},
                {"type": "表情异常", "detail": "检测到困倦表情"},
                {"type": "离席", "detail": "检测到离开座位"},
                {"type": "多人", "detail": "检测到多人出现"},
                {"type": "姿态异常", "detail": "头部姿态异常"},
            ]
            return random.choice(warn_types)
        return None

    def generate_video_frame_data(self) -> Dict[str, Any]:
        """
        生成符合PRI-01接口格式的视频帧数据（简化版）

        Returns:
            dict: 包含frame、faces、timestamp
        """
        if not self._global_enabled:
            return {}

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

        return {
            "frame": None,
            "faces": faces,
            "timestamp": random.uniform(0, 1000),
            "has_face": num_faces > 0,
            "main_face_id": 1 if num_faces > 0 else -1
        }

    def delete_face(self, face_id: str) -> Dict[str, Any]:
        """从模拟列表中移除指定人脸"""
        if face_id in self._simulated_face_ids:
            self._simulated_face_ids.remove(face_id)
            print(f"[MockDataManager] 已移除模拟人脸: {face_id}")
            return {"success": True, "deleted_face_id": face_id}
        return {"success": False, "deleted_face_id": face_id,
                "msg": f"未找到 face_id={face_id}"}

    def generate_face_ids(self) -> List[str]:
        """生成模拟学生ID列表"""
        return self._simulated_face_ids.copy()

    def generate_records(self, face_id: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        为指定学生生成历史记录（符合专注度评分记录表结构）

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
        if not self._global_enabled:
            return []

        if face_id not in self._simulated_records or count is not None:
            records = []

            sessions_created = {}
            session_count = count or random.randint(5, 15)

            for _ in range(session_count):
                day = random.randint(20, 29)
                hour = random.randint(9, 16)
                minute = random.randint(0, 30)

                date = f"2026-04-{day:02d}"
                time = f"{hour:02d}:{minute:02d}:00"

                session_key = f"{date}_{hour}"
                if session_key not in sessions_created:
                    session = self._generate_session(face_id, date, time)
                    sessions_created[session_key] = session
                else:
                    session = sessions_created[session_key]

            for session in sessions_created.values():
                record_count_per_session = random.randint(15, 40)
                end_time_part = session.end_time.split(" ")[1]
                start_time_part = session.start_time.split(" ")[1]
                session_duration = (int(end_time_part.split(":")[0]) - int(start_time_part.split(":")[0])) * 3600 + \
                                  (int(end_time_part.split(":")[1]) - int(start_time_part.split(":")[1])) * 60

                for i in range(record_count_per_session):
                    timestamp = (i / record_count_per_session) * session_duration
                    scores = self.generate_realtime_scores()

                    record = MockFocusRecord(
                        session_id=session.session_id,
                        timestamp=timestamp,
                        head_pose_score=scores.get("head_pose", 85),
                        behavior_score=scores.get("behavior", 85),
                        expression_score=scores.get("expression", 85),
                        evidence_score=scores.get("evidence", 85),
                        people_score=scores.get("people", 90),
                        final_focus_score=scores.get("final_focus", 85.0),
                        is_force_zero=False,
                        is_over_threshold=False,
                        date=session.start_time.split(" ")[0],
                        time=session.start_time.split(" ")[1]
                    )
                    records.append(record)

            records.sort(key=lambda x: (x.date, x.time, x.timestamp), reverse=True)
            self._simulated_records[face_id] = records

        return [
            {
                "session_id": record.session_id,
                "timestamp": record.timestamp,
                "date": record.date,
                "time": record.time,
                "head_pose_score": record.head_pose_score,
                "behavior_score": record.behavior_score,
                "expression_score": record.expression_score,
                "evidence_score": record.evidence_score,
                "people_score": record.people_score,
                "final_focus_score": record.final_focus_score,
                "is_force_zero": record.is_force_zero,
                "is_over_threshold": record.is_over_threshold,
                "focus_score": record.final_focus_score,
            }
            for record in self._simulated_records.get(face_id, [])
        ]

    def generate_sessions(self, face_id: str) -> List[Dict[str, Any]]:
        """
        为指定学生生成会话列表（符合会话信息表结构）

        Args:
            face_id: 学生ID

        Returns:
            list: 会话列表
        """
        if not self._global_enabled:
            return []

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

        return [
            {
                "session_id": s.session_id,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "mode": s.mode,
                "avg_focus_score": s.avg_focus_score,
                "abnormal_event_count": s.abnormal_event_count
            }
            for s in sessions
        ]

    def generate_records_with_session_id(self, session_id: str, start_time: str, end_time: str) -> List[Dict[str, Any]]:
        """为指定会话生成专注度评分记录"""
        if not self._global_enabled:
            return []

        date = start_time.split(" ")[0]
        st = start_time.split(" ")[1]
        et = end_time.split(" ")[1]
        session_duration = (int(et.split(":")[0]) - int(st.split(":")[0])) * 3600 + \
                          (int(et.split(":")[1]) - int(st.split(":")[1])) * 60
        if session_duration <= 0:
            session_duration = 3600

        record_count = random.randint(15, 40)
        records = []
        for i in range(record_count):
            scores = self.generate_realtime_scores()
            records.append({
                "session_id": session_id,
                "timestamp": (i / record_count) * session_duration,
                "date": date,
                "time": st,
                "head_pose_score": scores.get("head_pose", 85),
                "behavior_score": scores.get("behavior", 85),
                "expression_score": scores.get("expression", 85),
                "evidence_score": scores.get("evidence", 85),
                "people_score": scores.get("people", 90),
                "final_focus_score": scores.get("final_focus", 85.0),
                "is_force_zero": False,
                "is_over_threshold": False,
                "focus_score": scores.get("final_focus", 85.0),
            })
        records.sort(key=lambda x: x["timestamp"])
        return records

    def generate_camera_list(self) -> List[Dict[str, Any]]:
        """生成模拟摄像头列表"""
        return [
            {"device_id": 0, "device_name": "Integrated Camera"},
            {"device_id": 1, "device_name": "USB Camera HD"},
            {"device_id": 2, "device_name": "Webcam Pro 3000"},
        ]

    def generate_alarm_events(self, session_id: str) -> List[Dict[str, Any]]:
        """
        生成告警事件记录（符合告警事件记录表结构）

        Args:
            session_id: 会话ID

        Returns:
            list: 告警事件列表
        """
        if not self._global_enabled:
            return []

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
                "alert_type": random.choice(alarm_types)["type"],
                "detail": random.choice(alarm_types)["detail"],
                "frame_timestamp": random.uniform(0, 3600)
            })

        events.sort(key=lambda x: x["timestamp"])
        return events

    def delete_sessions(self, session_ids: List[str]) -> Dict[str, Any]:
        """从内存中删除指定会话及关联数据

        Args:
            session_ids: 要删除的会话 ID 列表

        Returns:
            {"deleted_count": N, "total": M}
        """
        if not session_ids:
            return {"deleted_count": 0, "total": 0}

        total = len(session_ids)
        session_set = set(session_ids)

        # Mock 数据每次生成都是新的随机 ID，不存在持久存储
        # 清理内存中的缓存（如果恰好命中），其余视为已删除
        deleted_sessions = sum(1 for sid in session_ids if sid in self._simulated_sessions)
        self._simulated_sessions = {
            k: v for k, v in self._simulated_sessions.items()
            if k not in session_set
        }

        for face_id in list(self._simulated_records.keys()):
            self._simulated_records[face_id] = [
                r for r in self._simulated_records.get(face_id, [])
                if r.session_id not in session_set
            ]

        # Mock 模式下数据为临时生成，无持久存储，视为全部删除成功
        print(f"[MockDataManager] 删除请求 {total} 条（缓存命中 {deleted_sessions} 条，其余视为已删除）")
        return {"deleted_count": total, "total": total}

    def clear_cache(self):
        """清除已生成的历史记录缓存"""
        self._simulated_records.clear()
        self._simulated_sessions.clear()
        print("[MockDataManager] 缓存已清除")


mock_data_manager = MockDataManager()
