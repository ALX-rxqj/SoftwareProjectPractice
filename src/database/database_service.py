"""数据库服务层（单例）

命令路由中心，接收来自 InterfaceManager 的查询指令并分发到对应的处理方法。
"""

from typing import Any, Dict, List, Optional

from .connection import ConnectionManager, connection_manager
from .schema import SchemaManager, schema_manager


class DatabaseService:
    """数据库服务（单例）—— 命令路由 + 查询处理"""

    _instance: Optional["DatabaseService"] = None

    def __new__(cls) -> "DatabaseService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._conn_mgr: ConnectionManager = connection_manager
        self._schema_mgr: SchemaManager = schema_manager
        self._command_handlers: Dict[str, callable] = {
            "query_sessions": self._query_sessions,
            "query_focus_records": self._query_focus_records,
        }

    def initialize(self, db_path: str) -> None:
        """初始化数据库连接并校验 schema"""
        self._conn_mgr.initialize(db_path)
        self._schema_mgr.ensure_schema()
        print(f"[DatabaseService] 数据库初始化完成: {db_path}")

    def handle_command(self, command: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """命令路由：字典分发给对应的处理方法

        后续扩展时在 _command_handlers 字典中添加映射即可。
        """
        handler = self._command_handlers.get(command)
        if handler is not None:
            return handler(params)
        print(f"[DatabaseService] 未知命令: {command}")
        return None

    def _query_sessions(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Stub: 查询会话信息列表

        DBI-01 接口。
        筛选参数（来自 FilterSidebar）:
            start_date, end_date, mode,
            focus_min, focus_max, abnormal_min, abnormal_max
        """
        print(f"[DatabaseService] stub: _query_sessions(params={params})")
        return []

    def _query_focus_records(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Stub: 查询专注度评分记录

        用于 SessionDetailWidget 展示单次会话的评分详情。
        参数: session_id, start_time, end_time
        """
        print(f"[DatabaseService] stub: _query_focus_records(params={params})")
        return []

    def shutdown(self) -> None:
        """关闭数据库连接"""
        self._conn_mgr.close()
        print("[DatabaseService] 数据库服务已关闭")


database_service = DatabaseService()
