"""
特征提取服务集成测试 — Feature Extraction Service Tests

测试 src/feature_extraction/service.py 中 FeatureExtractionService 的：
- process_feature_packet 字段验证
- 缺失字段的拒绝逻辑
- 回调分发（scoring_callback / state_callback）
- 统计计数累加与重置

技术要点：使用 unittest.mock.patch.object 绕过 IOInterface 的 MediaPipe 模型加载。

运行方式:
    python -m pytest test/test_feature_extraction_service.py -v
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

import numpy as np


@pytest.fixture
def fe_service():
    """创建 FeatureExtractionService，IOInterface 被 mock 掉"""
    import src.feature_extraction.service as fe_mod
    with patch.object(fe_mod, "IOInterface"):
        svc = fe_mod.FeatureExtractionService(
            mp_model_path="fake_path.task",
        )
    # 替换 io_interface.process 为 mock
    svc.io_interface = MagicMock()
    return svc


def _make_valid_packet():
    """构造符合格式的有效数据包（含 face_roi）"""
    dummy_roi = np.zeros((112, 112, 3), dtype=np.uint8)
    return {
        "timestamp": 1000.0,
        "face_id": "face_001",
        "owner_face_id": "face_001",
        "face_matched": True,
        "frame": np.zeros((480, 640, 3), dtype=np.uint8),
        "original_frame": np.zeros((480, 640, 3), dtype=np.uint8),
        "faces": [
            {"face_id": "face_001", "face_roi": dummy_roi, "face_matched": True},
        ],
    }


# ============================================================
# 字段验证测试
# ============================================================

class TestFieldValidation:
    """process_feature_packet 输入校验（返回值为 None，通过 stats 验证结果）"""

    def test_valid_packet_accepted(self, fe_service):
        """有效数据包成功处理 → packets_processed 增加"""
        packet = _make_valid_packet()
        fe_service.io_interface.process.side_effect = (
            lambda record, send_to_scoring: None
        )
        fe_service.process_feature_packet(packet)
        assert fe_service.stats["packets_received"] == 1
        assert fe_service.stats["packets_processed"] == 1
        assert fe_service.stats["packets_failed"] == 0

    def test_missing_timestamp_rejected(self, fe_service):
        """缺少 timestamp → packets_failed 增加"""
        packet = _make_valid_packet()
        del packet["timestamp"]
        fe_service.process_feature_packet(packet)
        assert fe_service.stats["packets_failed"] == 1

    def test_missing_owner_face_id_rejected(self, fe_service):
        """缺少 owner_face_id → packets_failed 增加"""
        packet = _make_valid_packet()
        del packet["owner_face_id"]
        fe_service.process_feature_packet(packet)
        assert fe_service.stats["packets_failed"] == 1

    def test_non_dict_rejected(self, fe_service):
        """非 dict 类型 → packets_failed 累加"""
        fe_service.process_feature_packet(None)
        fe_service.process_feature_packet("not_a_dict")
        assert fe_service.stats["packets_failed"] == 2

    def test_invalid_faces_type_rejected(self, fe_service):
        """faces 类型不是 list → 拒绝"""
        packet = _make_valid_packet()
        packet["faces"] = "not_a_list"
        fe_service.process_feature_packet(packet)
        assert fe_service.stats["packets_failed"] == 1

    def test_missing_faces_key_rejected(self, fe_service):
        """缺少 faces 键 → 拒绝"""
        packet = _make_valid_packet()
        del packet["faces"]
        fe_service.process_feature_packet(packet)
        assert fe_service.stats["packets_failed"] == 1


# ============================================================
# 回调测试
# ============================================================

class TestCallbacks:
    """scoring_callback 和 state_callback"""

    def test_scoring_callback_receives_output(self, fe_service):
        """验证 scoring_callback 被调用"""
        received = []
        fe_service.scoring_callback = lambda data: received.append(data)

        test_output = {
            "timestamp": 1000.0, "face_id": "face_001",
            "face_matched": True, "features": {"head_pose": {"pitch": 0.0}},
        }
        fe_service.io_interface.process.side_effect = (
            lambda record, send_to_scoring: send_to_scoring(test_output)
        )

        fe_service.process_feature_packet(_make_valid_packet())
        assert len(received) == 1
        assert received[0]["face_id"] == "face_001"

    def test_state_callback_receives_output(self, fe_service):
        """验证 state_callback 被调用"""
        received = []
        fe_service.state_callback = lambda data: received.append(data)

        test_output = {
            "timestamp": 1000.0, "face_id": "face_001",
            "face_matched": True, "features": {"head_pose": {"pitch": 0.0}},
        }
        fe_service.io_interface.process.side_effect = (
            lambda record, send_to_scoring: send_to_scoring(test_output)
        )

        fe_service.process_feature_packet(_make_valid_packet())
        assert len(received) == 1
        assert received[0] == test_output

    def test_state_callback_none_is_safe(self, fe_service):
        """state_callback 为 None 时不报错"""
        fe_service.state_callback = None
        fe_service.io_interface.process.side_effect = (
            lambda record, send_to_scoring: send_to_scoring({"features": {}})
        )
        # 不应抛出异常
        fe_service.process_feature_packet(_make_valid_packet())
        assert fe_service.stats["packets_processed"] == 1


# ============================================================
# 统计测试
# ============================================================

class TestStats:
    """统计计数"""

    def test_stats_accumulation(self, fe_service):
        """多次处理后统计正确累加"""
        fe_service.io_interface.process.side_effect = (
            lambda record, send_to_scoring: None
        )

        # 3 次成功
        for _ in range(3):
            fe_service.process_feature_packet(_make_valid_packet())
        # 2 次失败（非 dict）
        for _ in range(2):
            fe_service.process_feature_packet(None)

        assert fe_service.stats["packets_received"] == 5
        assert fe_service.stats["packets_processed"] == 3
        assert fe_service.stats["packets_failed"] == 2

    def test_reset_stats(self, fe_service):
        """reset_stats 清零所有计数器"""
        fe_service.io_interface.process.side_effect = (
            lambda record, send_to_scoring: None
        )
        fe_service.process_feature_packet(_make_valid_packet())
        fe_service.process_feature_packet(None)

        fe_service.reset_stats()
        assert fe_service.stats["packets_received"] == 0
        assert fe_service.stats["packets_processed"] == 0
        assert fe_service.stats["packets_failed"] == 0

    def test_get_stats_returns_copy(self, fe_service):
        """get_stats 返回拷贝，外部修改不影响内部"""
        stats = fe_service.get_stats()
        stats["packets_received"] = 999
        assert fe_service.stats["packets_received"] == 0
