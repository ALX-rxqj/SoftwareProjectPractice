from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QButtonGroup, QVBoxLayout,
    QSizePolicy,
)

from .config import TOP_NAV_HEIGHT
from .styles import COLORS, FONTS, get_style, get_font, get_spacing


class TopNavBar(QFrame):
    mode_changed = pyqtSignal(str)
    register_face_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(TOP_NAV_HEIGHT)
        self.setStyleSheet(get_style("nav_bar_gradient"))
        self._current_mode = "class"
        self._mode_display_map = {"网课模式": "class", "考试模式": "exam", "数据查询": "数据查询"}
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            get_spacing("xxl"), get_spacing("base"),
            get_spacing("xxl"), get_spacing("base"),
        )
        layout.setSpacing(get_spacing("xxl"))

        # ---- Logo: 渐变色圆点 ----
        logo_dot = QFrame()
        logo_dot.setFixedSize(36, 36)
        logo_dot.setStyleSheet(
            get_style("avatar_gradient") + f"border-radius: 18px;"
        )

        # ---- 标题区域 ----
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title_label = QLabel('<span style="color:#7A5CFF;">网课</span>专注度分析系统')
        title_label.setFont(QFont(*get_font("title", "extrabold", "display")))
        title_label.setStyleSheet(f"color: {COLORS['text']};")
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.sub_title = QLabel("网课模式")  # 初始显示
        self.sub_title.setFont(QFont(*get_font("sm", "normal", "ui")))
        self.sub_title.setStyleSheet(get_style("label_secondary"))
        title_layout.addWidget(title_label)
        title_layout.addWidget(self.sub_title)

        layout.addWidget(logo_dot)
        layout.addSpacing(get_spacing("md"))
        layout.addLayout(title_layout)
        layout.addStretch()

        # ---- 模式按钮组 ----
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        mode_names = ["网课模式", "考试模式", "数据查询"]
        for idx, name in enumerate(mode_names):
            btn = QPushButton(name)
            btn.setFixedSize(140, 34)
            btn.setFont(QFont(*get_font("base", "medium", "ui")))
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(get_style("mode_button_enhanced"))
            self.mode_group.addButton(btn, idx)
            layout.addWidget(btn)
        self.mode_group.button(0).setChecked(True)
        self.mode_group.buttonClicked.connect(self.on_mode_click)
        layout.addStretch()

        # ---- 录制指示器 ----
        self.record_frame = QFrame()
        self.record_frame.setStyleSheet(get_style("badge_danger"))
        self.record_frame.setFixedHeight(40)
        self.record_frame.setMinimumWidth(100)
        record_layout = QHBoxLayout(self.record_frame)
        record_layout.setContentsMargins(12, 0, 12, 0)
        record_layout.setSpacing(6)

        self.record_dot = QFrame()
        self.record_dot.setFixedSize(8, 8)
        self.record_dot.setStyleSheet(get_style("dot_danger"))
        self.record_label = QLabel("未录制")
        self.record_label.setFont(QFont(*get_font("sm", "normal", "ui")))
        self.record_label.setStyleSheet(
            f"color: {COLORS['danger']}; background: transparent;"
        )
        record_layout.addWidget(self.record_dot)
        record_layout.addWidget(self.record_label)
        layout.addWidget(self.record_frame)

        # ---- 注册人脸按钮 ----
        self.btn_register_face = QPushButton("注册人脸")
        self.btn_register_face.setFixedSize(90, 40)
        self.btn_register_face.setFont(QFont(*get_font("sm", "bold", "ui")))
        self.btn_register_face.setCursor(Qt.PointingHandCursor)
        self.btn_register_face.setStyleSheet(get_style("register_face_button"))
        self.btn_register_face.clicked.connect(self.register_face_clicked.emit)
        layout.addWidget(self.btn_register_face)

    def on_mode_click(self, btn):
        display_text = btn.text()
        self._current_mode = self._mode_display_map.get(display_text, display_text)
        self.mode_changed.emit(self._current_mode)

    def set_mode(self, mode):
        self._current_mode = mode
        # 反向映射：English → 中文展示
        display_map = {"class": "网课模式", "exam": "考试模式", "数据查询": "数据查询"}
        display_text = display_map.get(mode, mode)
        for i in range(self.mode_group.buttons().__len__()):
            btn = self.mode_group.button(i)
            if self._mode_display_map.get(btn.text()) == mode:
                btn.setChecked(True)
                break
        self.sub_title.setText(display_text)
        if mode == "数据查询":
            self.record_dot.setStyleSheet(get_style("dot_hint"))
            self.record_label.setText("数据表")
            self.record_label.setStyleSheet(
                f"color: {COLORS['text_hint']}; background: transparent;"
            )
            self.record_frame.setStyleSheet(get_style("badge"))
        else:
            self.record_dot.setStyleSheet(get_style("dot_danger"))
            self.record_label.setText("未录制")
            self.record_label.setStyleSheet(
                f"color: {COLORS['danger']}; background: transparent;"
            )
            self.record_frame.setStyleSheet(get_style("badge_danger"))

    def get_mode(self):
        return self._current_mode

    def set_recording(self, is_recording):
        if is_recording:
            self.record_dot.setStyleSheet(get_style("dot_danger"))
            self.record_label.setText("录制中")
            self.record_label.setStyleSheet(
                f"color: {COLORS['danger']}; background: transparent;"
            )
            self.record_frame.setStyleSheet(get_style("badge_danger"))
        else:
            self.record_dot.setStyleSheet(get_style("dot_success"))
            self.record_label.setText("未录制")
            self.record_label.setStyleSheet(
                f"color: {COLORS['focus_high']}; background: transparent;"
            )
            self.record_frame.setStyleSheet(get_style("badge_success"))

    def set_mode_buttons_enabled(self, enabled: bool):
        for i in range(self.mode_group.buttons().__len__()):
            self.mode_group.button(i).setEnabled(enabled)
