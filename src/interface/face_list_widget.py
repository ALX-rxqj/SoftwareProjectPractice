from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout
)

from .config import LEFT_BAR_WIDTH, FONT_FAMILY


class FaceListWidget(QFrame):
    session_selected = pyqtSignal(dict)
    face_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(LEFT_BAR_WIDTH)
        self.setStyleSheet("background-color: #1A1A3A; border-radius: 8px;")
        self.current_face_id = None
        self.current_sessions = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        header_layout = QHBoxLayout()
        title_label = QLabel("会话列表")
        title_label.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title_label.setStyleSheet("color: #FFFFFF;")

        self.face_id_label = QLabel("")
        self.face_id_label.setFont(QFont(FONT_FAMILY, 11))
        self.face_id_label.setStyleSheet("color: #AAAAAA; background-color: #252545; padding: 4px 12px; border-radius: 12px;")

        header_layout.addWidget(title_label)
        header_layout.addWidget(self.face_id_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.session_list = QListWidget()
        self.session_list.setFont(QFont(FONT_FAMILY, 11))
        self.session_list.setStyleSheet("""
            QListWidget {
                background-color: #0F0F25;
                border: none;
                border-radius: 6px;
                padding: 8px;
                color: #FFFFFF;
            }
            QListWidget::item {
                background-color: #252545;
                border-radius: 6px;
                padding: 12px;
                margin-bottom: 6px;
            }
            QListWidget::item:selected {
                background-color: #353560;
                border: 1px solid #6666CC;
            }
            QListWidget::item:hover {
                background-color: #2A2A50;
            }
        """)
        self.session_list.itemClicked.connect(self.on_session_clicked)
        layout.addWidget(self.session_list)

        hint_label = QLabel("点击左侧会话查看分析记录")
        hint_label.setFont(QFont(FONT_FAMILY, 10))
        hint_label.setStyleSheet("color: #888888;")
        hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint_label)

    def load_face_ids(self, face_ids):
        if face_ids:
            self.current_face_id = face_ids[0]
            self.face_id_label.setText(f"👤 {self.current_face_id}")
        else:
            self.current_face_id = None
            self.face_id_label.setText("")
        self.current_sessions = []
        self.session_list.clear()

    def load_sessions(self, face_id: str, sessions: list):
        self.current_face_id = face_id
        self.current_sessions = list(sessions)
        self.face_id_label.setText(f"👤 {face_id}")
        self.session_list.clear()

        for session in sessions:
            avg_score = session.get("avg_focus_score", 0)
            score_color = "#00E080" if avg_score >= 70 else "#FF6B6B" if avg_score < 50 else "#FFB84D"

            session_id = session.get("session_id", "")
            mode = session.get("mode", "")
            start_time = session.get("start_time", "")
            end_time = session.get("end_time", "")
            abnormal_count = session.get("abnormal_event_count", 0)

            display_text = f"📋 {session_id}\n" \
                          f"   {mode} | {start_time.split(' ')[-1]} ~ {end_time.split(' ')[-1]}\n" \
                          f"   专注度: {avg_score:.1f} | 异常事件: {abnormal_count}"

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, session)
            self.session_list.addItem(item)

    def on_session_clicked(self, item):
        session_data = item.data(Qt.UserRole)
        if session_data:
            self.session_selected.emit(session_data)
            self.face_changed.emit(self.current_face_id)

    def get_current_face_id(self):
        return self.current_face_id

    def clear_sessions(self):
        self.current_sessions = []
        self.session_list.clear()
