"""
压力测试 — 看门狗脚本
运行方式:
    conda activate testModel
    python test/run_stress_test.py                     # 默认 2 小时 Mock 模式
    python test/run_stress_test.py --duration 3600     # 1 小时
    python test/run_stress_test.py --video test.mp4    # 使用视频文件测试真实管线
    python test/run_stress_test.py --interval 30       # 每 30 秒记录一次健康状态

功能:
    - 以子进程方式启动 App，监控其运行状态
    - 崩溃时自动记录进程退出码、stdout/stderr
    - 周期性记录内存/CPU 使用情况（需 psutil，可选）
    - 生成带时间戳的日志文件到 test/stress_logs/
"""

import subprocess
import sys
import os
import time
import signal
import argparse
import threading
from datetime import datetime, timedelta
from pathlib import Path

# ── 可选依赖 ──
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("[警告] psutil 未安装，将跳过内存/CPU 监控。安装: pip install psutil")


# ── 日志系统 ──
class StressLogger:
    """同时输出到控制台和日志文件。"""

    def __init__(self, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = log_dir / f"stress_test_{timestamp}.log"
        self._file = open(self.log_path, "w", encoding="utf-8")
        self._start_time = datetime.now()

    def log(self, msg: str):
        elapsed = (datetime.now() - self._start_time).total_seconds()
        line = f"[{elapsed:7.1f}s] {msg}"
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"))
        self._file.write(line + "\n")
        self._file.flush()

    def close(self):
        self._file.close()


# ── 子进程输出过滤 ──

import re as _re

# 无害底层警告
NOISE_PATTERNS = [
    "QFontDatabase: Cannot find font directory",
    "Note that Qt no longer ships fonts",
    "This plugin does not support propagateSizeHints()",
    "This plugin does not support raise()",
    "VIDEOIO(DSHOW): backend is generally available but can't be used",
    "Specified provider 'CUDAExecutionProvider' is not in available provider",
    "UserWarning: Specified provider",
    "warnings.warn(",
    "onnxruntime_inference_collection.py",
    "QObject::startTimer: Timers can only be used with threads started with QThread",
]

# 默认不输出 STDOUT（压力测试只关心崩溃，不校验正确性）
# 用 --stdout 参数可恢复 STDOUT 输出
_FIELD_RE = _re.compile(r"^  \w.*\s{2,}:")   # DEBUG 字段行
_SEP_RE = _re.compile(r"^[=\-]{10,}$")        # 分隔线

# 模型相关异常模式（匹配到时在日志中高亮标记）
MODEL_ERROR_PATTERNS = [
    ("YOLO", ["ultralytics", "yolo", "YOLO"]),
    ("ONNX/w600k_r50", ["onnxruntime", "InferenceSession", "w600k", "onnx"]),
    ("CUDA/GPU", ["CUDA", "cuda", "out of memory", "CUDNN"]),
    ("Torch", ["torch", "Tensor", "backward", "grad"]),
    ("MediaPipe", ["mediapipe", "MediaPipe"]),
    ("MTCNN", ["mtcnn", "MTCNN"]),
    ("OpenCV", ["cv2.error", "OpenCV"]),
    ("推理异常", ["RuntimeError", "ValueError", "InvalidArgument"]),
]


def _is_noise(line: str) -> bool:
    for pat in NOISE_PATTERNS:
        if pat in line:
            return True
    if _FIELD_RE.match(line) or _SEP_RE.match(line):
        return True
    return False


MODEL_SUCCESS_MARKERS = [
    "模型已加载", "模型加载成功", "successfully loaded",
    "启动完成", "基准吞吐量", "吞吐量恢复正常",
    "[stress_test] STATUS:",  # 心跳状态行不是异常
]
"""包含这些文本的行不标记为模型异常。"""


def _check_model_error(line: str) -> str | None:
    """如果是模型相关异常，返回模型名称标签；否则返回 None。
    排除模型加载成功、吞吐量报告等正常信息。
    """
    for marker in MODEL_SUCCESS_MARKERS:
        if marker in line:
            return None
    for label, keywords in MODEL_ERROR_PATTERNS:
        for kw in keywords:
            if kw.lower() in line.lower():
                return label
    return None


# ── 子进程输出读取线程 ──
def stream_reader(pipe, logger, prefix: str, show: bool = True):
    """读取子进程输出。STDOUT 默认不输出（show=False 时仅记录异常行和 STATUS 心跳）。"""
    last_line = None
    last_count = 0

    def flush_dup():
        nonlocal last_count
        if last_count > 1:
            logger.log(f"{prefix} | [上条重复 {last_count} 次]")
        last_count = 0

    for line in iter(pipe.readline, ""):
        if not line:
            continue
        stripped = line.rstrip()
        if not stripped:
            continue

        # 无害噪音过滤
        if _is_noise(stripped):
            continue

        # STATUS 心跳行始终通过
        is_heartbeat = "[stress_test] STATUS:" in stripped

        # 连续重复去重
        if stripped == last_line:
            last_count += 1
            continue
        else:
            flush_dup()
            last_line = stripped
            last_count = 1
            tag = _check_model_error(stripped)
            if show or is_heartbeat:
                label = f"[{tag}异常] " if tag else ""
                logger.log(f"{prefix} | {label}{stripped}")
            elif tag:
                logger.log(f"{prefix} | [{tag}异常] {stripped}")

    flush_dup()
    pipe.close()


# ── 主逻辑 ──
def run_stress_test(args):
    project_root = Path(__file__).resolve().parent.parent
    log_dir = project_root / "test" / "stress_logs"
    logger = StressLogger(log_dir)

    logger.log("=" * 60)
    logger.log("压力测试开始")
    logger.log(f"  运行时长: {args.duration}s ({args.duration/3600:.1f}h)")
    logger.log(f"  健康检查间隔: {args.interval}s")
    logger.log(f"  模式: {'视频文件' if args.video else 'Mock 数据'}")
    if args.video:
        logger.log(f"  视频文件: {args.video}")
    logger.log(f"  psutil 可用: {HAS_PSUTIL}")
    logger.log(f"  日志文件: {logger.log_path}")
    logger.log("=" * 60)

    # 使用 conda testModel 环境的 Python（通过 CLAUDE.md 约定）
    conda_python = Path("D:/Lslgn/Anaconda3/envs/testModel/python.exe")
    if args.python:
        python_exe = args.python
    elif conda_python.exists():
        python_exe = str(conda_python)
    else:
        python_exe = sys.executable
        logger.log("[警告] 未找到 conda testModel 环境，使用当前 Python（可能缺少依赖）")

    # 构建启动命令
    launcher_path = project_root / "test" / "stress_test_app.py"
    cmd = [
        python_exe,
        str(launcher_path),
        "--duration", str(args.duration),
    ]
    if args.video:
        cmd.extend(["--video", args.video])
        if args.loop:
            cmd.append("--loop")
    else:
        cmd.append("--mock")

    logger.log(f"启动命令: {' '.join(cmd)}")

    # 启动子进程（设置 PYTHONIOENCODING=utf-8 确保中文输出正确）
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(project_root),
            env=env,
        )
    except Exception as e:
        logger.log(f"[致命错误] 无法启动子进程: {e}")
        logger.close()
        return 1

    logger.log(f"子进程 PID: {proc.pid}")

    # 启动 stdout/stderr 读取线程
    # STDOUT 默认关闭（压力测试只需确认不崩溃）；--stdout 可打开
    # STDERR 始终输出（用于捕获异常堆栈）
    show_stdout = getattr(args, "stdout", False)
    stdout_thread = threading.Thread(
        target=stream_reader, args=(proc.stdout, logger, "STDOUT", show_stdout),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=stream_reader, args=(proc.stderr, logger, "STDERR", True),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    # 获取 psutil 进程对象（用于内存/CPU 监控）
    psutil_proc = None
    if HAS_PSUTIL:
        try:
            psutil_proc = psutil.Process(proc.pid)
        except psutil.NoSuchProcess:
            logger.log("[警告] 无法获取 psutil 进程对象")

    # ── 监控循环 ──
    start_time = time.time()
    crash_detected = False
    crash_info = None
    last_health_log = 0.0
    health_samples = []  # (elapsed, cpu_percent, memory_mb)
    NORMAL_EXIT_TOLERANCE = 30  # 正常退出时间容差（秒）

    while True:
        elapsed = time.time() - start_time

        # 检查子进程是否存活
        poll_result = proc.poll()
        if poll_result is not None:
            near_expected = elapsed >= (args.duration - NORMAL_EXIT_TOLERANCE)
            if poll_result == 0 and near_expected:
                # 正常退出
                logger.log(f"[正常退出] 子进程按预期结束, exit_code=0, 运行 {elapsed:.1f}s")
            else:
                crash_detected = True
                crash_info = {
                    "exit_code": poll_result,
                    "elapsed": elapsed,
                }
                logger.log("")
                logger.log("=" * 60)
                if poll_result != 0:
                    logger.log(f"[崩溃检测] 子进程异常退出!")
                    logger.log(f"  说明: 非零退出码表示异常终止")
                else:
                    logger.log(f"[崩溃检测] 子进程过早退出（可能启动失败）!")
                logger.log(f"  运行时长: {elapsed:.1f}s ({elapsed/60:.1f}min)")
                logger.log(f"  退出码: {poll_result}")
                logger.log("=" * 60)
            break

        # 检查是否超时（子进程应该自行退出，这是保护）
        if elapsed >= args.duration + 120:  # 给 2 分钟缓冲
            logger.log("[超时] 子进程未按时退出，强制终止")
            crash_detected = True
            crash_info = {
                "exit_code": None,
                "elapsed": elapsed,
            }
            proc.terminate()
            time.sleep(5)
            if proc.poll() is None:
                proc.kill()
            break

        # 周期性健康检查
        if elapsed - last_health_log >= args.interval:
            last_health_log = elapsed
            health_msg = f"健康检查 | 运行中, 已运行 {elapsed/60:.0f}min"

            if psutil_proc and psutil_proc.is_running():
                try:
                    cpu_raw = psutil_proc.cpu_percent()
                    cpu = cpu_raw / psutil.cpu_count()  # 归一化到 0-100%
                    mem_info = psutil_proc.memory_info()
                    mem_mb = mem_info.rss / (1024 * 1024)
                    health_samples.append((elapsed, cpu, mem_mb))
                    health_msg += f", CPU: {cpu:.0f}%, 内存: {mem_mb:.0f}MB"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            logger.log(health_msg)

        time.sleep(0.5)  # 每 0.5 秒检查一次进程存活

    # ── 进程终结处理 ──
    final_exit_code = proc.poll()
    if final_exit_code is None:
        logger.log("发送 SIGTERM 终止子进程...")
        try:
            proc.terminate()
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            logger.log("子进程无响应，强制 kill")
            proc.kill()
            proc.wait()

    final_exit_code = proc.poll()

    # 等待读取线程收尾
    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)

    # ── 结果汇总 ──
    total_elapsed = time.time() - start_time
    logger.log("")
    logger.log("=" * 60)
    logger.log("压力测试结束")
    logger.log(f"  总运行时长: {total_elapsed:.1f}s ({total_elapsed/60:.1f}min / {total_elapsed/3600:.2f}h)")
    logger.log(f"  最终退出码: {final_exit_code}")
    logger.log(f"  预期时长: {args.duration}s ({args.duration/3600:.1f}h)")

    if crash_detected:
        logger.log("")
        logger.log(f"[结果] FAIL 崩溃 - 进程在 {crash_info['elapsed']:.1f}s 时异常退出 (exit_code={crash_info['exit_code']})")
        test_passed = False
    elif final_exit_code == 0:
        logger.log(f"[结果] PASS 通过 - 完整运行 {args.duration/3600:.1f} 小时无崩溃")
        test_passed = True
    else:
        logger.log(f"[结果] WARN 警告 - 进程以非零退出码 {final_exit_code} 结束")
        test_passed = False

    # 健康统计
    if health_samples:
        cpus = [s[1] for s in health_samples]
        mems = [s[2] for s in health_samples]
        logger.log("")
        logger.log("资源使用统计 (psutil):")
        logger.log(f"  CPU 均值/最大: {sum(cpus)/len(cpus):.0f}% / {max(cpus):.0f}% ({psutil.cpu_count()} 核)")
        logger.log(f"  内存 初始/最终/最大: {mems[0]:.0f}MB / {mems[-1]:.0f}MB / {max(mems):.0f}MB")
        # 简单内存泄漏检测
        if len(mems) >= 2 and mems[-1] > mems[0] * 1.5:
            logger.log(f"  WARN 内存增长超过 50%，可能存在内存泄漏")
        elif len(mems) >= 2 and mems[-1] > mems[0] * 2.0:
            logger.log(f"  FAIL 内存翻倍，疑似严重内存泄漏")

    logger.log(f"  完整日志: {logger.log_path}")
    logger.log("=" * 60)
    logger.close()

    return 0 if test_passed else 1


def main():
    parser = argparse.ArgumentParser(
        description="网课专注度分析系统 — 长时间运行压力测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python test/run_stress_test.py                        # Mock 模式 2 小时
  python test/run_stress_test.py --duration 600         # Mock 模式 10 分钟（快速验证）
  python test/run_stress_test.py --duration 3600 --video test_video.mp4  # 视频文件模式 1 小时
  python test/run_stress_test.py --interval 60          # 每 60 秒记录一次健康状态
        """,
    )
    parser.add_argument("--duration", type=int, default=7200,
                        help="运行时长（秒），默认 7200（2 小时）")
    parser.add_argument("--interval", type=int, default=30,
                        help="健康检查间隔（秒），默认 30")
    parser.add_argument("--video", type=str, default=None,
                        help="视频文件路径，用于测试真实处理管线（不指定则 Mock 模式）")
    parser.add_argument("--python", type=str, default=None,
                        help="Python 解释器路径（默认使用 conda testModel 环境）")
    parser.add_argument("--stdout", action="store_true", default=False,
                        help="输出子进程 STDOUT（默认关闭，因为压力测试只验证不崩溃）")
    parser.add_argument("--loop", action="store_true", default=False,
                        help="视频文件循环播放（仅 --video 模式有效）")
    args = parser.parse_args()

    return run_stress_test(args)


if __name__ == "__main__":
    sys.exit(main())
