from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedLayout, QSplitter

from .config import WINDOW_WIDTH, WINDOW_HEIGHT, TOP_NAV_HEIGHT, LEFT_BAR_WIDTH, RIGHT_PANEL_WIDTH
from .top_nav_bar import TopNavBar
from .left_sidebar import LeftSideBar
from .video_widget import VideoWidget
from .right_panel import RightPanel
from .face_list_widget import FaceListWidget
from .data_record_widget import DataRecordWidget
from .interface_manager import interface_manager
from .unified_data_manager import unified_data_manager, CameraInfo


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("2026网课专注度分析系统")
        self.setMinimumSize(1280, 720)
        self.showMaximized()
        self.setStyleSheet("background-color: #0F0F25;")
        self.current_mode = "网课模式"
        self.current_face_id = None
        self.current_device_id = 0
        self.init_ui()
        self._setup_interface_manager()
        self.connect_signals()
        self.init_data()

    def _setup_interface_manager(self):
        """配置接口管理器，设置预处理和状态估计模块的回调"""
        def preprocessing_handler(command: str, params: dict):
            print(f"[MainWindow] 预处理指令: {command}, params: {params}")
            if command == "toggle_capture":
                device_id = params.get("device_id", 0)
                start = params.get("start", False)
                print(f"[MainWindow] -> {'启动' if start else '停止'}摄像头 {device_id}")
                self.left_sidebar.set_status(start, f"摄像头 {device_id}")
                return {"success": True, "msg": "ok"}
            elif command == "load_video":
                print(f"[MainWindow] -> 加载视频: {params.get('file_path')}")
                return {"success": True, "msg": "ok"}
            return None

        def state_estimation_handler(command: str, params: dict):
            print(f"[MainWindow] 状态估计指令: {command}, params: {params}")
            if command == "query_cameras":
                print(f"[MainWindow] -> 查询摄像头列表")
                cameras = unified_data_manager.request_camera_list()
                return {"success": True, "cameras": cameras}
            elif command == "start_session":
                print(f"[MainWindow] -> 创建会话: {params.get('session_id')}")
                return {"success": True}
            elif command == "stop_session":
                print(f"[MainWindow] -> 结束会话: {params.get('session_id')}")
                return {"success": True}
            elif command == "switch_mode":
                print(f"[MainWindow] -> 切换模式: {params.get('mode')}")
                return {"success": True}
            elif command == "update_threshold":
                print(f"[MainWindow] -> 更新阈值: {params.get('threshold')}")
                return {"success": True}
            return None

        interface_manager.set_preprocessing_callback(preprocessing_handler)
        interface_manager.set_state_estimation_callback(state_estimation_handler)

        unified_data_manager.register_camera_list_callback(self.on_camera_list_received)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.stacked_layout = QStackedLayout(central_widget)
        self.stacked_layout.setContentsMargins(16, 16, 16, 16)

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

        self.face_list_widget = FaceListWidget()
        self.face_list_widget.setMinimumWidth(280)
        self.face_list_widget.setMaximumWidth(400)

        self.data_record_widget = DataRecordWidget()
        self.data_record_widget.setMinimumWidth(RIGHT_PANEL_WIDTH)

        monitoring_widget = QWidget()
        monitoring_layout = QVBoxLayout(monitoring_widget)
        monitoring_layout.setContentsMargins(0, 0, 0, 0)
        monitoring_layout.setSpacing(16)

        horizontal_splitter = QSplitter(Qt.Horizontal)
        horizontal_splitter.addWidget(self.left_sidebar)
        horizontal_splitter.addWidget(self.video_widget)
        horizontal_splitter.addWidget(self.right_panel)
        horizontal_splitter.setStretchFactor(1, 1)
        horizontal_splitter.setHandleWidth(8)
        horizontal_splitter.setChildrenCollapsible(False)
        horizontal_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #2D2D5A;
                border-radius: 4px;
            }
            QSplitter::handle:hover {
                background-color: #41418A;
            }
            QSplitter::handle:pressed {
                background-color: #6666CC;
            }
        """)
        horizontal_splitter.setSizes([LEFT_BAR_WIDTH, 560, RIGHT_PANEL_WIDTH])

        vertical_splitter = QSplitter(Qt.Vertical)
        vertical_splitter.addWidget(self.top_nav)
        vertical_splitter.addWidget(horizontal_splitter)
        vertical_splitter.setStretchFactor(1, 1)
        vertical_splitter.setHandleWidth(8)
        vertical_splitter.setChildrenCollapsible(False)
        vertical_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #2D2D5A;
                border-radius: 4px;
            }
            QSplitter::handle:hover {
                background-color: #41418A;
            }
            QSplitter::handle:pressed {
                background-color: #6666CC;
            }
        """)
        vertical_splitter.setSizes([TOP_NAV_HEIGHT, 550])

        monitoring_layout.addWidget(vertical_splitter)

        query_widget = QWidget()
        query_layout = QVBoxLayout(query_widget)
        query_layout.setContentsMargins(0, 0, 0, 0)
        query_layout.setSpacing(16)

        query_vertical_splitter = QSplitter(Qt.Vertical)
        query_vertical_splitter.addWidget(self.top_nav_query)

        query_horizontal_splitter = QSplitter(Qt.Horizontal)
        query_horizontal_splitter.addWidget(self.face_list_widget)
        query_horizontal_splitter.addWidget(self.data_record_widget)
        query_horizontal_splitter.setStretchFactor(1, 2)
        query_horizontal_splitter.setHandleWidth(8)
        query_horizontal_splitter.setChildrenCollapsible(False)
        query_horizontal_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #2D2D5A;
                border-radius: 4px;
            }
            QSplitter::handle:hover {
                background-color: #41418A;
            }
            QSplitter::handle:pressed {
                background-color: #6666CC;
            }
        """)
        query_horizontal_splitter.setSizes([280, 800])

        query_vertical_splitter.addWidget(query_horizontal_splitter)
        query_vertical_splitter.setStretchFactor(1, 1)
        query_vertical_splitter.setHandleWidth(8)
        query_vertical_splitter.setChildrenCollapsible(False)
        query_vertical_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #2D2D5A;
                border-radius: 4px;
            }
            QSplitter::handle:hover {
                background-color: #41418A;
            }
            QSplitter::handle:pressed {
                background-color: #6666CC;
            }
        """)
        query_vertical_splitter.setSizes([TOP_NAV_HEIGHT, 550])

        query_layout.addWidget(query_vertical_splitter)

        self.stacked_layout.addWidget(monitoring_widget)
        self.stacked_layout.addWidget(query_widget)
        self.stacked_layout.setCurrentIndex(0)

    def connect_signals(self):
        self.top_nav.mode_changed.connect(self.on_mode_changed)
        self.top_nav_query.mode_changed.connect(self.on_mode_changed)
        self.right_panel.start_analysis.connect(self.on_start_analysis)
        self.right_panel.stop_analysis.connect(self.on_stop_analysis)
        self.face_list_widget.face_selected.connect(self.on_face_selected)
        self.data_record_widget.record_deleted.connect(self.on_record_deleted)
        self.left_sidebar.camera_selected.connect(self.on_camera_selected)

    def init_data(self):
        """通过统一数据管理器获取初始数据（根据data_source决定来源）"""
        print(f"[MainWindow] 数据来源: {unified_data_manager.data_source.value}")
        print(f"[MainWindow] 初始化学生列表...")
        self.face_ids = unified_data_manager.generate_face_ids()
        print(f"[MainWindow] 获取到 {len(self.face_ids)} 个学生")

        print(f"[MainWindow] 请求摄像头列表...")
        unified_data_manager.request_camera_list()

    def on_camera_list_received(self, cameras):
        """摄像头列表回调"""
        print(f"[MainWindow] 收到摄像头列表: {len(cameras)} 个摄像头")
        self.left_sidebar.load_cameras(cameras)
        if cameras:
            self.current_device_id = cameras[0].device_id
            print(f"[MainWindow] 默认选中摄像头: device_id={self.current_device_id}")

    def on_camera_selected(self, device_id):
        """摄像头选择回调"""
        self.current_device_id = device_id
        print(f"[MainWindow] 用户选择摄像头: device_id={device_id}")

    def on_mode_changed(self, mode):
        self.current_mode = mode

        self.top_nav.set_mode(mode)
        self.top_nav_query.set_mode(mode)

        if mode == "数据查询":
            self.switch_to_query_mode()
        else:
            self.switch_to_monitoring_mode(mode)
            mode_str = "class" if mode == "网课模式" else "exam"
            result = interface_manager.switch_mode(mode_str)
            print(f"[MainWindow] 切换模式: {mode_str}, 结果: {result}")

    def switch_to_query_mode(self):
        self.face_list_widget.load_face_ids(self.face_ids)
        self.stacked_layout.setCurrentIndex(1)
        self.top_nav.set_mode("数据查询")
        self.top_nav_query.set_mode("数据查询")

    def switch_to_monitoring_mode(self, mode):
        self.stacked_layout.setCurrentIndex(0)
        self.top_nav.set_mode(mode)
        self.top_nav_query.set_mode(mode)

    def on_face_selected(self, face_id):
        self.current_face_id = face_id
        records = unified_data_manager.generate_records(face_id)
        print(f"[MainWindow] 获取学生 {face_id} 的记录: {len(records)} 条")
        self.data_record_widget.load_records(face_id, records)

    def on_record_deleted(self, face_id, record):
        print(f"[MainWindow] 删除记录: {face_id} - {record.get('session_id')}")

    def on_start_analysis(self):
        print("[MainWindow] 开始分析")
        result = interface_manager.toggle_capture(device_id=self.current_device_id, start=True)
        print(f"[MainWindow] 摄像头控制结果: {result}")

        session_result = interface_manager.toggle_analysis(start=True)
        if session_result and "session_id" in session_result:
            print(f"[MainWindow] 创建会话成功: {session_result['session_id']}")

        mode_str = "class" if self.current_mode == "网课模式" else "exam"
        interface_manager.switch_mode(mode_str)

        self.video_widget.start_processing()

    def on_stop_analysis(self):
        print("[MainWindow] 停止分析")
        result = interface_manager.toggle_analysis(start=False)
        print(f"[MainWindow] 分析停止结果: {result}")

        interface_manager.toggle_capture(device_id=self.current_device_id, start=False)
        self.video_widget.stop_processing()
