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

    # Email Vision処理（高速HTMLスクリーンショット解析）
    # Gemini 2.5 FlashでHTMLメールスクリーンショットを高速解析
    EMAIL_VISION = {
        "provider": AIProvider.GEMINI,
        "model": "gemini-2.5-flash",
        "description": "メールスクリーンショット高速解析",
        "temperature": 0.0,
        "max_tokens": 16384,
        "cost_per_1k_tokens": 0.00015  # Flashは低コスト
    }

    # Stage C: 詳細抽出（速度・コスト重視）
    # Claude Haiku 4.5に変更（コスト効率と速度向上）
    STAGEC_EXTRACTOR = {
        "provider": AIProvider.CLAUDE,
        "model": "claude-haiku-4-5-20251001",  # 最新のHaiku 4.5モデル
        "description": "高速な情報抽出・構造化",
        "temperature": 0.0,
        "max_tokens": 4096,
        "cost_per_1k_tokens": 0.0008  # Haikuは低コスト
    }

    # 後方互換性のためのエイリアス
    STAGE2_EXTRACTOR = STAGEC_EXTRACTOR

    # Email Stage C: メール専用の詳細抽出（超高速・超低コスト）
    # Gemini 2.5 Flash でメールのリッチ化処理
    EMAIL_STAGEC_EXTRACTOR = {
        "provider": AIProvider.GEMINI,
        "model": "gemini-2.5-flash",
        "description": "メール専用の情報抽出・構造化・タグ付け",
        "temperature": 0.0,
        "max_tokens": 16384,  # 長いメール + 表抽出テンプレートに対応
        "cost_per_1k_tokens": 0.00015  # Flashは超低コスト
    }
    
    # UI回答生成（デフォルト：速度・コスト・精度のバランス）
    # ✅ Gemini 2.5 Flashをデフォルトに設定（100万トークンコンテキスト、高速、GPT-5-miniより安定）
    UI_RESPONSE_GENERATOR = {
        "provider": AIProvider.GEMINI,
        "model": "gemini-2.5-flash",  # ✅ Gemini 2.5 Flash（デフォルト: $0.30/$2.50）
        "description": "100万トークンコンテキスト、高速で安定した対話応答",
        "temperature": 0.7,  # 自然な会話のため適度な創造性を保つ
        "max_tokens": 4096,
        "cost_per_1k_tokens": 0.0003  # Gemini 2.5 Flash
    }

    # UI回答生成（高速モード：大量処理・単純タスク用）
    # ✅ Gemini 2.5 Flash-Liteで超高速・超低コストを実現
    UI_RESPONSE_GENERATOR_LITE = {
        "provider": AIProvider.GEMINI,
        "model": "gemini-2.5-flash-lite",  # ✅ Gemini 2.5 Flash-Lite（$0.10/$0.40）
        "description": "超高速・超低コスト（Flash比80%削減）の単純タスク処理",
        "temperature": 0.5,
        "max_tokens": 2048,
        "cost_per_1k_tokens": 0.0001  # Gemini 2.5 Flash-Lite
    }

    # UI回答生成（高精度モード：複雑な推論・数学・コーディング用）
    # ✅ GPT-5.1を高精度オプションとして維持
    UI_RESPONSE_GENERATOR_PREMIUM = {
        "provider": AIProvider.OPENAI,
        "model": "gpt-5.1",  # ✅ GPT-5.1（高精度: $0.125/$10.00）
        "description": "最高精度の推論・数学・コーディング支援",
        # temperatureはGPT-5.1モデルでサポートされていないため削除
        "max_completion_tokens": 4096,
        "cost_per_1k_tokens": 0.000125  # GPT-5.1
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
            "stageA_classification": cls.STAGE1_CLASSIFIER,  # Stage A: 分類
            "stage1_classification": cls.STAGE1_CLASSIFIER,  # 後方互換性
            "email_vision": cls.EMAIL_VISION,
            "stageC_extraction": cls.STAGEC_EXTRACTOR,  # Stage C: 詳細抽出
            "stage2_extraction": cls.STAGEC_EXTRACTOR,  # 後方互換性
            "email_stageC_extraction": cls.EMAIL_STAGEC_EXTRACTOR,
            "email_stage2_extraction": cls.EMAIL_STAGEC_EXTRACTOR,  # 後方互換性
            "ui_response": cls.UI_RESPONSE_GENERATOR,  # デフォルト: Gemini 2.5 Flash
            "ui_response_lite": cls.UI_RESPONSE_GENERATOR_LITE,  # 高速モード: Gemini 2.5 Flash-Lite
            "ui_response_premium": cls.UI_RESPONSE_GENERATOR_PREMIUM,  # 高精度モード: GPT-5.1
            "embeddings": cls.EMBEDDING
        }
        return task_mapping.get(task, cls.STAGEC_EXTRACTOR)
    
    @classmethod
    def get_all_models(cls) -> Dict[str, Dict[str, Any]]:
        """全モデル設定を返す"""
        return {
            "stageA": cls.STAGE1_CLASSIFIER,
            "stageC": cls.STAGEC_EXTRACTOR,
            "ui": cls.UI_RESPONSE_GENERATOR,
            "embedding": cls.EMBEDDING,
            # 後方互換性
            "stage1": cls.STAGE1_CLASSIFIER,
            "stage2": cls.STAGEC_EXTRACTOR
        }

def get_model_config(tier: str) -> Dict[str, Any]:
    """指定されたタスクの最適モデル設定を取得 (COMPLETE_IMPLEMENTATION_GUIDE_v3.mdより)"""
    return ModelTier.get_model_for_task(tier)