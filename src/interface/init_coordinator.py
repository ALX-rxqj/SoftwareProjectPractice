"""
初始化协调器 - Init Coordinator

管理应用启动时的异步初始化流程：
数据库初始化 → 后端加载（后台线程）→ 轮询等待 → 回调注册 → 初始数据加载

从 MainWindow.__init__ + _start_async_init 中提取。
"""

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication

from .unified_data_manager import unified_data_manager


class InitCoordinator(QObject):
    """应用启动初始化协调器。

    用法:
        coordinator = InitCoordinator(loading_widget)
        coordinator.init_complete.connect(self.init_data)
        coordinator.start(
            on_video_frame=self._on_video_frame_for_display,
            on_focus_result=self._on_focus_result_for_display,
            on_camera_list=self.on_camera_list_received,
            on_file_ended=self._on_file_playback_ended,
        )
    """

    init_complete = pyqtSignal()
    progress_update = pyqtSignal(str, float)

    def __init__(self, loading_widget):
        super().__init__()
        self._loading_widget = loading_widget
        self._poll_timer = None
        self.progress_update.connect(self._on_progress_label)

    def _on_progress_label(self, message: str, progress: float):
        self._loading_widget.update_loading_progress(message, progress)

    def start(self, on_video_frame, on_focus_result,
              on_camera_list, on_file_ended):
        """启动异步初始化流程"""
        need_loading = unified_data_manager.preprocessing_source.value == "real"

        if need_loading:
            self._loading_widget.show_loading_overlay("正在初始化模型...")
            QApplication.processEvents()

        if not unified_data_manager.initialize_database():
            print("[InitCoordinator] 警告: 数据库初始化失败，历史数据功能不可用")

        if not unified_data_manager.initialize_all_backends(
            progress_callback=self._on_init_progress
        ):
            print("[InitCoordinator] 错误: 后端初始化失败")

        unified_data_manager.register_camera_list_callback(on_camera_list)
        unified_data_manager.register_video_frame_callback(on_video_frame)
        unified_data_manager.register_focus_result_callback(on_focus_result)
        unified_data_manager.register_file_playback_ended_callback(on_file_ended)

        if need_loading:
            self._poll_timer = QTimer()
            self._poll_timer.timeout.connect(self._poll_init_complete)
            self._poll_timer.start(200)
        else:
            self.init_complete.emit()

    def _on_init_progress(self, message: str, progress: float):
        self.progress_update.emit(message, progress)

    def _poll_init_complete(self):
        if not unified_data_manager.init_done:
            return

        self._poll_timer.stop()
        self._loading_widget.hide_loading_overlay()

        if unified_data_manager.init_success:
            print("[InitCoordinator] 已连接真实预处理后端")
        else:
            print("[InitCoordinator] 使用模拟数据模式（预处理模块不可用）")

        self.init_complete.emit()
