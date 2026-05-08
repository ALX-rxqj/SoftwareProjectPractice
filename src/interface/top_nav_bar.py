from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QButtonGroup, QVBoxLayout

from .config import TOP_NAV_HEIGHT
from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing


class TopNavBar(QFrame):
    mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(TOP_NAV_HEIGHT)
        self.setStyleSheet(get_style("frame_sidebar"))
        self._current_mode = "网课模式"
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(get_spacing("xxl"), get_spacing("base"), get_spacing("xxl"), get_spacing("base"))
        layout.setSpacing(get_spacing("xxl"))

        logo_label = QLabel("📌")
        logo_label.setFont(QFont(*get_font("xxl")))
        title_layout = QVBoxLayout()
        title_label = QLabel("2026网课专注度分析系统")
        title_label.setFont(QFont(*get_font("xl", "bold")))
        title_label.setStyleSheet(f"color: {COLORS['text']};")
        self.sub_title = QLabel("网课模式")
        self.sub_title.setFont(QFont(*get_font("sm")))
        self.sub_title.setStyleSheet(f"color: {COLORS['text_hint']};")
        title_layout.addWidget(title_label)
        title_layout.addWidget(self.sub_title)
        layout.addWidget(logo_label)
        layout.addLayout(title_layout)
        layout.addStretch()

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        mode_names = ["网课模式", "考试模式", "数据查询"]
        for idx, name in enumerate(mode_names):
            btn = QPushButton(name)
            btn.setFixedSize(160, 36)
            btn.setFont(QFont(*get_font("md")))
            btn.setCheckable(True)
            btn.setStyleSheet(get_style("mode_button"))
            self.mode_group.addButton(btn, idx)
            layout.addWidget(btn)
        self.mode_group.button(0).setChecked(True)
        self.mode_group.buttonClicked.connect(self.on_mode_click)
        layout.addStretch()

        self.record_layout = QHBoxLayout()
        self.record_dot = QLabel("●")
        self.record_dot.setStyleSheet(f"color: {COLORS['focus_high']}; font-size: {FONTS['size']['md']}px;")
        self.record_label = QLabel("录制中")
        self.record_label.setFont(QFont(*get_font("md")))
        self.record_label.setStyleSheet(f"color: {COLORS['text']};")
        self.record_layout.addWidget(self.record_dot)
        self.record_layout.addWidget(self.record_label)
        self.record_frame = QFrame()
        self.record_frame.setLayout(self.record_layout)
        self.record_frame.setStyleSheet(f"background-color: {COLORS['card']}; border-radius: {SIZES['radius']['xl']}px; padding: {SIZES['spacing']['sm']}px {SIZES['spacing']['lg']}px;")
        self.record_frame.setFixedHeight(30)
        layout.addWidget(self.record_frame)

    def on_mode_click(self, btn):
        self._current_mode = btn.text()
        self.mode_changed.emit(btn.text())

    def set_mode(self, mode):
        self._current_mode = mode
        for i in range(self.mode_group.buttons().__len__()):
            btn = self.mode_group.button(i)
            if btn.text() == mode:
                btn.setChecked(True)
                break
        self.sub_title.setText(mode)
        if mode == "数据查询":
            self.record_frame.hide()
        else:
            self.record_frame.show()

    def get_mode(self):
        return self._current_mode

    def set_recording(self, is_recording):
        if is_recording:
            self.record_dot.setStyleSheet("color: #FF4444; font-size: 14px;")
            self.record_label.setText("录制中")
        else:
            self.record_dot.setStyleSheet("color: #00E080; font-size: 14px;")
            self.record_label.setText("未录制")
