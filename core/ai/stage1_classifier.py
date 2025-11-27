"""
Stage 1 分類器 (Gemini 2.5 Flash)

Phase 2: 50種類の書類タイプ分類体系に対応
"""
from typing import Dict, Any, Optional
from pathlib import Path
import json
from core.ai.llm_client import LLMClient
from config.DOC_TYPE_CONSTANTS import (
    ALL_DOC_TYPES,
    DOC_TYPE_METADATA,
    FOLDER_MAPPINGS,
    get_display_name
)


class Stage1Classifier:
    """Stage 1: Gemini 2.5 Flashによる初期分類 (50種類対応)"""

    def __init__(self, llm_client: LLMClient):
        self.client = llm_client
        self.tier = "stage1_classification"

    def _generate_doc_types_list(self) -> str:
        """
        50種類の文書タイプをフォルダ別に整理したリストを生成

        Returns:
            フォルダ別に整理された文書タイプリスト（文字列）
        """
        doc_types_text = []

        for folder_key, folder_types in FOLDER_MAPPINGS.items():
            # フォルダ名を日本語に変換
            folder_names = {
                "ikuya_school": "📚 育哉-学校",
                "work": "💼 仕事",
                "finance": "💰 家計・金融",
                "medical": "🏥 医療・健康",
                "housing": "🏠 住まい・不動産",
                "legal_admin": "⚖️ 法律・行政",
                "lifestyle": "🎨 趣味・ライフスタイル",
                "other": "📁 その他",
            }

            folder_display = folder_names.get(folder_key, folder_key)
            doc_types_text.append(f"\n{folder_display}:")

            for doc_type in folder_types:
                display_name = get_display_name(doc_type)
                doc_types_text.append(f"  - {doc_type}: {display_name}")

        return "\n".join(doc_types_text)

    def generate_classification_prompt(self, doc_types_yaml: str = None) -> str:
        """
        分類プロンプトを生成（50種類対応）

        Args:
            doc_types_yaml: 後方互換性のため残しているが、使用しない

        Returns:
            分類用プロンプト
        """
        # 50種類の文書タイプリストを動的に生成
        doc_types_list = self._generate_doc_types_list()

        return f"""あなたは文書分類の専門家です。この文書を分析し、以下のJSON形式で回答してください:

{{
  "doc_type": "最適な文書タイプ（下記の50種類から1つ選択）",
  "workspace": "family/personal/work のいずれか",
  "relevant_date": "重要な日付 (YYYY-MM-DD形式、なければnull)",
  "summary": "文書の要約 (100文字以内)",
  "confidence": 0.0から1.0の信頼度スコア
}}

**利用可能な文書タイプ (全50種類):**
{doc_types_list}

**ワークスペース基準:**
- family: 学校、マンション理事会など家族全体の文書
- personal: 医療、金融など個人の文書
- work: 仕事関連の文書

**重要な指示:**
1. doc_typeは上記50種類のいずれか1つを必ず選択してください
2. 該当するものがない場合は "other" を選択してください
3. 必ずJSON形式のみで回答してください（説明は不要）
4. confidenceは分類の確信度を0.0〜1.0で示してください

必ずJSON形式のみで回答してください。"""

    async def classify(
        self,
        file_path: Path,
        doc_types_yaml: str,
        mime_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """ファイルを分類"""
        prompt = self.generate_classification_prompt(doc_types_yaml)
        
        response = self.client.call_model(
            tier=self.tier,
            prompt=prompt,
            file_path=file_path
        )
        
        if not response.get("success"):
            raise ValueError(f"Stage1分類に失敗: {response.get('error')}")
        
        # JSON応答をパース
        try:
            # マークダウンのコードブロックを除去
            content = response["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            return result
        except json.JSONDecodeError as e:
            raise ValueError(f"Stage1分類結果のJSON解析に失敗: {e}\n応答: {response['content']}")