"""
Stage 1 分類器 (Gemini 2.5 Flash)
"""
from typing import Dict, Any, Optional
from pathlib import Path
import json
from core.ai.llm_client import LLMClient


class Stage1Classifier:
    """Stage 1: Gemini 2.5 Flashによる初期分類"""
    
    def __init__(self, llm_client: LLMClient):
        self.client = llm_client
        self.tier = "stage1_classification"
        
    def generate_classification_prompt(self, doc_types_yaml: str) -> str:
        """簡潔な分類プロンプトを生成"""
        return f"""あなたは文書分類の専門家です。この文書を分析し、以下のJSON形式で回答してください:

{{
  "doc_type": "最適な文書タイプ",
  "workspace": "family/personal/work のいずれか",
  "relevant_date": "重要な日付 (YYYY-MM-DD形式、なければnull)",
  "summary": "文書の要約 (100文字以内)"
}}

利用可能な文書タイプ:
{doc_types_yaml}

ワークスペース基準:
- family: 学校、マンション理事会など家族全体の文書
- personal: 医療、金融など個人の文書
- work: 仕事関連の文書

必ずJSON形式のみで回答してください。説明は不要です。"""

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