from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout
)

from .config import RIGHT_PANEL_WIDTH, FONT_FAMILY


class DataRecordWidget(QFrame):
    record_selected = pyqtSignal(dict)
    record_deleted = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(RIGHT_PANEL_WIDTH)
        self.setStyleSheet("background-color: #1A1A3A; border-radius: 8px;")
        self.current_face_id = None
        self.current_records = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        header_layout = QHBoxLayout()
        title_label = QLabel("分析记录")
        title_label.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title_label.setStyleSheet("color: #FFFFFF;")

        self.face_id_label = QLabel("")
        self.face_id_label.setFont(QFont(FONT_FAMILY, 11))
        self.face_id_label.setStyleSheet("color: #AAAAAA; background-color: #252545; padding: 4px 12px; border-radius: 12px;")

        header_layout.addWidget(title_label)
        header_layout.addWidget(self.face_id_label)
        header_layout.addStretch()

        self.delete_btn = QPushButton("🗑️ 删除")
        self.delete_btn.setFont(QFont(FONT_FAMILY, 11))
        self.delete_btn.setFixedSize(80, 32)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                color: #FFFFFF;
                background-color: #4A2A3A;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #5A3A4A;
            }
            QPushButton:disabled {
                background-color: #2A2A3A;
                color: #666666;
            }
        """)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        header_layout.addWidget(self.delete_btn)

        layout.addLayout(header_layout)

        self.record_table = QTableWidget()
        self.record_table.setColumnCount(6)
        self.record_table.setHorizontalHeaderLabels(["日期", "时间", "会话ID", "专注度", "表情评分", "行为评分"])
        self.record_table.setFont(QFont(FONT_FAMILY, 11))
        self.record_table.setStyleSheet("""
            QTableWidget {
                background-color: #0F0F25;
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                gridline-color: #2D2D5A;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #2D2D5A;
            }
            QTableWidget::item:selected {
                background-color: #353560;
            }
            QHeaderView::section {
                background-color: #252545;
                color: #AAAAAA;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #353560;
                font-weight: bold;
            }
        """)
        self.record_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.record_table.verticalHeader().setVisible(False)
        self.record_table.setAlternatingRowColors(False)
        self.record_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.record_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.record_table.itemClicked.connect(self.on_record_clicked)
        layout.addWidget(self.record_table)

        hint_label = QLabel("选中记录后点击删除按钮移除")
        hint_label.setFont(QFont(FONT_FAMILY, 10))
        hint_label.setStyleSheet("color: #888888;")
        hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint_label)

    def load_records(self, face_id, records):
        self.current_face_id = face_id
        self.current_records = list(records)
        self.face_id_label.setText(f"👤 {face_id}")
        self.record_table.setRowCount(len(records))

        for row, record in enumerate(records):
            bg_color = "#0F0F25" if row % 2 == 0 else "#1A1A3A"

            date_item = QTableWidgetItem(record.get("date", ""))
            time_item = QTableWidgetItem(record.get("time", ""))
            session_item = QTableWidgetItem(record.get("session_id", ""))
            focus_item = QTableWidgetItem(f"{record.get('focus_score', 0):.1f}")
            expression_item = QTableWidgetItem(str(record.get("expression_score", 0)))
            behavior_item = QTableWidgetItem(str(record.get("behavior_score", 0)))

            for item in [date_item, time_item, session_item, focus_item, expression_item, behavior_item]:
                item.setTextAlignment(Qt.AlignCenter)
                item.setBackground(QColor(bg_color))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            self.record_table.setItem(row, 0, date_item)
            self.record_table.setItem(row, 1, time_item)
            self.record_table.setItem(row, 2, session_item)
            self.record_table.setItem(row, 3, focus_item)
            self.record_table.setItem(row, 4, expression_item)
            self.record_table.setItem(row, 5, behavior_item)

        self.delete_btn.setEnabled(False)

    def clear_records(self):
        self.current_face_id = None
        self.current_records = []
        self.face_id_label.setText("")
        self.record_table.setRowCount(0)
        self.delete_btn.setEnabled(False)

    def on_record_clicked(self, item):
        row = item.row()
        self.record_table.selectRow(row)
        self.delete_btn.setEnabled(True)

        record_data = {
            "date": self.record_table.item(row, 0).text(),
            "time": self.record_table.item(row, 1).text(),
            "session_id": self.record_table.item(row, 2).text(),
            "focus_score": float(self.record_table.item(row, 3).text()),
            "expression_score": int(self.record_table.item(row, 4).text()),
            "behavior_score": int(self.record_table.item(row, 5).text())
        }
        self.record_selected.emit(record_data)

    def on_delete_clicked(self):
        selected_rows = self.record_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        record_data = {
            "date": self.record_table.item(row, 0).text(),
            "time": self.record_table.item(row, 1).text(),
            "session_id": self.record_table.item(row, 2).text(),
            "focus_score": float(self.record_table.item(row, 3).text()),
            "expression_score": int(self.record_table.item(row, 4).text()),
            "behavior_score": int(self.record_table.item(row, 5).text())
        }

        self.record_table.removeRow(row)
        self.current_records.pop(row)

        if self.current_face_id:
            self.record_deleted.emit(self.current_face_id, record_data)

        self.delete_btn.setEnabled(False)
