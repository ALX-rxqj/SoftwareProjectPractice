from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout

from .config import FONT_FAMILY
from .interface_manager import interface_manager, VideoFrameData


class VideoWidget(QFrame):
    warn_updated = pyqtSignal(str)
    frame_updated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #1A1A3A; border-radius: 8px;")
        self.is_running = False
        self.current_frame_data = None
        self.init_ui()
        self._register_interface_callback()

    def _register_interface_callback(self):
        """注册接口管理器的视频帧回调"""
        interface_manager.register_video_frame_callback(self.on_video_frame_received)

    def on_video_frame_received(self, data: VideoFrameData):
        """
        PRI-01: 接收预处理模块发送的视频帧数据
        用于画面渲染与人脸标注
        """
        self.current_frame_data = data
        self.update_frame(data)

    def update_frame(self, processed_data=None):
        """
        更新视频画面显示
        如果传入VideoFrameData，则渲染带标注的帧
        """
        if processed_data is None:
            processed_data = self.current_frame_data

        if processed_data is None:
            return

        if isinstance(processed_data, VideoFrameData):
            frame = processed_data.frame
            faces = processed_data.faces
            self._render_frame_with_faces(frame, faces)
        else:
            self._render_frame_with_faces(None, [])

    def _render_frame_with_faces(self, frame, faces):
        """
        渲染视频帧及人脸标注框

        Args:
            frame: BGR numpy array or None
            faces: list of {face_id:int, bbox:[x,y,w,h]}
        """
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
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.video_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"[VideoWidget] 帧渲染错误: {e}")

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 16)
        layout.setSpacing(16)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #0A0A1A; border-radius: 6px;")
        self.video_label.setText("等待预处理模块接入...")
        self.video_label.setFont(QFont(FONT_FAMILY, 13))
        self.video_label.setStyleSheet("color: #666666; background-color: #0A0A1A; border-radius: 6px;")
        layout.addWidget(self.video_label)

        self.warn_bar = QFrame()
        self.warn_bar.setFixedHeight(56)
        self.warn_bar.setStyleSheet("background-color: #4A1A2A; border-radius: 8px;")
        warn_layout = QHBoxLayout(self.warn_bar)
        warn_layout.setContentsMargins(20, 10, 20, 10)
        warn_icon = QLabel("📋")
        warn_icon.setFont(QFont(FONT_FAMILY, 13))
        self.warn_text = QLabel("当前xxx值低于阈值，请注意xxx")
        self.warn_text.setFont(QFont(FONT_FAMILY, 12))
        self.warn_text.setStyleSheet("color: #FFFFFF;")
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
        self.video_label.setStyleSheet("color: #00E0A0; background-color: #0A0A1A; border-radius: 6px;")

    def stop_processing(self):
        self.is_running = False
        self.video_label.setText("等待预处理模块接入...")
        self.video_label.setStyleSheet("color: #666666; background-color: #0A0A1A; border-radius: 6px;")
        self.video_label.clear()
        self.current_frame_data = None

    def set_preprocessing_callback(self, callback):
        pass
