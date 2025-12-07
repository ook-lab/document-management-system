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

    # Email Vision処理（超高速・超低コスト）
    # Gemini 2.5 Flash-LiteでHTMLメールスクリーンショットを解析
    EMAIL_VISION = {
        "provider": AIProvider.GEMINI,
        "model": "gemini-2.0-flash-lite",
        "description": "メールスクリーンショット解析（大量処理向け）",
        "temperature": 0.0,
        "max_tokens": 16384,  # 超長文メールに対応（Flash-Liteは最大32K）
        "cost_per_1k_tokens": 0.00005  # Flash-Liteは超低コスト
    }

    # Stage 2: 詳細抽出（速度・コスト重視）
    # Claude Haiku 4.5に変更（コスト効率と速度向上）
    STAGE2_EXTRACTOR = {
        "provider": AIProvider.CLAUDE,
        "model": "claude-haiku-4-5-20251001",  # 最新のHaiku 4.5モデル
        "description": "高速な情報抽出・構造化",
        "temperature": 0.0,
        "max_tokens": 4096,
        "cost_per_1k_tokens": 0.0008  # Haikuは低コスト
    }

    # Email Stage 2: メール専用の詳細抽出（超高速・超低コスト）
    # Gemini 2.5 Flash でメールのリッチ化処理
    EMAIL_STAGE2_EXTRACTOR = {
        "provider": AIProvider.GEMINI,
        "model": "gemini-2.5-flash",
        "description": "メール専用の情報抽出・構造化・タグ付け",
        "temperature": 0.0,
        "max_tokens": 16384,  # 長いメール + 表抽出テンプレートに対応
        "cost_per_1k_tokens": 0.00015  # Flashは超低コスト
    }
    
    # UI回答生成（速度・コスト重視）
    # ✅ GPT-5 miniをデフォルトに設定（高速・安価）
    UI_RESPONSE_GENERATOR = {
        "provider": AIProvider.OPENAI,
        "model": "gpt-5-mini",  # ✅ GPT-5 mini（デフォルト: $0.25/$2.00）
        "description": "高速で効率的な対話応答",
        # temperatureはGPT-5.1モデルでサポートされていないため削除
        "max_completion_tokens": 2048,
        "cost_per_1k_tokens": 0.00025  # GPT-5 mini
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
            "email_vision": cls.EMAIL_VISION,
            "stage2_extraction": cls.STAGE2_EXTRACTOR,
            "email_stage2_extraction": cls.EMAIL_STAGE2_EXTRACTOR,
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