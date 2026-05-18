from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QHBoxLayout, QPushButton, QCheckBox,
)

from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing
from .styles.effects import create_card_shadow


class DataRecordWidget(QFrame):
    session_selected = pyqtSignal(dict)
    delete_requested = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(400)
        self.setStyleSheet(get_style("card_elevated_glass"))
        self.setGraphicsEffect(create_card_shadow(elevated=True))
        self.current_filter = {}
        self.current_sessions = []
        self._selection_mode = False
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

        # 选择模式控件
        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setFont(QFont(*get_font("sm", "bold", "ui")))
        self._btn_cancel.setFixedSize(60, SIZES["button"]["height"])
        self._btn_cancel.setCursor(Qt.PointingHandCursor)
        self._btn_cancel.setStyleSheet(get_style("button_select"))
        self._btn_cancel.clicked.connect(self._on_cancel_clicked)
        self._btn_cancel.setVisible(False)

        self._cb_select_all = QCheckBox("全选")
        self._cb_select_all.setFont(QFont(*get_font("sm", "normal", "ui")))
        self._cb_select_all.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self._cb_select_all.setTristate(True)
        self._cb_select_all.setVisible(False)
        self._cb_select_all.stateChanged.connect(self._on_select_all_changed)

        self._btn_select = QPushButton("选择")
        self._btn_select.setFont(QFont(*get_font("sm", "bold", "ui")))
        self._btn_select.setFixedSize(60, SIZES["button"]["height"])
        self._btn_select.setCursor(Qt.PointingHandCursor)
        self._btn_select.setStyleSheet(get_style("button_select"))
        self._btn_select.clicked.connect(self._on_select_toggle)

        self._btn_delete = QPushButton("删除")
        self._btn_delete.setFont(QFont(*get_font("sm", "bold", "ui")))
        self._btn_delete.setFixedSize(60, SIZES["button"]["height"])
        self._btn_delete.setCursor(Qt.PointingHandCursor)
        self._btn_delete.setStyleSheet(get_style("button_danger"))
        self._btn_delete.clicked.connect(self._on_delete_clicked)
        self._btn_delete.setVisible(False)

        header_layout.addWidget(title_label)
        header_layout.addWidget(self.filter_info_label)
        header_layout.addStretch()
        header_layout.addWidget(self._btn_cancel)
        header_layout.addWidget(self._cb_select_all)
        header_layout.addWidget(self._btn_select)
        header_layout.addWidget(self._btn_delete)
        layout.addLayout(header_layout)

        self.record_table = QTableWidget()
        # 9 列：col 0 = 勾选框（默认隐藏），col 1~8 = 数据
        self.record_table.setColumnCount(9)
        self.record_table.setHorizontalHeaderLabels([
            "", "会话 ID", "人脸 ID", "日期", "开始时间", "结束时间",
            "模式", "平均专注度", "异常事件",
        ])
        self.record_table.setFont(QFont(*get_font("sm", "normal", "data")))
        self.record_table.setStyleSheet(get_style("table_enhanced"))
        self.record_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.record_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.record_table.setColumnWidth(0, 40)
        self.record_table.setColumnHidden(0, True)
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
        if self._selection_mode:
            self._exit_selection_mode()
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
            # 第 0 列：勾选框（始终初始化，切换可见性控制）
            cb_item = QTableWidgetItem()
            cb_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            cb_item.setCheckState(Qt.Unchecked)
            self.record_table.setItem(row, 0, cb_item)

            session_id = session.get("session_id", "")
            face_id = session.get("face_id", "")
            start_time = session.get("start_time", "")
            end_time = session.get("end_time", "")
            mode = {"class": "网课模式", "exam": "考试模式"}.get(
                session.get("mode", ""), session.get("mode", "")
            )
            avg_focus = session.get("avg_focus_score") or 0.0
            abnormal_count = session.get("abnormal_event_count") or 0

            date_str = start_time.split(" ")[0] if " " in start_time else start_time
            time_start = start_time.split(" ")[1] if " " in start_time else start_time
            time_end = end_time.split(" ")[1] if " " in end_time else end_time

            # 数据列 col 1~8
            items = [
                QTableWidgetItem(session_id),
                QTableWidgetItem(face_id),
                QTableWidgetItem(date_str),
                QTableWidgetItem(time_start),
                QTableWidgetItem(time_end),
                QTableWidgetItem(mode),
                QTableWidgetItem(f"{avg_focus:.1f}"),
                QTableWidgetItem(str(abnormal_count)),
            ]

            for col_offset, item_ in enumerate(items):
                col = col_offset + 1
                item_.setForeground(QColor(COLORS["text"]))
                item_.setTextAlignment(Qt.AlignCenter)
                self.record_table.setItem(row, col, item_)

            focus_item = self.record_table.item(row, 7)
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
        if self._selection_mode:
            if item.column() != 0:
                # 点击勾选框列时 Qt 已通过 ItemIsUserCheckable 自动切换，跳过手动 toggle
                self._toggle_row_checkbox(item.row())
            self._update_select_all_state()
            return

        row = item.row()
        if row < len(self.current_sessions):
            session_data = self.current_sessions[row]
            print(f"[DataRecordWidget] 点击会话记录: {session_data.get('session_id')}")
            self.session_selected.emit(session_data)

    # ──────────────────── 选择/删除模式 ────────────────────

    def _on_select_toggle(self):
        self._enter_selection_mode()

    def _enter_selection_mode(self):
        self._selection_mode = True
        self._btn_select.setVisible(False)
        self._btn_cancel.setVisible(True)
        self._cb_select_all.setVisible(True)
        self._btn_delete.setVisible(True)
        self._cb_select_all.setChecked(False)
        self.record_table.setColumnHidden(0, False)

    def _exit_selection_mode(self):
        self._selection_mode = False
        self._btn_select.setVisible(True)
        self._btn_cancel.setVisible(False)
        self._cb_select_all.setVisible(False)
        self._btn_delete.setVisible(False)
        self.record_table.setColumnHidden(0, True)

    def _on_cancel_clicked(self):
        self._exit_selection_mode()

    def _toggle_row_checkbox(self, row: int):
        item = self.record_table.item(row, 0)
        if item and (item.flags() & Qt.ItemIsUserCheckable):
            new_state = Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
            item.setCheckState(new_state)

    def _update_select_all_state(self):
        checked = 0
        total = 0
        for row in range(self.record_table.rowCount()):
            item = self.record_table.item(row, 0)
            if item and (item.flags() & Qt.ItemIsUserCheckable):
                total += 1
                if item.checkState() == Qt.Checked:
                    checked += 1
        self._cb_select_all.blockSignals(True)
        if total == 0:
            self._cb_select_all.setCheckState(Qt.Unchecked)
        elif checked == total:
            self._cb_select_all.setCheckState(Qt.Checked)
        elif checked == 0:
            self._cb_select_all.setCheckState(Qt.Unchecked)
        else:
            self._cb_select_all.setCheckState(Qt.PartiallyChecked)
        self._cb_select_all.blockSignals(False)

    def _on_select_all_changed(self, state):
        if state == Qt.PartiallyChecked:
            self._cb_select_all.blockSignals(True)
            self._cb_select_all.setCheckState(Qt.Checked)
            self._cb_select_all.blockSignals(False)
            target = Qt.Checked
        elif state == Qt.Checked:
            target = Qt.Checked
        else:
            target = Qt.Unchecked
        for row in range(self.record_table.rowCount()):
            item = self.record_table.item(row, 0)
            if item and (item.flags() & Qt.ItemIsUserCheckable):
                item.setCheckState(target)

    def _get_checked_session_ids(self):
        session_ids = []
        for row in range(self.record_table.rowCount()):
            item = self.record_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                if row < len(self.current_sessions):
                    session_ids.append(self.current_sessions[row].get("session_id", ""))
        return session_ids

    def _on_delete_clicked(self):
        session_ids = self._get_checked_session_ids()
        if not session_ids:
            return
        self.delete_requested.emit(session_ids)

    def exit_selection_mode(self):
        """外部调用：完成删除后恢复正常模式"""
        self._exit_selection_mode()
