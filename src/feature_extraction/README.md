# Head Pose Estimation

这是一个基于 OpenCV + ONNX Runtime 的实时人脸姿态分析项目。

当前版本会从摄像头或视频中检测人脸，并输出以下信息：

- `head_pose`：头部姿态（`pitch` / `yaw` / `roll` / `confidence`）
- `ear`：眼睛纵横比（EAR）
- `eye_state`：是否睁眼（`0 = 睁眼`，`1 = 闭眼`）
- `is_looking_screen`：是否看着屏幕
- `num_face_total`：当前画面中的人脸数量

## 运行环境

建议使用 Windows + Anaconda + Python 3.10。

### 依赖安装

先创建并激活环境：

```powershell
conda create -n headpose python=3.10 -y
conda activate headpose
```

安装依赖：

```powershell
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## 模型文件

请确保 `assets` 目录下存在以下文件：

- `assets/face_detector.onnx`
- `assets/face_landmarks.onnx`
- `assets/model.txt`

## 运行方式

### 1. 摄像头实时运行

```powershell
python main.py --cam 0 --face-id 1
```

如果摄像头编号不是 `0`，可以尝试：

```powershell
python main.py --cam 1 --face-id 1
```

### 2. 视频文件运行

```powershell
python main.py --video "D:\test.mp4" --face-id 1
```

## 窗口显示内容

预览窗口会显示：

- `Pitch / Yaw / Roll`
- `头部姿态置信度`
- `EAR`
- `Eye: Open / Closed`
- `Look: Looking / Not looking`
- `Faces: 当前人脸数量`
- `FPS`


output = process_feature_packet(input_data)
```

输入字典需要符合结构：

```python
{
    "timestamp": float,
    "faces": [
        {"face_id": 1, "face_roi": face_img1},
        {"face_id": 2, "face_roi": face_img2}
    ],
    "owner_face_id": 1,
    "frame": frame
}
```

其中：

- `faces` 是所有人脸信息，每项至少包含 `face_id` 和 `face_roi`
- `owner_face_id` 是主人脸 ID，`-1` 表示没有主人脸
- `frame` 是原始视频帧（BGR）

`process_feature_packet` 会返回完整输出字典，并且支持把结果回调到 `send_to_scoring(output)`。

## 输出接口

程序会调用回调函数：

```python
send_to_scoring(output)
```

输出字典结构如下：

```python
{
    "timestamp": float,
    "face_id": int,
    "features": {
        "head_pose": {
            "pitch": float,
            "yaw": float,
            "roll": float,
            "confidence": float
        },
        "ear": {
            "left": float,
            "right": float,
            "value": float,
            "confidence": float
        },
        "eye_state": {
            "value": int,        # 0 = 睁眼, 1 = 闭眼
            "confidence": float
        },
        "is_looking_screen": {
            "value": bool,      # True = 注视屏幕, False = 未注视
            "confidence": float
        },
        "attention_state": {
            "value": int,       # 0 = 专注, 1 = 分心, 2 = 困倦, 3 = 缺席
            "confidence": float
        },
        "face_distance_state": {
            "value": int,       # 0 = 正常距离, 1 = 太远, 2 = 太近
            "confidence": float
        },
        "is_yawning": {
            "value": bool,      # True = 打哈欠, False = 未打哈欠
            "confidence": float
        },
        "num_face_total": {
            "value": int,
            "confidence": float
        }
    }
}
```

## 字段说明

### `head_pose`

- `pitch`：俯仰角
- `yaw`：偏航角
- `roll`：滚转角
- `confidence`：头部姿态置信度，范围为 0 到 1

### `ear`

- `left`：左眼 EAR
- `right`：右眼 EAR
- `value`：左右眼 EAR 平均值
- `confidence`：眼睛状态相关置信度，范围为 0 到 1

### `eye_state`

- `0`：睁眼
- `1`：闭眼

### `is_looking_screen`

这个值结合了头部姿态和睁眼状态：

- 闭眼时，直接认为 `False`
- 睁眼时，再根据头部朝向判断是否在看屏幕

### `attention_state`

- `0`：专注
- `1`：分心
- `2`：困倦
- `3`：缺席

### `face_distance_state`

- `0`：正常距离
- `1`：太远
- `2`：太近

### `is_yawning`

- `True`：打哈欠
- `False`：未打哈欠

### `num_face_total`

表示当前画面检测到的人脸总数。

## 常见问题

### 1. 闭眼却仍然显示睁眼

可以继续调 `eye_state` 的 EAR 阈值。当前代码已经把 EAR 显示在窗口中，方便你现场观察。

### 2. `Looking / Not looking` 判断不准

这是基于头部姿态的启发式判断，不是严格的眼球视线跟踪。如果需要更高精度，可以后续增加专门的 gaze 模型。

### 3. 摄像头打不开

- 检查 Windows 隐私设置是否允许摄像头访问
- 尝试修改 `--cam` 参数，例如 `0`、`1`、`2`

## 退出方式

在预览窗口按 `Esc` 即可退出。

## 说明

本项目的检测逻辑目前以实时性和易调参为主，适合演示和基础行为分析。
