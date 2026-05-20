"""告警信息弹窗 - Alert Info Dialog"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QSizePolicy,
)

from .styles import COLORS, SIZES, get_style, get_font, get_spacing


class AlertInfoDialog(QDialog):
    def __init__(self, session_data: dict, alerts: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("告警信息")
        self.setMinimumSize(780, 520)
        self.setMaximumSize(1000, 750)
        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(get_style("face_registration_dialog"))
        self.setModal(True)

        self._session_data = session_data
        self._alerts = alerts
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---- 标题栏 ----
        title_bar = QFrame()
        title_bar.setFixedHeight(48)
        title_bar.setStyleSheet(
            f"background-color: {COLORS['card']}; "
            f"border-top-left-radius: {SIZES['radius']['xxl']}px; "
            f"border-top-right-radius: {SIZES['radius']['xxl']}px;"
        )
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(
            get_spacing("xl"), get_spacing("sm"),
            get_spacing("md"), get_spacing("sm"),
        )

        session_id = self._session_data.get("session_id", "")
        short_id = session_id[-8:] if len(session_id) >= 8 else session_id
        title_label = QLabel(f"告警信息 - {short_id}")
        title_label.setFont(QFont(*get_font("lg", "bold", "ui")))
        title_label.setStyleSheet(
            f"color: {COLORS['text']}; background: transparent;"
        )

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 36)
        close_btn.setFont(QFont(*get_font("lg", "bold", "ui")))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                color: {COLORS['text_secondary']};
                background: transparent;
                border: none;
                border-radius: {SIZES['radius']['sm']}px;
            }}
            QPushButton:hover {{
                color: {COLORS['danger']};
                background-color: {COLORS['card_hover']};
            }}
        """)
        close_btn.clicked.connect(self.accept)

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(close_btn)
        main_layout.addWidget(title_bar)

        # ---- 分隔线 ----
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(get_style("divider_subtle"))
        main_layout.addWidget(sep)

        # ---- 内容区域 ----
        content = QVBoxLayout()
        content.setContentsMargins(
            get_spacing("xl"), get_spacing("lg"),
            get_spacing("xl"), get_spacing("xl"),
        )
        content.setSpacing(get_spacing("md"))

        if self._alerts:
            alert_label = QLabel(f"共 {len(self._alerts)} 条告警记录")
            alert_label.setFont(QFont(*get_font("base", "normal", "ui")))
            alert_label.setStyleSheet(
                f"color: {COLORS['text_secondary']}; background: transparent;"
            )
            content.addWidget(alert_label)

            # 滚动区域
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet(f"""
                QScrollArea {{
                    background-color: transparent;
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: {COLORS['background']};
                    width: 8px;
                    border-radius: 4px;
                }}
                QScrollBar::handle:vertical {{
                    background: {COLORS['border']};
                    border-radius: 4px;
                    min-height: 30px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: {COLORS['border_light']};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

            card_container = QWidget()
            card_container.setStyleSheet("background: transparent;")
            card_layout = QVBoxLayout(card_container)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(get_spacing("sm"))

            for alert in self._alerts:
                card = self._create_alert_card(alert)
                card_layout.addWidget(card)

            card_layout.addStretch()
            scroll.setWidget(card_container)
            content.addWidget(scroll)
        else:
            empty_label = QLabel("该会话暂无告警记录")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setFont(QFont(*get_font("lg", "normal", "ui")))
            empty_label.setStyleSheet(
                f"color: {COLORS['text_hint']}; background: transparent;"
            )
            content.addWidget(empty_label)

        main_layout.addLayout(content)

    def _create_alert_card(self, alert: dict) -> QFrame:
        """创建单条告警卡片：标题行 + 详情行"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['card']};
                border: 1px solid {COLORS['border']};
                border-radius: {SIZES['radius']['base']}px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            get_spacing("md"), get_spacing("sm"),
            get_spacing("md"), get_spacing("sm"),
        )
        layout.setSpacing(get_spacing("xs"))

        # ---- 标题行：课程ID | 时间 | 类型 ----
        title_row = QHBoxLayout()
        title_row.setSpacing(get_spacing("lg"))

        sid = alert.get("session_id", "")
        short_sid = sid[-8:] if len(sid) >= 8 else sid
        ts = alert.get("timestamp", 0)
        time_str = ""
        if ts:
            m = int(ts // 60)
            s = int(ts % 60)
            time_str = f"{m:02d}:{s:02d}"

        id_label = QLabel(f"课程ID: {short_sid}")
        id_label.setFont(QFont(*get_font("base", "bold", "ui")))
        id_label.setStyleSheet(
            f"color: {COLORS['text']}; background: transparent; border: none;"
        )

        time_label = QLabel(f"时间: {time_str}")
        time_label.setFont(QFont(*get_font("base", "normal", "ui")))
        time_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background: transparent; border: none;"
        )

        type_label = QLabel(f"类型: {alert.get('alert_type', '')}")
        type_label.setFont(QFont(*get_font("base", "bold", "ui")))
        type_label.setStyleSheet(
            f"color: {COLORS['warning']}; background: transparent; border: none;"
        )

        title_row.addWidget(id_label)
        title_row.addWidget(time_label)
        title_row.addWidget(type_label)
        title_row.addStretch()
        layout.addLayout(title_row)

        # ---- 详情行 ----
        detail_label = QLabel(alert.get("detail", ""))
        detail_label.setFont(QFont(*get_font("sm", "normal", "ui")))
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet(
            f"color: {COLORS['text_hint']}; background: transparent; border: none;"
        )
        layout.addWidget(detail_label)

        return card
