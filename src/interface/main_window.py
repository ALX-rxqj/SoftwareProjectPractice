from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedLayout, QSplitter, QMenu, QFileDialog, QMessageBox

from .config import WINDOW_WIDTH, WINDOW_HEIGHT, TOP_NAV_HEIGHT, LEFT_BAR_WIDTH, RIGHT_PANEL_WIDTH
from .styles import get_style, get_spacing
from .top_nav_bar import TopNavBar
from .left_sidebar import LeftSideBar
from .video_widget import VideoWidget
from .right_panel import RightPanel
from .filter_sidebar import FilterSidebar
from .data_record_widget import DataRecordWidget
from .session_detail_widget import SessionDetailWidget
from .interface_manager import interface_manager
from .unified_data_manager import unified_data_manager, CameraInfo
from .face_registration_dialog import FaceRegistrationDialog
from .alert_info_dialog import AlertInfoDialog
from .export_report_util import export_to_excel, export_to_pdf


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("网课专注度分析系统")
        self.setMinimumSize(1280, 720)
        self.showMaximized()
        self.setStyleSheet(get_style("main_window"))
        self.current_mode = "class"
        self.current_face_id = None
        self.current_device_id = 0
        self.init_ui()
        self._setup_interface_manager()
        self.connect_signals()
        self.init_data()

    def _setup_interface_manager(self):
        """配置接口管理器，连接预处理模块和状态估计模块"""

        # 数据库必须在任何模块初始化之前就绪
        if not unified_data_manager.initialize_database():
            print("[MainWindow] 警告: 数据库初始化失败，历史数据功能不可用")

        if unified_data_manager.initialize_real_backend():
            print("[MainWindow] 已连接真实预处理后端")
        else:
            print("[MainWindow] 使用模拟数据模式（预处理模块不可用）")
            interface_manager.set_preprocessing_callback(
                lambda cmd, params: print(
                    f"[MainWindow] 预处理指令(MOCK): {cmd}, params: {params}"
                ) or {"success": True, "msg": "mock"}
            )

        if unified_data_manager.initialize_state_estimation_backend():
            print("[MainWindow] 已连接真实状态估计后端")
        else:
            print("[MainWindow] 使用模拟数据模式（状态估计模块不可用）")
            interface_manager.set_state_estimation_callback(
                lambda cmd, params: print(
                    f"[MainWindow] 状态估计指令(MOCK): {cmd}, params: {params}"
                ) or {"success": True, "msg": "mock"}
            )

        unified_data_manager.register_camera_list_callback(self.on_camera_list_received)

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
        self.filter_sidebar.setMinimumWidth(280)
        self.filter_sidebar.setMaximumWidth(400)

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
        self.filter_sidebar.filter_applied.connect(self.on_filter_applied)
        self.filter_sidebar.chart_options_changed.connect(self.on_chart_options_changed)
        self.data_record_widget.session_selected.connect(self.on_session_clicked)
        self.data_record_widget.delete_requested.connect(self.on_delete_sessions)
        self.session_detail_widget.back_pressed.connect(self.on_back_to_sessions)
        self.session_detail_widget.alert_info_clicked.connect(self.on_alert_info_clicked)
        self.session_detail_widget.export_report_clicked.connect(self.on_export_report_clicked)
        self.left_sidebar.camera_selected.connect(self.on_camera_selected)
        self.left_sidebar.refresh_requested.connect(self.on_refresh_camera_list)
        self.video_widget.frame_updated.connect(self.on_video_frame_updated)
        self.top_nav.register_face_clicked.connect(self.on_register_face_clicked)
        self.top_nav_query.register_face_clicked.connect(self.on_register_face_clicked)

    def init_data(self):
        """通过统一数据管理器获取初始数据（各模块独立数据源）"""
        print(f"[MainWindow] 预处理模块数据源: {unified_data_manager.preprocessing_source.value}")
        print(f"[MainWindow] 状态估计模块数据源: {unified_data_manager.state_estimation_source.value}")
        print(f"[MainWindow] 数据库模块数据源: {unified_data_manager.database_source.value}")
        print(f"[MainWindow] 初始化学生列表...")
        self.face_ids = unified_data_manager.generate_face_ids()
        print(f"[MainWindow] 获取到 {len(self.face_ids)} 个学生")

        print(f"[MainWindow] 请求摄像头列表...")
        unified_data_manager.request_camera_list()

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
            result = interface_manager.switch_mode(mode)
            print(f"[MainWindow] 切换模式: {mode}, 结果: {result}")

    def switch_to_monitoring_mode(self, mode):
        self.main_stacked_layout.setCurrentIndex(0)
        self.top_nav.set_mode(mode)
        self.top_nav_query.set_mode(mode)

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

    def on_start_analysis(self):
        print("[MainWindow] 开始分析")
        result = interface_manager.toggle_capture(device_id=self.current_device_id, start=True)
        print(f"[MainWindow] 摄像头控制结果: {result}")

        session_result = interface_manager.toggle_analysis(start=True)
        if session_result and "session_id" in session_result:
            print(f"[MainWindow] 创建会话成功: {session_result['session_id']}")

        interface_manager.switch_mode(self.current_mode)

        self.video_widget.start_processing()
        self.top_nav.set_recording(True)
        self.top_nav_query.set_recording(True)
        self.top_nav.set_mode_buttons_enabled(False)
        self.top_nav_query.set_mode_buttons_enabled(False)

    def on_stop_analysis(self):
        print("[MainWindow] 停止分析")
        self.video_widget.stop_processing()

        result = interface_manager.toggle_capture(device_id=self.current_device_id, start=False)
        print(f"[MainWindow] 摄像头控制结果: {result}")

        session_result = interface_manager.toggle_analysis(start=False)
        if session_result and "session_id" in session_result:
            print(f"[MainWindow] 结束会话成功: {session_result['session_id']}")

        self.top_nav.set_recording(False)
        self.top_nav_query.set_recording(False)
        self.top_nav.set_mode_buttons_enabled(True)
        self.top_nav_query.set_mode_buttons_enabled(True)

    def on_camera_selected(self, device_id: int):
        """用户选择摄像头"""
        print(f"[MainWindow] 用户选择摄像头: {device_id}")
        self.current_device_id = device_id

    def on_refresh_camera_list(self):
        """刷新摄像头列表"""
        print("[MainWindow] 手动刷新摄像头列表")
        unified_data_manager.refresh_camera_list()

    def on_video_frame_updated(self, frame_data):
        """视频帧更新时，同步更新左侧人脸列表"""
        faces = frame_data.get("faces", [])
        if faces:
            self.left_sidebar.update_faces(faces)

    def on_register_face_clicked(self):
        """注册人脸按钮点击"""
        if interface_manager.is_capture_running:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "提示",
                '正在分析中，请先点击"停止分析"后再注册人脸。'
            )
            return

        print("[MainWindow] 打开人脸注册弹窗")
        dialog = FaceRegistrationDialog(
            device_id=self.current_device_id, parent=self
        )
        dialog.registration_completed.connect(self.on_face_registration_completed)
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

        result = interface_manager.register_face(name, frames, storage_type)
        print(f"[MainWindow] register_face 结果: {result}")

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
        menu.setStyleSheet("""
            QMenu {
                background-color: #262650;
                color: #FFFFFF;
                border: 1px solid #3A3A60;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 32px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #7A5CFF;
            }
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
        reply = QMessageBox.question(
            None, "确认删除",
            f"确定删除选中的 {count} 条会话及其关联数据吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
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
        box.setStyleSheet("""
            QMessageBox {
                background-color: #FFFFFF;
                color: #000000;
            }
            QLabel {
                color: #000000;
            }
            QPushButton {
                color: #000000;
                background-color: #E0E0E0;
                border: 1px solid #AAAAAA;
                border-radius: 4px;
                padding: 6px 16px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
        """)
        if level == "info":
            box.setIcon(QMessageBox.Information)
        elif level == "warning":
            box.setIcon(QMessageBox.Warning)
        elif level == "critical":
            box.setIcon(QMessageBox.Critical)
        box.exec_()
