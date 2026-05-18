"""数据库连接管理器（单例）

提供 SQLite 连接的创建、获取和关闭。
支持线程安全、连接健康检查和自动重连。
"""

import sqlite3
from typing import Optional


class ConnectionManager:
    """SQLite 数据库连接管理器（单例）"""

    _instance: Optional["ConnectionManager"] = None

    def __new__(cls) -> "ConnectionManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._connection: Optional[sqlite3.Connection] = None
        self._db_path: Optional[str] = None

    def initialize(self, db_path: str) -> None:
        """打开（或创建）指定路径的 SQLite 数据库"""
        if self._connection is not None:
            self.close()
        self._db_path = db_path
        self._connection = sqlite3.connect(
            db_path, check_same_thread=False, timeout=5.0
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys = ON")
        print(f"[ConnectionManager] 已连接数据库: {db_path}")

    def get_connection(self) -> sqlite3.Connection:
        """获取当前数据库连接，自动检测并恢复失效连接"""
        if self._connection is None:
            if self._db_path is not None:
                print("[ConnectionManager] 连接为空，尝试自动重连...")
                self.initialize(self._db_path)
            else:
                raise RuntimeError(
                    "数据库连接尚未初始化，请先调用 ConnectionManager.initialize(db_path)"
                )
        else:
            try:
                self._connection.execute("SELECT 1")
            except (sqlite3.ProgrammingError, sqlite3.DatabaseError) as e:
                print(f"[ConnectionManager] 连接已失效 ({e})，尝试自动重连...")
                self.initialize(self._db_path)
        return self._connection

    def close(self) -> None:
        """提交事务并关闭数据库连接"""
        if self._connection is not None:
            try:
                self._connection.commit()
                self._connection.close()
            except sqlite3.Error:
                pass
            print(f"[ConnectionManager] 已关闭数据库: {self._db_path}")
            self._connection = None
            self._db_path = None

    @property
    def db_path(self) -> Optional[str]:
        return self._db_path

    @property
    def is_connected(self) -> bool:
        return self._connection is not None


connection_manager = ConnectionManager()
