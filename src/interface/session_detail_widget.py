from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QWidget
)

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing


class SessionDetailWidget(QFrame):
    back_pressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(get_style("container"))
        self.current_session = {}
        self.current_records = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            get_spacing("xl"), get_spacing("xl"), 
            get_spacing("xl"), get_spacing("xl")
        )
        layout.setSpacing(get_spacing("xl"))

        header_layout = QHBoxLayout()
        self.back_btn = QPushButton("← 返回")
        self.back_btn.setFont(QFont(*get_font("md", "bold")))
        self.back_btn.setFixedSize(120, SIZES["button"]["height_lg"])
        self.back_btn.setStyleSheet(get_style("button_primary"))
        self.back_btn.clicked.connect(self.back_pressed.emit)

        self.title_label = QLabel("会话详情")
        self.title_label.setFont(QFont(*get_font("xl", "bold")))
        self.title_label.setStyleSheet(get_style("label_title"))

        header_layout.addWidget(self.back_btn)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.session_info_label = QLabel("")
        self.session_info_label.setFont(QFont(*get_font("base")))
        self.session_info_label.setStyleSheet(
            f"color: {COLORS['text_hint']}; background-color: {COLORS['card']}; padding: 8px 16px; border-radius: {SIZES['radius']['base']}px;"
        )
        layout.addWidget(self.session_info_label)

        self.record_table = QTableWidget()
        self.record_table.setColumnCount(9)
        self.record_table.setHorizontalHeaderLabels([
            "时间戳", "头部姿态", "行为动作",
            "表情", "证据理论", "人数项", "最终专注度", "强制置0", "会话ID"
        ])
        self.record_table.setFont(QFont(*get_font("sm")))
        self.record_table.setStyleSheet(get_style("table"))
        self.record_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.record_table.verticalHeader().setVisible(False)
        self.record_table.setAlternatingRowColors(False)
        self.record_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.record_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.record_table.setMinimumHeight(200)
        layout.addWidget(self.record_table, 1)

        chart_title_label = QLabel("📊 专注度评分折线图")
        chart_title_label.setFont(QFont(*get_font("xl", "bold")))
        chart_title_label.setStyleSheet(get_style("label_title"))
        layout.addWidget(chart_title_label)

        self.chart_container = QWidget()
        self.chart_container.setMinimumHeight(300)
        self.chart_container.setStyleSheet(
            f"background-color: {COLORS['background']}; border-radius: {SIZES['radius']['base']}px;"
        )
        chart_layout = QVBoxLayout(self.chart_container)
        chart_layout.setContentsMargins(get_spacing("sm"), get_spacing("sm"), get_spacing("sm"), get_spacing("sm"))
        
        self.figure = Figure(facecolor=COLORS['background'])
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet(f"background-color: {COLORS['background']};")
        chart_layout.addWidget(self.canvas)
        
        layout.addWidget(self.chart_container, 2)

    def load_session_detail(self, session: dict, records: list, chart_options: dict = None):
        self.current_session = session
        self.current_records = records

        session_id = session.get("session_id", "")
        start_time = session.get("start_time", "")
        end_time = session.get("end_time", "")
        mode = session.get("mode", "")
        avg_focus = session.get("avg_focus_score", 0)
        abnormal_count = session.get("abnormal_event_count", 0)

        self.title_label.setText(f"会话详情 - {session_id}")
        self.session_info_label.setText(
            f"📅 会话时间: {start_time} ~ {end_time} | 🎯 模式: {mode} | "
            f"📈 平均专注度: {avg_focus:.1f} | ⚠️ 异常事件: {abnormal_count} | 📝 记录数: {len(records)}"
        )

        self.record_table.setRowCount(len(records))
        for row, record in enumerate(records):
            bg_color = COLORS["background"] if row % 2 == 0 else COLORS["background_sidebar"]

            timestamp = record.get("timestamp", 0)
            head_pose = record.get("head_pose_score", 0)
            behavior = record.get("behavior_score", 0)
            expression = record.get("expression_score", 0)
            evidence = record.get("evidence_score", 0)
            people = record.get("people_score", 0)
            final_focus = record.get("final_focus_score", 0)
            is_force_zero = record.get("is_force_zero", False)
            session_id = record.get("session_id", "")

            items = [
                QTableWidgetItem(f"{timestamp:.1f}s"),
                QTableWidgetItem(f"{head_pose:.1f}"),
                QTableWidgetItem(f"{behavior:.1f}"),
                QTableWidgetItem(f"{expression:.1f}"),
                QTableWidgetItem(f"{evidence:.1f}"),
                QTableWidgetItem(f"{people:.1f}"),
                QTableWidgetItem(f"{final_focus:.1f}"),
                QTableWidgetItem("是" if is_force_zero else "否"),
                QTableWidgetItem(session_id),
            ]

            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter)
                item.setBackground(QColor(bg_color))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                if col == 6:
                    if final_focus >= 70:
                        item.setForeground(QColor(COLORS["focus_high"]))
                    elif final_focus < 50:
                        item.setForeground(QColor(COLORS["focus_low"]))
                    else:
                        item.setForeground(QColor(COLORS["focus_medium"]))
                if col == 7:
                    if is_force_zero:
                        item.setForeground(QColor(COLORS["danger"]))

                self.record_table.setItem(row, col, item)

        self.draw_chart(records, chart_options)

    def update_chart(self, chart_options: dict):
        if self.current_records:
            self.draw_chart(self.current_records, chart_options)

    def draw_chart(self, records: list, chart_options: dict = None):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(COLORS['background'])
        
        if chart_options is None:
            chart_options = {
                "final_focus": True,
                "head_pose": True,
                "behavior": True,
                "expression": False,
                "evidence": False,
                "people": False
            }
        
        sampled_records = self.downsample_records(records, 60)
        n = len(sampled_records)
        
        if n == 0:
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', fontsize=14, color='white')
            ax.set_title('专注度评分变化趋势', fontsize=12, color='white')
            self.canvas.draw()
            return

        x = np.arange(n)
        lines_plotted = 0

        if chart_options.get("final_focus"):
            final_focus = [r.get("final_focus_score", 0) for r in sampled_records]
            ax.plot(x, final_focus, label='最终专注度', color=COLORS['focus_high'], linewidth=2)
            lines_plotted += 1
        
        if chart_options.get("head_pose"):
            head_pose = [r.get("head_pose_score", 0) for r in sampled_records]
            ax.plot(x, head_pose, label='头部姿态', color=COLORS['danger'], linewidth=1.5, linestyle='--')
            lines_plotted += 1
        
        if chart_options.get("behavior"):
            behavior = [r.get("behavior_score", 0) for r in sampled_records]
            ax.plot(x, behavior, label='行为动作', color=COLORS['warning'], linewidth=1.5, linestyle='--')
            lines_plotted += 1
        
        if chart_options.get("expression"):
            expression = [r.get("expression_score", 0) for r in sampled_records]
            ax.plot(x, expression, label='表情评分', color=COLORS['primary'], linewidth=1.5, linestyle='--')
            lines_plotted += 1
        
        if chart_options.get("evidence"):
            evidence = [r.get("evidence_score", 0) for r in sampled_records]
            ax.plot(x, evidence, label='证据理论', color=COLORS['primary_light'], linewidth=1.5, linestyle='--')
            lines_plotted += 1
        
        if chart_options.get("people"):
            people = [r.get("people_score", 0) for r in sampled_records]
            ax.plot(x, people, label='人数项', color=COLORS['secondary'], linewidth=1.5, linestyle='--')
            lines_plotted += 1

        ax.set_title('专注度评分变化趋势', fontsize=12, color='white')
        ax.set_xlabel('采样点', fontsize=10, color='#888888')
        ax.set_ylabel('评分', fontsize=10, color='#888888')
        ax.set_ylim(0, 100)
        ax.grid(True, color='#2D2D5A', linestyle='--', alpha=0.5)
        ax.tick_params(axis='both', colors='#888888')

        if lines_plotted > 0:
            ax.legend(loc='upper right', facecolor='#1A1A3A', edgecolor='#353560', labelcolor='white')

        self.canvas.draw()

    def downsample_records(self, records: list, max_samples: int) -> list:
        n = len(records)
        if n <= max_samples:
            return records
        step = n // max_samples
        return records[::step][:max_samples]
