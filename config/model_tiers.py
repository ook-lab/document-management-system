"""
ハイブリッドAIモデル構成 (FINAL_UNIFIED_COMPLETE_v4.md, INCREMENTAL_LEARNING_GUIDE_v2.mdに基づく)
各タスクに最適なモデルを割り当て
"""

from enum import Enum
from typing import Dict, Any

class AIProvider(Enum):
    """AIプロバイダの定義"""
    GEMINI = "gemini"
    CLAUDE = "claude"
    OPENAI = "openai"

class ModelTier:
    """モデル階層の定義"""
    
    # Stage 1: 初期分類（高速・低コスト重視）
    # Gemini 2.5 FlashによりPDF/画像を直接解析 (FINAL_UNIFIED_COMPLETE_v4.md, INCREMENTAL_LEARNING_GUIDE_v2.md)
    STAGE1_CLASSIFIER = {
        "provider": AIProvider.GEMINI,
        "model": "gemini-2.5-flash",
        "description": "PDF/画像直接解析、OCR不要",
        "temperature": 0.0,
        "max_tokens": 2048,
        "cost_per_1k_tokens": 0.00015
    }
    
    # Stage 2: 詳細抽出（速度・コスト重視）
    # Claude 4.5 Haikuに変更（コスト効率と速度向上）
    STAGE2_EXTRACTOR = {
        "provider": AIProvider.CLAUDE,
        "model": "claude-haiku-4-5-20250929",  # コスト効率と速度重視
        "description": "高速な情報抽出・構造化",
        "temperature": 0.0,
        "max_tokens": 4096,
        "cost_per_1k_tokens": 0.0008  # Haikuは低コスト
    }
    
    # UI回答生成（速度・コスト重視）
    # ✅ GPT-5-miniに変更（コスト効率と速度向上）
    UI_RESPONSE_GENERATOR = {
        "provider": AIProvider.OPENAI,
        "model": "gpt-5-mini",  # ✅ コスト効率と速度重視
        "description": "高速で効率的な対話応答",
        "temperature": 0.7,
        "max_completion_tokens": 2048,
        "cost_per_1k_tokens": 0.003  # GPT-5-miniは低コスト
    }
    
    # Embedding生成
    # OpenAI text-embedding-3-small (COMPLETE_IMPLEMENTATION_GUIDE_v3.mdより)
    EMBEDDING = {
        "provider": AIProvider.OPENAI,
        "model": "text-embedding-3-small",
        "description": "ベクトル検索用Embedding",
        "dimensions": 1536
    }
    
    @classmethod
    def get_model_for_task(cls, task: str) -> Dict[str, Any]:
        """タスクに応じた最適なモデルを返す"""
        task_mapping = {
            "stage1_classification": cls.STAGE1_CLASSIFIER,
            "stage2_extraction": cls.STAGE2_EXTRACTOR,
            "ui_response": cls.UI_RESPONSE_GENERATOR,
            "embeddings": cls.EMBEDDING
        }
        return task_mapping.get(task, cls.STAGE2_EXTRACTOR)
    
    @classmethod
    def get_all_models(cls) -> Dict[str, Dict[str, Any]]:
        """全モデル設定を返す"""
        return {
            "stage1": cls.STAGE1_CLASSIFIER,
            "stage2": cls.STAGE2_EXTRACTOR,
            "ui": cls.UI_RESPONSE_GENERATOR,
            "embedding": cls.EMBEDDING
        }

def get_model_config(tier: str) -> Dict[str, Any]:
    """指定されたタスクの最適モデル設定を取得 (COMPLETE_IMPLEMENTATION_GUIDE_v3.mdより)"""
    return ModelTier.get_model_for_task(tier)