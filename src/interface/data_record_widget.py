from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QHBoxLayout,
)

from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing
from .styles.effects import create_card_shadow


class DataRecordWidget(QFrame):
    session_selected = pyqtSignal(dict)
    record_deleted = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(400)
        self.setStyleSheet(get_style("card_elevated_glass"))
        self.setGraphicsEffect(create_card_shadow(elevated=True))
        self.current_filter = {}
        self.current_sessions = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            get_spacing("xl"), get_spacing("xl"),
            get_spacing("xl"), get_spacing("xl"),
        )
        layout.setSpacing(get_spacing("xl"))

        header_layout = QHBoxLayout()
        title_label = QLabel("会话列表")
        title_label.setFont(QFont(*get_font("xl", "bold", "display")))
        title_label.setStyleSheet(get_style("label_title"))

        self.filter_info_label = QLabel("")
        self.filter_info_label.setFont(QFont(*get_font("xs", "normal", "ui")))
        self.filter_info_label.setStyleSheet(get_style("badge_success"))

        header_layout.addWidget(title_label)
        header_layout.addWidget(self.filter_info_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.record_table = QTableWidget()
        self.record_table.setColumnCount(7)
        self.record_table.setHorizontalHeaderLabels([
            "会话 ID", "日期", "开始时间", "结束时间",
            "模式", "平均专注度", "异常事件",
        ])
        self.record_table.setFont(QFont(*get_font("sm", "normal", "data")))
        self.record_table.setStyleSheet(get_style("table_enhanced"))
        self.record_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.record_table.verticalHeader().setVisible(False)
        self.record_table.setAlternatingRowColors(False)
        self.record_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.record_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.record_table.verticalHeader().setDefaultSectionSize(44)
        self.record_table.itemClicked.connect(self.on_record_clicked)
        self.record_table.cellEntered.connect(self._on_row_hover)
        self._hovered_row = -1
        self._hover_color = QColor(122, 92, 255, 20)
        layout.addWidget(self.record_table)

        hint_label = QLabel("点击会话记录查看详情")
        hint_label.setFont(QFont(*get_font("xs", "normal", "ui")))
        hint_label.setStyleSheet(get_style("label_hint"))
        hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint_label)

    def load_sessions(self, filter_params: dict, sessions: list):
        self.current_filter = filter_params
        self.current_sessions = list(sessions)

        parts = [f"{filter_params.get('start_date', '')} ~ {filter_params.get('end_date', '')}"]
        if filter_params.get("mode"):
            mode_display = {"class": "网课模式", "exam": "考试模式"}.get(
                filter_params["mode"], filter_params["mode"]
            )
            parts.append(mode_display)
        parts.append(f"专注度: {filter_params.get('focus_min', 0)}-{filter_params.get('focus_max', 100)}")
        parts.append(f"异常: {filter_params.get('abnormal_min', 0)}-{filter_params.get('abnormal_max', 100)}")
        self.filter_info_label.setText(" | ".join(parts))

        self.record_table.setRowCount(len(sessions))

        for row, session in enumerate(sessions):
            session_id = session.get("session_id", "")
            start_time = session.get("start_time", "")
            end_time = session.get("end_time", "")
            mode = {"class": "网课模式", "exam": "考试模式"}.get(
                session.get("mode", ""), session.get("mode", "")
            )
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
                QTableWidgetItem(str(abnormal_count)),
            ]

            for col, item in enumerate(items):
                item.setForeground(QColor(COLORS["text"]))
                item.setTextAlignment(Qt.AlignCenter)
                self.record_table.setItem(row, col, item)

            focus_item = self.record_table.item(row, 5)
            if avg_focus >= 70:
                focus_item.setForeground(QColor(COLORS["focus_high"]))
            elif avg_focus < 50:
                focus_item.setForeground(QColor(COLORS["focus_low"]))
            else:
                focus_item.setForeground(QColor(COLORS["focus_medium"]))

    def _on_row_hover(self, row: int, col: int):
        if row == self._hovered_row:
            return
        # 清除上一行 hover 效果
        if self._hovered_row >= 0 and self._hovered_row < self.record_table.rowCount():
            if not self.record_table.selectionModel().isRowSelected(self._hovered_row, 0):
                for c in range(self.record_table.columnCount()):
                    item = self.record_table.item(self._hovered_row, c)
                    if item:
                        item.setBackground(QColor(0, 0, 0, 0))
        # 设置新行 hover 效果
        if row >= 0 and not self.record_table.selectionModel().isRowSelected(row, 0):
            for c in range(self.record_table.columnCount()):
                item = self.record_table.item(row, c)
                if item:
                    item.setBackground(self._hover_color)
        self._hovered_row = row

    def on_record_clicked(self, item):
        row = item.row()
        if row < len(self.current_sessions):
            session_data = self.current_sessions[row]
            print(f"[DataRecordWidget] 点击会话记录: {session_data.get('session_id')}")
            self.session_selected.emit(session_data)
