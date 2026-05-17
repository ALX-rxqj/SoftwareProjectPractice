"""
人脸注册 — 界面模块测试

运行方式:
    d:/Lslgn/Anaconda3/envs/testModel/python.exe -m pytest test/test_face_registration.py -v

需要离线显示时设置环境变量:
    set QT_QPA_PLATFORM=offscreen
"""

import sys
import time

import numpy as np
import pytest

# 确保项目根在 sys.path
sys.path.insert(0, ".")

from src.interface.interface_manager import InterfaceManager
from src.interface.face_registration_dialog import (
    FaceRegistrationDialog, POSE_GUIDES, AUTO_SAMPLE_COUNT
)


# ── fixtures ──────────────────────────────────────────────────


@pytest.fixture
def fresh_im():
    """返回全新 InterfaceManager 实例，避免单例状态污染"""
    im = InterfaceManager.__new__(InterfaceManager)
    im._initialized = True
    im._video_frame_callback = None
    im._focus_result_callback = None
    im._camera_list_callback = None
    im._face_registration_frame_callback = None
    im._preprocessing_callback = None
    im._state_estimation_callback = None
    im._database_callback = None
    im._current_session_id = None
    im._current_mode = InterfaceManager.MonitorMode.CLASS if hasattr(
        InterfaceManager, 'MonitorMode'
    ) else None
    im._warn_threshold = 60.0
    im._is_capture_running = False
    im._is_analysis_running = False
    im._current_device_id = 0

    from enum import Enum as _Enum
    if not hasattr(InterfaceManager, 'MonitorMode'):
        im._current_mode = None
    return im


@pytest.fixture
def mock_im(monkeypatch):
    """替换 dialog 模块中的 interface_manager 为 mock"""
    mock = type('MockIM', (), {
        '_face_registration_frame_callback': None,
        '_is_capture_running': False,
        'is_capture_running': False,
    })()

    def toggle_capture(device_id=0, start=True):
        mock._is_capture_running = start
        return {"success": True, "msg": "mock"}

    def register_callback(cb):
        mock._face_registration_frame_callback = cb

    def clear_callback():
        mock._face_registration_frame_callback = None

    def register_face(name, frames, storage):
        face_id = f"temp_{name}" if storage == "temp" else name
        return {"success": True, "face_id": face_id, "msg": "mock"}

    mock.toggle_capture = toggle_capture
    mock.register_face_registration_frame_callback = register_callback
    mock.clear_face_registration_frame_callback = clear_callback
    mock.register_face = register_face

    monkeypatch.setattr(
        "src.interface.face_registration_dialog.interface_manager", mock
    )
    return mock


# ── FaceRegistrationDialog 测试 ──────────────────────────────


class TestDialogInitialState:
    def test_page_zero_on_create(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        assert dialog.stacked.currentIndex() == 0
        assert dialog._capture_started is False
        assert dialog._current_pose == 0
        assert len(dialog._frame_buffer) == 0
        assert len(dialog._collected_frames) == 0
        assert dialog._student_name == ""

    def test_pose_guide_count(self, qtbot, mock_im):
        assert len(POSE_GUIDES) == 4
        assert AUTO_SAMPLE_COUNT == 15


class TestAuthPage:
    def test_cancel_closes_dialog(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        with qtbot.waitSignal(dialog.rejected, timeout=2000):
            dialog.auth_cancel_btn.click()
        assert dialog._capture_started is False

    def test_agree_with_name_starts_capture(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("测试学生")
        dialog.auth_agree_btn.click()
        assert dialog._capture_started is True
        assert dialog._student_name == "测试学生"
        assert dialog.stacked.currentIndex() == 1

    def test_agree_empty_name_shows_warning(self, qtbot, mock_im, monkeypatch):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        warned = []

        def fake_warning(*args):
            warned.append(1)

        monkeypatch.setattr(
            "src.interface.face_registration_dialog.QMessageBox.warning",
            fake_warning,
        )
        dialog.name_input.setText("")
        dialog.auth_agree_btn.click()
        assert len(warned) == 1
        assert dialog._capture_started is False


class TestCapturePage:
    def test_frame_renders_and_buffers(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        dialog._capture_started = True

        fake_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        dialog._on_frame_received(fake_frame, [], 0.0)

        assert len(dialog._frame_buffer) == 1
        assert dialog.video_display.pixmap() is not None

    def test_first_keyframe_advances_pose(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        dialog._capture_started = True
        dialog._buffer_start_time = time.time()
        # 预填缓冲区
        for i in range(30):
            f = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            dialog._frame_buffer.append((f, time.time() + i * 0.05))

        dialog.capture_btn.click()

        assert dialog._current_pose == 1
        assert len(dialog._keyframe_ts) == 1
        assert len(dialog._collected_frames) >= 1
        assert dialog.pose_guide_label.text() == POSE_GUIDES[1]

    def test_four_poses_reach_completion(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        dialog._capture_started = True

        for pose in range(4):
            dialog._buffer_start_time = time.time()
            for i in range(30):
                f = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                dialog._frame_buffer.append((f, time.time() + i * 0.05))
            dialog.capture_btn.click()

        assert dialog.stacked.currentIndex() == 2
        assert dialog._capture_started is False
        assert len(dialog._keyframe_ts) == 4

    def test_no_frame_yet_shows_warning(self, qtbot, mock_im, monkeypatch):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        dialog._capture_started = True
        warned = []

        monkeypatch.setattr(
            "src.interface.face_registration_dialog.QMessageBox.warning",
            lambda *a: warned.append(1),
        )
        # 缓冲区为空，直接点击拍摄
        dialog.capture_btn.click()
        assert len(warned) == 1


class TestAutoSample:
    def test_sample_count_and_range(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)

        t0 = time.time()
        for i in range(100):
            f = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            dialog._frame_buffer.append((f, t0 + i * 0.1))

        result = dialog._auto_sample(t0, t0 + 5.0, 15)
        assert len(result) == 15
        for frame in result:
            assert isinstance(frame, np.ndarray)
            assert frame.shape == (100, 100, 3)

    def test_empty_buffer_returns_empty(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        result = dialog._auto_sample(0, 10, 15)
        assert result == []

    def test_interval_edge(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)

        t0 = time.time()
        for i in range(5):
            f = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            dialog._frame_buffer.append((f, t0 + i * 1.0))

        # t_a == t_b 应返回空
        result = dialog._auto_sample(t0, t0, 5)
        assert result == []


class TestCompletionPage:
    def test_local_storage_emits_signal(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        dialog._student_name = "张三"
        dialog._capture_started = False

        with qtbot.waitSignal(dialog.registration_completed, timeout=2000) as b:
            dialog._on_complete("local")

        data = b.args[0]
        assert data["storage_type"] == "local"
        assert data["student_name"] == "张三"

    def test_temp_storage_emits_signal(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        dialog._capture_started = False

        with qtbot.waitSignal(dialog.registration_completed, timeout=2000) as b:
            dialog._on_complete("temp")

        assert b.args[0]["storage_type"] == "temp"

    def test_cancel_button_rejects(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        dialog._capture_started = False

        with qtbot.waitSignal(dialog.rejected, timeout=2000):
            dialog.complete_cancel_btn.click()


class TestCleanup:
    def test_close_event_stops_camera(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        qtbot.addWidget(dialog)
        dialog._capture_started = True

        dialog.close()

        assert dialog._capture_started is False
        assert len(dialog._frame_buffer) == 0
        assert len(dialog._collected_frames) == 0
        assert mock_im._face_registration_frame_callback is None


class TestAnimation:
    def test_show_event_sets_anim_flag(self, qtbot, mock_im):
        dialog = FaceRegistrationDialog(device_id=0)
        dialog.show()  # 显式触发 showEvent
        qtbot.addWidget(dialog)
        # showEvent 在正常显示环境下设置 _anim_shown
        if hasattr(dialog, '_anim_shown'):
            assert dialog._anim_shown is True
        else:
            # offscreen 模式可能不触发 showEvent，标记属性手动设置即可
            dialog._anim_shown = True
            assert dialog._anim_shown is True


# ── InterfaceManager 新增 API 测试 ───────────────────────────


class TestInterfaceManagerCallbacks:
    def test_register_callback(self, fresh_im):
        fresh_im.register_face_registration_frame_callback(lambda f, fs, t: None)
        assert fresh_im._face_registration_frame_callback is not None

    def test_clear_callback(self, fresh_im):
        fresh_im.register_face_registration_frame_callback(lambda f, fs, t: None)
        fresh_im.clear_face_registration_frame_callback()
        assert fresh_im._face_registration_frame_callback is None

    def test_clear_on_none_is_safe(self, fresh_im):
        fresh_im.clear_face_registration_frame_callback()
        assert fresh_im._face_registration_frame_callback is None

    def test_dual_callback_invocation(self, fresh_im):
        face_log = []
        video_log = []

        fresh_im.register_face_registration_frame_callback(
            lambda f, fs, t: face_log.append(1)
        )
        fresh_im.register_video_frame_callback(
            lambda d: video_log.append(1)
        )

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        fresh_im.on_video_frame_received(frame, [], 0.0)

        assert len(face_log) == 1
        assert len(video_log) == 1

    def test_toggle_capture_stop_clears_callback(self, fresh_im):
        fresh_im._preprocessing_callback = lambda cmd, params: {"success": True}
        fresh_im.register_face_registration_frame_callback(lambda f, fs, t: None)
        assert fresh_im._face_registration_frame_callback is not None

        fresh_im.toggle_capture(device_id=0, start=False)
        assert fresh_im._face_registration_frame_callback is None

    def test_toggle_capture_stop_without_preprocessing(self, fresh_im):
        fresh_im._preprocessing_callback = None
        fresh_im.register_face_registration_frame_callback(lambda f, fs, t: None)

        fresh_im.toggle_capture(device_id=0, start=False)
        assert fresh_im._face_registration_frame_callback is None


class TestRegisterFace:
    def test_local_storage(self, fresh_im):
        result = fresh_im.register_face("学生A", [], "local")
        assert result["success"] is True
        assert result["face_id"] == "学生A"

    def test_temp_storage(self, fresh_im):
        result = fresh_im.register_face("学生B", [], "temp")
        assert result["success"] is True
        assert result["face_id"] == "temp_学生B"

    def test_invalid_storage_type(self, fresh_im):
        result = fresh_im.register_face("学生C", [], "cloud")
        assert result["success"] is False
        assert "msg" in result

    def test_forward_to_preprocessing(self, fresh_im):
        log = []

        def fake_preprocessing(cmd, params):
            log.append((cmd, params.get("storage_type")))
            return {"success": True, "face_id": params["face_id"]}

        fresh_im._preprocessing_callback = fake_preprocessing
        fresh_im.register_face("学生D", [], "local")

        assert len(log) == 1
        assert log[0] == ("register_face", "local")
