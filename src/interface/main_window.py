from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedLayout, QSplitter, QMenu, QFileDialog, QMessageBox, QApplication

from .config import WINDOW_WIDTH, WINDOW_HEIGHT, TOP_NAV_HEIGHT, LEFT_BAR_WIDTH, RIGHT_PANEL_WIDTH
from .styles import get_style, get_spacing, SIZES, COLORS
from .top_nav_bar import TopNavBar
from .left_sidebar import LeftSideBar
from .video_widget import VideoWidget, ToastWidget
from .right_panel import RightPanel
from .filter_sidebar import FilterSidebar
from .data_record_widget import DataRecordWidget
from .session_detail_widget import SessionDetailWidget
from .unified_data_manager import unified_data_manager, CameraInfo, VideoFrameData, FocusResultData
from .face_registration_dialog import FaceRegistrationDialog
from .alert_info_dialog import AlertInfoDialog
from .export_report_util import export_to_excel, export_to_pdf


class MainWindow(QMainWindow):
    _init_progress_signal = pyqtSignal(str, float)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("网课专注度分析系统")
        self.setMinimumSize(1280, 720)
        self.showMaximized()
        self.setStyleSheet(get_style("main_window"))
        self.current_mode = "class"
        self.current_face_id = None
        self.current_device_id = 0
        self._current_source_type = "camera"  # "camera" 或 "file"
        self._current_file_path: Optional[str] = None
        self._init_poll_timer = None
        self.init_ui()
        self.toast_widget = ToastWidget(anchor=self.video_widget)
        self.connect_signals()
        self._init_progress_signal.connect(self._on_init_progress_label)
        self._start_async_init()

    def closeEvent(self, event):
        """窗口关闭时正确关闭数据库连接，确保 WAL checkpoint 执行"""
        from ..database.database_service import database_service
        database_service.shutdown()
        super().closeEvent(event)

    def _start_async_init(self):
        """快速显示窗口，后台异步加载预处理模型。"""

        need_loading_label = (
            unified_data_manager.preprocessing_source.value == "real"
        )

        if need_loading_label:
            self.video_widget.show_loading_overlay("正在初始化模型...")
            QApplication.processEvents()

        # 数据库（同步，轻量）
        if not unified_data_manager.initialize_database():
            print("[MainWindow] 警告: 数据库初始化失败，历史数据功能不可用")

        # 统一初始化后端（Mock 适配器 / REAL 后端加载）
        if not unified_data_manager.initialize_all_backends(
            progress_callback=self._on_init_progress
        ):
            print("[MainWindow] 错误: 后端初始化失败")

        unified_data_manager.register_camera_list_callback(self.on_camera_list_received)

        # 注册数据分发回调：MainWindow 作为数据中转中心
        unified_data_manager.register_video_frame_callback(self._on_video_frame_for_display)
        unified_data_manager.register_focus_result_callback(self._on_focus_result_for_display)

        # 注册文件播放完成回调
        from .interface_manager import interface_manager
        interface_manager.register_file_playback_ended_callback(self._on_file_playback_ended)

        if need_loading_label:
            self._init_poll_timer = QTimer()
            self._init_poll_timer.timeout.connect(self._poll_init_complete)
            self._init_poll_timer.start(200)
        else:
            self.init_data()

    def _on_init_progress(self, message: str, progress: float):
        """后台线程进度回调 → 通过信号安全传递到 UI 线程"""
        self._init_progress_signal.emit(message, progress)

    def _on_init_progress_label(self, message: str, progress: float):
        """UI 线程更新视频覆盖层的进度文本"""
        self.video_widget.update_loading_progress(message, progress)

    def _poll_init_complete(self):
        """轮询：检查后台预处理初始化是否完成。"""
        if not unified_data_manager.init_done:
            return

        # 初始化完成
        self._init_poll_timer.stop()
        self.video_widget.hide_loading_overlay()

        if unified_data_manager.init_success:
            print("[MainWindow] 已连接真实预处理后端")
        else:
            print("[MainWindow] 使用模拟数据模式（预处理模块不可用）")

        self.init_data()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.main_stacked_layout = QStackedLayout(central_widget)
        self.main_stacked_layout.setContentsMargins(
            get_spacing("base"), get_spacing("lg"),
            get_spacing("base"), get_spacing("lg"),
        )

        self.top_nav = TopNavBar()
        self.top_nav.setMinimumHeight(TOP_NAV_HEIGHT)

        self.top_nav_query = TopNavBar()
        self.top_nav_query.setMinimumHeight(TOP_NAV_HEIGHT)

        self.left_sidebar = LeftSideBar()
        self.left_sidebar.setMinimumWidth(LEFT_BAR_WIDTH)
        self.left_sidebar.setMaximumWidth(LEFT_BAR_WIDTH * 2)

        self.video_widget = VideoWidget()
        self.video_widget.setMinimumWidth(400)

        self.right_panel = RightPanel()
        self.right_panel.setMinimumWidth(RIGHT_PANEL_WIDTH)
        self.right_panel.setMaximumWidth(RIGHT_PANEL_WIDTH * 2)

        self.filter_sidebar = FilterSidebar()
        self.filter_sidebar.setMinimumWidth(SIZES["sidebar"]["width"])
        self.filter_sidebar.setMaximumWidth(SIZES["sidebar"]["width"] + 80)

        self.data_record_widget = DataRecordWidget()
        self.data_record_widget.setMinimumWidth(RIGHT_PANEL_WIDTH)

        self.session_detail_widget = SessionDetailWidget()

        monitoring_widget = QWidget()
        monitoring_layout = QVBoxLayout(monitoring_widget)
        monitoring_layout.setContentsMargins(0, 0, 0, 0)
        monitoring_layout.setSpacing(get_spacing("lg"))

        horizontal_splitter = QSplitter(Qt.Horizontal)
        horizontal_splitter.addWidget(self.left_sidebar)
        horizontal_splitter.addWidget(self.video_widget)
        horizontal_splitter.addWidget(self.right_panel)
        horizontal_splitter.setStretchFactor(1, 1)
        horizontal_splitter.setHandleWidth(6)
        horizontal_splitter.setChildrenCollapsible(False)
        horizontal_splitter.setStyleSheet(get_style("splitter"))
        horizontal_splitter.setSizes([LEFT_BAR_WIDTH, 560, RIGHT_PANEL_WIDTH])

        vertical_splitter = QSplitter(Qt.Vertical)
        vertical_splitter.addWidget(self.top_nav)
        vertical_splitter.addWidget(horizontal_splitter)
        vertical_splitter.setStretchFactor(1, 1)
        vertical_splitter.setHandleWidth(8)
        vertical_splitter.setChildrenCollapsible(False)
        vertical_splitter.setStyleSheet(get_style("splitter"))
        vertical_splitter.setSizes([TOP_NAV_HEIGHT, 550])

        monitoring_layout.addWidget(vertical_splitter)

        query_widget = QWidget()
        query_layout = QVBoxLayout(query_widget)
        query_layout.setContentsMargins(0, 0, 0, 0)
        query_layout.setSpacing(get_spacing("lg"))

        query_vertical_splitter = QSplitter(Qt.Vertical)
        query_vertical_splitter.addWidget(self.top_nav_query)

        self.right_stacked_layout = QStackedLayout()
        self.right_stacked_layout.setContentsMargins(0, 0, 0, 0)
        self.right_stacked_layout.addWidget(self.data_record_widget)
        self.right_stacked_layout.addWidget(self.session_detail_widget)
        self.right_stacked_layout.setCurrentIndex(0)

        right_stacked_widget = QWidget()
        right_stacked_widget.setLayout(self.right_stacked_layout)

        query_horizontal_splitter = QSplitter(Qt.Horizontal)
        query_horizontal_splitter.addWidget(self.filter_sidebar)
        query_horizontal_splitter.addWidget(right_stacked_widget)
        query_horizontal_splitter.setStretchFactor(1, 2)
        query_horizontal_splitter.setHandleWidth(6)
        query_horizontal_splitter.setChildrenCollapsible(False)
        query_horizontal_splitter.setStyleSheet(get_style("splitter"))
        query_horizontal_splitter.setSizes([280, 800])

        query_vertical_splitter.addWidget(query_horizontal_splitter)
        query_vertical_splitter.setStretchFactor(1, 1)
        query_vertical_splitter.setHandleWidth(6)
        query_vertical_splitter.setChildrenCollapsible(False)
        query_vertical_splitter.setStyleSheet(get_style("splitter"))
        query_vertical_splitter.setSizes([TOP_NAV_HEIGHT, 550])

        query_layout.addWidget(query_vertical_splitter)

        self.main_stacked_layout.addWidget(monitoring_widget)
        self.main_stacked_layout.addWidget(query_widget)
        self.main_stacked_layout.setCurrentIndex(0)

    def connect_signals(self):
        self.top_nav.mode_changed.connect(self.on_mode_changed)
        self.top_nav_query.mode_changed.connect(self.on_mode_changed)
        self.right_panel.start_analysis.connect(self.on_start_analysis)
        self.right_panel.stop_analysis.connect(self.on_stop_analysis)
        self.right_panel.toast_requested.connect(self.toast_widget.show_toast)
        self.right_panel.toast_dismiss_requested.connect(self.toast_widget.dismiss)
        self.right_panel.set_start_validator(self._validate_start_analysis)
        self.filter_sidebar.filter_applied.connect(self.on_filter_applied)
        self.filter_sidebar.chart_options_changed.connect(self.on_chart_options_changed)
        self.data_record_widget.session_selected.connect(self.on_session_clicked)
        self.data_record_widget.delete_requested.connect(self.on_delete_sessions)
        self.session_detail_widget.back_pressed.connect(self.on_back_to_sessions)
        self.session_detail_widget.alert_info_clicked.connect(self.on_alert_info_clicked)
        self.session_detail_widget.export_report_clicked.connect(self.on_export_report_clicked)
        self.left_sidebar.camera_selected.connect(self.on_camera_selected)
        self.left_sidebar.refresh_requested.connect(self.on_refresh_camera_list)
        self.left_sidebar.face_selected.connect(self.on_face_selected)
        self.left_sidebar.face_delete_requested.connect(self.on_delete_face)
        self.left_sidebar.show_bbox_toggled.connect(self.video_widget.set_show_face_boxes)
        self.left_sidebar.file_selected.connect(self.on_file_selected)
        self.video_widget.frame_updated.connect(self.on_video_frame_updated)
        self.top_nav.register_face_clicked.connect(self.on_register_face_clicked)
        self.top_nav_query.register_face_clicked.connect(self.on_register_face_clicked)

    def init_data(self):
        """通过统一数据管理器获取初始数据（各模块独立数据源）"""
        print(f"[MainWindow] 预处理模块数据源: {unified_data_manager.preprocessing_source.value}")
        print(f"[MainWindow] 状态估计模块数据源: {unified_data_manager.state_estimation_source.value}")
        print(f"[MainWindow] 数据库模块数据源: {unified_data_manager.database_source.value}")
        print(f"[MainWindow] 请求摄像头列表...")
        unified_data_manager.request_camera_list()
        self.refresh_face_list()

    def refresh_face_list(self):
        """从预处理注册表（降级至数据库）获取已注册人脸列表"""
        faces = unified_data_manager.generate_face_ids_with_details()
        print(f"[MainWindow] 刷新人脸列表: {len(faces)} 个已注册人脸")
        self.left_sidebar.update_faces(faces)
        face_ids = unified_data_manager.generate_face_ids()
        self.filter_sidebar.refresh_face_list(face_ids)

    def _on_video_frame_for_display(self, data: VideoFrameData):
        """UIM 视频帧回调 → 分发给 VideoWidget"""
        self.video_widget.render_frame(data)

        # 文件模式：更新进度条
        if data.frame_progress:
            self.video_widget.update_progress(
                data.frame_progress.get("current_frame", 0),
                data.frame_progress.get("total_frames", 0),
            )

    def _on_focus_result_for_display(self, data: FocusResultData):
        """UIM 专注度结果回调 → 分发给 RightPanel"""
        self.right_panel.handle_focus_result(data)

    def on_camera_list_received(self, cameras):
        """摄像头列表回调"""
        print(f"[MainWindow] 收到摄像头列表: {len(cameras)} 个摄像头")
        self.left_sidebar.load_cameras(cameras)

    def on_mode_changed(self, mode):
        """切换模式回调"""
        print(f"[MainWindow] 用户选择模式: {mode}")
        self.current_mode = mode
        if mode == "数据查询":
            self.switch_to_query_mode()
        else:
            self.switch_to_monitoring_mode(mode)
            result = unified_data_manager.switch_mode(mode)
            print(f"[MainWindow] 切换模式: {mode}, 结果: {result}")

    def switch_to_monitoring_mode(self, mode):
        self.main_stacked_layout.setCurrentIndex(0)
        self.top_nav.set_mode(mode)
        self.top_nav_query.set_mode(mode)
        self.refresh_face_list()

    def switch_to_query_mode(self):
        self.main_stacked_layout.setCurrentIndex(1)
        self.top_nav.set_mode("数据查询")
        self.top_nav_query.set_mode("数据查询")
        self.right_stacked_layout.setCurrentIndex(0)
        self.filter_sidebar.show_filter_mode()

        filter_params = self.filter_sidebar.get_current_filter()
        self.apply_filter(filter_params)

    def apply_filter(self, filter_params: dict):
        """应用筛选条件，查询会话信息表（UII-01）"""
        print(f"[MainWindow] 应用筛选条件: {filter_params}")
        filtered_sessions = unified_data_manager.query_sessions(filter_params)
        print(f"[MainWindow] 筛选结果: {len(filtered_sessions)} 条会话记录")
        self.data_record_widget.load_sessions(filter_params, filtered_sessions)

    def on_filter_applied(self, filter_params):
        self.apply_filter(filter_params)

    def on_session_clicked(self, session_data):
        """点击会话记录，进入详情页"""
        print(f"[MainWindow] 用户点击会话记录")

        session_id = session_data.get("session_id", "")
        start_time = session_data.get("start_time", "")
        end_time = session_data.get("end_time", "")

        print(f"[MainWindow] 查询条件:")
        print(f"  - session_id: {session_id}")
        print(f"  - start_time: {start_time}")
        print(f"  - end_time: {end_time}")

        records = unified_data_manager.generate_records_by_session(
            session_id, start_time, end_time
        )
        print(f"[MainWindow] 查询到 {len(records)} 条专注度评分记录")

        chart_options = self.filter_sidebar.get_chart_options()
        self.session_detail_widget.load_session_detail(session_data, records, chart_options)
        self.right_stacked_layout.setCurrentIndex(1)
        self.filter_sidebar.show_chart_mode()

    def on_back_to_sessions(self):
        """从详情页返回到会话列表"""
        print(f"[MainWindow] 返回会话列表")
        self.filter_sidebar.show_filter_mode()
        self.right_stacked_layout.setCurrentIndex(0)

    def on_chart_options_changed(self, chart_options):
        """图表选项改变时更新详情页图表"""
        if self.right_stacked_layout.currentIndex() == 1:
            self.session_detail_widget.update_chart(chart_options)

    def on_face_selected(self, face_id: str):
        """用户在人脸列表中选择人脸"""
        self.current_face_id = face_id
        print(f"[MainWindow] 当前选中人脸: {face_id}")

    def _validate_start_analysis(self):
        """开始分析前验证，被 RightPanel.on_control_click 调用。返回 (bool, str)。"""
        if not self.left_sidebar.has_faces():
            self._msg("warning", "提示", "请先完成人脸注册")
            return False, ""
        return True, ""

    def on_start_analysis(self):
        print("[MainWindow] 开始分析")

        face_id = self.left_sidebar.get_selected_face_id()
        if face_id:
            self.current_face_id = face_id
        monitored_faces = [face_id] if face_id else []

        import os
        file_name = os.path.basename(self._current_file_path) if self._current_file_path else None

        # 根据视频源类型分发启动命令
        if self._current_source_type == "file":
            print(f"[MainWindow] 文件模式: {self._current_file_path}")
            result = unified_data_manager.load_video_file(self._current_file_path)
            print(f"[MainWindow] 视频文件加载结果: {result}")
        else:
            print(f"[MainWindow] 摄像头模式: device_id={self.current_device_id}, "
                  f"监控人脸: {monitored_faces}")
            result = unified_data_manager.toggle_capture(
                device_id=self.current_device_id, start=True,
                monitored_faces=monitored_faces,
            )
            print(f"[MainWindow] 摄像头控制结果: {result}")

        session_result = unified_data_manager.toggle_analysis(
            start=True, face_id=face_id,
            video_source_type=self._current_source_type,
            file_name=file_name if self._current_source_type == "file" else None,
        )
        if session_result and "session_id" in session_result:
            print(f"[MainWindow] 创建会话成功: {session_result['session_id']}")

        unified_data_manager.switch_mode(self.current_mode)

        self.video_widget.start_processing()

        # 文件模式：显示进度条
        if self._current_source_type == "file":
            self.video_widget.show_progress_bar()

        self.top_nav.set_recording(True)
        self.top_nav_query.set_recording(True)
        self.top_nav.set_mode_buttons_enabled(False)
        self.top_nav_query.set_mode_buttons_enabled(False)
        self.left_sidebar.set_faces_enabled(False)

    def on_stop_analysis(self):
        print("[MainWindow] 停止分析")
        self.toast_widget.dismiss()
        self.video_widget.stop_processing()

        # 统一停止命令
        result = unified_data_manager.stop_capture()
        print(f"[MainWindow] 停止采集结果: {result}")

        session_result = unified_data_manager.toggle_analysis(start=False)
        if session_result and "session_id" in session_result:
            print(f"[MainWindow] 结束会话成功: {session_result['session_id']}")

        # 重置视频源类型
        self._current_source_type = "camera"

        self.top_nav.set_recording(False)
        self.top_nav_query.set_recording(False)
        self.top_nav.set_mode_buttons_enabled(True)
        self.top_nav_query.set_mode_buttons_enabled(True)
        self.left_sidebar.set_faces_enabled(True)
        self.right_panel.reset_button_state()
        self.right_panel.reset_scores()

    def on_camera_selected(self, device_id: int):
        """用户选择摄像头"""
        print(f"[MainWindow] 用户选择摄像头: {device_id}")
        self.current_device_id = device_id
        self._current_source_type = "camera"

    def on_file_selected(self, file_path: str):
        """用户选择本地文件"""
        print(f"[MainWindow] 用户选择本地文件: {file_path}")
        self._current_file_path = file_path
        self._current_source_type = "file"

    def _on_file_playback_ended(self, file_path: str):
        """文件播放完成回调 — 自动执行停止 session 流程

        注意：此回调可能从预处理工作线程被调用，
        使用 QTimer.singleShot 将所有 Qt 操作调度到主线程执行。"""
        print(f"[MainWindow] 文件播放完成，自动停止: {file_path}")
        QTimer.singleShot(0, self.on_stop_analysis)

    def on_refresh_camera_list(self):
        """刷新摄像头列表"""
        print("[MainWindow] 手动刷新摄像头列表")
        unified_data_manager.refresh_camera_list()

    def on_video_frame_updated(self, frame_data):
        """视频帧更新时，传递 bbox 数据给 video_widget 用于勾选框绘制"""
        faces = frame_data.get("faces", [])
        if faces:
            self.video_widget.set_face_boxes(faces)

    def on_register_face_clicked(self):
        """注册人脸按钮点击"""
        if unified_data_manager.is_capture_running:
            self._msg("warning", "提示",
                      '正在分析中，请先点击"停止分析"后再注册人脸。')
            return

        print("[MainWindow] 打开人脸注册弹窗")
        dialog = FaceRegistrationDialog(
            device_id=self.current_device_id, parent=self
        )
        dialog.registration_completed.connect(self.on_face_registration_completed)
        dialog.face_registration_success.connect(self.refresh_face_list)
        dialog.show()

    def on_face_registration_completed(self, data: dict):
        """人脸注册完成回调"""
        name = data.get("student_name", "")
        frames = data.get("frames", [])
        storage_type = data.get("storage_type", "temp")

        print(
            f"[MainWindow] 人脸注册完成: name={name}, "
            f"frames={len(frames)}, storage={storage_type}"
        )

        result = unified_data_manager.register_face(name, frames, storage_type)
        print(f"[MainWindow] register_face 结果: {result}")

    def on_delete_face(self, face_id: str):
        """删除人脸：确认 → 删除 → 刷新列表"""
        if not face_id:
            return

        # 从 _faces_data 获取 student_name 用于确认提示
        student_name = face_id
        for f in self.left_sidebar._faces_data:
            if f.get("face_id") == face_id:
                student_name = f.get("student_name", face_id)
                break

        confirm_box = QMessageBox()
        confirm_box.setWindowTitle("确认删除")
        confirm_box.setText(f"确定删除学生「{student_name}」的人脸注册信息吗？")
        confirm_box.setIcon(QMessageBox.Question)
        confirm_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        confirm_box.setDefaultButton(QMessageBox.No)
        confirm_box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
                background-color: {COLORS['surface']};
            }}
            QPushButton {{
                color: {COLORS['text']};
                background-color: {COLORS['card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 16px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['card_hover']};
            }}
        """)
        if confirm_box.exec_() != QMessageBox.Yes:
            return

        print(f"[MainWindow] 删除人脸: face_id={face_id}, name={student_name}")
        result = unified_data_manager.delete_face(face_id)
        if result.get("success"):
            self.refresh_face_list()
            self._msg("info", "删除成功", f"已删除「{student_name}」的人脸注册信息")
        else:
            self._msg("warning", "删除失败",
                      result.get("msg", "未知错误"))

    def on_alert_info_clicked(self, session_data: dict):
        """查看告警信息"""
        session_id = session_data.get("session_id", "")
        if not session_id:
            self._msg("warning", "提示", "无有效的会话ID")
            return

        print(f"[MainWindow] 查看告警信息: session_id={session_id}")
        alerts = unified_data_manager.generate_alarm_events(session_id)
        print(f"[MainWindow] 获取到 {len(alerts)} 条告警记录")

        dialog = AlertInfoDialog(session_data, alerts, parent=self)
        dialog.show()

    def on_export_report_clicked(self, session_data: dict, records: list):
        """导出报告"""
        session_id = session_data.get("session_id", "")
        if not session_id or not records:
            self._msg("warning", "提示", "无有效数据可供导出")
            return

        # 提前生成告警数据，确保弹窗和导出一致
        alerts = unified_data_manager.generate_alarm_events(session_id)

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 32px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['primary']};
            }}
        """)

        excel_action = menu.addAction("导出 Excel (.xlsx)")
        pdf_action = menu.addAction("导出 PDF (.pdf)")

        chosen = menu.exec_(self.cursor().pos())
        if not chosen:
            return

        if chosen == excel_action:
            filepath, _ = QFileDialog.getSaveFileName(
                self, "导出 Excel 报告",
                f"{session_id}_report.xlsx",
                "Excel 文件 (*.xlsx)",
            )
            if filepath:
                try:
                    export_to_excel(session_data, records, alerts, filepath)
                    self._msg("info", "成功", f"报告已导出至:\n{filepath}")
                except Exception as e:
                    self._msg("critical", "错误", f"导出失败: {str(e)}")

        elif chosen == pdf_action:
            filepath, _ = QFileDialog.getSaveFileName(
                self, "导出 PDF 报告",
                f"{session_id}_report.pdf",
                "PDF 文件 (*.pdf)",
            )
            if filepath:
                try:
                    export_to_pdf(session_data, records, alerts, filepath)
                    self._msg("info", "成功", f"报告已导出至:\n{filepath}")
                except Exception as e:
                    self._msg("critical", "错误", f"导出失败: {str(e)}")

    def on_delete_sessions(self, session_ids: list):
        """批量删除会话及关联数据"""
        if not session_ids:
            return

        count = len(session_ids)
        reply = self._question(
            "确认删除",
            f"确定删除选中的 {count} 条会话及其关联数据吗？此操作不可撤销。",
        )
        if not reply:
            return

        result = unified_data_manager.delete_sessions(session_ids)
        deleted = result.get("deleted_count", 0)
        total = result.get("total", 0)

        if deleted > 0:
            self._msg("info", "删除成功", f"已删除 {deleted} 条会话")
        else:
            source_name = "数据库" if unified_data_manager.database_source.value == "real" else "模拟数据"
            self._msg(
                "warning", "未能删除",
                f"未能删除选中的 {total} 条会话（{deleted}/{total}）。\n"
                f"数据源：{source_name}\n"
                f"可能原因：会话数据尚未持久化或已被清理。"
            )

        # 退出选择模式并刷新列表
        self.data_record_widget.exit_selection_mode()
        self.apply_filter(self.filter_sidebar.get_current_filter())

    @staticmethod
    def _msg(level: str, title: str, text: str):
        """显示不受深色主题影响的提示框"""
        box = QMessageBox()
        box.setWindowTitle(title)
        box.setText(text)
        box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
            QPushButton {{
                color: {COLORS['text']};
                background-color: {COLORS['card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 16px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['card_hover']};
            }}
        """)
        if level == "info":
            box.setIcon(QMessageBox.Information)
        elif level == "warning":
            box.setIcon(QMessageBox.Warning)
        elif level == "critical":
            box.setIcon(QMessageBox.Critical)
        box.exec_()

    @staticmethod
    def _question(title: str, text: str) -> bool:
        """显示确认框，返回 True 表示用户点击 Yes"""
        box = QMessageBox()
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Question)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
            QPushButton {{
                color: {COLORS['text']};
                background-color: {COLORS['card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 16px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['card_hover']};
            }}
        """)
        return box.exec_() == QMessageBox.Yes
