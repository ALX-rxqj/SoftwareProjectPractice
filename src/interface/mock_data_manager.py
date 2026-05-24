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
    video_source_type: str = "camera"
    file_name: Optional[str] = None


@dataclass
class MockFocusRecord:
    """模拟专注度评分记录（对应专注度评分记录表）"""
    session_id: str
    timestamp: float
    head_pose_score: float = 0.0
    eye_score: float = 0.0
    yawn_score: float = 0.0
    distance_score: float = 0.0
    behavior_score: float = 0.0  # 弃用
    expression_score: float = 0.0  # 弃用
    evidence_score: float = 0.0
    people_score: float = 0.0
    final_focus_score: float = 0.0
    is_force_zero: bool = False
    is_over_threshold: bool = False
    date: str = ""
    time: str = ""


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
            "eye": ScoreConfig(92, 70, 100, 10, 0.25),
            "yawn": ScoreConfig(90, 70, 100, 5, 0.15),
            "distance": ScoreConfig(85, 60, 100, 10, 0.15),
            "evidence": ScoreConfig(90, 70, 100, 5, 0.15),
            "people": ScoreConfig(95, 80, 100, 3, 0.1),
        }

        self._simulated_face_ids = [
            f"STU_2024{i:03d}" for i in range(1, 9)
        ]

        self._simulated_sessions: Dict[str, MockSession] = {}
        self._simulated_records: Dict[str, List[MockFocusRecord]] = {}

        # 文件模式 Mock 状态
        self._file_mode_path: Optional[str] = None
        self._file_frame_index: int = 0
        self._file_total_frames: int = 300  # 模拟 10 秒 @30fps

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
            abnormal_event_count=random.randint(0, 5),
            video_source_type=random.choice(["camera", "file"]),
            file_name="模拟课堂录像.mp4" if random.random() > 0.7 else None,
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

        final_focus = weighted_sum / total_weight if total_weight > 0 else 0.0
        scores["final_focus"] = final_focus

        result = {k: int(v) if isinstance(v, float) and v.is_integer() else v for k, v in scores.items()}
        result["warn_info"] = self._generate_warn_msg()
        return result

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
            "eye_score": scores.get("eye", 85),
            "yawn_score": scores.get("yawn", 85),
            "distance_score": scores.get("distance", 85),
            "behavior_score": 0.0,
            "expression_score": 0.0,
            "evidence_score": scores.get("evidence", 85),
            "people_score": scores.get("people", 90),
            "final_focus_score": scores.get("final_focus", 85.0),
            "is_force_zero": False,
            "is_over_threshold": False,
            "warn_info": self._generate_warn_msg()
        }

    def _generate_warn_msg(self) -> Optional[Dict[str, str]]:
        """随机生成告警消息（约 15% 概率）"""
        if random.random() < 0.150:
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

    def set_file_mode(self, file_path: Optional[str]) -> None:
        """设置/清除文件模式

        Args:
            file_path: 文件路径，传 None 退出文件模式
        """
        self._file_mode_path = file_path
        self._file_frame_index = 0
        if file_path:
            print(f"[MockDataManager] 进入文件模式: {file_path}")

    @property
    def is_file_mode(self) -> bool:
        return self._file_mode_path is not None

    @property
    def current_file_name(self) -> Optional[str]:
        if self._file_mode_path:
            import os
            return os.path.basename(self._file_mode_path)
        return None

    def generate_video_frame_data(self) -> Dict[str, Any]:
        """
        生成符合PRI-01接口格式的视频帧数据（简化版）

        Returns:
            dict: 包含frame、faces、timestamp，文件模式下额外包含frame_progress
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

        result = {
            "frame": None,
            "faces": faces,
            "timestamp": random.uniform(0, 1000),
            "has_face": num_faces > 0,
            "main_face_id": 1 if num_faces > 0 else -1
        }

        # 文件模式：附加进度信息
        if self._file_mode_path:
            self._file_frame_index += 1
            if self._file_frame_index > self._file_total_frames:
                self._file_frame_index = self._file_total_frames
            result["frame_progress"] = {
                "current_frame": self._file_frame_index,
                "total_frames": self._file_total_frames,
            }
            # 模拟文件播放结束
            if self._file_frame_index >= self._file_total_frames:
                result["file_ended"] = True

        return result

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
                        eye_score=scores.get("eye", 85),
                        yawn_score=scores.get("yawn", 85),
                        distance_score=scores.get("distance", 85),
                        behavior_score=0.0,
                        expression_score=0.0,
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
                "eye_score": record.eye_score,
                "yawn_score": record.yawn_score,
                "distance_score": record.distance_score,
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
                "abnormal_event_count": s.abnormal_event_count,
                "video_source_type": s.video_source_type,
                "file_name": s.file_name,
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
                "eye_score": scores.get("eye", 85),
                "yawn_score": scores.get("yawn", 85),
                "distance_score": scores.get("distance", 85),
                "behavior_score": 0.0,
                "expression_score": 0.0,
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

    @staticmethod
    def seed_debug_data(db_service) -> None:
        """写入调试数据（幂等：已有数据则跳过）

        仅当数据库已有会话时跳过，避免重复播种。
        应由 UnifiedDataManager.initialize_database() 调用。
        """
        import datetime
        import time as _time

        existing = db_service.query_sessions({})
        if existing:
            print(f"[MockDataManager] 数据库已有 {len(existing)} 条会话，跳过 seed_debug_data")
            return

        try:
            import numpy as np
        except ImportError:
            np = None

        students = [
            {"face_id": "face_debug_zhangsan", "student_name": "张三"},
            {"face_id": "face_debug_lisi", "student_name": "李四"},
            {"face_id": "face_debug_wangwu", "student_name": "王五"},
        ]
        now = _time.time()
        for s in students:
            dummy_embeddings = [
                (np.random.randn(512).astype(np.float32).tobytes() if np is not None
                 else b"\x00" * 2048,
                 ["frontal", "left", "right", "down"][i % 4])
                for i in range(8)
            ]
            db_service.insert_face_embeddings_batch(
                s["face_id"], s["student_name"], dummy_embeddings, now
            )

        session_defs = [
            {"sid": "seed_001", "face_id": "face_debug_zhangsan", "mode": "class",
             "start": datetime.datetime(2026, 4, 22, 9, 0, 0),
             "duration_min": 50, "focus_base": 88, "alert_count": 0},
            {"sid": "seed_002", "face_id": "face_debug_lisi", "mode": "exam",
             "start": datetime.datetime(2026, 4, 25, 10, 0, 0),
             "duration_min": 60, "focus_base": 75, "alert_count": 2},
            {"sid": "seed_003", "face_id": "face_debug_wangwu", "mode": "class",
             "start": datetime.datetime(2026, 4, 28, 14, 0, 0),
             "duration_min": 45, "focus_base": 65, "alert_count": 3},
            {"sid": "seed_004", "face_id": "face_debug_zhangsan", "mode": "exam",
             "start": datetime.datetime(2026, 5, 2, 8, 30, 0),
             "duration_min": 55, "focus_base": 45, "alert_count": 4},
            {"sid": "seed_005", "face_id": "face_debug_lisi", "mode": "class",
             "start": datetime.datetime(2026, 5, 5, 15, 0, 0),
             "duration_min": 40, "focus_base": 92, "alert_count": 0},
            {"sid": "seed_006", "face_id": "face_debug_wangwu", "mode": "exam",
             "start": datetime.datetime(2026, 5, 8, 9, 30, 0),
             "duration_min": 50, "focus_base": 58, "alert_count": 2},
        ]

        alert_types = [
            ("离席", "检测到离开座位超过30秒"),
            ("低分告警", "专注度低于阈值60分"),
            ("姿态异常", "头部持续低倾超过15秒"),
            ("多人", "画面中检测到多人"),
            ("行为异常", "检测到走神行为"),
        ]

        for sd in session_defs:
            start_ts = sd["start"].timestamp()
            db_service.create_session({
                "session_id": sd["sid"],
                "face_id": sd["face_id"],
                "mode": sd["mode"],
                "start_time": start_ts,
            })

            duration_s = sd["duration_min"] * 60
            record_count = random.randint(15, 25)
            records = []
            for i in range(record_count):
                ts = start_ts + (i / record_count) * duration_s
                variation = lambda: random.uniform(-8, 8)
                scores = {
                    "head_pose_score": max(0, min(100, sd["focus_base"] + variation())),
                    "eye_score": max(0, min(100, sd["focus_base"] + variation())),
                    "yawn_score": max(0, min(100, sd["focus_base"] + variation())),
                    "distance_score": max(0, min(100, sd["focus_base"] + variation())),
                    "behavior_score": 0.0,
                    "expression_score": 0.0,
                    "evidence_score": max(0, min(100, sd["focus_base"] + variation())),
                    "people_score": random.uniform(80, 100),
                }
                scores["final_focus_score"] = sum(
                    v for k, v in scores.items()
                    if k not in ("behavior_score", "expression_score")
                ) / (len(scores) - 2)
                scores["is_force_zero"] = False
                scores["is_over_threshold"] = False
                records.append({
                    "session_id": sd["sid"],
                    "timestamp": ts,
                    **scores,
                    "warn_info": None,
                })

            if sd["alert_count"] > 0:
                alert_indices = random.sample(
                    range(record_count), min(sd["alert_count"], record_count)
                )
                for idx in alert_indices:
                    a_type, a_detail = random.choice(alert_types)
                    records[idx]["warn_info"] = {"type": a_type, "detail": a_detail}

            db_service.insert_focus_records_batch(records)

            end_ts = start_ts + duration_s
            db_service.end_session(sd["sid"], end_ts)

        print(f"[MockDataManager] seed_debug_data 完成: "
              f"{len(students)} 学生, {len(session_defs)} 会话")


mock_data_manager = MockDataManager()
