from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QComboBox, QDateEdit, QPushButton, QHBoxLayout,
    QSpinBox, QCheckBox, QGroupBox, QWidget
)
from datetime import datetime

from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing


class FilterSidebar(QFrame):
    filter_applied = pyqtSignal(dict)
    chart_options_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(SIZES["sidebar"]["width"])
        self.setStyleSheet(get_style("container"))
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            get_spacing("lg"), get_spacing("sm"),
            get_spacing("lg"), get_spacing("lg")
        )
        layout.setSpacing(get_spacing("base"))

        self.title_label = QLabel("📊 筛选条件")
        self.title_label.setFont(QFont(*get_font("lg", "bold")))
        self.title_label.setStyleSheet(get_style("label_title"))
        self.title_label.setFixedHeight(26)
        layout.addWidget(self.title_label)

        self.filter_container = QWidget()
        filter_layout = QVBoxLayout(self.filter_container)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(get_spacing("base"))

        date_widget = self._create_date_section()
        filter_layout.addWidget(date_widget)

        mode_widget = self._create_mode_section()
        filter_layout.addWidget(mode_widget)

        focus_widget = self._create_focus_section()
        filter_layout.addWidget(focus_widget)

        abnormal_widget = self._create_abnormal_section()
        filter_layout.addWidget(abnormal_widget)

        self.apply_btn = QPushButton("🔍 应用筛选")
        self.apply_btn.setFont(QFont(*get_font("base", "bold")))
        self.apply_btn.setFixedHeight(SIZES["button"]["height"])
        self.apply_btn.setStyleSheet(get_style("button_primary"))
        self.apply_btn.clicked.connect(self.on_apply_clicked)
        filter_layout.addWidget(self.apply_btn)

        hint_label = QLabel("设置筛选条件后点击应用")
        hint_label.setFont(QFont(*get_font("xs")))
        hint_label.setStyleSheet(get_style("label_hint"))
        hint_label.setAlignment(Qt.AlignCenter)
        filter_layout.addWidget(hint_label)

        layout.addWidget(self.filter_container)

        self.chart_container = QWidget()
        self._init_chart_container()
        layout.addWidget(self.chart_container)
        self.chart_container.hide()

    def _create_date_section(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_spacing("xs"))

        label = QLabel("📅 日期范围")
        label.setFont(QFont(*get_font("sm")))
        label.setStyleSheet(get_style("label_hint"))
        layout.addWidget(label)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(get_spacing("base"))

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setFont(QFont(*get_font("sm")))
        self.start_date_edit.setStyleSheet(get_style("date_edit"))
        self.start_date_edit.setDate(datetime(2026, 4, 1))

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setFont(QFont(*get_font("sm")))
        self.end_date_edit.setStyleSheet(get_style("date_edit"))
        self.end_date_edit.setDate(datetime(2026, 4, 30))

        h_layout.addWidget(self.start_date_edit)
        h_layout.addWidget(self.end_date_edit)
        layout.addLayout(h_layout)

        return widget

    def _create_mode_section(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_spacing("xs"))

        label = QLabel("🎯 运行模式")
        label.setFont(QFont(*get_font("sm")))
        label.setStyleSheet(get_style("label_hint"))
        layout.addWidget(label)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["全部模式", "网课模式", "考试模式"])
        self.mode_combo.setFont(QFont(*get_font("sm")))
        self.mode_combo.setStyleSheet(get_style("combo_box"))
        self.mode_combo.currentTextChanged.connect(self.on_filter_changed)
        layout.addWidget(self.mode_combo)

        return widget

    def _create_focus_section(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_spacing("xs"))

        label = QLabel("📈 专注度评分")
        label.setFont(QFont(*get_font("sm")))
        label.setStyleSheet(get_style("label_hint"))
        layout.addWidget(label)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(get_spacing("base"))

        min_label = QLabel("最低:")
        min_label.setFont(QFont(*get_font("sm")))
        min_label.setStyleSheet(get_style("label_hint"))

        self.focus_min_spin = QSpinBox()
        self.focus_min_spin.setRange(0, 100)
        self.focus_min_spin.setValue(0)
        self.focus_min_spin.setSuffix(" 分")
        self.focus_min_spin.setFont(QFont(*get_font("sm")))
        self.focus_min_spin.setStyleSheet(get_style("spin_box"))

        max_label = QLabel("最高:")
        max_label.setFont(QFont(*get_font("sm")))
        max_label.setStyleSheet(get_style("label_hint"))

        self.focus_max_spin = QSpinBox()
        self.focus_max_spin.setRange(0, 100)
        self.focus_max_spin.setValue(100)
        self.focus_max_spin.setSuffix(" 分")
        self.focus_max_spin.setFont(QFont(*get_font("sm")))
        self.focus_max_spin.setStyleSheet(get_style("spin_box"))

        h_layout.addWidget(min_label)
        h_layout.addWidget(self.focus_min_spin)
        h_layout.addWidget(max_label)
        h_layout.addWidget(self.focus_max_spin)
        layout.addLayout(h_layout)

        return widget

    def _create_abnormal_section(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_spacing("xs"))

        label = QLabel("⚠️ 异常事件")
        label.setFont(QFont(*get_font("sm")))
        label.setStyleSheet(get_style("label_hint"))
        layout.addWidget(label)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(get_spacing("base"))

        min_label = QLabel("最少:")
        min_label.setFont(QFont(*get_font("sm")))
        min_label.setStyleSheet(get_style("label_hint"))

        self.abnormal_min_spin = QSpinBox()
        self.abnormal_min_spin.setRange(0, 100)
        self.abnormal_min_spin.setValue(0)
        self.abnormal_min_spin.setFont(QFont(*get_font("sm")))
        self.abnormal_min_spin.setStyleSheet(get_style("spin_box"))

        max_label = QLabel("最多:")
        max_label.setFont(QFont(*get_font("sm")))
        max_label.setStyleSheet(get_style("label_hint"))

        self.abnormal_max_spin = QSpinBox()
        self.abnormal_max_spin.setRange(0, 100)
        self.abnormal_max_spin.setValue(100)
        self.abnormal_max_spin.setFont(QFont(*get_font("sm")))
        self.abnormal_max_spin.setStyleSheet(get_style("spin_box"))

        h_layout.addWidget(min_label)
        h_layout.addWidget(self.abnormal_min_spin)
        h_layout.addWidget(max_label)
        h_layout.addWidget(self.abnormal_max_spin)
        layout.addLayout(h_layout)

        return widget

    def _init_chart_container(self):
        chart_layout = QVBoxLayout(self.chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(get_spacing("base"))

        self.chart_options_group = QGroupBox("📊 图表显示选项")
        self.chart_options_group.setStyleSheet(get_style("group_box"))
        self.chart_options_group.setFont(QFont(*get_font("base", "bold")))

        chart_options_layout = QVBoxLayout()
        chart_options_layout.setSpacing(get_spacing("xs"))

        self.show_final_focus = QCheckBox("最终专注度")
        self.show_final_focus.setChecked(True)
        self.show_final_focus.setFont(QFont(*get_font("sm")))
        style = get_style("check_box")
        style += f" QCheckBox::indicator:checked {{background-color: {COLORS['focus_high']};}}"
        self.show_final_focus.setStyleSheet(style)
        self.show_final_focus.stateChanged.connect(self.on_chart_option_changed)

        self.show_head_pose = QCheckBox("头部姿态")
        self.show_head_pose.setChecked(True)
        self.show_head_pose.setFont(QFont(*get_font("sm")))
        style = get_style("check_box")
        style += f" QCheckBox::indicator:checked {{background-color: {COLORS['danger']};}}"
        self.show_head_pose.setStyleSheet(style)
        self.show_head_pose.stateChanged.connect(self.on_chart_option_changed)

        self.show_behavior = QCheckBox("行为动作")
        self.show_behavior.setChecked(True)
        self.show_behavior.setFont(QFont(*get_font("sm")))
        style = get_style("check_box")
        style += f" QCheckBox::indicator:checked {{background-color: {COLORS['warning']};}}"
        self.show_behavior.setStyleSheet(style)
        self.show_behavior.stateChanged.connect(self.on_chart_option_changed)

        self.show_expression = QCheckBox("表情评分")
        self.show_expression.setChecked(False)
        self.show_expression.setFont(QFont(*get_font("sm")))
        style = get_style("check_box")
        style += f" QCheckBox::indicator:checked {{background-color: {COLORS['primary']};}}"
        self.show_expression.setStyleSheet(style)
        self.show_expression.stateChanged.connect(self.on_chart_option_changed)

        self.show_evidence = QCheckBox("证据理论")
        self.show_evidence.setChecked(False)
        self.show_evidence.setFont(QFont(*get_font("sm")))
        style = get_style("check_box")
        style += f" QCheckBox::indicator:checked {{background-color: #4ECDC4;}}"
        self.show_evidence.setStyleSheet(style)
        self.show_evidence.stateChanged.connect(self.on_chart_option_changed)

        self.show_people = QCheckBox("人数项")
        self.show_people.setChecked(False)
        self.show_people.setFont(QFont(*get_font("sm")))
        style = get_style("check_box")
        style += f" QCheckBox::indicator:checked {{background-color: #FF9FF3;}}"
        self.show_people.setStyleSheet(style)
        self.show_people.stateChanged.connect(self.on_chart_option_changed)

        chart_options_layout.addWidget(self.show_final_focus)
        chart_options_layout.addWidget(self.show_head_pose)
        chart_options_layout.addWidget(self.show_behavior)
        chart_options_layout.addWidget(self.show_expression)
        chart_options_layout.addWidget(self.show_evidence)
        chart_options_layout.addWidget(self.show_people)

        self.chart_options_group.setLayout(chart_options_layout)
        chart_layout.addWidget(self.chart_options_group)
        chart_layout.addStretch()

    def on_filter_changed(self):
        pass

    def on_apply_clicked(self):
        filter_params = {
            "start_date": self.start_date_edit.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date_edit.date().toString("yyyy-MM-dd"),
            "mode": self.mode_combo.currentText() if self.mode_combo.currentText() != "全部模式" else None,
            "focus_min": self.focus_min_spin.value(),
            "focus_max": self.focus_max_spin.value(),
            "abnormal_min": self.abnormal_min_spin.value(),
            "abnormal_max": self.abnormal_max_spin.value()
        }
        print(f"[FilterSidebar] 应用筛选条件: {filter_params}")
        self.filter_applied.emit(filter_params)

    def get_current_filter(self):
        return {
            "start_date": self.start_date_edit.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date_edit.date().toString("yyyy-MM-dd"),
            "mode": self.mode_combo.currentText() if self.mode_combo.currentText() != "全部模式" else None,
            "focus_min": self.focus_min_spin.value(),
            "focus_max": self.focus_max_spin.value(),
            "abnormal_min": self.abnormal_min_spin.value(),
            "abnormal_max": self.abnormal_max_spin.value()
        }

    def get_chart_options(self):
        return {
            "final_focus": self.show_final_focus.isChecked(),
            "head_pose": self.show_head_pose.isChecked(),
            "behavior": self.show_behavior.isChecked(),
            "expression": self.show_expression.isChecked(),
            "evidence": self.show_evidence.isChecked(),
            "people": self.show_people.isChecked()
        }

    def on_chart_option_changed(self):
        chart_options = self.get_chart_options()
        self.chart_options_changed.emit(chart_options)

    def show_filter_mode(self):
        self.title_label.setText("📊 筛选条件")
        self.filter_container.show()
        self.chart_container.hide()

    def show_chart_mode(self):
        self.title_label.setText("📈 图表选项")
        self.filter_container.hide()
        self.chart_container.show()
