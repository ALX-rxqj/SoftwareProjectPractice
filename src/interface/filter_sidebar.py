from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QComboBox, QDateEdit, QPushButton, QHBoxLayout,
    QSpinBox, QCheckBox, QGroupBox, QWidget,
)
from datetime import datetime

from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing
from .styles.effects import create_card_shadow


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
            get_spacing("lg"), get_spacing("base"),
            get_spacing("lg"), get_spacing("lg"),
        )
        layout.setSpacing(get_spacing("group"))

        self.title_label = QLabel("筛选条件")
        self.title_label.setFont(QFont(*get_font("xl", "bold", "ui")))
        self.title_label.setStyleSheet(get_style("label_title"))
        layout.addWidget(self.title_label)

        self.filter_container = QWidget()
        filter_layout = QVBoxLayout(self.filter_container)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(get_spacing("group"))

        filter_layout.addWidget(self._create_date_section())
        filter_layout.addWidget(self._create_mode_section())
        filter_layout.addWidget(self._create_source_section())
        filter_layout.addWidget(self._create_face_id_section())
        filter_layout.addWidget(self._create_focus_section())
        filter_layout.addWidget(self._create_abnormal_section())

        self.apply_btn = QPushButton("应用筛选")
        self.apply_btn.setFont(QFont(*get_font("base", "bold", "ui")))
        self.apply_btn.setFixedHeight(SIZES["button"]["height"])
        self.apply_btn.setCursor(Qt.PointingHandCursor)
        self.apply_btn.setStyleSheet(get_style("button_primary"))
        self.apply_btn.clicked.connect(self.on_apply_clicked)
        filter_layout.addWidget(self.apply_btn)

        hint_label = QLabel("设置筛选条件后点击应用")
        hint_label.setFont(QFont(*get_font("xs", "normal", "ui")))
        hint_label.setStyleSheet(get_style("label_hint"))
        hint_label.setAlignment(Qt.AlignCenter)
        filter_layout.addWidget(hint_label)

        layout.addWidget(self.filter_container)

        self.chart_container = QWidget()
        self._init_chart_container()
        layout.addWidget(self.chart_container)
        self.chart_container.hide()

        layout.addStretch()

        self.setGraphicsEffect(create_card_shadow(elevated=True))

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont(*get_font("sm", "semibold", "ui")))
        label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; "
            f"padding-bottom: 2px;"
        )
        return label

    def _create_date_section(self):
        widget = QWidget()
        widget.setStyleSheet(get_style("filter_group_wrapper"))
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_spacing("tight"))

        layout.addWidget(self._section_label("日期范围"))

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(get_spacing("tight"))

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setFont(QFont(*get_font("sm")))
        self.start_date_edit.setDate(datetime(2026, 4, 1))
        # 先设置 QDateEdit 样式
        self.start_date_edit.setStyleSheet(get_style("date_edit"))
        self.start_date_edit.calendarWidget().setStyleSheet(get_style("calendar_popup"))

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setFont(QFont(*get_font("sm")))
        self.end_date_edit.setDate(datetime.now())
        # 先设置 QDateEdit 样式
        self.end_date_edit.setStyleSheet(get_style("date_edit"))
        self.end_date_edit.calendarWidget().setStyleSheet(get_style("calendar_popup"))

        h_layout.addWidget(self.start_date_edit)
        h_layout.addWidget(self.end_date_edit)
        layout.addLayout(h_layout)
        return widget

    def _create_mode_section(self):
        widget = QWidget()
        widget.setStyleSheet(get_style("filter_group_wrapper"))
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_spacing("tight"))

        layout.addWidget(self._section_label("运行模式"))

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["全部模式", "网课模式", "考试模式"])
        self._mode_values = ["全部模式", "class", "exam"]  # 与 combo index 一一对应
        self.mode_combo.setFont(QFont(*get_font("sm")))
        self.mode_combo.setStyleSheet(get_style("combo_box"))
        self.mode_combo.currentTextChanged.connect(self.on_filter_changed)
        layout.addWidget(self.mode_combo)
        return widget

    def _create_source_section(self):
        widget = QWidget()
        widget.setStyleSheet(get_style("filter_group_wrapper"))
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_spacing("tight"))

        layout.addWidget(self._section_label("视频来源"))

        self.source_combo = QComboBox()
        self.source_combo.addItems(["全部来源", "摄像头", "本地文件"])
        self._source_values = [None, "camera", "file"]
        self.source_combo.setFont(QFont(*get_font("sm")))
        self.source_combo.setStyleSheet(get_style("combo_box"))
        self.source_combo.currentTextChanged.connect(self.on_filter_changed)
        layout.addWidget(self.source_combo)
        return widget

    def _create_face_id_section(self):
        widget = QWidget()
        widget.setStyleSheet(get_style("filter_group_wrapper"))
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_spacing("tight"))

        layout.addWidget(self._section_label("人脸 ID"))

        self.face_id_combo = QComboBox()
        self.face_id_combo.addItem("全部人脸", None)
        self.face_id_combo.setFont(QFont(*get_font("sm")))
        self.face_id_combo.setStyleSheet(get_style("combo_box"))
        layout.addWidget(self.face_id_combo)
        return widget

    def _create_focus_section(self):
        widget = QWidget()
        widget.setStyleSheet(get_style("filter_group_wrapper"))
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_spacing("tight"))

        layout.addWidget(self._section_label("专注度评分"))

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(get_spacing("tight"))

        for label_text, spin_ref, default_val in [
            ("最低:", "focus_min_spin", 0),
            ("最高:", "focus_max_spin", 100),
        ]:
            row = QHBoxLayout()
            row.setSpacing(get_spacing("tight"))
            lbl = QLabel(label_text)
            lbl.setFont(QFont(*get_font("sm")))
            lbl.setStyleSheet(get_style("label_hint"))
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(default_val)
            spin.setSuffix(" 分")
            spin.setFont(QFont(*get_font("sm")))
            spin.setStyleSheet(get_style("spin_box"))
            row.addWidget(lbl)
            row.addWidget(spin)
            v_layout.addLayout(row)
            if spin_ref == "focus_min_spin":
                self.focus_min_spin = spin
            else:
                self.focus_max_spin = spin

        layout.addLayout(v_layout)
        return widget

    def _create_abnormal_section(self):
        widget = QWidget()
        widget.setStyleSheet(get_style("filter_group_wrapper"))
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_spacing("tight"))

        layout.addWidget(self._section_label("异常事件"))

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(get_spacing("tight"))

        for label_text, spin_ref, default_val in [
            ("最少:", "abnormal_min_spin", 0),
            ("最多:", "abnormal_max_spin", 9999),
        ]:
            row = QHBoxLayout()
            row.setSpacing(get_spacing("tight"))
            lbl = QLabel(label_text)
            lbl.setFont(QFont(*get_font("sm")))
            lbl.setStyleSheet(get_style("label_hint"))
            spin = QSpinBox()
            spin.setRange(0, 2147483647)
            spin.setValue(default_val)
            spin.setFont(QFont(*get_font("sm")))
            spin.setStyleSheet(get_style("spin_box"))
            row.addWidget(lbl)
            row.addWidget(spin)
            v_layout.addLayout(row)
            if spin_ref == "abnormal_min_spin":
                self.abnormal_min_spin = spin
            else:
                self.abnormal_max_spin = spin

        layout.addLayout(v_layout)
        return widget

    def _make_checkbox(self, text: str, checked: bool, indicator_color: str) -> QCheckBox:
        cb = QCheckBox(text)
        cb.setChecked(checked)
        cb.setFont(QFont(*get_font("sm")))
        style = get_style("check_box")
        style += f"\nQCheckBox::indicator:checked {{ background-color: {indicator_color}; }}"
        cb.setStyleSheet(style)
        cb.stateChanged.connect(self.on_chart_option_changed)
        return cb

    def _init_chart_container(self):
        chart_layout = QVBoxLayout(self.chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(get_spacing("base"))

        self.chart_options_group = QGroupBox("图表显示选项")
        self.chart_options_group.setStyleSheet(get_style("group_box"))
        self.chart_options_group.setFont(QFont(*get_font("base", "bold")))

        chart_options_layout = QVBoxLayout()
        chart_options_layout.setSpacing(get_spacing("xs"))

        cc = COLORS["chart_colors"]
        self.show_final_focus = self._make_checkbox("最终专注度", True, cc[0])
        self.show_head_pose = self._make_checkbox("头部姿态", True, cc[1])
        self.show_eye = self._make_checkbox("眼部状态", True, cc[2])
        self.show_yawn = self._make_checkbox("哈欠检测", False, cc[3])
        self.show_distance = self._make_checkbox("人脸距离", False, cc[4])
        self.show_evidence = self._make_checkbox("证据理论", False, cc[5])
        self.show_people = self._make_checkbox("人数项", False, cc[6])

        for cb in [
            self.show_final_focus, self.show_head_pose, self.show_eye,
            self.show_yawn, self.show_distance, self.show_evidence, self.show_people,
        ]:
            chart_options_layout.addWidget(cb)

        self.chart_options_group.setLayout(chart_options_layout)
        chart_layout.addWidget(self.chart_options_group)
        chart_layout.addStretch()

    def on_filter_changed(self):
        pass

    def on_apply_clicked(self):
        idx = self.mode_combo.currentIndex()
        mode_value = self._mode_values[idx] if idx > 0 else None
        src_idx = self.source_combo.currentIndex()
        source_value = self._source_values[src_idx] if src_idx > 0 else None
        face_id_data = self.face_id_combo.currentData()
        filter_params = {
            "start_date": self.start_date_edit.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date_edit.date().toString("yyyy-MM-dd"),
            "mode": mode_value,
            "face_id": face_id_data,
            "focus_min": self.focus_min_spin.value(),
            "focus_max": self.focus_max_spin.value(),
            "abnormal_min": self.abnormal_min_spin.value(),
            "abnormal_max": self.abnormal_max_spin.value(),
            "video_source_type": source_value,
        }
        print(f"[FilterSidebar] 应用筛选条件: {filter_params}")
        self.filter_applied.emit(filter_params)

    def get_current_filter(self):
        idx = self.mode_combo.currentIndex()
        mode_value = self._mode_values[idx] if idx > 0 else None
        src_idx = self.source_combo.currentIndex()
        source_value = self._source_values[src_idx] if src_idx > 0 else None
        face_id_data = self.face_id_combo.currentData()
        return {
            "start_date": self.start_date_edit.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date_edit.date().toString("yyyy-MM-dd"),
            "mode": mode_value,
            "face_id": face_id_data,
            "focus_min": self.focus_min_spin.value(),
            "focus_max": self.focus_max_spin.value(),
            "abnormal_min": self.abnormal_min_spin.value(),
            "abnormal_max": self.abnormal_max_spin.value(),
            "video_source_type": source_value,
        }

    def get_chart_options(self):
        return {
            "final_focus": self.show_final_focus.isChecked(),
            "head_pose": self.show_head_pose.isChecked(),
            "eye": self.show_eye.isChecked(),
            "yawn": self.show_yawn.isChecked(),
            "distance": self.show_distance.isChecked(),
            "evidence": self.show_evidence.isChecked(),
            "people": self.show_people.isChecked(),
        }

    def refresh_face_list(self, face_ids: list):
        """刷新人脸 ID 下拉选项"""
        current_data = self.face_id_combo.currentData()
        self.face_id_combo.blockSignals(True)
        self.face_id_combo.clear()
        self.face_id_combo.addItem("全部人脸", None)
        for fid in face_ids:
            self.face_id_combo.addItem(fid, fid)
        # 恢复之前选中的项
        idx = self.face_id_combo.findData(current_data)
        if idx >= 0:
            self.face_id_combo.setCurrentIndex(idx)
        self.face_id_combo.blockSignals(False)

    def on_chart_option_changed(self):
        self.chart_options_changed.emit(self.get_chart_options())

    def show_filter_mode(self):
        self.title_label.setText("筛选条件")
        self.filter_container.show()
        self.chart_container.hide()

    def show_chart_mode(self):
        self.title_label.setText("图表选项")
        self.filter_container.hide()
        self.chart_container.show()
