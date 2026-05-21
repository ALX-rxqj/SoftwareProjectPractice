from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QWidget, QHBoxLayout, QPushButton, QCheckBox, QMenu, QAction,
    QFileDialog,
)

from .config import LEFT_BAR_WIDTH
from .styles import COLORS, FONTS, get_style, get_font, get_spacing
from .styles.effects import create_card_shadow


class LeftSideBar(QFrame):
    camera_selected = pyqtSignal(int)
    refresh_requested = pyqtSignal()
    face_selected = pyqtSignal(str)
    face_delete_requested = pyqtSignal(str)
    show_bbox_toggled = pyqtSignal(bool)
    file_selected = pyqtSignal(str)  # 发射 file_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(LEFT_BAR_WIDTH)
        self.setStyleSheet(get_style("frame_sidebar"))
        self.setGraphicsEffect(create_card_shadow(elevated=True))
        self._cameras = []
        self._current_device_id = 0
        self._faces_data = []
        self._file_path: Optional[str] = None
        self._file_item: Optional[QListWidgetItem] = None
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
        camera_title = QLabel("数据源列表")
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
        self.face_list.setSelectionMode(QListWidget.SingleSelection)
        self.face_list.setCursor(Qt.PointingHandCursor)
        self.face_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.face_list.itemClicked.connect(self._on_face_item_clicked)
        self.face_list.customContextMenuRequested.connect(self._on_face_context_menu)
        layout.addWidget(face_title)
        layout.addWidget(self.face_list)
        layout.addStretch()

        # ---- 底部可视化勾选框 ----
        self.show_bbox_checkbox = QCheckBox("可视化显示")
        self.show_bbox_checkbox.setChecked(False)
        self.show_bbox_checkbox.setCursor(Qt.PointingHandCursor)
        self.show_bbox_checkbox.setFont(QFont(*get_font("sm", "normal", "ui")))
        self.show_bbox_checkbox.setStyleSheet(
            f"color: {COLORS['text_hint']};"
        )
        self.show_bbox_checkbox.toggled.connect(self.show_bbox_toggled.emit)
        layout.addWidget(self.show_bbox_checkbox)

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

        # ── 第一个条目：打开本地文件 ──
        self._file_item = QListWidgetItem()
        file_widget = QWidget()
        file_widget.setStyleSheet("background: transparent;")
        file_layout = QHBoxLayout(file_widget)
        file_layout.setContentsMargins(
            get_spacing("md"), get_spacing("sm"),
            get_spacing("md"), get_spacing("sm"),
        )

        file_avatar = self._make_avatar("F")
        self._file_label = QLabel("📁 打开本地文件...")
        self._file_label.setFont(QFont(*get_font("base", "medium", "ui")))
        self._file_label.setStyleSheet(f"color: {COLORS['text']};")

        file_layout.addWidget(file_avatar)
        file_layout.addSpacing(get_spacing("md"))
        file_layout.addWidget(self._file_label)
        file_layout.addStretch()

        self._file_item.setData(Qt.UserRole, -1)  # device_id=-1 标识文件条目
        self.camera_list.addItem(self._file_item)
        self.camera_list.setItemWidget(self._file_item, file_widget)

        # ── 摄像头条目 ──
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
        """加载注册人脸列表（来自 query_face_registry / database）

        faces: [{"face_id": str, "student_name": str, ...}, ...]
        """
        self._faces_data = list(faces)
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

            student_name = face.get("student_name", face.get("face_id", "?"))
            face_id = face.get("face_id", "?")
            avatar = self._make_avatar(student_name)
            name_label = QLabel(student_name)
            name_label.setFont(QFont(*get_font("base", "medium", "ui")))
            name_label.setStyleSheet(f"color: {COLORS['text']};")
            id_label = QLabel(f"ID: {face_id}")
            id_label.setFont(QFont(*get_font("xs", "normal", "data")))
            id_label.setStyleSheet(f"color: {COLORS['text_hint']};")

            item_layout.addWidget(avatar)
            item_layout.addSpacing(get_spacing("md"))
            item_layout.addWidget(name_label)
            item_layout.addStretch()
            item_layout.addWidget(id_label)

            item.setData(Qt.UserRole, face_id)
            self.face_list.addItem(item)
            self.face_list.setItemWidget(item, item_widget)

        if self.face_list.count() > 0:
            self.face_list.setCurrentRow(0)
            first_id = self.face_list.item(0).data(Qt.UserRole)
            self.face_selected.emit(first_id)

    def get_selected_face_id(self) -> Optional[str]:
        item = self.face_list.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return None

    def set_faces_enabled(self, enabled: bool):
        self.face_list.setEnabled(enabled)

    def has_faces(self) -> bool:
        return self.face_list.count() > 0

    def _on_face_item_clicked(self, item):
        face_id = item.data(Qt.UserRole)
        self.face_list.setCurrentItem(item)
        self.face_selected.emit(face_id)
        print(f"[LeftSideBar] 选择人脸: face_id={face_id}")

    def _on_face_context_menu(self, pos):
        item = self.face_list.itemAt(pos)
        if item is None:
            return
        face_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 32px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['card_hover']};
            }}
        """)
        delete_action = QAction("删除人脸", menu)
        delete_action.triggered.connect(lambda: self.face_delete_requested.emit(face_id))
        menu.addAction(delete_action)
        menu.exec_(self.face_list.mapToGlobal(pos))

    # ──────────────────── 事件 ────────────────────

    def on_camera_clicked(self, item):
        device_id = item.data(Qt.UserRole)

        if device_id == -1:
            # 文件选择条目
            file_path, _ = QFileDialog.getOpenFileName(
                self, "打开本地视频文件", "",
                "所有文件 (*.*)",
            )
            if file_path:
                self._file_path = file_path
                import os
                self._file_label.setText(f"📁 {os.path.basename(file_path)}")
                self.camera_list.clearSelection()
                self._file_item.setSelected(True)
                self._current_device_id = -1
                self.file_selected.emit(file_path)
                print(f"[LeftSideBar] 选择本地文件: {file_path}")
        else:
            # 摄像头条目：清除文件选择
            self._file_path = None
            self._file_label.setText("📁 打开本地文件...")
            self._current_device_id = device_id
            self.camera_selected.emit(device_id)
            print(f"[LeftSideBar] 选择摄像头: device_id={device_id}")

    def set_current_device(self, device_id):
        self._current_device_id = device_id
        self._select_camera_by_device_id(device_id)

    def get_current_device_id(self) -> int:
        return self._current_device_id

    def get_selected_file_path(self) -> Optional[str]:
        return self._file_path
