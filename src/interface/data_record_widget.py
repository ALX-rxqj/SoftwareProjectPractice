from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QHBoxLayout
)

from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing


class DataRecordWidget(QFrame):
    session_selected = pyqtSignal(dict)
    record_deleted = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(400)
        self.setStyleSheet(get_style("container"))
        self.current_filter = {}
        self.current_sessions = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            get_spacing("xl"), get_spacing("xl"), 
            get_spacing("xl"), get_spacing("xl")
        )
        layout.setSpacing(get_spacing("xl"))

        header_layout = QHBoxLayout()
        title_label = QLabel("📋 会话列表")
        title_label.setFont(QFont(*get_font("xl", "bold")))
        title_label.setStyleSheet(get_style("label_title"))

        self.filter_info_label = QLabel("")
        self.filter_info_label.setFont(QFont(*get_font("xs")))
        self.filter_info_label.setStyleSheet(
            f"color: {COLORS['text_hint']}; background-color: {COLORS['card']}; padding: 4px 12px; border-radius: 12px;"
        )

        header_layout.addWidget(title_label)
        header_layout.addWidget(self.filter_info_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.record_table = QTableWidget()
        self.record_table.setColumnCount(7)
        self.record_table.setHorizontalHeaderLabels(["会话 ID", "日期", "开始时间", "结束时间", "模式", "平均专注度", "异常事件"])
        self.record_table.setFont(QFont(*get_font("base")))
        self.record_table.setStyleSheet(get_style("table"))
        self.record_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.record_table.verticalHeader().setVisible(False)
        self.record_table.setAlternatingRowColors(False)
        self.record_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.record_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.record_table.itemClicked.connect(self.on_record_clicked)
        layout.addWidget(self.record_table)

        hint_label = QLabel("点击会话记录查看详情（调试模式）")
        hint_label.setFont(QFont(*get_font("xs")))
        hint_label.setStyleSheet(get_style("label_hint"))
        hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint_label)

    def load_sessions(self, filter_params: dict, sessions: list):
        self.current_filter = filter_params
        self.current_sessions = list(sessions)

        filter_text = f"📅 {filter_params.get('start_date', '')} ~ {filter_params.get('end_date', '')}"
        if filter_params.get('mode'):
            filter_text += f" | {filter_params['mode']}"
        filter_text += f" | 专注度: {filter_params.get('focus_min', 0)}-{filter_params.get('focus_max', 100)}"
        filter_text += f" | 异常: {filter_params.get('abnormal_min', 0)}-{filter_params.get('abnormal_max', 100)}"
        self.filter_info_label.setText(filter_text)

        self.record_table.setRowCount(len(sessions))

        for row, session in enumerate(sessions):
            bg_color = COLORS["background"] if row % 2 == 0 else COLORS["background_sidebar"]

            session_id = session.get("session_id", "")
            start_time = session.get("start_time", "")
            end_time = session.get("end_time", "")
            mode = session.get("mode", "")
            avg_focus = session.get("avg_focus_score", 0)
            abnormal_count = session.get("abnormal_event_count", 0)

            date_str = start_time.split(" ")[0] if " " in start_time else start_time
            time_start = start_time.split(" ")[1] if " " in start_time else start_time
            time_end = end_time.split(" ")[1] if " " in end_time else end_time

            items = [
                QTableWidgetItem(session_id),
                QTableWidgetItem(date_str),
                QTableWidgetItem(time_start),
                QTableWidgetItem(time_end),
                QTableWidgetItem(mode),
                QTableWidgetItem(f"{avg_focus:.1f}"),
                QTableWidgetItem(str(abnormal_count))
            ]

            for col, item in enumerate(items):
                item.setForeground(QColor(COLORS["text"]))
                item.setBackground(QColor(bg_color))
                item.setTextAlignment(Qt.AlignCenter)
                self.record_table.setItem(row, col, item)

            focus_item = self.record_table.item(row, 5)
            if avg_focus >= 70:
                focus_item.setForeground(QColor(COLORS["focus_high"]))
            elif avg_focus < 50:
                focus_item.setForeground(QColor(COLORS["focus_low"]))
            else:
                focus_item.setForeground(QColor(COLORS["focus_medium"]))

    def on_record_clicked(self, item):
        row = item.row()
        if row < len(self.current_sessions):
            session_data = self.current_sessions[row]
            print(f"[DataRecordWidget] 点击会话记录:")
            print(f"  会话ID: {session_data.get('session_id')}")
            print(f"  日期: {session_data.get('start_time', '').split(' ')[0] if ' ' in session_data.get('start_time', '') else session_data.get('start_time')}")
            print(f"  时间范围: {session_data.get('start_time')} ~ {session_data.get('end_time')}")
            print(f"  模式: {session_data.get('mode')}")
            print(f"  平均专注度: {session_data.get('avg_focus_score')}")
            print(f"  异常事件数: {session_data.get('abnormal_event_count')}")
            print(f"  --- 查询专注度评分记录条件 ---")
            print(f"  session_id: {session_data.get('session_id')}")
            print(f"  start_time: {session_data.get('start_time')}")
            print(f"  end_time: {session_data.get('end_time')}")
            self.session_selected.emit(session_data)
