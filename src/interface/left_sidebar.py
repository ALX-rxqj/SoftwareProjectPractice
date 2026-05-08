from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QWidget, QHBoxLayout
)

from .config import LEFT_BAR_WIDTH
from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing


class LeftSideBar(QFrame):
    camera_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(LEFT_BAR_WIDTH)
        self.setStyleSheet(get_style("frame_sidebar"))
        self._cameras = []
        self._current_device_id = 0
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(get_spacing("xl"), get_spacing("xxl"), get_spacing("xl"), get_spacing("xxl"))
        layout.setSpacing(get_spacing("xxl"))

        camera_title = QLabel("摄像头列表")
        camera_title.setFont(QFont(*get_font("md")))
        camera_title.setStyleSheet(f"color: {COLORS['text_hint']}; padding-left: {SIZES['spacing']['md']}px;")

        self.refresh_btn = QLabel("🔄")
        self.refresh_btn.setFont(QFont(*get_font("md")))
        self.refresh_btn.setStyleSheet(f"color: {COLORS['text_hint']}; padding-right: {SIZES['spacing']['md']}px;")
        self.refresh_btn.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)

        title_layout = QHBoxLayout()
        title_layout.addWidget(camera_title)
        title_layout.addStretch()
        title_layout.addWidget(self.refresh_btn)

        self.camera_list = QListWidget()
        self.camera_list.setStyleSheet(get_style("list_widget"))
        self.camera_list.itemClicked.connect(self.on_camera_clicked)
        layout.addLayout(title_layout)
        layout.addWidget(self.camera_list)

        face_title = QLabel("当前人脸")
        face_title.setFont(QFont(*get_font("md")))
        face_title.setStyleSheet(f"color: {COLORS['text_hint']}; padding-left: {SIZES['spacing']['md']}px;")
        self.face_list = QListWidget()
        self.face_list.setStyleSheet(get_style("list_widget"))
        face_data = {"name": "人脸id", "no": "NO.009", "avatar": "👤", "warn": True}
        item = QListWidgetItem()
        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(get_spacing("lg"), get_spacing("sm"), get_spacing("lg"), get_spacing("sm"))
        avatar_label = QLabel(face_data["avatar"])
        avatar_label.setFont(QFont(*get_font("xxl")))
        name_label = QLabel(face_data["name"])
        name_label.setFont(QFont(*get_font("md", "medium")))
        name_label.setStyleSheet(f"color: {COLORS['text']};")
        no_label = QLabel(face_data["no"])
        no_label.setFont(QFont(*get_font("sm")))
        no_label.setStyleSheet(f"color: {COLORS['text_hint']};")
        warn_label = QLabel("🚨")
        arrow_label = QLabel(">")
        arrow_label.setStyleSheet(f"color: {COLORS['text_hint']};")
        item_layout.addWidget(avatar_label)
        item_layout.addWidget(name_label)
        item_layout.addStretch()
        item_layout.addWidget(no_label)
        if face_data["warn"]:
            item_layout.addWidget(warn_label)
        item_layout.addWidget(arrow_label)
        self.face_list.addItem(item)
        self.face_list.setItemWidget(item, item_widget)
        self.face_list.setCurrentRow(0)

        layout.addWidget(face_title)
        layout.addWidget(self.face_list)
        layout.addStretch()

        bottom_status = QHBoxLayout()
        self.check_label = QLabel("✅")
        self.status_text_label = QLabel("可视化显示")
        self.status_text_label.setStyleSheet(f"color: {COLORS['text_hint']}; font-size: {FONTS['size']['md']}px;")
        bottom_status.addWidget(self.check_label)
        bottom_status.addWidget(self.status_text_label)
        bottom_status.addStretch()
        layout.addLayout(bottom_status)

    def load_cameras(self, cameras):
        """
        加载摄像头列表

        Args:
            cameras: list of CameraInfo {device_id: int, device_name: str}
        """
        self._cameras = cameras
        self.camera_list.clear()

        for camera in cameras:
            item = QListWidgetItem()
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(get_spacing("lg"), get_spacing("sm"), get_spacing("lg"), get_spacing("sm"))

            avatar_label = QLabel("📷")
            avatar_label.setFont(QFont(*get_font("xxl")))
            name_label = QLabel(camera.device_name)
            name_label.setFont(QFont(*get_font("md", "medium")))
            name_label.setStyleSheet(f"color: {COLORS['text']};")
            device_id_label = QLabel(f"ID:{camera.device_id}")
            device_id_label.setFont(QFont(*get_font("sm")))
            device_id_label.setStyleSheet(f"color: {COLORS['text_hint']};")
            arrow_label = QLabel(">")
            arrow_label.setStyleSheet(f"color: {COLORS['text_hint']};")

            item_layout.addWidget(avatar_label)
            item_layout.addWidget(name_label)
            item_layout.addStretch()
            item_layout.addWidget(device_id_label)
            item_layout.addWidget(arrow_label)

            item.setData(Qt.UserRole, camera.device_id)
            self.camera_list.addItem(item)
            self.camera_list.setItemWidget(item, item_widget)

        self._select_camera_by_device_id(self._current_device_id)

    def _select_camera_by_device_id(self, device_id):
        """根据设备ID选中摄像头"""
        for i in range(self.camera_list.count()):
            item = self.camera_list.item(i)
            if item.data(Qt.UserRole) == device_id:
                self.camera_list.setCurrentRow(i)
                self._current_device_id = device_id
                self._update_camera_item_style(i, True)
                break

    def _update_camera_item_style(self, row, selected):
        """更新摄像头项的样式"""
        pass

    def on_camera_clicked(self, item):
        """摄像头列表项被点击"""
        device_id = item.data(Qt.UserRole)
        self._current_device_id = device_id
        self.camera_selected.emit(device_id)
        print(f"[LeftSideBar] 选择摄像头: device_id={device_id}")

    def set_current_device(self, device_id):
        """设置当前选中的摄像头"""
        self._current_device_id = device_id
        self._select_camera_by_device_id(device_id)

    def set_status(self, running: bool, text: str = None):
        """设置状态显示"""
        if running:
            self.check_label.setText("✅")
            self.status_text_label.setText("运行中" if not text else text)
            self.status_text_label.setStyleSheet("color: #00E0A0; font-size: 12px;")
        else:
            self.check_label.setText("⏸️")
            self.status_text_label.setText("已停止" if not text else text)
            self.status_text_label.setStyleSheet("color: #AAAAAA; font-size: 12px;")

    def get_current_device_id(self) -> int:
        """获取当前选中的摄像头ID"""
        return self._current_device_id
