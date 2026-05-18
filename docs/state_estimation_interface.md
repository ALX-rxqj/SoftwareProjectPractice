# 状态估计模块 — 对外接口文档

## 版本：v2.0  
## 更新日期：2026-05-18  

---

## 1. 模块概述

状态估计模块负责将特征提取模块的输出（FEI-01）转换为专注度评分结果（SEI-01），并通过回调推送给界面模块。

核心评分管线：
```
特征提取模块 ──FEI-01──▶ 状态估计模块 ──SEI-01──▶ 界面模块
```

---

## 2. 输入接口（FEI-01）：特征数据

### 调用方：特征提取模块

特征提取模块通过调用 `StateEstimationService.on_features_extracted()` 传入数据。

### `on_features_extracted(timestamp, face_id, features)`

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `timestamp` | `float` | 帧时间戳（Unix秒） |
| `face_id` | `int` | 人脸追踪ID（owner_face_id），无人脸时为 -1（此时不调用此方法） |
| `features` | `dict` | 特征字典，详见下方 |

**`features` 字典结构（FEI-01 格式）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `head_pose` | `dict` | `{"pitch": float, "yaw": float, "roll": float, "confidence": float}` |
| `eye_state` | `dict` | `{"value": int(0=睁眼/1=闭眼), "confidence": float}` |
| `is_looking_screen` | `dict` | `{"value": bool(True=注视), "confidence": float}` |
| `attention_state` | `dict` | `{"value": int(0=专注/1=分心/2=困倦/3=离席), "confidence": float}` |
| `face_distance_state` | `dict` | `{"value": int(0=正常/1=太远/2=太近), "confidence": float}` |
| `is_yawning` | `dict` | `{"value": bool(True=打哈欠), "confidence": float}` |
| `num_face_total` | `dict` | **新增** — `{"value": int(画面人脸总数), "confidence": float}` |

---

## 3. 输出接口（SEI-01）：专注度评分结果

### 接收方：界面模块

界面模块通过注册回调 `set_focus_result_callback(callback)` 接收结果。

### `FocusResultData` 数据结构

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| `timestamp` | `float` | — | 帧时间戳 |
| `session_id` | `str` | — | 会话ID |
| `head_pose_score` | `float` | [0, 100] | 头部姿态综合分（pitch/yaw/roll 加权） |
| `behavior_score` | `float` | [0, 100] | 行为动作综合分（眼部/注视/哈欠/距离加权） |
| `expression_score` | `float` | [0, 100] | 表情评分（专注/分心/困倦/离席四级） |
| `evidence_score` | `float` | [0, 100] | D-S 证据理论融合分（三源：头姿+动作+表情） |
| `people_score` | `float` | 0 或 100 | 人数评分（1人=100，否则=0） |
| `final_focus_score` | `float` | [0, 100] | 最终专注度评分（单人=evidence_score，否则=0） |
| `is_force_zero` | `bool` | — | 当前帧是否因人数异常强制置零 |
| `is_over_threshold` | `bool` | — | **新增** — 人数异常累计次数是否超过阈值 |
| `warn_msg` | `WarnInfo` 或 `None` | — | 告警信息（可选） |

### `WarnInfo` 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `warn_type` | `str` | 告警类型：`"no_face"`（无人脸）、`"multi_face"`（多人脸） |
| `detail` | `str` | 告警详情描述 |

### `to_dict()` 输出示例

```json
{
    "timestamp": 1716000000.123,
    "session_id": "session_a1b2c3d4",
    "head_pose_score": 85.0,
    "behavior_score": 70.5,
    "expression_score": 90.0,
    "evidence_score": 85.2,
    "people_score": 100.0,
    "final_focus_score": 85.2,
    "is_force_zero": false,
    "is_over_threshold": false,
    "warn_info": null
}
```

---

## 4. 指令接口（on_* 系列）

界面模块通过 `StateEstimationService` 实例直接调用以下方法：

### 4.1 会话控制

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `on_session_init()` | 无 | `{"success": bool, "session_id": str}` | 创建新会话，默认 CLASS 模式 |
| `on_session_end(session_id)` | `session_id: str` | `{"success": bool}` | 结束指定会话 |
| `on_control_analysis(start)` | `start: bool` | `{"session_id": str}` (启动) / `{"success": bool}` (停止) | 启动/停止专注度分析，启动时自动创建会话 |
| `on_mode_changed(mode)` | `mode: str` (`"class"` / `"exam"`) | `{"success": bool}` | 切换监督模式（影响评分策略） |
| `on_threshold_changed(threshold)` | `threshold: float` [0, 100] | `{"success": bool}` | 更新当前会话告警阈值 |

### 4.2 视频控制（转发预处���模块）

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `on_control_capture(device_id, start)` | `device_id: int, start: bool` | `{"success": bool, "msg": str}` | 启动/停止摄像头采集 |
| `on_load_video(file_path)` | `file_path: str` | `{"success": bool, "msg": str}` | 加载本地视频文件 |
| `on_query_cameras()` | 无 | `{"success": bool, "cameras": list}` | 获取可用摄像头列表 |

### 4.3 数据查询

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `on_query_sessions(start_date, end_date, mode, focus_min, focus_max, abnormal_min, abnormal_max)` | 筛选条件详见签名 | `list[dict]` | 按条件查询会话摘要列表 |
| `on_query_records(session_id, start_time, end_time)` | `session_id: str, start_time: str, end_time: str` | `list[dict]` | 查询指定会话的逐帧评分记录 |

---

## 5. 回调注册

界面模块在初始化阶段注册回调：

```python
from src.state_estimation.service import StateEstimationService

svc = StateEstimationService()

# 注册专注度评分结果回调（SEI-01）
svc.set_focus_result_callback(on_focus_result_received)
# 回调签名：def on_focus_result_received(result: FocusResultData) -> None

# 注册预处理模块指令回调（路由摄像头/视频控制）
svc.set_preprocessing_callback(on_preprocessing_command)
# 回调签名：def on_preprocessing_command(cmd: str, params: dict) -> Optional[dict]

# 注册日志回调（可选）
svc.set_log_callback(on_log_message)
# 回调签名：def on_log_message(message: str) -> None
```

---

## 6. 评分逻辑简述

### 6.1 头部姿态评分
- 三个子维度：pitch(上下, w=0.4) / yaw(左右, w=0.4) / roll(歪头, w=0.2)
- 正常范围（满分）：pitch[-15°, 10°], yaw[-12°, 12°], roll[-10°, 10°]
- 超出正常但在 ±90° 内：100→0 线性衰减
- 超过 ±90°：0 分
- 置信度 ≥0.8 直接采用，0.5~0.8 向 0 线性插值，<0.5 置 50

### 6.2 行为动作评分
- 四个子维度：睁眼闭眼(w=0.35) / 注视屏幕(w=0.35) / 打哈欠(w=0.1) / 人脸距离(w=0.2)
- 好状态→100，坏状态→0，各自独立置信度修正
- 置信度低时向 50 收敛

### 6.3 表情评分
- attention_state：专注=100，分心=60，困倦=30，离席=0
- 置信度低时向下一级插值（离席无下级，始终 0）

### 6.4 证据融合评分
- D-S 证据理论，三源（头姿/动作/表情）折扣融合
- 识别框��� Θ = {专注, 不专注}，只提供正面证据
- 折扣系数按模式区分：

| 证据源 | 网课(CLASS) | 考试(EXAM) |
|--------|------------|-----------|
| 头部姿态 | α=0.6 | α=0.5 |
| 行为动作 | α=0.6 | α=0.5 |
| 表情 | α=0.6 | α=0.6 |

### 6.5 最终分与人数开关
- 人数=1：`final_focus_score = evidence_score`，`is_force_zero = False`
- 人数≠1：`final_focus_score = 0`，`is_force_zero = True`
- 人数异常累计超过阈值则 `is_over_threshold = True`

| 模式 | 人数异常累计阈值 | 说明 |
|------|----------------|------|
| CLASS (网课) | 500 帧 | 较宽松 |
| EXAM (考试) | 200 帧 | 较严格 |

---

## 7. 完整数据流（一次性说明）

```
┌─────────────┐  on_control_analysis(True)
│  界面模块   │ ──────────────────────────────▶ StateEstimationService
│ (GUI)       │                                      │
│             │ ◀── FocusResultData (每帧) ─────────┤
│             │        via focus_result_callback      │
└─────────────┘                                      │
                                                     │
┌─────────────────┐  on_features_extracted()         │
│ 特征提取模块    │ ────────────────────────────────▶│
│ (Feature Extract)│      FEI-01 格式 features dict   │
└─────────────────┘                                  │
                                                     ▼
                                          FocusEstimator.estimate()
                                          ┌────────────────────┐
                                          │ 头姿/动作/表情评分 │
                                          │ → 证据融合         │
                                          │ → 人数开关控制     │
                                          │ → 异常累计阈值判断 │
                                          └────────────────────┘
```

---

## 8. 变更记录

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-05-18 | v2.0 | `FocusResultData` 新增 `is_over_threshold: bool`；FEI-01 `features` 新增 `num_face_total` 字段；评分算法从占位 stub 全部实现（头姿/动作/表情/证据融合/人数开关）；`EstimationStats` 类已删除 |
| 更早 | v1.0 | 初始骨架（评分返回零值占位） |

---

有疑问直接找状态估计模块负责人。
