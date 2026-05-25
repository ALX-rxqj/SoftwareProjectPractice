from PyQt5.QtCore import Qt, QModelIndex, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QWidget,
)

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing
from .styles.effects import create_card_shadow


class SessionDetailWidget(QFrame):
    back_pressed = pyqtSignal()
    alert_info_clicked = pyqtSignal(dict)
    export_report_clicked = pyqtSignal(dict, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(get_style("card_elevated_glass"))
        self.setGraphicsEffect(create_card_shadow(elevated=True))
        self.current_session = {}
        self.current_records = []
        self._pan_pressed = False
        self._pan_start_x = None
        self._pan_start_y = None
        self._pan_start_xlim = None
        self._pan_start_ylim = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            get_spacing("xl"), get_spacing("xl"),
            get_spacing("xl"), get_spacing("xl"),
        )
        layout.setSpacing(get_spacing("xl"))

        # ---- 头部 ----
        header_layout = QHBoxLayout()
        self.back_btn = QPushButton("< 返回")
        self.back_btn.setFont(QFont(*get_font("md", "bold", "ui")))
        self.back_btn.setFixedSize(100, SIZES["button"]["height_lg"])
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setStyleSheet(get_style("button_secondary"))
        self.back_btn.clicked.connect(self.back_pressed.emit)

        self.title_label = QLabel("会话详情")
        self.title_label.setFont(QFont(*get_font("xl", "bold", "ui")))
        self.title_label.setStyleSheet(get_style("label_title"))

        header_layout.addWidget(self.back_btn)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.btn_alert_info = QPushButton("查看告警")
        self.btn_alert_info.setFont(QFont(*get_font("sm", "bold", "ui")))
        self.btn_alert_info.setFixedSize(90, SIZES["button"]["height_lg"])
        self.btn_alert_info.setCursor(Qt.PointingHandCursor)
        self.btn_alert_info.setStyleSheet(get_style("button_select") + f"""
            QPushButton {{
                font-weight: {FONTS['weight']['bold']};
            }}
        """)
        self.btn_alert_info.clicked.connect(self._on_alert_info_clicked)

        self.btn_export_report = QPushButton("导出")
        self.btn_export_report.setFont(QFont(*get_font("sm", "bold", "ui")))
        self.btn_export_report.setFixedSize(90, SIZES["button"]["height_lg"])
        self.btn_export_report.setCursor(Qt.PointingHandCursor)
        self.btn_export_report.setStyleSheet(get_style("completion_btn_temp"))
        self.btn_export_report.clicked.connect(self._on_export_report_clicked)

        header_layout.addWidget(self.btn_alert_info)
        header_layout.addWidget(self.btn_export_report)
        layout.addLayout(header_layout)

        # ---- 会话信息标签 ----
        self.session_info_label = QLabel("")
        self.session_info_label.setFont(QFont(*get_font("base", "normal", "ui")))
        self.session_info_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background-color: {COLORS['card']}; "
            f"padding: {get_spacing('sm')}px {get_spacing('base')}px; "
            f"border-radius: {SIZES['radius']['base']}px;"
        )
        layout.addWidget(self.session_info_label)

        # ---- 评分表格 ----
        self.record_table = QTableWidget()
        self.record_table.setColumnCount(11)
        self.record_table.setHorizontalHeaderLabels([
            "时间戳", "头部姿态", "眼部状态", "哈欠检测",
            "人脸距离", "证据理论", "人数项", "最终专注度", "强制置0",
            "是否达到阈值", "会话ID",
        ])
        self.record_table.setFont(QFont(*get_font("sm", "normal", "data")))
        self.record_table.setStyleSheet(get_style("table_enhanced"))
        self.record_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.record_table.verticalHeader().setVisible(False)
        self.record_table.setAlternatingRowColors(False)
        self.record_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.record_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.record_table.setMinimumHeight(180)
        self.record_table.verticalHeader().setDefaultSectionSize(36)
        self.record_table.cellEntered.connect(self._on_row_hover)
        self._hovered_row = -1
        self._hover_color = QColor(122, 92, 255, 20)
        layout.addWidget(self.record_table, 1)

        # ---- 图表标题 ----
        chart_title_label = QLabel("专注度评分趋势")
        chart_title_label.setFont(QFont(*get_font("xl", "bold", "ui")))
        chart_title_label.setStyleSheet(get_style("label_title"))
        layout.addWidget(chart_title_label)

        # ---- Matplotlib 图表 ----
        self.chart_container = QWidget()
        self.chart_container.setMinimumHeight(300)
        self.chart_container.setStyleSheet(
            get_style("card_section") + f"""
            background-color: {COLORS['background']};
            border-radius: {SIZES['radius']['xxl']}px;
            """
        )
        chart_layout = QVBoxLayout(self.chart_container)
        chart_layout.setContentsMargins(
            get_spacing("sm"), get_spacing("sm"),
            get_spacing("sm"), get_spacing("sm"),
        )

        self.figure = Figure(facecolor=COLORS["background"])
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet(f"background-color: {COLORS['background']};")
        self.canvas.mpl_connect("button_press_event", self._on_mouse_press)
        self.canvas.mpl_connect("button_release_event", self._on_mouse_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_motion)
        chart_layout.addWidget(self.canvas)
        layout.addWidget(self.chart_container, 2)

    def _on_row_hover(self, row: int, col: int):
        if row == self._hovered_row:
            return
        if self._hovered_row >= 0 and self._hovered_row < self.record_table.rowCount():
            if not self.record_table.selectionModel().isRowSelected(self._hovered_row, QModelIndex()):
                for c in range(self.record_table.columnCount()):
                    item = self.record_table.item(self._hovered_row, c)
                    if item:
                        item.setBackground(QColor(0, 0, 0, 0))
        if row >= 0 and not self.record_table.selectionModel().isRowSelected(row, QModelIndex()):
            for c in range(self.record_table.columnCount()):
                item = self.record_table.item(row, c)
                if item:
                    item.setBackground(self._hover_color)
        self._hovered_row = row

    def load_session_detail(self, session: dict, records: list, chart_options: dict = None):
        self.current_session = session
        self.current_records = records

        session_id = session.get("session_id", "")
        face_id = session.get("face_id") or "-"
        start_time = session.get("start_time") or "-"
        end_time = session.get("end_time") or "-"
        mode = {"class": "网课模式", "exam": "考试模式"}.get(
            session.get("mode", ""), session.get("mode", "")
        )
        avg_focus = session.get("avg_focus_score") or 0.0
        abnormal_count = session.get("abnormal_event_count") or 0
        video_source_type = session.get("video_source_type", "camera")
        file_name = session.get("file_name") or ""

        if video_source_type == "file":
            source_info = f"本地文件 — {file_name}" if file_name else "本地文件"
        else:
            source_info = "摄像头"

        self.title_label.setText(f"会话详情 - {session_id}")
        self.session_info_label.setText(
            f"人脸ID: {face_id}  |  "
            f"会话时间: {start_time} ~ {end_time}  |  模式: {mode}  |  "
            f"视频来源: {source_info}  |  "
            f"平均专注度: {avg_focus:.1f}  |  异常事件: {abnormal_count}  |  记录数: {len(records)}"
        )

        self.record_table.setRowCount(len(records))
        for row, record in enumerate(records):
            items = [
                QTableWidgetItem(f"{record.get('timestamp', 0):.1f}s"),
                QTableWidgetItem(f"{record.get('head_pose_score', 0):.1f}"),
                QTableWidgetItem(f"{record.get('eye_score', 0):.1f}"),
                QTableWidgetItem(f"{record.get('yawn_score', 0):.1f}"),
                QTableWidgetItem(f"{record.get('distance_score', 0):.1f}"),
                QTableWidgetItem(f"{record.get('evidence_score', 0):.1f}"),
                QTableWidgetItem(f"{record.get('people_score', 0):.1f}"),
                QTableWidgetItem(f"{record.get('final_focus_score', 0):.1f}"),
                QTableWidgetItem("是" if record.get("is_force_zero", False) else "否"),
                QTableWidgetItem("是" if record.get("is_over_threshold", False) else "否"),
                QTableWidgetItem(record.get("session_id", "")),
            ]

            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                if col == 7:
                    final_focus = record.get("final_focus_score", 0)
                    if final_focus >= 70:
                        item.setForeground(QColor(COLORS["focus_high"]))
                    elif final_focus < 50:
                        item.setForeground(QColor(COLORS["focus_low"]))
                    else:
                        item.setForeground(QColor(COLORS["focus_medium"]))
                if col == 8 and record.get("is_force_zero", False):
                    item.setForeground(QColor(COLORS["danger"]))
                if col == 9 and record.get("is_over_threshold", False):
                    item.setForeground(QColor(COLORS["danger"]))

                self.record_table.setItem(row, col, item)

        self.draw_chart(records, chart_options)

    def update_chart(self, chart_options: dict):
        if self.current_records:
            self.draw_chart(self.current_records, chart_options)

    def draw_chart(self, records: list, chart_options: dict = None):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(COLORS["background"])

        cc = COLORS["chart_colors"]

        if chart_options is None:
            chart_options = {
                "final_focus": True, "head_pose": True, "eye": True,
                "yawn": False, "distance": False, "evidence": False, "people": False,
            }

        n = len(records)

        if n == 0:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    fontsize=14, color=COLORS["text_hint"])
            ax.set_title("专注度评分变化趋势", fontsize=12, color=COLORS["text"])
            self.canvas.draw()
            return

        t0 = records[0].get("timestamp", 0) if records else 0
        x = [r.get("timestamp", 0) - t0 for r in records]

        line_configs = [
            ("final_focus", "最终专注度", cc[0], 2.5),
            ("head_pose", "头部姿态", cc[1], 1.5),
            ("eye", "眼部状态", cc[2], 1.5),
            ("yawn", "哈欠检测", cc[3], 1.5),
            ("distance", "人脸距离", cc[4], 1.5),
            ("evidence", "证据理论", cc[5], 1.5),
            ("people", "人数项", cc[6], 1.5),
        ]

        for key, label, color, lw in line_configs:
            if chart_options.get(key):
                ax.plot(x, [r.get(f"{key}_score" if key != "final_focus" else "final_focus_score", 0)
                         for r in records],
                        label=label, color=color, linewidth=lw,
                        linestyle="-" if key == "final_focus" else "--")

        ax.set_title("专注度评分变化趋势", fontsize=12, color=COLORS["text"])
        ax.set_xlabel("时间 (秒)", fontsize=10, color=COLORS["text_hint"])
        ax.set_ylabel("评分", fontsize=10, color=COLORS["text_hint"])
        ax.set_ylim(0, 120)
        ax.grid(True, color=COLORS["border"], linestyle="--", alpha=0.4)
        ax.tick_params(axis="both", colors=COLORS["text_hint"])
        for spine in ax.spines.values():
            spine.set_color(COLORS["border"])

        ax.legend(
            loc="upper right",
            facecolor=COLORS["surface"],
            edgecolor=COLORS["border"],
            labelcolor=COLORS["text_secondary"],
            fontsize=9,
        )

        self._ax = ax
        self._scroll_cid = self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.canvas.draw()

    def _on_scroll(self, event):
        ax = getattr(self, "_ax", None)
        if ax is None or event.xdata is None or event.ydata is None:
            return
        base_scale = 1.2
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        scale_factor = 1 / base_scale if event.button == "up" else base_scale
        relx = (cur_xlim[1] - event.xdata) / (cur_xlim[1] - cur_xlim[0])
        rely = (cur_ylim[1] - event.ydata) / (cur_ylim[1] - cur_ylim[0])
        ax.set_xlim([
            event.xdata - (cur_xlim[1] - cur_xlim[0]) * scale_factor * (1 - relx),
            event.xdata + (cur_xlim[1] - cur_xlim[0]) * scale_factor * relx,
        ])
        ax.set_ylim([
            event.ydata - (cur_ylim[1] - cur_ylim[0]) * scale_factor * (1 - rely),
            event.ydata + (cur_ylim[1] - cur_ylim[0]) * scale_factor * rely,
        ])
        self.canvas.draw_idle()

    def _on_mouse_press(self, event):
        if event.button != 1 or event.xdata is None or event.ydata is None:
            return
        ax = getattr(self, "_ax", None)
        if ax is None:
            return
        self._pan_pressed = True
        self._pan_start_x = event.xdata
        self._pan_start_y = event.ydata
        self._pan_start_xlim = ax.get_xlim()
        self._pan_start_ylim = ax.get_ylim()

    def _on_mouse_release(self, event):
        self._pan_pressed = False

    def _on_mouse_motion(self, event):
        if not self._pan_pressed or event.xdata is None or event.ydata is None:
            return
        ax = getattr(self, "_ax", None)
        if ax is None:
            return
        dx = event.xdata - self._pan_start_x
        dy = event.ydata - self._pan_start_y
        ax.set_xlim([self._pan_start_xlim[0] - dx, self._pan_start_xlim[1] - dx])
        ax.set_ylim([self._pan_start_ylim[0] - dy, self._pan_start_ylim[1] - dy])
        self.canvas.draw_idle()

    def _on_alert_info_clicked(self):
        if self.current_session:
            self.alert_info_clicked.emit(self.current_session)

    def _on_export_report_clicked(self):
        if self.current_session:
            self.export_report_clicked.emit(self.current_session, self.current_records)
