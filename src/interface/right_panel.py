import pyqtgraph as pg
from PyQt5.QtCore import Qt, pyqtSignal, QSettings
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QWidget, QCheckBox,
)

from .config import RIGHT_PANEL_WIDTH
from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing
from .styles.effects import create_card_shadow


def _progress_color(value: float) -> str:
    if value >= 70:
        return COLORS["focus_high"]
    elif value >= 50:
        return COLORS["focus_medium"]
    else:
        return COLORS["focus_low"]


class RightPanel(QFrame):
    start_analysis = pyqtSignal()
    stop_analysis = pyqtSignal()
    score_updated = pyqtSignal(dict)
    toast_requested = pyqtSignal(str, str)
    toast_dismiss_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(RIGHT_PANEL_WIDTH)
        self.setStyleSheet(get_style("card_elevated_glass"))
        self.setGraphicsEffect(create_card_shadow(elevated=True))
        self.is_running = False
        self._start_validator = None
        self._toast_enabled = QSettings().value("toast/enabled", True, type=bool)
        self.init_ui()
        self.score_updated.connect(self.update_scores)

    def handle_focus_result(self, data):
        """由 MainWindow 调用，统一处理 MOCK/REAL 专注度结果"""
        score_dict = {
            "head_pose": data.head_pose_score,
            "behavior": data.behavior_score,
            "expression": data.expression_score,
            "evidence": data.evidence_score,
            "people": data.people_score,
            "final_focus": data.final_focus_score,
        }
        self.score_updated.emit(score_dict)

        if data.warn_msg and self._toast_enabled:
            self.toast_requested.emit(
                data.warn_msg.get("type", ""),
                data.warn_msg.get("detail", ""),
            )

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            get_spacing("xl"), get_spacing("xxl"),
            get_spacing("xl"), get_spacing("xxl"),
        )
        layout.setSpacing(get_spacing("lg"))

        # ---- 标题 (L2) ----
        title_label = QLabel("实时评审")
        title_label.setFont(QFont(*get_font("xl", "bold", "ui")))
        title_label.setStyleSheet(get_style("label_title"))
        layout.addWidget(title_label)

        # ---- 5 项评分 ----
        self.score_items = {}
        score_config = [
            {"key": "head_pose", "name": "头部姿态", "max": 100, "default": 0},
            {"key": "behavior", "name": "行为", "max": 100, "default": 0},
            {"key": "expression", "name": "表情", "max": 100, "default": 0},
            {"key": "evidence", "name": "证据", "max": 100, "default": 0},
            {"key": "people", "name": "人数", "max": 100, "default": 0},
        ]
        for config in score_config:
            item_layout = QVBoxLayout()
            item_layout.setSpacing(get_spacing("xs"))

            label_layout = QHBoxLayout()
            # L3 子标签
            name_label = QLabel(config["name"])
            name_label.setFont(QFont(*get_font("base", "medium", "ui")))
            name_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
            # L4 数据值 (等宽)
            score_label = QLabel(str(config["default"]))
            score_label.setFont(QFont(*get_font("lg", "semibold", "data")))
            score_label.setStyleSheet(f"color: {COLORS['text']};")
            label_layout.addWidget(name_label)
            label_layout.addStretch()
            label_layout.addWidget(score_label)

            progress_bar = QProgressBar()
            progress_bar.setFixedHeight(8)
            progress_bar.setRange(0, config["max"])
            progress_bar.setValue(config["default"])
            progress_bar.setTextVisible(False)
            progress_bar.setStyleSheet(get_style("progress_bar"))

            item_layout.addLayout(label_layout)
            item_layout.addWidget(progress_bar)
            layout.addLayout(item_layout)
            self.score_items[config["key"]] = {
                "label": score_label,
                "progress": progress_bar,
            }

        layout.addSpacing(get_spacing("base"))

        # ---- 当前专注度 (L5) ----
        focus_wrapper = QWidget()
        focus_wrapper.setStyleSheet(get_style("container"))
        focus_wrapper.setFixedHeight(150)
        focus_wrapper.setGraphicsEffect(create_card_shadow(elevated=False))
        focus_layout = QVBoxLayout(focus_wrapper)
        focus_layout.setContentsMargins(0, get_spacing("sm"), 0, get_spacing("sm"))
        focus_layout.setSpacing(0)

        focus_title = QLabel("当前专注度")
        focus_title.setFont(QFont(*get_font("base", "normal", "ui")))
        focus_title.setStyleSheet(f"color: {COLORS['text_hint']}; background: transparent;")
        focus_title.setAlignment(Qt.AlignCenter)

        self.focus_score_label = QLabel("0.0")
        self.focus_score_label.setFont(QFont(
            *get_font("hero", "extrabold", "ui")
        ))
        self.focus_score_label.setStyleSheet(
            f"color: {COLORS['focus_high']}; background: transparent;"
        )
        self.focus_score_label.setAlignment(Qt.AlignCenter)

        focus_layout.addStretch()
        focus_layout.addWidget(focus_title)
        focus_layout.addWidget(self.focus_score_label)
        focus_layout.addStretch()
        layout.addWidget(focus_wrapper)

        # ---- 专注度曲线 ----
        curve_title = QLabel("专注度曲线")
        curve_title.setFont(QFont(*get_font("base", "normal", "ui")))
        curve_title.setStyleSheet(f"color: {COLORS['text_hint']};")
        self.curve_widget = pg.PlotWidget()
        self.curve_widget.setFixedHeight(180)
        self.curve_widget.setBackground(COLORS["background"])
        self.curve_widget.showGrid(x=False, y=True, alpha=0.15)
        self.curve_widget.setYRange(0, 100)
        self.curve_widget.setMouseEnabled(x=False, y=False)
        self.curve_widget.hideAxis("bottom")
        self.curve_widget.getAxis("left").setPen(
            pg.mkPen(color=COLORS["text_hint"], width=1)
        )
        self.curve_widget.getAxis("left").setTextPen(
            pg.mkPen(color=COLORS["text_hint"])
        )
        self.curve_data = [0.0] * 50
        self.curve_line = self.curve_widget.plot(
            self.curve_data,
            pen=pg.mkPen(color=COLORS["focus_high"], width=3),
        )
        fill_brush = pg.mkBrush(0, 224, 128, 25)
        self.curve_fill = self.curve_widget.plot(
            self.curve_data, pen=None, fillLevel=0, brush=fill_brush,
        )
        layout.addWidget(curve_title)
        layout.addWidget(self.curve_widget)

        layout.addStretch()

        # ---- 弹窗提醒开关 ----
        self.toast_enabled_checkbox = QCheckBox("分析时弹窗提醒")
        self.toast_enabled_checkbox.setChecked(self._toast_enabled)
        self.toast_enabled_checkbox.setCursor(Qt.PointingHandCursor)
        self.toast_enabled_checkbox.setFont(QFont(*get_font("sm", "normal", "ui")))
        self.toast_enabled_checkbox.setStyleSheet(
            f"color: {COLORS['text_hint']};"
        )
        self.toast_enabled_checkbox.toggled.connect(self._on_toast_toggle)
        layout.addWidget(self.toast_enabled_checkbox)

        # ---- 控制按钮 ----
        self.control_btn = QPushButton("▶  开始分析")
        self.control_btn.setFixedHeight(50)
        self.control_btn.setFont(QFont(*get_font("lg", "bold", "ui")))
        self.control_btn.setCursor(Qt.PointingHandCursor)
        self.control_btn.setStyleSheet(get_style("button_glow") + f"""
            QPushButton {{ border-radius: {SIZES['radius']['xxl']}px; }}
        """)
        self.control_btn.clicked.connect(self.on_control_click)
        layout.addWidget(self.control_btn)

    def update_scores(self, score_dict):
        if not self.is_running:
            return
        for key in ["head_pose", "behavior", "expression", "evidence", "people"]:
            if key in score_dict:
                val = score_dict[key]
                self.score_items[key]["label"].setText(f"{val:.1f}")
                self.score_items[key]["progress"].setValue(int(val))
                color = _progress_color(val)
                self.score_items[key]["progress"].setStyleSheet(
                    f"QProgressBar {{ background-color: {COLORS['card']}; "
                    f"border-radius: {SIZES['radius']['sm']}px; }}\n"
                    f"QProgressBar::chunk {{ background-color: {color}; "
                    f"border-radius: {SIZES['radius']['sm']}px; }}"
                )
        if "final_focus" in score_dict:
            val = score_dict["final_focus"]
            self.focus_score_label.setText(f"{val:.1f}")
            color = _progress_color(val)
            self.focus_score_label.setStyleSheet(
                f"color: {color}; background: transparent;"
            )
            self.curve_data.append(val)
            self.curve_data.pop(0)
            self.curve_line.setData(self.curve_data)
            self.curve_fill.setData(self.curve_data)

    def set_start_validator(self, validator):
        """设置开始分析前的验证回调。validator 返回 (bool, str)，True 表示通过。"""
        self._start_validator = validator

    def reset_button_state(self):
        """由 MainWindow 在验证失败时调用，回退按钮状态"""
        self.is_running = False
        self.control_btn.setText("▶  开始分析")

    def reset_scores(self):
        """停止分析时重置所有评分为 0"""
        for key in ["head_pose", "behavior", "expression", "evidence", "people"]:
            self.score_items[key]["label"].setText("0.0")
            self.score_items[key]["progress"].setValue(0)
            self.score_items[key]["progress"].setStyleSheet(
                f"QProgressBar {{ background-color: {COLORS['card']}; "
                f"border-radius: {SIZES['radius']['sm']}px; }}\n"
                f"QProgressBar::chunk {{ background-color: {COLORS['focus_low']}; "
                f"border-radius: {SIZES['radius']['sm']}px; }}"
            )
        self.focus_score_label.setText("0.0")
        self.focus_score_label.setStyleSheet(
            f"color: {COLORS['focus_high']}; background: transparent;"
        )
        self.curve_data = [0.0] * 50
        self.curve_line.setData(self.curve_data)
        self.curve_fill.setData(self.curve_data)

    def _on_toast_toggle(self, checked: bool):
        self._toast_enabled = checked
        QSettings().setValue("toast/enabled", checked)
        if not checked:
            self.toast_dismiss_requested.emit()

    def on_control_click(self):
        if not self.is_running:
            if self._start_validator is not None:
                ok, msg = self._start_validator()
                if not ok:
                    return
            self.is_running = True
            self.control_btn.setText("■  停止分析")
            self.start_analysis.emit()
        else:
            self.is_running = False
            self.control_btn.setText("▶  开始分析")
            self.stop_analysis.emit()
