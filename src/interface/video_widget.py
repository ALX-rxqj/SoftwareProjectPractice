from enum import Enum

from PyQt5.QtCore import (
    Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint,
)
from PyQt5.QtGui import QPixmap, QImage, QFont, QPainter, QPen, QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QHBoxLayout, QGraphicsOpacityEffect,
)

from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing
from .styles.effects import create_card_shadow


class ToastState(Enum):
    IDLE = 0
    FADING_IN = 1
    VISIBLE = 2
    FADING_OUT = 3


class ToastWidget(QFrame):
    """悬浮告警提示，淡入淡出。Qt.Tool 窗口跟随父窗口生命周期，失焦自动隐藏。"""

    def __init__(self, anchor=None):
        super().__init__(None)
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._anchor = anchor
        self._state = ToastState.IDLE
        self._current_content = None
        self._pending_content = None
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_in = None
        self._fade_out = None
        self._dismiss_timer = None
        self._init_ui()
        self.hide()

    def _init_ui(self):
        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._indicator = QFrame()
        self._indicator.setFixedWidth(4)
        layout.addWidget(self._indicator)

        text_container = QFrame()
        text_container.setStyleSheet(
            f"background-color: rgba(22, 27, 34, 0.92);"
        )
        text_layout = QHBoxLayout(text_container)
        text_layout.setContentsMargins(14, 0, 20, 0)
        text_layout.setSpacing(6)

        self._type_label = QLabel()
        self._type_label.setFont(QFont(*get_font("base", "bold", "ui")))
        self._detail_label = QLabel()
        self._detail_label.setFont(QFont(*get_font("base", "normal", "ui")))
        self._detail_label.setStyleSheet(
            f"color: {COLORS['text']}; background: transparent;"
        )
        text_layout.addWidget(self._type_label)
        text_layout.addWidget(self._detail_label)
        text_layout.addStretch()
        layout.addWidget(text_container)

    def show_toast(self, alert_type: str, detail: str):
        new_content = (alert_type, detail)

        if self._state == ToastState.IDLE:
            self._current_content = new_content
            self._update_content(alert_type, detail)
            self._transition_to(ToastState.FADING_IN)
            self._start_fade_in()

        elif self._state == ToastState.FADING_IN:
            if new_content == self._current_content:
                return
            self._cancel_animations()
            self._current_content = new_content
            self._update_content(alert_type, detail)
            self._transition_to(ToastState.FADING_IN)
            self._start_fade_in()

        elif self._state == ToastState.VISIBLE:
            if new_content == self._current_content:
                return
            self._pending_content = new_content
            self._transition_to(ToastState.FADING_OUT)
            self._start_fade_out()

        else:  # FADING_OUT
            if new_content == self._pending_content:
                return
            self._cancel_animations()
            self._current_content = new_content
            self._pending_content = None
            self._update_content(alert_type, detail)
            self._transition_to(ToastState.FADING_IN)
            self._start_fade_in()

    def dismiss(self):
        self._cancel_animations()
        self._opacity_effect.setOpacity(0.0)
        self.hide()
        self._state = ToastState.IDLE
        self._current_content = None
        self._pending_content = None
        self._remove_anchor_filter()

    def _transition_to(self, state: ToastState):
        self._state = state

    def _update_content(self, alert_type: str, detail: str):
        if alert_type in ("no_face", "multi_face"):
            self._indicator_color = COLORS["danger"]
        else:
            self._indicator_color = COLORS["warning"]
        self._indicator.setStyleSheet(
            f"background-color: {self._indicator_color};"
        )
        self._type_label.setText(f"[{alert_type}]")
        self._type_label.setStyleSheet(
            f"color: {self._indicator_color}; background: transparent;"
        )
        self._detail_label.setText(detail)

    def _start_fade_in(self):
        if self._anchor is not None:
            self._anchor.installEventFilter(self)
        self._position_over_anchor()
        self.show()
        self.raise_()
        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(self._opacity_effect.opacity())
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_in.finished.connect(self._on_fade_in_done)
        self._fade_in.start()

    def _on_fade_in_done(self):
        self._fade_in = None
        self._transition_to(ToastState.VISIBLE)
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._start_fade_out)
        self._dismiss_timer.start(3000)

    def _start_fade_out(self):
        self._dismiss_timer = None
        self._transition_to(ToastState.FADING_OUT)
        self._fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out.setDuration(200)
        self._fade_out.setStartValue(self._opacity_effect.opacity())
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.InCubic)
        self._fade_out.finished.connect(self._on_fade_out_done)
        self._fade_out.start()

    def _on_fade_out_done(self):
        self._fade_out = None
        self._state = ToastState.IDLE
        if self._pending_content is not None:
            content = self._pending_content
            self._pending_content = None
            self._current_content = content
            self._update_content(content[0], content[1])
            self._transition_to(ToastState.FADING_IN)
            self._start_fade_in()
        else:
            self.hide()
            self._remove_anchor_filter()

    def _remove_anchor_filter(self):
        if self._anchor is not None:
            try:
                self._anchor.removeEventFilter(self)
            except Exception:
                pass

    def _cancel_animations(self):
        for anim in (self._fade_in, self._fade_out):
            if anim is not None:
                try:
                    anim.finished.disconnect()
                except TypeError:
                    pass
                anim.stop()
        self._fade_in = None
        self._fade_out = None
        if self._dismiss_timer is not None:
            try:
                self._dismiss_timer.timeout.disconnect()
            except TypeError:
                pass
            self._dismiss_timer.stop()
            self._dismiss_timer = None

    def _position_over_anchor(self):
        if self._anchor is None:
            return
        top_left = self._anchor.mapToGlobal(QPoint(0, 0))
        pw = self._anchor.width()
        ph = self._anchor.height()
        toast_w = int(pw * 0.78)
        x = top_left.x() + (pw - toast_w) // 2
        y = top_left.y() + ph - self.height() - get_spacing("md")
        self.setGeometry(x, y, toast_w, self.height())

    def eventFilter(self, obj, event):
        if obj is self._anchor and event.type() in (event.Move, event.Resize):
            if self._state != ToastState.IDLE:
                self._position_over_anchor()
        return False


class VideoWidget(QFrame):
    frame_updated = pyqtSignal(dict)
    _render_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(get_style("card_elevated_glass"))
        self.setGraphicsEffect(create_card_shadow(elevated=True))
        self.is_running = False
        self.current_frame_data = None
        self._show_face_boxes = False
        self._current_face_boxes = []
        self.init_ui()
        self._render_requested.connect(self._do_render)

    def render_frame(self, data):
        """子线程安全：仅存储数据并 emit 信号，实际渲染由主线程 _do_render 执行"""
        if not self.is_running:
            return
        self.current_frame_data = data
        self._current_face_boxes = list(data.faces) if data.faces else []
        self.frame_updated.emit({
            "faces": data.faces,
            "timestamp": data.timestamp,
        })
        self._render_requested.emit(data)

    def _do_render(self, data):
        """在主线程执行 Qt 渲染操作"""
        if not self.is_running:
            return
        self.update_frame(data)

    def update_frame(self, processed_data=None):
        if processed_data is None:
            processed_data = self.current_frame_data
        if processed_data is None:
            return
        if hasattr(processed_data, 'frame') and hasattr(processed_data, 'faces'):
            self._render_frame_with_faces(processed_data.frame, processed_data.faces)
        else:
            self._render_frame_with_faces(None, [])

    def _render_frame_with_faces(self, frame, faces):
        if frame is None:
            return
        try:
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                rgb_frame = frame[:, :, ::-1]
                h, w, ch = rgb_frame.shape
                qt_image = QImage(rgb_frame.data.tobytes(), w, h, ch * w, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qt_image)
                scaled_pixmap = pixmap.scaled(
                    self.video_label.width(), self.video_label.height(),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )

                if self._show_face_boxes and self._current_face_boxes:
                    painter = QPainter(scaled_pixmap)
                    pen = QPen(QColor(COLORS["focus_high"]), 2)
                    painter.setPen(pen)
                    scale_x = scaled_pixmap.width() / w
                    scale_y = scaled_pixmap.height() / h
                    for face in self._current_face_boxes:
                        bbox = face.get("bbox", [])
                        if len(bbox) == 4:
                            x, y, bw, bh = bbox
                            painter.drawRect(
                                int(x * scale_x), int(y * scale_y),
                                int(bw * scale_x), int(bh * scale_y),
                            )
                    painter.end()

                self.video_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"[VideoWidget] 帧渲染错误: {e}")

    def set_show_face_boxes(self, enabled: bool):
        self._show_face_boxes = enabled
        if not enabled:
            self._current_face_boxes = []
        self.update_frame()

    def set_face_boxes(self, boxes: list):
        self._current_face_boxes = list(boxes)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            get_spacing("md"), get_spacing("md"),
            get_spacing("md"), get_spacing("md"),
        )
        layout.setSpacing(get_spacing("base"))

        # ---- 视频显示区 ----
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setText("等待预处理模块接入...")
        self.video_label.setFont(QFont(*get_font("base", "normal", "ui")))
        self.video_label.setStyleSheet(get_style("video_placeholder"))
        layout.addWidget(self.video_label)

        # ---- 告警 Toast ----
        self.toast = ToastWidget(anchor=self)

    def show_toast(self, alert_type: str, detail: str):
        self.toast.show_toast(alert_type, detail)

    def dismiss_toast(self):
        self.toast.dismiss()

    def start_processing(self):
        self.is_running = True
        self.video_label.setText("预处理模块运行中...")
        self.video_label.setStyleSheet(
            f"color: {COLORS['focus_high']}; "
            f"background-color: {COLORS['background']}; "
            f"border-radius: {SIZES['radius']['base']}px;"
        )

    def stop_processing(self):
        self.is_running = False
        self.video_label.clear()
        self.current_frame_data = None
        self._current_face_boxes = []
        self.video_label.setText("等待预处理模块接入...")
        self.video_label.setStyleSheet(get_style("video_placeholder"))

    def set_preprocessing_callback(self, callback):
        pass
