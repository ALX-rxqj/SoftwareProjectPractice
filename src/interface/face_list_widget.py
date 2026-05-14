from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QHBoxLayout
)

from .config import LEFT_BAR_WIDTH
from .styles import COLORS, get_style, get_font, get_spacing


class FaceListWidget(QFrame):
    session_selected = pyqtSignal(dict)
    face_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(LEFT_BAR_WIDTH)
        self.setStyleSheet(get_style("frame_card"))
        self.current_face_id = None
        self.current_sessions = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            get_spacing("base"), get_spacing("base"),
            get_spacing("base"), get_spacing("base"),
        )
        layout.setSpacing(get_spacing("base"))

        header_layout = QHBoxLayout()
        title_label = QLabel("会话列表")
        title_label.setFont(QFont(*get_font("lg", "bold", "display")))
        title_label.setStyleSheet(get_style("label_title"))

        self.face_id_label = QLabel("")
        self.face_id_label.setFont(QFont(*get_font("sm", "normal", "ui")))
        self.face_id_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; "
            f"background-color: {COLORS['card']}; "
            f"padding: 4px 12px; border-radius: 12px;"
        )

        header_layout.addWidget(title_label)
        header_layout.addWidget(self.face_id_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.session_list = QListWidget()
        self.session_list.setFont(QFont(*get_font("sm", "normal", "ui")))
        self.session_list.setStyleSheet(get_style("list_widget"))
        self.session_list.setCursor(Qt.PointingHandCursor)
        self.session_list.itemClicked.connect(self.on_session_clicked)
        layout.addWidget(self.session_list)

        hint_label = QLabel("点击左侧会话查看分析记录")
        hint_label.setFont(QFont(*get_font("xs", "normal", "ui")))
        hint_label.setStyleSheet(get_style("label_hint"))
        hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint_label)

    def load_face_ids(self, face_ids):
        if face_ids:
            self.current_face_id = face_ids[0]
            self.face_id_label.setText(f"{self.current_face_id}")
        else:
            self.current_face_id = None
            self.face_id_label.setText("")
        self.current_sessions = []
        self.session_list.clear()

    def load_sessions(self, face_id: str, sessions: list):
        self.current_face_id = face_id
        self.current_sessions = list(sessions)
        self.face_id_label.setText(f"{face_id}")
        self.session_list.clear()

        for session in sessions:
            avg_score = session.get("avg_focus_score", 0)
            if avg_score >= 70:
                score_color = COLORS["focus_high"]
            elif avg_score < 50:
                score_color = COLORS["focus_low"]
            else:
                score_color = COLORS["focus_medium"]

            session_id = session.get("session_id", "")
            mode = session.get("mode", "")
            start_time = session.get("start_time", "")
            end_time = session.get("end_time", "")
            abnormal_count = session.get("abnormal_event_count", 0)

            display_text = (
                f"{session_id}\n"
                f"   {mode} | {start_time.split(' ')[-1]} ~ {end_time.split(' ')[-1]}\n"
                f"   {avg_score:.1f} | {abnormal_count}"
            )

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
