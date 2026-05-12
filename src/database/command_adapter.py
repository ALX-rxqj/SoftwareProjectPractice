"""数据库模块回调适配器

将 DatabaseService 包装为 InterfaceManager.register_database_callback() 所需的
可调用对象，签名: (command: str, params: dict) -> Optional[List[Dict]]
"""

from typing import Any, Dict, List, Optional

from .database_service import DatabaseService


class DatabaseCommandAdapter:
    """将 DatabaseService 适配为 InterfaceManager 所需的回调格式

    镜像 PreprocessingCommandAdapter 的设计模式。
    """

    def __init__(self, service: DatabaseService) -> None:
        self._service = service

    def __call__(self, command: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        return self._service.handle_command(command, params)
