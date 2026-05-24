# 测试文档

## 快速开始

```bash
conda activate testModel

# 运行全部新增测试
python -m pytest test/ -v -k "not test_face_registration"

# 只运行纯逻辑测试（最快）
python -m pytest test/ -v -m unit

# 无显示器环境
set QT_QPA_PLATFORM=offscreen
python -m pytest test/ -v
```

## 测试架构

```
test/
├── conftest.py                          # 共享夹具（FeatureData、FocusResultData、组件实例等）
├── test_face_registration.py            # 已有：人脸注册 UI 测试（18 tests）
│
│  纯逻辑单元测试（零外部依赖）
├── test_contracts.py                    # 数据合约：告警优先级、序列化
├── test_focus_estimator.py              # 核心评分算法：5 维度 + D-S 融合
├── test_session_manager.py              # 会话生命周期：创建/结束/删除/统计
├── test_downsampler.py                  # 降采样：时间窗压缩、均值帧选取
├── test_mock_data_manager.py            # 模拟数据：生成格式与值域
│
│  集成测试（mock 外部依赖）
├── test_database_service.py             # 数据库：Schema 建表、CRUD、级联删除
├── test_state_estimation_service.py     # 评分管线：FeatureData → FocusResultData
└── test_feature_extraction_service.py   # 字段验证：数据包校验与回调分发
```

## 测试分层

| 层级 | 文件 | 测试数 | 运行时间 | 依赖 |
|------|------|--------|---------|------|
| 纯逻辑 | contracts / estimator / session / downsampler / mock_data | ~103 | < 1s | 无 |
| 数据库 | database_service | ~15 | ~1s | sqlcipher3（临时文件） |
| 服务集成 | state_estimation / feature_extraction | ~34 | ~1s | Mock IOInterface |

## 核心夹具（conftest.py）

| 夹具名 | 用途 |
|--------|------|
| `sample_feature_data_good` | 全部正常的人脸特征数据 |
| `sample_feature_data_distracted` | 注意力分散 |
| `sample_feature_data_sleepy` | 困倦 + 打哈欠 |
| `sample_feature_data_multi_face` | 画面中有多人 |
| `sample_feature_data_no_face` | 画面中无人脸 |
| `sample_feature_data_low_conf` | 所有特征维度低置信度 |
| `sample_feature_data_mismatch` | 人脸不匹配 |
| `estimator_class` / `estimator_exam` | CLASS/EXAM 模式的评分器 |
| `session_manager` | 干净的会话管理器 |
| `downsampler` | 干净的降采样器 |
| `db_service` | 使用临时文件的加密数据库（mock 密钥派生） |

## Mock 策略

| 被 Mock 的依赖 | 方式 | 原因 |
|---------------|------|------|
| `ConnectionManager._derive_key` | `monkeypatch.setattr` | 绕过 Windows 注册表读取 |
| `StateEstimationService._start_processing` | `monkeypatch.setattr` → no-op | 避免 daemon 线程，同步测试 |
| `IOInterface` (MediaPipe 模型) | `unittest.mock.patch.object` | 绕过模型文件加载 |
| 单例状态 (DatabaseService 等) | `reset_singletons` autouse fixture | 测试间隔离 |

## 运行选项

```bash
# 按标记筛选
python -m pytest test/ -v -m unit          # 纯逻辑测试
python -m pytest test/ -v -m integration   # 集成测试
python -m pytest test/ -v -m smoke         # 冒烟测试

# 只运行特定模块
python -m pytest test/test_focus_estimator.py -v

# 查看所有测试（不执行）
python -m pytest --collect-only

# 失败时显示局部变量
python -m pytest test/ -v --tb=long -l
```

## 未覆盖的范围（需模型文件或硬件）

- `PreprocessingService` — 依赖 YOLOv8 + InsightFace 模型 + 摄像头
- `ExportController` / `ExportReportUtil` — 依赖 Qt 原生对话框 + matplotlib/reportlab
- 完整端到端测试 — 已有 `test/run_stress_test.py` 提供基础
