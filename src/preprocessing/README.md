# 预处理模块

本目录实现了系统概要设计中“预处理模块”的独立版本，且不改动项目已有文件。

## 已覆盖能力

- 视频采集：支持摄像头和本地视频文件两种输入源
- 视频解码与逐帧读取：基于 `cv2.VideoCapture`
- 帧标准化：统一分辨率到 `1280x720`
- 异常帧过滤：过滤空帧、损坏帧、非数组帧
- 人脸检测：优先使用 `MTCNN`，缺失时回退到 OpenCV Haar Cascade
- 人脸跟踪：对连续帧内目标分配稳定 `face_id`
- 活体检测：使用清晰度和纹理变化的轻量级启发式判断
- 主人脸确认：综合面积、中心位置和跟踪连续性选择 `owner_face_id`
- 双通道输出：同时生成界面渲染数据和特征提取数据
- 异常恢复：连续失败超过阈值时自动重置管线
- 人脸注册：支持 `register_face` 异步注册与 PRI-04 结果回调
- 内存注册表：支持 `query_face_registry` 查询已注册人脸摘要
- 数据库解耦：支持 `set_face_embedding_writer()` 与 `load_faces_from_db()`
- 帧内匹配：支持 embedding 匹配、`face_matched` 标记与 `monitored_faces` 筛选

## 主要文件

- `contracts.py`：数据结构定义
- `video_source.py`：视频输入源管理
- `face_tracker.py`：人脸编号跟踪
- `liveness.py`：活体检测
- `pipeline.py`：预处理主流程
- `service.py`：命令入口与后台处理线程

## 对外接口

`PreprocessingService.handle_command(command, params)` 支持：

- `toggle_capture`：`{"device_id": 0, "start": true}`
- `toggle_capture`：`{"device_id": 0, "start": true, "monitored_faces": ["face_xxx"]}`
- `load_video`：`{"file_path": "demo.mp4"}`
- `load_video_file`：`{"file_path": "demo.mp4"}`
- `query_cameras`：`{}`
- `refresh_camera_list`：`{}`
- `register_face`：`{"student_name": "Alice", "frames": [...], "storage_type": "temp", "face_id": "temp_xxx"}`
- `query_face_registry`：`{}`

与接口文档对齐的公开方法：

- `on_control_capture(device_id, start)`：控制摄像头起停
- `on_load_video(file_path)`：加载本地视频文件
- `on_query_cameras()`：查询摄像头列表并通过 `on_camera_list_received(camera_list)` 形式回调
- `start_camera(device_id)` / `stop_camera()` / `load_video(file_path)`：预处理模块执行函数
- `register_face(student_name, frames, storage_type, face_id)`：异步注册人脸
- `query_face_registry()`：返回内存注册表摘要
- `set_face_embedding_writer(callback)`：注入数据库写回调
- `load_faces_from_db(faces_data)`：程序启动时载入持久人脸

与接口文档对齐的回调形式：

- `on_video_frame_received(frame, faces, timestamp)`
- `on_frame_received(data)`
- `on_camera_list_received(camera_list)`
- `ui_callback({"type": "face_registration_result", ...})`

界面输出格式：

```python
{
    "frame": frame,
    "faces": [{"face_id": 1, "bbox": [x, y, w, h]}],
    "timestamp": 1734567890.123,
}
```

特征提取输出格式：

```python
{
    "timestamp": 1734567890.123,
    "faces": [{
        "face_id": "face_xxx",
        "student_name": "Alice",
        "face_roi": face_img,
        "confidence": 0.91,
        "face_matched": True,
    }],
    "owner_face_id": "face_xxx",
    "frame": frame,
    "face_matched": True,
}
```

## 使用示例

```python
from src.preprocessing.service import PreprocessingService


def on_video_frame_received(frame, faces, timestamp):
    print("ui packet", timestamp, len(faces))


def on_frame_received(data):
    print("feature packet", data["owner_face_id"])


def on_camera_list_received(camera_list):
    print("camera list", camera_list)


service = PreprocessingService(
    log_callback=print,
    video_frame_callback=on_video_frame_received,
    frame_received_callback=on_frame_received,
    camera_list_callback=on_camera_list_received,
)

service.on_query_cameras()
service.on_control_capture(device_id=0, start=True)
```

## 运行方式

基础摄像头演示：

```powershell
conda activate software_project_practice_py310
cd E:\网课监督系统\SoftwareProjectPractice
$env:YOLO_CONFIG_DIR="E:\网课监督系统\SoftwareProjectPractice\.ultralytics"
python -m src.preprocessing.handoff_demo --camera 0 --duration 10
```

交接文档完整演示（含 `register_face`、`query_face_registry`、`monitored_faces`）：

```powershell
conda activate software_project_practice_py310
cd E:\网课监督系统\SoftwareProjectPractice
$env:YOLO_CONFIG_DIR="E:\网课监督系统\SoftwareProjectPractice\.ultralytics"
python -m src.preprocessing.handoff_demo --camera 0 --duration 10 --enable-registration --monitor-registered
```

本地视频演示：

```powershell
python -m src.preprocessing.handoff_demo --video "D:\your_video.mp4" --duration 10 --enable-registration
```
