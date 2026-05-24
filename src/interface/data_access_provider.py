"""
数据访问提供者 - Data Access Provider

统一管理历史数据查询和数据库操作，根据 DataSource 自动选择 REAL/MOCK 路径。
由 UnifiedDataManager 持有，MainWindow 通过 UDM 间接访问。
"""

import os
from typing import Dict, List, Optional, Any

from .interface_manager import interface_manager
from .mock_data_manager import mock_data_manager
from ..database.database_service import database_service

DataAccessSource = object  # DataSource reference, injected by UDM


class DataAccessProvider:
    """历史数据查询和数据库初始化。

    不创建单例——由 UnifiedDataManager 在 __init__ 中实例化。
    通过 _get_db_source 回调读取 UDM 的当前 database_source。
    """

    def __init__(self, get_db_source, DataSource):
        self._get_db_source = get_db_source
        self._DS = DataSource

    @property
    def _database_source(self):
        return self._get_db_source()

    # ──────────────────── 数据库初始化 ────────────────────

    def initialize_database(self, db_path: str = None) -> bool:
        if db_path is None:
            db_dir = os.path.join(os.path.expanduser("~"), ".class_monitor")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "data.db")
        try:
            database_service.initialize(db_path)
            print(f"[DataAccess] 数据库已初始化: {db_path}")
            mock_data_manager.seed_debug_data(database_service)
            return True
        except Exception as e:
            print(f"[DataAccess] 数据库初始化失败: {e}")
            return False

    # ──────────────────── 历史数据查询 ────────────────────

    def generate_face_ids(self) -> List[str]:
        if self._database_source == self._DS.REAL:
            result = interface_manager.query_face_registry()
            if result and result.get("success"):
                return [f.get("face_id", "") for f in result.get("faces", [])
                        if f.get("face_id")]
            faces = database_service.query_registered_faces()
            return [f.get("face_id", "") for f in faces if f.get("face_id")]
        return mock_data_manager.generate_face_ids()

    def generate_face_ids_with_details(self) -> List[Dict[str, Any]]:
        if self._database_source == self._DS.REAL:
            result = interface_manager.query_face_registry()
            if result and result.get("success"):
                return result.get("faces", [])
            faces = database_service.query_registered_faces()
            return [{"face_id": f.get("face_id", ""),
                     "student_name": f.get("student_name", ""),
                     "storage_type": "local",
                     "registered_at": f.get("registered_at", 0)}
                    for f in faces]
        face_ids = mock_data_manager.generate_face_ids()
        return [
            {"face_id": fid, "student_name": f"学生 {fid}",
             "storage_type": "local", "registered_at": 0}
            for fid in face_ids
        ]

    def delete_face(self, face_id: str) -> Dict[str, Any]:
        print(f"[DataAccess] 删除人脸: {face_id}")
        if self._database_source == self._DS.REAL:
            interface_manager.delete_face(face_id)
            db_result = database_service.delete_face(face_id)
            print(f"[DataAccess] 删除结果: {db_result}")
            return db_result
        else:
            return mock_data_manager.delete_face(face_id)

    def generate_records(self, face_id: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        if self._database_source == self._DS.REAL:
            return []
        return mock_data_manager.generate_records(face_id, count)

    def generate_sessions(self, face_id: str) -> List[Dict[str, Any]]:
        if self._database_source == self._DS.REAL:
            return []
        return mock_data_manager.generate_sessions(face_id)

    def generate_all_sessions(self) -> List[Dict[str, Any]]:
        if self._database_source == self._DS.REAL:
            return []
        all_sessions = []
        for face_id in mock_data_manager.generate_face_ids():
            sessions = mock_data_manager.generate_sessions(face_id)
            for session in sessions:
                session["face_id"] = face_id
                all_sessions.append(session)
        all_sessions.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        print(f"[DataAccess] 获取全部会话记录: {len(all_sessions)} 条")
        return all_sessions

    def query_sessions(self, filter_params: dict) -> List[Dict[str, Any]]:
        if self._database_source == self._DS.REAL:
            db_params = dict(filter_params)
            if db_params.get("start_date"):
                db_params["start_date"] = self._date_str_to_ts(
                    db_params["start_date"], day_start=True)
            if db_params.get("end_date"):
                db_params["end_date"] = self._date_str_to_ts(
                    db_params["end_date"], day_start=False)
            results = database_service.query_sessions(db_params)
            for r in results:
                if r.get("start_time"):
                    r["start_time"] = self._ts_to_str(r["start_time"])
                if r.get("end_time"):
                    r["end_time"] = self._ts_to_str(r["end_time"])
            return results

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

            video_source_filter = filter_params.get("video_source_type")
            if video_source_filter and session.get("video_source_type") != video_source_filter:
                continue

            filtered.append(session)
        return filtered

    def generate_records_by_session(self, session_id: str, start_time: str, end_time: str) -> List[Dict[str, Any]]:
        print(f"[DataAccess] 查询会话记录: session_id={session_id}")
        if self._database_source == self._DS.REAL:
            return database_service.query_focus_records(session_id)
        all_records = self.generate_records_for_session(session_id, start_time, end_time)
        print(f"[DataAccess] 筛选结果: {len(all_records)} 条记录")
        return all_records

    def generate_records_for_session(self, session_id: str, start_time: str = "", end_time: str = "") -> List[Dict[str, Any]]:
        if self._database_source == self._DS.REAL:
            return []
        if start_time and end_time:
            return mock_data_manager.generate_records_with_session_id(
                session_id, start_time, end_time)
        return []

    def generate_alarm_events(self, session_id: str) -> List[Dict[str, Any]]:
        if self._database_source == self._DS.REAL:
            return database_service.query_alert_events(session_id)
        return mock_data_manager.generate_alarm_events(session_id)

    def delete_sessions(self, session_ids: List[str]) -> Dict[str, Any]:
        print(f"[DataAccess] 删除会话请求: {len(session_ids)} 条")
        if self._database_source == self._DS.REAL:
            result = database_service.delete_sessions(session_ids)
        else:
            result = mock_data_manager.delete_sessions(session_ids)
        print(f"[DataAccess] 删除完成: {result['deleted_count']}/{result['total']}")
        return result

    # ──────────────────── 工具方法 ────────────────────

    @staticmethod
    def _ts_to_str(ts: float) -> str:
        import datetime
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _date_str_to_ts(date_str: str, day_start: bool) -> float:
        import datetime
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        if not day_start:
            dt = dt.replace(hour=23, minute=59, second=59)
        return dt.timestamp()

    def clear_cache(self):
        mock_data_manager.clear_cache()
        print("[DataAccess] 缓存已清除")
