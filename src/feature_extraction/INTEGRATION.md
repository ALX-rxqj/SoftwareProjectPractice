## Feature Extraction Module - 特征提取模块对接指南

### 模块概述

Feature Extraction模块负责从预处理后的视频帧中提取和分析人脸特征，包括：
- 头部姿态估计（pitch, yaw, roll）
- 眼睛状态检测（睁闭）
- 注视方向判断
- 打哈欠检测
- 注意力状态评估
- 人脸距离评估

### 数据对接架构

```
Preprocessing Module
  ├─ 视频源处理
  ├─ 人脸检测/追踪
  ├─ 人脸识别匹配
  └─ 生成 FeatureFramePacket
       ↓ (feature_callback)
Feature Extraction Service
  ├─ 接收特征帧数据包
  ├─ 数据格式验证
  └─ 调用 IOInterface 处理
       ↓ (scoring_callback)
  Scoring System
  ├─ 评分/评估
  └─ 后续业务逻辑
```

### 快速开始

#### 1. 基础使用

```python
from src.preprocessing import PreprocessingService
from src.feature_extraction import FeatureExtractionService

# 创建feature_extraction service
feature_service = FeatureExtractionService(
    face_model_path='src/feature_extraction/assets/face_detector.onnx',
    mark_model_path='src/feature_extraction/assets/face_landmarks.onnx',
    scoring_callback=my_scoring_function,
    log_callback=my_logger
)

# 创建preprocessing service，注册feature_callback
preprocessing_service = PreprocessingService(
    ui_callback=on_ui_packet,
    feature_callback=feature_service.process_feature_packet,  # 数据对接点
    log_callback=log_callback
)

# 启动摄像头
preprocessing_service.start_camera(device_id=0)
```

#### 2. 实现评分回调

```python
def my_scoring_function(output: Dict[str, Any]) -> None:
    """处理特征提取的结果。
    
    输出结构：
    {
        "timestamp": float,
        "face_id": int,
        "face_matched": bool,
        "features": {
            "head_pose": {
                "pitch": float,
                "yaw": float,
                "roll": float,
                "confidence": float
            },
            "eye_state": {
                "value": 0 | 1,  # 0=睁眼, 1=闭眼
                "confidence": float
            },
            "is_looking_screen": {
                "value": bool,
                "confidence": float
            },
            "attention_state": {
                "value": 0 | 1 | 2,  # 0=专注, 1=不专注, 2=偏离
                "confidence": float
            },
            "face_distance_state": {
                "value": 0 | 1 | 2,  # 0=正常, 1=过近, 2=过远
                "confidence": float
            },
            "is_yawning": {
                "value": bool,
                "confidence": float
            },
            "num_face_total": {
                "value": int,
                "confidence": float
            }
        }
    }
    """
    timestamp = output.get('timestamp')
    face_id = output.get('face_id')
    features = output.get('features', {})
    
    # 示例：检查注意力状态
    attention = features.get('attention_state', {})
    if attention.get('value') != 0:
        print(f"警告: 学生 {face_id} 注意力不集中")
    
    # 其他处理逻辑...
```

#### 3. 实现日志回调

```python
def my_logger(message: str) -> None:
    """处理来自feature_extraction的日志信息。"""
    print(f"[Feature Extraction] {message}")
```

### 数据流示例

当preprocessing检测到人脸时，会生成如下数据包并通过feature_callback传递：

```python
# FeatureFramePacket.to_dict()
{
    "timestamp": 1234567890.123,
    "faces": [
        {
            "face_id": "student_001",
            "student_name": "Alice",
            "face_roi": <np.ndarray shape=(480, 640, 3)>,  # 裁剪的人脸区域
            "confidence": 0.95,
            "face_matched": True
        },
        {
            "face_id": "student_002",
            "student_name": "Bob",
            "face_roi": <np.ndarray shape=(480, 640, 3)>,
            "confidence": 0.92,
            "face_matched": True
        }
    ],
    "owner_face_id": "student_001",  # 主人脸
    "frame": <np.ndarray shape=(1080, 1920, 3)>,  # 原始帧
    "face_matched": True
}
```

Feature Extraction Service接收此包后，会为每条记录调用IOInterface.process()，
然后通过scoring_callback发送结果。

### 性能优化

1. **模型路径配置**
   - 确保模型文件正确放置在`assets/`目录
   - 使用相对路径便于部署

2. **异常处理**
   - Service会自动捕获处理异常，不影响后续帧处理
   - 使用log_callback查看错误详情

3. **统计信息**
   ```python
   stats = feature_service.get_stats()
   print(f"已处理数据包: {stats['packets_processed']}")
   print(f"处理失败: {stats['packets_failed']}")
   ```

### 常见问题

**Q: 如何处理没有检测到人脸的情况？**

A: 当没有检测到人脸时，preprocessing会设置`owner_face_id`为-1，
IOInterface会生成默认输出（num_face_total=0，其他特征值为默认值）。

**Q: 人脸ID应该如何设置？**

A: `face_id`由preprocessing在人脸识别匹配时设置，可以是：
- 数字ID（如学生学号）
- 字符串ID（如"student_001"）
- 任意可序列化的值

**Q: 如何保证时间戳的准确性？**

A: 时间戳在preprocessing中由视频源或摄像头驱动，
feature_extraction直接使用preprocessing传入的时间戳值。

### 集成检查清单

- [ ] Preprocessing和Feature Extraction已正确导入
- [ ] 模型文件（face_detector.onnx, face_landmarks.onnx）已放置在assets目录
- [ ] feature_callback已在PreprocessingService中注册
- [ ] scoring_callback已实现并能正确处理输出
- [ ] log_callback（可选）已配置用于调试
- [ ] 测试单条数据包处理: `feature_service.process_feature_packet(test_packet)`
- [ ] 测试完整流程: 从摄像头或视频文件读取数据

### 关键代码位置

- **Service实现**: `src/feature_extraction/service.py`
- **IOInterface**: `src/feature_extraction/io_interface.py`
- **Preprocessing Service**: `src/preprocessing/service.py`
- **数据合约**: `src/preprocessing/contracts.py` (FeatureFramePacket定义)
