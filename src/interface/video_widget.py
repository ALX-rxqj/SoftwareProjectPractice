from enum import Enum

import cv2
from PyQt5.QtCore import (
    Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint,
)
from PyQt5.QtGui import QPixmap, QImage, QFont, QPainter, QPen, QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QHBoxLayout, QGraphicsOpacityEffect,
    QSlider, QWidget,
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
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
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
        self._render_pending = False
        self.init_ui()
        self._render_requested.connect(self._do_render)

    def render_frame(self, data):
        """子线程安全：仅存储数据并 emit 信号，实际渲染由主线程 _do_render 执行。

        如果上一帧还未渲染完成则跳过当前帧，避免主线程事件队列积压。
        """
        if not self.is_running:
            return
        if self._render_pending:
            return
        self._render_pending = True
        self.current_frame_data = data
        self._current_face_boxes = list(data.faces) if data.faces else []
        self.frame_updated.emit({
            "faces": data.faces,
            "timestamp": data.timestamp,
        })
        self._render_requested.emit(data)

    def _do_render(self, data):
        """在主线程执行 Qt 渲染操作"""
        self._render_pending = False
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
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                qt_image = QImage(rgb_frame.data, w, h, ch * w, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qt_image)
                scaled_pixmap = pixmap.scaled(
                    self.video_label.width(), self.video_label.height(),
                    Qt.KeepAspectRatio, Qt.FastTransformation,
                )

                if self._show_face_boxes and self._current_face_boxes:
                    painter = QPainter(scaled_pixmap)
                    scale_x = scaled_pixmap.width() / w
                    scale_y = scaled_pixmap.height() / h

                    for face in self._current_face_boxes:
                        bbox = face.get("bbox", [])
                        if len(bbox) != 4:
                            continue
                        x, y, bw, bh = bbox
                        rx, ry = int(x * scale_x), int(y * scale_y)
                        rw, rh = int(bw * scale_x), int(bh * scale_y)

                        is_live = face.get("is_live", True)
                        is_matched = face.get("face_matched", False)

                        if not is_live:
                            # 活体不通过 → 红色 + "伪造!"
                            color = QColor(COLORS["focus_low"])
                            label = "伪造!"
                        elif not is_matched:
                            # 识别不通过 → 黄色 + "未知"
                            color = QColor(COLORS["focus_medium"])
                            label = "未知"
                        else:
                            # 正常识别 → 绿色 + 姓名
                            color = QColor(COLORS["focus_high"])
                            label = face.get("student_name", "")

                        # 边框
                        pen = QPen(color, 2)
                        painter.setPen(pen)
                        painter.drawRect(rx, ry, rw, rh)

                        # 标签背景 + 文字
                        font = QFont(*get_font("xs", "bold", "ui"))
                        painter.setFont(font)
                        fm = painter.fontMetrics()
                        label_w = max(fm.horizontalAdvance(label) + 12, 40)
                        label_h = fm.height() + 4
                        label_y = ry - label_h - 4
                        if label_y < 0:
                            label_y = ry + rh + 4
                        painter.fillRect(rx, label_y, label_w, label_h, color)
                        painter.setPen(QPen(QColor(255, 255, 255)))
                        painter.drawText(rx + 4, label_y, label_w - 8, label_h,
                                         Qt.AlignVCenter | Qt.AlignLeft, label)
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
        layout.addWidget(self.video_label, 1)

        # ---- 文件播放进度条（默认隐藏） ----
        self._progress_container = QWidget()
        self._progress_container.setFixedHeight(36)
        progress_layout = QHBoxLayout(self._progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(get_spacing("sm"))

        self._progress_label = QLabel("")
        self._progress_label.setFont(QFont(*get_font("xs", "normal", "data")))
        self._progress_label.setStyleSheet(f"color: {COLORS['text_hint']};")
        self._progress_label.setFixedWidth(100)

        self._progress_slider = QSlider(Qt.Horizontal)
        self._progress_slider.setEnabled(False)  # 只读，不可拖动
        self._progress_slider.setFixedHeight(20)
        self._progress_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {COLORS['card_hover']};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {COLORS['accent']};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: transparent;
                border: none;
                width: 0px;
            }}
        """)

        progress_layout.addWidget(self._progress_slider)
        progress_layout.addWidget(self._progress_label)
        self._progress_container.setVisible(False)
        layout.addWidget(self._progress_container)



    def show_loading_overlay(self, message: str = "正在初始化模型..."):
        if not hasattr(self, '_loading_overlay'):
            self._loading_overlay = _LoadingOverlay(self)
        self._loading_overlay.set_message(message)
        self._loading_overlay.show()
        self._loading_overlay.raise_()

    def update_loading_progress(self, message: str, progress: float):
        if hasattr(self, '_loading_overlay') and self._loading_overlay.isVisible():
            self._loading_overlay.set_message(f"{message} ({progress:.0%})")

    def hide_loading_overlay(self):
        if hasattr(self, '_loading_overlay'):
            self._loading_overlay.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay') and self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

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
        self.hide_progress_bar()

    def set_preprocessing_callback(self, callback):
        pass

    def show_progress_bar(self):
        """显示进度条（文件模式）"""
        self._progress_container.setVisible(True)

    def hide_progress_bar(self):
        """隐藏进度条（摄像头模式）"""
        self._progress_container.setVisible(False)
        self._progress_slider.setValue(0)
        self._progress_label.setText("")

    def update_progress(self, current_frame: int, total_frames: int):
        """更新进度条位置和文字

        Args:
            current_frame: 当前帧序号
            total_frames: 总帧数
        """
        if total_frames <= 0:
            return
        percentage = int(current_frame / total_frames * 100)
        self._progress_slider.setValue(percentage)
        self._progress_label.setText(f"{current_frame}/{total_frames}")


class _LoadingOverlay(QFrame):
    """视频区域半透明加载覆盖层"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            _LoadingOverlay {{
                background-color: rgba(13, 17, 23, 0.85);
                border-radius: {SIZES['radius']['base']}px;
            }}
        """)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        self._spinner = QLabel("⏳")
        self._spinner.setAlignment(Qt.AlignCenter)
        self._spinner.setFont(QFont(*get_font("xl", "bold", "display")))
        self._spinner.setStyleSheet("background: transparent;")
        layout.addWidget(self._spinner)

        self._message = QLabel("正在初始化模型...")
        self._message.setAlignment(Qt.AlignCenter)
        self._message.setFont(QFont(*get_font("lg", "normal", "ui")))
        self._message.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        layout.addWidget(self._message)

        self._progress_bar = QLabel()
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setStyleSheet(f"""
            background-color: {COLORS['primary']};
            border-radius: 1px;
        """)
        self._progress_bar.setFixedWidth(0)
        layout.addWidget(self._progress_bar, alignment=Qt.AlignCenter)

        self.setGeometry(parent.rect())
        self.hide()

    def set_message(self, text: str):
        self._message.setText(text)
        # 从文本中解析进度百分比，更新进度条
        import re
        match = re.search(r'(\d+)%', text)
        if match:
            pct = int(match.group(1)) / 100.0
        elif text.endswith(")"):
            match = re.search(r'\((\d+)%\)', text)
            pct = int(match.group(1)) / 100.0 if match else 0.0
        else:
            return  # 不更新进度条
        self._progress_bar.setFixedWidth(int(self.parent().width() * 0.4 * pct))

