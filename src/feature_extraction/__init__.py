"""Feature Extraction Module - 特征提取模块

核心模块：
- io_interface: 输入/输出接口，处理单条数据包
- service: 特征提取服务，接收并处理来自preprocessing的数据包

使用：
    from src.feature_extraction import FeatureExtractionService
    
    service = FeatureExtractionService(
        scoring_callback=my_callback
    )
    # 在PreprocessingService中注册回调
    preprocessing_service = PreprocessingService(
        feature_callback=service.process_feature_packet
    )
"""

from .service import FeatureExtractionService

__all__ = [
    'FeatureExtractionService',
]
