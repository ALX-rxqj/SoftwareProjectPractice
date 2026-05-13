import pyqtgraph as pg
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar
)

from .config import RIGHT_PANEL_WIDTH
from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing
from .interface_manager import interface_manager, FocusResultData
from .unified_data_manager import unified_data_manager


class RightPanel(QFrame):
    start_analysis = pyqtSignal()
    stop_analysis = pyqtSignal()
    score_updated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(RIGHT_PANEL_WIDTH)
        self.setStyleSheet(get_style("frame_sidebar"))
        self.is_running = False
        self.init_ui()
        self.score_updated.connect(self.update_scores)
        self._register_interface_callback()

        self.simulation_timer = QTimer()
        self.simulation_timer.timeout.connect(self.generate_simulated_data)
        self.simulation_interval = 1000

    def _register_interface_callback(self):
        """注册接口管理器的专注度结果回调"""
        interface_manager.register_focus_result_callback(self.on_focus_result_received)

    def on_focus_result_received(self, data: FocusResultData):
        """
        SEI-01: 接收状态估计模块发送的专注度评分结果
        用于更新UI显示
        """
        score_dict = {
            "head_pose": data.head_pose_score,
            "behavior": data.behavior_score,
            "expression": data.expression_score,
            "evidence": data.evidence_score,
            "people": data.people_score,
            "final_focus": data.final_focus_score
        }
        self.score_updated.emit(score_dict)

        if data.warn_msg:
            warn_text = f"{data.warn_msg.get('type', '')}: {data.warn_msg.get('detail', '')}"
            self.parent().parent().video_widget.update_warn(warn_text)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(get_spacing("xxl"), get_spacing("xxl"), get_spacing("xxl"), get_spacing("xxl"))
        layout.setSpacing(get_spacing("xxl"))

        title_layout = QHBoxLayout()
        title_label = QLabel("实时评审")
        title_label.setFont(QFont(*get_font("xl", "bold")))
        title_label.setStyleSheet(f"color: {COLORS['text']};")
        weight_tag = QLabel("标准权重")
        weight_tag.setStyleSheet(f"""
            background-color: {COLORS['card']};
            color: {COLORS['text_hint']};
            font-size: {FONTS['size']['xs']}px;
            border-radius: {SIZES['radius']['lg']}px;
            padding: {SIZES['spacing']['xs']}px {SIZES['spacing']['lg']}px;
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(weight_tag)
        layout.addLayout(title_layout)

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
            label_layout = QHBoxLayout()
            name_label = QLabel(config["name"])
            name_label.setFont(QFont(*get_font("md")))
            name_label.setStyleSheet(f"color: {COLORS['text']};")
            score_label = QLabel(str(config["default"]))
            score_label.setFont(QFont(*get_font("md", "bold")))
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
                "progress": progress_bar
            }

        focus_layout = QVBoxLayout()
        focus_title = QLabel("当前专注度")
        focus_title.setFont(QFont(*get_font("md")))
        focus_title.setStyleSheet(f"color: {COLORS['text_hint']};")
        focus_title.setAlignment(Qt.AlignCenter)
        self.focus_score_label = QLabel("0.0")
        self.focus_score_label.setFont(QFont(FONTS["family"], 42, FONTS["weight"]["bold"]))
        self.focus_score_label.setStyleSheet(f"color: {COLORS['focus_high']};")
        self.focus_score_label.setAlignment(Qt.AlignCenter)
        focus_layout.addWidget(focus_title)
        focus_layout.addWidget(self.focus_score_label)
        layout.addLayout(focus_layout)

        curve_title = QLabel("专注度曲线")
        curve_title.setFont(QFont(*get_font("md")))
        curve_title.setStyleSheet(f"color: {COLORS['text_hint']};")
        self.curve_widget = pg.PlotWidget()
        self.curve_widget.setFixedHeight(180)
        self.curve_widget.setBackground(COLORS["background"])
        self.curve_widget.showGrid(x=False, y=True, alpha=0.3)
        self.curve_widget.setYRange(0, 100)
        self.curve_widget.setMouseEnabled(x=False, y=False)
        self.curve_widget.hideAxis("bottom")
        self.curve_data = [0.0] * 50
        self.curve_line = self.curve_widget.plot(self.curve_data, pen=pg.mkPen(color=COLORS["focus_high"], width=2))
        layout.addWidget(curve_title)
        layout.addWidget(self.curve_widget)

        layout.addStretch()

        self.control_btn = QPushButton("✅ 启动/完成")
        self.control_btn.setFixedHeight(48)
        self.control_btn.setFont(QFont(*get_font("lg", "bold")))
        self.control_btn.setStyleSheet(get_style("push_button_gradient"))
        self.control_btn.clicked.connect(self.on_control_click)
        layout.addWidget(self.control_btn)

    def update_scores(self, score_dict):
        if "head_pose" in score_dict:
            val = score_dict["head_pose"]
            self.score_items["head_pose"]["label"].setText(str(val))
            self.score_items["head_pose"]["progress"].setValue(int(val))
        if "behavior" in score_dict:
            val = score_dict["behavior"]
            self.score_items["behavior"]["label"].setText(str(val))
            self.score_items["behavior"]["progress"].setValue(int(val))
        if "expression" in score_dict:
            val = score_dict["expression"]
            self.score_items["expression"]["label"].setText(str(val))
            self.score_items["expression"]["progress"].setValue(int(val))
        if "evidence" in score_dict:
            val = score_dict["evidence"]
            self.score_items["evidence"]["label"].setText(str(val))
            self.score_items["evidence"]["progress"].setValue(int(val))
        if "people" in score_dict:
            val = score_dict["people"]
            self.score_items["people"]["label"].setText(str(val))
            self.score_items["people"]["progress"].setValue(int(val))
        if "final_focus" in score_dict:
            val = score_dict["final_focus"]
            self.focus_score_label.setText(f"{val:.1f}")
            self.curve_data.append(val)
            self.curve_data.pop(0)
            self.curve_line.setData(self.curve_data)

    def generate_simulated_data(self):
        score_dict = unified_data_manager.generate_realtime_scores()
        if score_dict:
            self.score_updated.emit(score_dict)

    def on_control_click(self):
        if not self.is_running:
            self.is_running = True
            self.control_btn.setText("⏹️ 停止分析")
            self.start_analysis.emit()
            self.simulation_timer.start(self.simulation_interval)
        else:
            self.is_running = False
            self.control_btn.setText("✅ 启动/完成")
            self.stop_analysis.emit()
            self.simulation_timer.stop()
