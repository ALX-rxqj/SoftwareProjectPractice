"""
会话管理器 - Session Manager

负责管理分析会话的生命周期，包括：
1. 创建新会话
2. 结束会话
3. 维护会话状态
4. 管理告警阈值
5. 记录会话统计信息
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, Optional

from .contracts import MonitorMode, SessionInfo


class SessionManager:
    """
    会话管理器核心类
    
    管理所有分析会话的生命周期，提供会话创建、结束、查询等功能。
    支持同时管理多个会话，但同一时间只有一个活动会话。
    """

    def __init__(self):
        """初始化会话管理器"""
        self._sessions: Dict[str, SessionInfo] = {}  # 会话存储
        self._current_session_id: Optional[str] = None  # 当前活动会话ID
        self._default_warn_threshold: float = 60.0  # 默认告警阈值

    @property
    def current_session(self) -> Optional[SessionInfo]:
        """获取当前活动会话"""
        if self._current_session_id and self._current_session_id in self._sessions:
            return self._sessions[self._current_session_id]
        return None

    @property
    def current_session_id(self) -> Optional[str]:
        """获取当前会话ID"""
        return self._current_session_id

    def create_session(self, mode: MonitorMode = MonitorMode.CLASS, 
                       warn_threshold: Optional[float] = None) -> str:
        """
        创建新会话
        
        Args:
            mode: 监督模式（CLASS/EXAM）
            warn_threshold: 告警阈值，默认为60.0
        
        Returns:
            session_id: 新创建的会话ID
        
        Raises:
            ValueError: 如果已有活动会话未结束
        """
        # 如果有活动会话，先结束它
        if self._current_session_id:
            self.end_session(self._current_session_id)

        # 生成唯一会话ID
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        
        # 创建会话信息
        session_info = SessionInfo(
            session_id=session_id,
            mode=mode,
            start_time=time.time(),
            warn_threshold=warn_threshold or self._default_warn_threshold,
            is_running=True,
        )

        # 保存会话并设置为当前会话
        self._sessions[session_id] = session_info
        self._current_session_id = session_id

        return session_id

    def adopt_session(self, session_id: str, mode: MonitorMode = MonitorMode.CLASS,
                      warn_threshold: float = 60.0) -> str:
        """
        接管外部已创建的会话（session_id 已由 interface_manager 写入数据库）

        与 create_session 不同，此方法不生成新的 session_id，
        直接使用传入的 ID 注册到内存中。
        """
        if self._current_session_id:
            self.end_session(self._current_session_id)

        session_info = SessionInfo(
            session_id=session_id,
            mode=mode,
            start_time=time.time(),
            warn_threshold=warn_threshold,
            is_running=True,
        )
        self._sessions[session_id] = session_info
        self._current_session_id = session_id
        return session_id

    def end_session(self, session_id: str) -> bool:
        """
        结束指定会话
        
        Args:
            session_id: 要结束的会话ID
        
        Returns:
            是否成功结束
        
        Raises:
            ValueError: 如果会话不存在
        """
        if session_id not in self._sessions:
            raise ValueError(f"会话不存在: {session_id}")

        session_info = self._sessions[session_id]
        session_info.is_running = False
        session_info.end_time = time.time()

        # 如果结束的是当前会话，清空当前会话ID
        if self._current_session_id == session_id:
            self._current_session_id = None

        return True

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """
        获取指定会话信息
        
        Args:
            session_id: 会话ID
        
        Returns:
            会话信息，如果不存在返回None
        """
        return self._sessions.get(session_id)

    def update_session_stats(self, session_id: str, frames_processed: int = 0, 
                            abnormal_events: int = 0):
        """
        更新会话统计信息
        
        Args:
            session_id: 会话ID
            frames_processed: 新增处理帧数
            abnormal_events: 新增异常事件数
        """
        if session_id in self._sessions:
            self._sessions[session_id].total_frames += frames_processed
            self._sessions[session_id].abnormal_event_count += abnormal_events

    def set_warn_threshold(self, session_id: str, threshold: float) -> bool:
        """
        设置会话的告警阈值
        
        Args:
            session_id: 会话ID
            threshold: 告警阈值 [0, 100]
        
        Returns:
            是否成功设置
        
        Raises:
            ValueError: 如果阈值不在有效范围
        """
        if not (0.0 <= threshold <= 100.0):
            raise ValueError(f"告警阈值必须在0-100之间: {threshold}")

        if session_id in self._sessions:
            self._sessions[session_id].warn_threshold = threshold
            return True
        return False

    def get_all_sessions(self) -> Dict[str, SessionInfo]:
        """获取所有会话（包括已结束的）"""
        return self._sessions.copy()

    def get_active_sessions(self) -> Dict[str, SessionInfo]:
        """获取所有活动会话"""
        return {k: v for k, v in self._sessions.items() if v.is_running}

    def clear_sessions(self):
        """清除所有会话记录"""
        self._sessions.clear()
        self._current_session_id = None

    def delete_session(self, session_id: str) -> bool:
        """
        删除指定会话
        
        Args:
            session_id: 要删除的会话ID
        
        Returns:
            是否成功删除
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            if self._current_session_id == session_id:
                self._current_session_id = None
            return True
        return False

    def has_active_session(self) -> bool:
        """检查是否有活动会话"""
        return self._current_session_id is not None

    def get_session_duration(self, session_id: str) -> Optional[float]:
        """
        获取会话持续时间（秒）
        
        Args:
            session_id: 会话ID
        
        Returns:
            持续时间（秒），如果会话不存在返回None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        end_time = session.end_time or time.time()
        return end_time - session.start_time

    def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """
        获取会话摘要信息
        
        Args:
            session_id: 会话ID
        
        Returns:
            会话摘要字典，如果会话不存在返回None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "mode": session.mode.value,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "duration": self.get_session_duration(session_id),
            "warn_threshold": session.warn_threshold,
            "is_running": session.is_running,
            "total_frames": session.total_frames,
            "abnormal_event_count": session.abnormal_event_count,
        }
