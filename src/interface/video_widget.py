from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout

from .interface_manager import interface_manager, VideoFrameData
from .styles import COLORS, FONTS, SIZES, get_style, get_font, get_spacing
from .styles.effects import create_card_shadow


class VideoWidget(QFrame):
    warn_updated = pyqtSignal(str)
    frame_updated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(get_style("card_elevated_glass"))
        self.setGraphicsEffect(create_card_shadow(elevated=True))
        self.is_running = False
        self.current_frame_data = None
        self.init_ui()
        self._register_interface_callback()

    def _register_interface_callback(self):
        interface_manager.register_video_frame_callback(self.on_video_frame_received)

    def on_video_frame_received(self, data: VideoFrameData):
        if not self.is_running:
            return
        self.current_frame_data = data
        self.update_frame(data)
        self.frame_updated.emit({
            "faces": data.faces,
            "timestamp": data.timestamp,
        })

    def update_frame(self, processed_data=None):
        if processed_data is None:
            processed_data = self.current_frame_data
        if processed_data is None:
            return
        if isinstance(processed_data, VideoFrameData):
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
                self.video_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"[VideoWidget] 帧渲染错误: {e}")

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

        # ---- 警告栏 ----
        self.warn_bar = QFrame()
        self.warn_bar.setFixedHeight(52)
        self.warn_bar.setStyleSheet(get_style("warn_bar"))
        warn_layout = QHBoxLayout(self.warn_bar)
        warn_layout.setContentsMargins(
            get_spacing("base"), get_spacing("sm"),
            get_spacing("base"), get_spacing("sm"),
        )
        warn_icon = QFrame()
        warn_icon.setFixedSize(6, 6)
        warn_icon.setStyleSheet(
            f"background-color: {COLORS['danger']}; border-radius: 3px;"
        )
        self.warn_text = QLabel("当前专注度值低于阈值，请注意")
        self.warn_text.setFont(QFont(*get_font("base", "normal", "ui")))
        self.warn_text.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background: transparent;"
        )
        warn_layout.addWidget(warn_icon)
        warn_layout.addWidget(self.warn_text)
        warn_layout.addStretch()
        self.warn_bar.hide()
        layout.addWidget(self.warn_bar)

        self.warn_updated.connect(self.update_warn)

    def update_warn(self, text):
        if text:
            self.warn_text.setText(text)
            self.warn_bar.show()
        else:
            self.warn_bar.hide()

    def start_processing(self):
        self.is_running = True
        self.video_label.setText("预处理模块运行中...")
        self.video_label.setStyleSheet(
            f"color: {COLORS['focus_high']}; "
            f"background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.8, "
            f"fx:0.5, fy:0.5, stop:0 #1A1A3A, stop:1 {COLORS['background']}); "
            f"border-radius: {SIZES['radius']['base']}px;"
        )

    def stop_processing(self):
        self.is_running = False
        self.video_label.clear()
        self.current_frame_data = None
        self.video_label.setText("等待预处理模块接入...")
        self.video_label.setStyleSheet(get_style("video_placeholder"))

    def set_preprocessing_callback(self, callback):
        pass
