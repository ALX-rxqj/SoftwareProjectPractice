"""
共享测试夹具 — Shared pytest fixtures

为所有测试模块提供可复用的测试数据和工具函数。
"""

import hashlib
import os
import tempfile
import time as _time

import pytest

from src.state_estimation.contracts import (
    FeatureData,
    FocusResultData,
    MonitorMode,
    WarnInfo,
    WARN_EYE_STATE,
)
from src.state_estimation.estimator import FocusEstimator
from src.state_estimation.downsampler import Downsampler
from src.state_estimation.session_manager import SessionManager


# ============================================================
# FeatureData 夹具 — 覆盖各种典型场景
# ============================================================

def _make_feature_data(
    head_pose=None,
    eye_state=None,
    is_looking_screen=None,
    attention_state=None,
    face_distance_state=None,
    is_yawning=None,
    num_face_total=None,
    face_matched=True,
    face_id="face_001",
    timestamp=1000.0,
):
    """构造 FeatureData 的辅助函数，减少重复代码"""
    return FeatureData(
        timestamp=timestamp,
        face_id=face_id,
        face_matched=face_matched,
        head_pose=head_pose or {"pitch": 0.0, "yaw": 0.0, "roll": 0.0, "confidence": 1.0},
        eye_state=eye_state or {"value": 0, "confidence": 1.0},
        is_looking_screen=is_looking_screen or {"value": True, "confidence": 1.0},
        attention_state=attention_state or {"value": 0, "confidence": 1.0},
        face_distance_state=face_distance_state or {"value": 0, "confidence": 1.0},
        is_yawning=is_yawning or {"value": False, "confidence": 1.0},
        num_face_total=num_face_total or {"value": 1, "confidence": 1.0},
    )


@pytest.fixture
def sample_feature_data_good():
    """全部状态良好的特征数据：正面姿态、睁眼、注视屏幕、单人"""
    return _make_feature_data()


@pytest.fixture
def sample_feature_data_distracted():
    """注意力分散的特征数据"""
    return _make_feature_data(
        attention_state={"value": 1, "confidence": 1.0},
    )


@pytest.fixture
def sample_feature_data_sleepy():
    """困倦状态的特征数据"""
    return _make_feature_data(
        attention_state={"value": 2, "confidence": 1.0},
        is_yawning={"value": True, "confidence": 1.0},
    )


@pytest.fixture
def sample_feature_data_multi_face():
    """多人画面的特征数据"""
    return _make_feature_data(
        num_face_total={"value": 3, "confidence": 1.0},
    )


@pytest.fixture
def sample_feature_data_no_face():
    """无人脸的特征数据"""
    return _make_feature_data(
        num_face_total={"value": 0, "confidence": 1.0},
    )


@pytest.fixture
def sample_feature_data_low_conf():
    """低置信度的特征数据"""
    return _make_feature_data(
        head_pose={"pitch": 0.0, "yaw": 0.0, "roll": 0.0, "confidence": 0.4},
        eye_state={"value": 0, "confidence": 0.4},
        is_looking_screen={"value": True, "confidence": 0.4},
        attention_state={"value": 0, "confidence": 0.4},
    )


@pytest.fixture
def sample_feature_data_mismatch():
    """人脸不匹配的特征数据"""
    return _make_feature_data(face_matched=False)


@pytest.fixture
def sample_feature_data_bad_pose():
    """头部姿态偏移较大的特征数据（会触发低分告警）"""
    return _make_feature_data(
        head_pose={"pitch": 80.0, "yaw": 80.0, "roll": 80.0, "confidence": 1.0},
    )


# ============================================================
# FocusResultData 夹具
# ============================================================

def _make_focus_result(
    session_id="test_session",
    timestamp=1000.0,
    head_pose_score=90.0,
    eye_score=85.0,
    yawn_score=80.0,
    distance_score=50.0,
    evidence_score=85.0,
    people_score=100.0,
    final_focus_score=85.0,
    is_force_zero=False,
    is_over_threshold=False,
    warn_candidates=(),
):
    return FocusResultData(
        timestamp=timestamp,
        session_id=session_id,
        head_pose_score=head_pose_score,
        eye_score=eye_score,
        yawn_score=yawn_score,
        distance_score=distance_score,
        evidence_score=evidence_score,
        people_score=people_score,
        final_focus_score=final_focus_score,
        is_force_zero=is_force_zero,
        is_over_threshold=is_over_threshold,
        warn_candidates=warn_candidates,
    )


@pytest.fixture
def sample_focus_result_good():
    return _make_focus_result()


@pytest.fixture
def sample_focus_result_low():
    return _make_focus_result(
        final_focus_score=30.0,
        warn_candidates=(
            WarnInfo(warn_type=WARN_EYE_STATE, detail="眼部状态评分过低: 25"),
        ),
    )


@pytest.fixture
def sample_focus_result_anomaly():
    return _make_focus_result(
        final_focus_score=0.0,
        is_force_zero=True,
        warn_candidates=(
            WarnInfo(warn_type="no_face", detail="画面中无人脸"),
        ),
    )


# ============================================================
# 组件实例夹具
# ============================================================

@pytest.fixture
def estimator_class():
    """CLASS 模式的 FocusEstimator 实例"""
    return FocusEstimator(mode=MonitorMode.CLASS)


@pytest.fixture
def estimator_exam():
    """EXAM 模式的 FocusEstimator 实例"""
    return FocusEstimator(mode=MonitorMode.EXAM)


@pytest.fixture
def session_manager():
    """全新的 SessionManager 实例"""
    return SessionManager()


@pytest.fixture
def downsampler():
    """全新的 Downsampler 实例"""
    return Downsampler()


# ============================================================
# 数据库测试夹具
# ============================================================

@pytest.fixture
def db_service(monkeypatch):
    """创建使用临时文件的 DatabaseService，绕过 Windows 注册表密钥派生"""
    from src.database.database_service import DatabaseService
    from src.database.connection import ConnectionManager
    from src.database.schema import SchemaManager

    # 固定密钥替代 Windows MachineGuid 派生
    fixed_key = hashlib.sha256(b"test_fixed_key").digest()
    monkeypatch.setattr(ConnectionManager, "_derive_key", staticmethod(lambda: fixed_key))

    # 重置单例状态
    DatabaseService._instance = None
    ConnectionManager._instance = None
    SchemaManager._instance = None

    # 使用临时文件（sqlcipher3 的 PRAGMA key 需要文件支持）
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="test_")
    os.close(fd)

    svc = DatabaseService()
    svc.initialize(db_path)

    yield svc

    svc.shutdown()
    DatabaseService._instance = None
    ConnectionManager._instance = None
    SchemaManager._instance = None

    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def reset_singletons():
    """每个测试后重置所有单例状态，防止测试间状态泄漏"""
    yield
    from src.database.database_service import DatabaseService
    from src.database.connection import ConnectionManager
    from src.database.schema import SchemaManager
    from src.interface.mock_data_manager import MockDataManager

    DatabaseService._instance = None
    ConnectionManager._instance = None
    SchemaManager._instance = None
    MockDataManager._instance = None
