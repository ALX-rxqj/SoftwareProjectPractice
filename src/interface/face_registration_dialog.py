"""
人脸注册弹窗 - Face Registration Dialog
流程：授权页 → 采集页（4姿势关键帧 + 自动采样）→ 完成页
"""

from collections import deque
import time

import numpy as np
from PyQt5.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QPoint, QSize,
)
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QStackedWidget, QWidget,
    QLabel, QPushButton, QLineEdit, QFrame, QMessageBox,
)

from .styles import COLORS, SIZES, get_style, get_font, get_spacing
from .interface_manager import interface_manager

# 4 个采集姿势
POSE_GUIDES = [
    "请正对摄像头，保持面部居中",
    "请将头部转向左侧",
    "请将头部转向右侧",
    "请略微低头，俯视摄像头",
]

POSE_NAMES = ["正脸", "左侧脸", "右侧脸", "俯视"]

AUTO_SAMPLE_COUNT = 15
BUFFER_SECONDS = 30
FPS_ESTIMATE = 15
BUFFER_MAX = BUFFER_SECONDS * FPS_ESTIMATE  # 450


class FaceRegistrationDialog(QDialog):
    """人脸注册弹窗"""

    registration_completed = pyqtSignal(dict)
    _camera_started_externally = False

    def __init__(self, device_id: int, parent=None):
        super().__init__(parent)
        self._device_id = device_id
        self._student_name = ""
        self._current_pose = 0
        self._capture_started = False
        self._buffer_start_time: float = 0.0
        self._keyframe_ts: list = []
        self._collected_frames: list = []
        self._frame_buffer: deque = deque(maxlen=BUFFER_MAX)

        self.setWindowTitle("人脸注册")
        self.setMinimumSize(700, 600)
        self.setMaximumSize(800, 700)
        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(get_style("face_registration_dialog"))
        self.setModal(True)

        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 标题栏（带关闭按钮）
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

        title_label = QLabel("人脸注册")
        title_label.setFont(QFont(*get_font("lg", "bold", "display")))
        title_label.setStyleSheet(
            f"color: {COLORS['text']}; background: transparent;"
        )

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(36, 36)
        self.close_btn.setFont(QFont(*get_font("lg", "bold", "ui")))
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
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
        self.close_btn.clicked.connect(self.reject)

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.close_btn)

        main_layout.addWidget(title_bar)

        # 分隔线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(get_style("divider_subtle"))
        main_layout.addWidget(sep)

        # 页面栈
        self.stacked = QStackedWidget()
        self.stacked.setContentsMargins(0, 0, 0, 0)
        self.stacked.addWidget(self._create_auth_page())
        self.stacked.addWidget(self._create_capture_page())
        self.stacked.addWidget(self._create_completion_page())
        self.stacked.setCurrentIndex(0)
        main_layout.addWidget(self.stacked)

    # ─── 授权页 ───────────────────────────────────────

    def _create_auth_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            get_spacing("xxl"), get_spacing("xxl"),
            get_spacing("xxl"), get_spacing("xxl"),
        )
        layout.setSpacing(get_spacing("lg"))

        layout.addStretch()

        icon_label = QLabel("📷")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFont(QFont(*get_font("hero", "normal", "display")))
        icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(icon_label)

        notice_title = QLabel("需要打开摄像头")
        notice_title.setAlignment(Qt.AlignCenter)
        notice_title.setFont(QFont(*get_font("xl", "bold", "display")))
        notice_title.setStyleSheet(
            f"color: {COLORS['text']}; background: transparent;"
        )
        layout.addWidget(notice_title)

        notice_text = QLabel(
            "为完成人脸注册，需要开启摄像头采集\n"
            "正脸、左侧脸、右侧脸、俯视四个视角的人脸图像。"
        )
        notice_text.setAlignment(Qt.AlignCenter)
        notice_text.setFont(QFont(*get_font("base", "normal", "ui")))
        notice_text.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background: transparent;"
        )
        layout.addWidget(notice_text)

        layout.addSpacing(get_spacing("md"))

        name_layout = QHBoxLayout()
        name_layout.addStretch()
        name_label = QLabel("学生姓名：")
        name_label.setFont(QFont(*get_font("base", "medium", "ui")))
        name_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background: transparent;"
        )
        self.name_input = QLineEdit()
        self.name_input.setFixedWidth(260)
        self.name_input.setPlaceholderText("请输入学生姓名")
        self.name_input.setFont(QFont(*get_font("base", "normal", "ui")))
        self.name_input.setStyleSheet(get_style("input_field_dialog"))
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        name_layout.addStretch()
        layout.addLayout(name_layout)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.setSpacing(get_spacing("md"))

        self.auth_cancel_btn = QPushButton("取消")
        self.auth_cancel_btn.setFixedSize(120, 42)
        self.auth_cancel_btn.setFont(QFont(*get_font("base", "medium", "ui")))
        self.auth_cancel_btn.setCursor(Qt.PointingHandCursor)
        self.auth_cancel_btn.setStyleSheet(get_style("button_secondary"))
        self.auth_cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.auth_cancel_btn)

        self.auth_agree_btn = QPushButton("同意并继续")
        self.auth_agree_btn.setFixedSize(140, 42)
        self.auth_agree_btn.setFont(QFont(*get_font("base", "bold", "ui")))
        self.auth_agree_btn.setCursor(Qt.PointingHandCursor)
        self.auth_agree_btn.setStyleSheet(get_style("button_glow"))
        self.auth_agree_btn.clicked.connect(self._on_auth_agree)
        btn_layout.addWidget(self.auth_agree_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        return page

    # ─── 采集页 ───────────────────────────────────────

    def _create_capture_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            get_spacing("xl"), get_spacing("lg"),
            get_spacing("xl"), get_spacing("xl"),
        )
        layout.setSpacing(get_spacing("md"))

        # 姿势引导文字
        self.pose_guide_label = QLabel(POSE_GUIDES[0])
        self.pose_guide_label.setAlignment(Qt.AlignCenter)
        self.pose_guide_label.setFont(QFont(*get_font("xl", "bold", "display")))
        self.pose_guide_label.setStyleSheet(get_style("pose_guide_label"))
        layout.addWidget(self.pose_guide_label)

        # 进度指示
        self.progress_label = QLabel(f"1 / {len(POSE_GUIDES)}")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setFont(QFont(*get_font("sm", "normal", "ui")))
        self.progress_label.setStyleSheet(
            f"color: {COLORS['text_hint']}; background: transparent;"
        )
        layout.addWidget(self.progress_label)

        # 视频显示区
        video_frame = QFrame()
        video_frame.setStyleSheet(
            f"background-color: {COLORS['background']}; "
            f"border-radius: {SIZES['radius']['lg']}px; "
            f"border: 1px solid {COLORS['border']};"
        )
        video_layout = QVBoxLayout(video_frame)
        video_layout.setContentsMargins(0, 0, 0, 0)

        self.video_display = QLabel()
        self.video_display.setAlignment(Qt.AlignCenter)
        self.video_display.setMinimumHeight(380)
        self.video_display.setText("摄像头画面加载中...")
        self.video_display.setFont(QFont(*get_font("base", "normal", "ui")))
        self.video_display.setStyleSheet(
            f"color: {COLORS['text_hint']}; "
            f"background-color: {COLORS['background']};"
        )
        video_layout.addWidget(self.video_display)
        layout.addWidget(video_frame)

        # 拍摄按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.capture_btn = QPushButton("📷 拍摄关键帧")
        self.capture_btn.setMinimumSize(180, 48)
        self.capture_btn.setFont(QFont(*get_font("lg", "bold", "ui")))
        self.capture_btn.setCursor(Qt.PointingHandCursor)
        self.capture_btn.setStyleSheet(get_style("button_glow") + f"""
            QPushButton {{ border-radius: {SIZES['radius']['xl']}px; }}
        """)
        self.capture_btn.clicked.connect(self._on_capture_keyframe)

        btn_layout.addWidget(self.capture_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return page

    # ─── 完成页 ───────────────────────────────────────

    def _create_completion_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            get_spacing("xxl"), get_spacing("xxl"),
            get_spacing("xxl"), get_spacing("xxl"),
        )
        layout.setSpacing(get_spacing("lg"))

        layout.addStretch()

        check_label = QLabel("✓")
        check_label.setAlignment(Qt.AlignCenter)
        check_label.setFont(QFont(*get_font("hero", "extrabold", "display")))
        check_label.setStyleSheet(
            f"color: {COLORS['success']}; background: transparent;"
        )
        layout.addWidget(check_label)

        success_title = QLabel("采集成功")
        success_title.setAlignment(Qt.AlignCenter)
        success_title.setFont(QFont(*get_font("xl", "bold", "display")))
        success_title.setStyleSheet(
            f"color: {COLORS['text']}; background: transparent;"
        )
        layout.addWidget(success_title)

        self.frame_count_label = QLabel()
        self.frame_count_label.setAlignment(Qt.AlignCenter)
        self.frame_count_label.setFont(QFont(*get_font("base", "normal", "ui")))
        self.frame_count_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background: transparent;"
        )
        layout.addWidget(self.frame_count_label)

        layout.addSpacing(get_spacing("xl"))

        storage_label = QLabel("请选择存储方式：")
        storage_label.setAlignment(Qt.AlignCenter)
        storage_label.setFont(QFont(*get_font("base", "medium", "ui")))
        storage_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background: transparent;"
        )
        layout.addWidget(storage_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.setSpacing(get_spacing("md"))

        self.local_btn = QPushButton("存储在本地")
        self.local_btn.setMinimumSize(140, 44)
        self.local_btn.setFont(QFont(*get_font("base", "bold", "ui")))
        self.local_btn.setCursor(Qt.PointingHandCursor)
        self.local_btn.setStyleSheet(get_style("completion_btn_local"))
        self.local_btn.clicked.connect(lambda: self._on_complete("local"))
        btn_layout.addWidget(self.local_btn)

        self.temp_btn = QPushButton("临时存储")
        self.temp_btn.setMinimumSize(120, 44)
        self.temp_btn.setFont(QFont(*get_font("base", "bold", "ui")))
        self.temp_btn.setCursor(Qt.PointingHandCursor)
        self.temp_btn.setStyleSheet(get_style("completion_btn_temp"))
        self.temp_btn.clicked.connect(lambda: self._on_complete("temp"))
        btn_layout.addWidget(self.temp_btn)

        self.complete_cancel_btn = QPushButton("取消")
        self.complete_cancel_btn.setMinimumSize(100, 44)
        self.complete_cancel_btn.setFont(QFont(*get_font("base", "medium", "ui")))
        self.complete_cancel_btn.setCursor(Qt.PointingHandCursor)
        self.complete_cancel_btn.setStyleSheet(get_style("completion_btn_cancel"))
        self.complete_cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.complete_cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        return page

    # ─── 信号连接 ─────────────────────────────────────

    def connect_signals(self):
        self.finished.connect(self._cleanup)

    # ─── 生命周期 ─────────────────────────────────────

    def showEvent(self, event):
        """弹窗弹出缩放动画"""
        super().showEvent(event)
        if hasattr(self, '_anim_shown') and self._anim_shown:
            return
        self._anim_shown = True

        final_geom = self.geometry()
        center = final_geom.center()
        scale = 0.6
        small_w = int(final_geom.width() * scale)
        small_h = int(final_geom.height() * scale)
        small_geom = QRect(
            QPoint(center.x() - small_w // 2, center.y() - small_h // 2),
            QSize(small_w, small_h),
        )

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(250)
        self.anim.setStartValue(small_geom)
        self.anim.setEndValue(final_geom)
        self.anim.setEasingCurve(QEasingCurve.OutBack)
        self.anim.start()

    def closeEvent(self, event):
        self._cleanup()
        super().closeEvent(event)

    def _cleanup(self):
        """统一清理：关闭摄像头 + 清除回调 + 清空缓冲区"""
        if self._capture_started:
            print("[FaceRegistrationDialog] 清理摄像头资源")
            interface_manager.toggle_capture(
                device_id=self._device_id, start=False
            )
            self._capture_started = False
        interface_manager.clear_face_registration_frame_callback()
        self._frame_buffer.clear()
        self._collected_frames.clear()

    # ─── 授权页逻辑 ───────────────────────────────────

    def _on_auth_agree(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入学生姓名")
            return
        self._student_name = name

        print(f"[FaceRegistrationDialog] 开启摄像头 device_id={self._device_id}")
        result = interface_manager.toggle_capture(
            device_id=self._device_id, start=True
        )
        if not result.get("success", False):
            QMessageBox.critical(self, "错误", "无法打开摄像头，请检查设备。")
            return

        self._capture_started = True
        interface_manager.register_face_registration_frame_callback(
            self._on_frame_received
        )
        self._buffer_start_time = time.time()
        self._current_pose = 0
        self._keyframe_ts = []
        self._collected_frames = []
        self._frame_buffer.clear()

        self.pose_guide_label.setText(POSE_GUIDES[0])
        self.progress_label.setText(f"1 / {len(POSE_GUIDES)}")
        self.video_display.setText("摄像头画面加载中...")
        self.stacked.setCurrentIndex(1)

    # ─── 采集页逻辑 ───────────────────────────────────

    def _on_frame_received(self, frame, faces, timestamp):
        """接收摄像头帧：渲染 + 存入缓冲区"""
        if not self._capture_started:
            return
        try:
            if frame is not None and len(frame.shape) == 3 and frame.shape[2] == 3:
                # 存入缓冲区（深拷贝）
                self._frame_buffer.append((frame.copy(), timestamp))
                # 渲染到画面
                self._render_frame(frame)
        except Exception as e:
            print(f"[FaceRegistrationDialog] 帧处理错误: {e}")

    def _render_frame(self, frame):
        """将 BGR 帧渲染到 video_display"""
        rgb = frame[:, :, ::-1]
        h, w, ch = rgb.shape
        qt_image = QImage(rgb.data.tobytes(), w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        scaled = pixmap.scaled(
            self.video_display.width(), self.video_display.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self.video_display.setPixmap(scaled)

    def _on_capture_keyframe(self):
        """拍摄关键帧 + 区间自动采样"""
        t_now = time.time()
        current_frame = None
        if self._frame_buffer:
            current_frame = self._frame_buffer[-1][0].copy()

        if current_frame is None:
            QMessageBox.warning(self, "提示", "尚未收到摄像头画面，请稍候再试")
            return

        idx = self._current_pose

        # 区间自动采样
        t_a = self._keyframe_ts[-1] if self._keyframe_ts else self._buffer_start_time
        t_b = t_now
        if idx > 0 and len(self._frame_buffer) >= AUTO_SAMPLE_COUNT:
            sampled = self._auto_sample(t_a, t_b, AUTO_SAMPLE_COUNT)
            self._collected_frames.extend(sampled)

        # 保存关键帧
        self._collected_frames.append(current_frame)
        self._keyframe_ts.append(t_now)
        self._current_pose += 1

        idx_new = self._current_pose
        if idx_new >= len(POSE_GUIDES):
            # 采集完成
            self._capture_started = False
            interface_manager.toggle_capture(
                device_id=self._device_id, start=False
            )
            interface_manager.clear_face_registration_frame_callback()
            self._show_completion()
        else:
            self.pose_guide_label.setText(POSE_GUIDES[idx_new])
            self.progress_label.setText(f"{idx_new + 1} / {len(POSE_GUIDES)}")
            self._buffer_start_time = t_now

    def _auto_sample(self, t_a: float, t_b: float, n: int) -> list:
        """正态分布采样 n 帧，均值 = 中点，σ = 区间长/6"""
        if t_b <= t_a or not self._frame_buffer:
            return []

        t_mid = (t_a + t_b) / 2.0
        sigma = (t_b - t_a) / 6.0

        frames_out = []
        for _ in range(n):
            t_target = np.random.normal(t_mid, sigma)
            t_target = max(t_a, min(t_b, t_target))
            nearest = self._find_nearest_frame(t_target)
            if nearest is not None:
                frames_out.append(nearest)

        return frames_out

    def _find_nearest_frame(self, t_target: float):
        """在缓冲区中找最接近目标时间戳的帧"""
        best = None
        best_dt = float("inf")
        for frame, ts in self._frame_buffer:
            dt = abs(ts - t_target)
            if dt < best_dt:
                best_dt = dt
                best = frame
        return best.copy() if best is not None else None

    # ─── 完成页逻辑 ───────────────────────────────────

    def _show_completion(self):
        total = len(self._collected_frames)
        keyframes = len(self._keyframe_ts)
        self.frame_count_label.setText(
            f"共采集 {total} 帧（{keyframes} 张关键帧 + {total - keyframes} 张自动采样帧）"
        )
        self.stacked.setCurrentIndex(2)

    def _on_complete(self, storage_type: str):
        """完成注册，发送信号"""
        print(
            f"[FaceRegistrationDialog] 注册完成: name={self._student_name}, "
            f"storage={storage_type}, frames={len(self._collected_frames)}"
        )
        self.registration_completed.emit({
            "student_name": self._student_name,
            "frames": self._collected_frames,
            "storage_type": storage_type,
        })
        self.accept()
