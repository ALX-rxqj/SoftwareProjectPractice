"""
模拟数据管理器单元测试 — Mock Data Manager Tests

测试 src/interface/mock_data_manager.py 中 MockDataManager 的：
- 实时评分生成的结构和值域
- 摄像头列表生成
- 全局启用/禁用开关
- 专注度结果结构
- 记录生成结构

运行方式:
    python -m pytest test/test_mock_data_manager.py -v
"""

import pytest

from src.interface.mock_data_manager import MockDataManager, mock_data_manager


@pytest.fixture
def fresh_mock():
    """全新的 MockDataManager 实例（绕过单例）"""
    # 重置单例
    MockDataManager._instance = None
    mgr = MockDataManager()
    return mgr


class TestRealtimeScores:
    """实时评分生成测试"""

    def test_has_all_dimension_keys(self, fresh_mock):
        """generate_realtime_scores 包含所有评分维度"""
        scores = fresh_mock.generate_realtime_scores()
        expected_keys = {"head_pose", "eye", "yawn", "distance", "evidence",
                        "people", "final_focus", "warn_info"}
        for key in expected_keys:
            assert key in scores, f"缺少键: {key}"

    def test_all_scores_in_range(self, fresh_mock):
        """所有评分在 [0, 100] 内"""
        for _ in range(20):
            scores = fresh_mock.generate_realtime_scores()
            for key in ["head_pose", "eye", "yawn", "distance", "evidence", "people"]:
                assert 0 <= scores[key] <= 100, f"{key}={scores[key]} 超出范围"
            assert 0 <= scores["final_focus"] <= 100

    def test_disabled_returns_empty(self, fresh_mock):
        """禁用时 generate_realtime_scores 返回空字典"""
        fresh_mock.set_global_enabled(False)
        assert fresh_mock.generate_realtime_scores() == {}

    def test_enabled_returns_non_empty(self, fresh_mock):
        """启用时返回非空字典"""
        fresh_mock.set_global_enabled(True)
        assert len(fresh_mock.generate_realtime_scores()) > 0


class TestFocusResult:
    """专注度结果生成测试"""

    def test_has_all_sei01_fields(self, fresh_mock):
        """generate_focus_result 包含 SEI-01 全部字段"""
        result = fresh_mock.generate_focus_result("test_sid")
        expected_keys = {
            "timestamp", "session_id", "head_pose_score", "eye_score",
            "yawn_score", "distance_score", "behavior_score", "expression_score",
            "evidence_score", "people_score",
            "final_focus_score", "is_force_zero", "is_over_threshold", "warn_info",
        }
        assert set(result.keys()) == expected_keys

    def test_disabled_returns_empty(self, fresh_mock):
        """禁用时 generate_focus_result 返回空字典"""
        fresh_mock.set_global_enabled(False)
        assert fresh_mock.generate_focus_result() == {}


class TestCameraList:
    """摄像头列表测试"""

    def test_returns_list_of_devices(self, fresh_mock):
        """返回包含多个摄像头的列表"""
        cameras = fresh_mock.generate_camera_list()
        assert len(cameras) >= 1
        for cam in cameras:
            assert "device_id" in cam
            assert "device_name" in cam
            assert isinstance(cam["device_id"], int)

    def test_disabled_no_effect_on_camera_list(self, fresh_mock):
        """摄像头列表不受全局开关影响（不检查 _global_enabled）"""
        fresh_mock.set_global_enabled(False)
        cameras = fresh_mock.generate_camera_list()
        assert len(cameras) >= 1


class TestGlobalToggle:
    """全局开关测试"""

    def test_default_enabled(self, fresh_mock):
        """默认启用"""
        assert fresh_mock.is_enabled is True

    def test_toggle_off(self, fresh_mock):
        """关闭后 is_enabled=False"""
        fresh_mock.set_global_enabled(False)
        assert fresh_mock.is_enabled is False

    def test_toggle_on_again(self, fresh_mock):
        """关闭再开启"""
        fresh_mock.set_global_enabled(False)
        fresh_mock.set_global_enabled(True)
        assert fresh_mock.is_enabled is True


class TestRecords:
    """历史记录生成测试"""

    def test_records_structure(self, fresh_mock):
        """generate_records 返回的记录结构正确"""
        records = fresh_mock.generate_records("STU_2024001", count=3)
        assert len(records) > 0
        for r in records:
            assert "session_id" in r
            assert "timestamp" in r
            assert "date" in r
            assert "time" in r
            assert "final_focus_score" in r
            assert "is_force_zero" in r

    def test_disabled_returns_empty_list(self, fresh_mock):
        """禁用时 generate_records 返回空列表"""
        fresh_mock.set_global_enabled(False)
        assert fresh_mock.generate_records("STU_2024001") == []
