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


# ✅ Deep Research 構成フロー定義
class ResearchFlow:
    """Deep Research構成フローの定義"""

    # 各構成フローの定義: {"steps": [model_list], "description": "説明", "cost": コスト, "ability": 能力}
    FLOWS = {
        "flash-x1": {
            "steps": ["gemini-2.5-flash"],
            "description": "Flash×1 (標準・高速)",
            "cost": 0.64,
            "ability": 8.0
        },
        "lite-lite-pro": {
            "steps": ["gemini-2.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-pro"],
            "description": "Lite→Lite→Pro (コスパ最強)",
            "cost": 2.86,
            "ability": 8.8
        },
        "lite-flash-pro": {
            "steps": ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"],
            "description": "Lite→Flash→Pro (黄金比・標準)",
            "cost": 2.94,
            "ability": 8.95
        },
        "flash-flash-pro": {
            "steps": ["gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.5-pro"],
            "description": "Flash→Flash→Pro (3回ループの王)",
            "cost": 3.02,
            "ability": 9.3
        },
        "lite-flash-flash-pro": {
            "steps": ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.5-pro"],
            "description": "Lite→Flash→Flash→Pro (賢い節約術)",
            "cost": 3.1,
            "ability": 9.45
        },
        "flash-flash-flash-pro": {
            "steps": ["gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.5-pro"],
            "description": "Flash→Flash→Flash→Pro (Deep Research推奨)",
            "cost": 3.18,
            "ability": 9.5
        },
        "lite-lite-flash-flash": {
            "steps": ["gemini-2.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash"],
            "description": "Lite→Lite→Flash→Flash (粘りの凡人)",
            "cost": 0.48,
            "ability": 7.35
        },
        "flash-flash-flash": {
            "steps": ["gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.5-flash"],
            "description": "Flash→Flash→Flash (ザ・標準)",
            "cost": 0.48,
            "ability": 7.4
        },
        "lite-lite-lite-flash": {
            "steps": ["gemini-2.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash"],
            "description": "Lite→Lite→Lite→Flash (人海戦術)",
            "cost": 0.4,
            "ability": 7.5
        },
        "flash-flash-flash-flash": {
            "steps": ["gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.5-flash"],
            "description": "Flash→Flash→Flash→Flash (優等生の限界)",
            "cost": 0.64,
            "ability": 7.85
        },
        "lite-lite-flash-pro": {
            "steps": ["gemini-2.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"],
            "description": "Lite→Lite→Flash→Pro (泥臭い名探偵)",
            "cost": 3.02,
            "ability": 9.28
        },
        "lite-lite-lite-pro": {
            "steps": ["gemini-2.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-pro"],
            "description": "Lite→Lite→Lite→Pro (質より量の極み)",
            "cost": 2.94,
            "ability": 9.15
        },
        "flash-pro-pro": {
            "steps": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-pro"],
            "description": "Flash→Pro→Pro (精鋭部隊)",
            "cost": 5.56,
            "ability": 9.6
        },
        "lite-pro-pro": {
            "steps": ["gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-2.5-pro"],
            "description": "Lite→Pro→Pro (一点突破・改)",
            "cost": 5.48,
            "ability": 9.55
        },
        "lite-lite-pro-pro": {
            "steps": ["gemini-2.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-2.5-pro"],
            "description": "Lite→Lite→Pro→Pro (素材重視のプロ)",
            "cost": 5.56,
            "ability": 9.65
        },
        "lite-flash-pro-pro": {
            "steps": ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-pro"],
            "description": "Lite→Flash→Pro→Pro (超・黄金比)",
            "cost": 5.64,
            "ability": 9.7
        },
        "flash-flash-pro-pro": {
            "steps": ["gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-pro"],
            "description": "Flash→Flash→Pro→Pro (編集長決済)",
            "cost": 5.72,
            "ability": 9.75
        },
        "pro-pro-pro": {
            "steps": ["gemini-2.5-pro", "gemini-2.5-pro", "gemini-2.5-pro"],
            "description": "Pro→Pro→Pro (富豪の鉄板)",
            "cost": 8.1,
            "ability": 9.85
        },
        "lite-pro-pro-pro": {
            "steps": ["gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-2.5-pro", "gemini-2.5-pro"],
            "description": "Lite→Pro→Pro→Pro (成り上がり)",
            "cost": 8.18,
            "ability": 9.9
        },
        "flash-pro-pro-pro": {
            "steps": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-pro", "gemini-2.5-pro"],
            "description": "Flash→Pro→Pro→Pro (天才集団)",
            "cost": 8.26,
            "ability": 9.95
        },
        "pro-pro-pro-pro": {
            "steps": ["gemini-2.5-pro", "gemini-2.5-pro", "gemini-2.5-pro", "gemini-2.5-pro"],
            "description": "Pro→Pro→Pro→Pro (全知全能)",
            "cost": 10.8,
            "ability": 9.99
        }
    }

    @classmethod
    def get_flow(cls, flow_id: str) -> Dict[str, Any]:
        """指定されたフローIDの構成を取得"""
        return cls.FLOWS.get(flow_id, cls.FLOWS["flash-x1"])

    @classmethod
    def get_all_flows(cls) -> Dict[str, Dict[str, Any]]:
        """全構成フローを取得"""
        return cls.FLOWS