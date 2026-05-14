from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QWidget, QHBoxLayout, QPushButton,
)

from .config import LEFT_BAR_WIDTH
from .styles import COLORS, FONTS, get_style, get_font, get_spacing
from .styles.effects import create_card_shadow


class LeftSideBar(QFrame):
    camera_selected = pyqtSignal(int)
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(LEFT_BAR_WIDTH)
        self.setStyleSheet(get_style("frame_sidebar"))
        self.setGraphicsEffect(create_card_shadow(elevated=True))
        self._cameras = []
        self._current_device_id = 0
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            get_spacing("xl"), get_spacing("xxl"),
            get_spacing("xl"), get_spacing("xxl"),
        )
        layout.setSpacing(get_spacing("xxl"))

        # ---- 摄像头标题栏 ----
        layout.addWidget(self._section_divider())

        title_layout = QHBoxLayout()
        camera_title = QLabel("摄像头列表")
        camera_title.setFont(QFont(*get_font("base", "semibold", "ui")))
        camera_title.setStyleSheet(get_style("label_section_title"))

        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setFont(QFont(*get_font("lg", "normal", "ui")))
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setStyleSheet(get_style("button_refresh"))
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)

        title_layout.addWidget(camera_title)
        title_layout.addStretch()
        title_layout.addWidget(self.refresh_btn)

        self.camera_list = QListWidget()
        self.camera_list.setStyleSheet(get_style("list_widget"))
        self.camera_list.setCursor(Qt.PointingHandCursor)
        self.camera_list.itemClicked.connect(self.on_camera_clicked)
        layout.addLayout(title_layout)
        layout.addWidget(self.camera_list)

        # ---- 人脸列表 ----
        layout.addWidget(self._section_divider())

        face_title = QLabel("当前人脸")
        face_title.setFont(QFont(*get_font("base", "semibold", "ui")))
        face_title.setStyleSheet(get_style("label_section_title"))
        self.face_list = QListWidget()
        self.face_list.setStyleSheet(get_style("list_widget"))
        layout.addWidget(face_title)
        layout.addWidget(self.face_list)
        layout.addStretch()

        # ---- 底部状态栏 ----
        bottom_status = QHBoxLayout()
        self.status_dot = QFrame()
        self.status_dot.setFixedSize(8, 8)
        self.status_dot.setStyleSheet(get_style("dot_success"))
        self.status_text_label = QLabel("可视化显示")
        self.status_text_label.setFont(QFont(*get_font("sm", "normal", "ui")))
        self.status_text_label.setStyleSheet(
            f"color: {COLORS['text_hint']};"
        )
        bottom_status.addWidget(self.status_dot)
        bottom_status.addWidget(self.status_text_label)
        bottom_status.addStretch()
        layout.addLayout(bottom_status)

    def _section_divider(self) -> QFrame:
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(get_style("divider_subtle"))
        return divider

    # ──────────────────── 头像 ────────────────────

    def _make_avatar(self, text: str) -> QFrame:
        avatar = QFrame()
        avatar.setFixedSize(40, 40)
        avatar.setStyleSheet(
            get_style("avatar_gradient") + f"border-radius: 20px;"
        )
        avatar_layout = QVBoxLayout(avatar)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text[0].upper() if text else "?")
        label.setFont(QFont(*get_font("lg", "bold", "ui")))
        label.setStyleSheet(get_style("label_transparent"))
        label.setAlignment(Qt.AlignCenter)
        avatar_layout.addWidget(label)
        return avatar

    # ──────────────────── 摄像头列表 ────────────────────

    def load_cameras(self, cameras):
        self._cameras = cameras
        self.camera_list.clear()

        for camera in cameras:
            item = QListWidgetItem()
            item_widget = QWidget()
            item_widget.setStyleSheet("background: transparent;")
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(
                get_spacing("md"), get_spacing("sm"),
                get_spacing("md"), get_spacing("sm"),
            )

            avatar = self._make_avatar("C")
            name_label = QLabel(camera.device_name)
            name_label.setFont(QFont(*get_font("base", "medium", "ui")))
            name_label.setStyleSheet(f"color: {COLORS['text']};")
            id_label = QLabel(f"ID: {camera.device_id}")
            id_label.setFont(QFont(*get_font("xs", "normal", "data")))
            id_label.setStyleSheet(f"color: {COLORS['text_hint']};")

            item_layout.addWidget(avatar)
            item_layout.addSpacing(get_spacing("md"))
            item_layout.addWidget(name_label)
            item_layout.addStretch()
            item_layout.addWidget(id_label)

            item.setData(Qt.UserRole, camera.device_id)
            self.camera_list.addItem(item)
            self.camera_list.setItemWidget(item, item_widget)

        self._select_camera_by_device_id(self._current_device_id)

    def _select_camera_by_device_id(self, device_id):
        for i in range(self.camera_list.count()):
            item = self.camera_list.item(i)
            if item.data(Qt.UserRole) == device_id:
                self.camera_list.setCurrentRow(i)
                self._current_device_id = device_id
                break

    # ──────────────────── 人脸列表 ────────────────────

    def update_faces(self, faces: list):
        self.face_list.clear()
        for face in faces:
            item = QListWidgetItem()
            item_widget = QWidget()
            item_widget.setStyleSheet("background: transparent;")
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(
                get_spacing("md"), get_spacing("sm"),
                get_spacing("md"), get_spacing("sm"),
            )

            avatar = self._make_avatar(f"F{face.get('face_id', '?')}")
            name_label = QLabel(f"人脸 ID: {face.get('face_id', '?')}")
            name_label.setFont(QFont(*get_font("base", "medium", "ui")))
            name_label.setStyleSheet(f"color: {COLORS['text']};")

            item_layout.addWidget(avatar)
            item_layout.addSpacing(get_spacing("md"))
            item_layout.addWidget(name_label)
            item_layout.addStretch()

            self.face_list.addItem(item)
            self.face_list.setItemWidget(item, item_widget)

    # ──────────────────── 事件 ────────────────────

    def on_camera_clicked(self, item):
        device_id = item.data(Qt.UserRole)
        self._current_device_id = device_id
        self.camera_selected.emit(device_id)
        print(f"[LeftSideBar] 选择摄像头: device_id={device_id}")

    def set_current_device(self, device_id):
        self._current_device_id = device_id
        self._select_camera_by_device_id(device_id)

    def set_status(self, running: bool, text: str = None):
        if running:
            self.status_dot.setStyleSheet(get_style("dot_success"))
            self.status_text_label.setText("运行中" if not text else text)
            self.status_text_label.setStyleSheet(f"color: {COLORS['focus_high']};")
        else:
            self.status_dot.setStyleSheet(get_style("dot_hint"))
            self.status_text_label.setText("已停止" if not text else text)
            self.status_text_label.setStyleSheet(f"color: {COLORS['text_hint']};")

    def get_current_device_id(self) -> int:
        return self._current_device_id
