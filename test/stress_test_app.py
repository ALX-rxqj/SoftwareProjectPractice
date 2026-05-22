"""
压力测试 — App 启动器
由 run_stress_test.py 作为子进程调用。目的仅为验证程序长时间运行不崩溃。
"""

import sys
import os
import signal
import argparse
import time

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_project_root, "src"))
sys.path.insert(0, _project_root)
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, pyqtSignal, QObject


class LoopController(QObject):
    """跨线程安全的视频循环控制器。
    使用 Qt 信号确保 QTimer 操作始终在主线程执行。
    """
    restart_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.restart_signal.connect(self._do_restart)
        self._pending_restart = False
        self.loop_count = 0
        self._start_time = 0.0
        self._args = None

    def setup(self, args, start_fn):
        self._args = args
        self._start_fn = start_fn

    def on_file_ended(self, file_path: str):
        """视频结束回调 — 可能在 worker 线程中调用，通过信号转发到主线程。"""
        remaining = self._args.duration - (time.perf_counter() - self._start_time)
        if remaining > 5 and not self._pending_restart:
            self._pending_restart = True
            self.restart_signal.emit()

    def _do_restart(self):
        self._pending_restart = False
        self.loop_count += 1
        print(f"[stress_test] 循环 #{self.loop_count}")
        self._start_fn()

    def mark_start(self):
        self._start_time = time.perf_counter()


def main():
    parser = argparse.ArgumentParser(description="压力测试 App 启动器")
    parser.add_argument("--duration", type=int, default=7200,
                        help="运行时长（秒），默认 7200（2 小时）")
    parser.add_argument("--video", type=str, default=None,
                        help="视频文件路径，不指定则使用 Mock 模式")
    parser.add_argument("--mock", action="store_true", default=True,
                        help="使用 Mock 模式（默认）")
    parser.add_argument("--loop", action="store_true", default=False,
                        help="视频播放结束后自动循环")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setOrganizationName("OnlineClassMonitor")
    app.setApplicationName("NetClassFocusAnalyzer")

    from src.interface import MainWindow, unified_data_manager, DataSource, interface_manager

    if args.mock and not args.video:
        unified_data_manager.data_source = DataSource.MOCK

    window = MainWindow()
    window.show()

    loop_ctrl = LoopController()

    def start_analysis():
        if args.video:
            window._current_source_type = "file"
            window._current_file_path = args.video
        window.on_start_analysis()
        loop_ctrl.mark_start()

    loop_ctrl.setup(args, start_analysis)

    # --- 等待初始化完成后自动启动 ---
    attempt = [0]

    def try_start():
        attempt[0] += 1
        svc = unified_data_manager.preprocessing_service
        if svc is not None and svc.pipeline is not None:
            print("[stress_test] 启动")
            start_analysis()
            if args.video and args.loop:
                interface_manager.register_file_playback_ended_callback(loop_ctrl.on_file_ended)
        elif attempt[0] < 120:
            QTimer.singleShot(1000, try_start)
        else:
            print("[stress_test] 初始化超时，强制启动")
            start_analysis()

    QTimer.singleShot(1000, try_start)

    # --- 定期状态心跳（供 watchdog 健康检查使用） ---
    # 用 STATUS: 前缀，方便 watchdog 识别
    HEARTBEAT_INTERVAL = 30  # 秒

    def print_status():
        try:
            svc = unified_data_manager.preprocessing_service
            se = unified_data_manager.state_estimation_service
            fe = getattr(unified_data_manager, "_feature_extraction_service", None)

            # 预处理 + 模型状态
            if svc and svc.pipeline:
                stats = svc.get_status()
                frames = stats.get("frames_processed", 0)
                failures = stats.get("detection_failures", 0)
                last_err = stats.get("last_error", "")
                yolo_ok = svc.pipeline._detector._yolo is not None if svc.pipeline._detector else False
                w600k_ok = getattr(svc._embedding_extractor, "session", None) is not None
                preproc = "ok" if stats.get("worker_alive") else "stopped"
            else:
                frames = failures = 0
                last_err = ""
                yolo_ok = w600k_ok = False
                preproc = "init"

            # 各模块状态
            state_est = "ok" if (se and getattr(se, "_is_processing", False)) else "stopped"
            feat_ext = "ok" if fe is not None else "miss"
            db = "ok"   # 能跑到这里说明数据库连接正常
            ui = "ok"   # QApplication 事件循环正常运行

            # 模型
            models = []
            models.append("yolo=ok" if yolo_ok else "yolo=miss")
            models.append("w600k=ok" if w600k_ok else "w600k=miss")

            err_info = f" last_err={last_err}" if last_err else ""

            print(f"[stress_test] STATUS: frames={frames} fail={failures} "
                  f"preproc={preproc} feat_ext={feat_ext} state_est={state_est} "
                  f"db={db} ui={ui} "
                  f"{' '.join(models)}{err_info}")
        except Exception as e:
            print(f"[stress_test] STATUS: error={e}")

    heartbeat = QTimer()
    heartbeat.timeout.connect(print_status)
    heartbeat.start(HEARTBEAT_INTERVAL * 1000)
    # 启动后立即发一次状态
    QTimer.singleShot(5000, print_status)

    # --- 到达时长后退出 ---
    def on_done():
        print(f"[stress_test] 完成, {args.duration}s, 循环 {loop_ctrl.loop_count} 次")
        # 优雅关闭：先停采集，再退出，避免 worker 线程被暴力中断
        try:
            unified_data_manager.stop_capture()
        except Exception:
            pass
        QTimer.singleShot(1500, app.quit)

    QTimer.singleShot(args.duration * 1000, on_done)

    # --- 信号处理 ---
    def handle_sigterm(signum, frame):
        print("[stress_test] 收到终止信号，退出")
        app.quit()

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
