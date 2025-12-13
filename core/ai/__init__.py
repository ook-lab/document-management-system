"""
Core AI モジュール
B1更新: Stage1/Stage2 → StageA/B/C 命名変更
"""
from .llm_client import LLMClient
from .stageA_classifier import StageAClassifier
# from .stageB_vision import StageBVisionProcessor  # Gmail取り込み専用（Cloud Runでは不要）
from .stageC_extractor import StageCExtractor
from .embeddings import EmbeddingClient

__all__ = [
    'LLMClient',
    'StageAClassifier',
    # 'StageBVisionProcessor',  # Gmail取り込み専用
    'StageCExtractor',
    'EmbeddingClient',
]
