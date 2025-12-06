"""
Self-Querying（セルフクエリ）

ユーザーの曖昧な質問をLLMが構造化された検索条件に翻訳します。
"""
from typing import Dict, Any, Optional
import json
from loguru import logger


class SelfQuerying:
    """LLMを使ってユーザーの質問を構造化された検索条件に翻訳"""

    def __init__(self, llm_client):
        """
        Args:
            llm_client: LLMClient インスタンス
        """
        self.llm_client = llm_client

    def parse_query_with_llm(self, user_query: str) -> Dict[str, Any]:
        """
        ユーザーの質問をLLMで解析して構造化された検索条件に変換

        Args:
            user_query: ユーザーの質問

        Returns:
            構造化された検索条件:
            {
                "search_query": str,  # 実際の検索クエリ
                "filters": {
                    "year": int,
                    "month": int,
                    "doc_type": str,
                    "grade_level": str,
                    "date_range": {"start": str, "end": str}
                },
                "intent": str  # ユーザーの意図（"find", "summarize", "compare"など）
            }
        """
        prompt = self._build_self_querying_prompt(user_query)

        try:
            # LLMに質問を構造化させる
            response = self.llm_client.call_model(
                tier="ui_response",  # 軽量なモデルで十分
                prompt=prompt
            )

            if not response.get("success"):
                logger.error(f"[Self-Querying] LLM呼び出し失敗: {response.get('error')}")
                return self._get_fallback_result(user_query)

            content = response.get("content", "")

            # JSONを抽出
            result = self._extract_json_from_response(content)

            if result:
                logger.info(f"[Self-Querying] 成功: {result}")
                return result
            else:
                logger.warning("[Self-Querying] JSON抽出失敗、フォールバック使用")
                return self._get_fallback_result(user_query)

        except Exception as e:
            logger.error(f"[Self-Querying] エラー: {e}", exc_info=True)
            return self._get_fallback_result(user_query)

    def _build_self_querying_prompt(self, user_query: str) -> str:
        """
        Self-Querying用のプロンプトを構築

        Args:
            user_query: ユーザーの質問

        Returns:
            LLMに送信するプロンプト
        """
        from datetime import datetime

        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month

        prompt = f"""あなたは検索クエリ解析の専門家です。ユーザーの曖昧な質問を、構造化された検索条件に変換してください。

# 現在の日付情報
今日: {current_date.strftime('%Y年%m月%d日')}
現在の年: {current_year}
現在の月: {current_month}

# ユーザーの質問
「{user_query}」

# タスク
以下のJSON形式で、検索条件を抽出してください：

```json
{{
  "search_query": "実際に検索するクエリ（検索語句のみ、条件は除外）",
  "filters": {{
    "year": 年（整数、例：2023）または null,
    "month": 月（1-12の整数）または null,
    "doc_type": "文書タイプ（ikuya_school/notice/invoice/contract/reportなど）" または null,
    "grade_level": "学年（例：5年生）" または null,
    "date_range": {{
      "start": "開始日（YYYY-MM-DD）",
      "end": "終了日（YYYY-MM-DD）"
    }} または null
  }},
  "intent": "ユーザーの意図（find/summarize/compare/listなど）"
}}
```

# 重要な変換ルール

1. **相対日付の解釈**（今日を基準に計算）:
   - 「去年」「昨年」 → year = {current_year - 1}
   - 「今年」「本年」 → year = {current_year}
   - 「来年」「翌年」 → year = {current_year + 1}
   - 「先月」 → year = {current_year}, month = {current_month - 1 if current_month > 1 else 12}
   - 「今月」「本月」 → year = {current_year}, month = {current_month}
   - 「来月」「翌月」 → year = {current_year}, month = {current_month + 1 if current_month < 12 else 1}
   - 「先週の金曜日」「3日後」などは date_range で表現

2. **文書タイプのキーワードマッピング**:
   - 「学年通信」「学級通信」「時間割」「予定表」「学校」 → "ikuya_school"
   - 「お知らせ」「通知」「案内」 → "notice"
   - 「請求書」「領収書」「見積書」 → "invoice"
   - 「契約書」「同意書」 → "contract"
   - 「レポート」「報告書」 → "report"

3. **検索クエリの抽出**:
   - 検索対象のキーワードのみを search_query に設定
   - 条件部分（「2023年の」「12月の」など）は除外

4. **意図の判定**:
   - 「〜を見せて」「〜を探して」 → "find"
   - 「〜を要約して」「〜の内容は？」 → "summarize"
   - 「〜と〜を比較して」 → "compare"
   - 「〜のリストを作って」 → "list"

# 例

**ユーザー質問**: 「去年の12月の、田中さんの日報ある？」

**出力**:
```json
{{
  "search_query": "田中 日報",
  "filters": {{
    "year": {current_year - 1},
    "month": 12,
    "doc_type": null,
    "grade_level": null,
    "date_range": null
  }},
  "intent": "find"
}}
```

**ユーザー質問**: 「2023年の学年通信を要約して」

**出力**:
```json
{{
  "search_query": "学年通信",
  "filters": {{
    "year": 2023,
    "month": null,
    "doc_type": "ikuya_school",
    "grade_level": null,
    "date_range": null
  }},
  "intent": "summarize"
}}
```

それでは、上記のユーザーの質問を解析して、JSON形式で出力してください（JSON以外の説明は不要）:
"""

        return prompt

    def _extract_json_from_response(self, content: str) -> Optional[Dict[str, Any]]:
        """
        LLMのレスポンスからJSONを抽出

        Args:
            content: LLMのレスポンス

        Returns:
            抽出されたJSON辞書
        """
        import json_repair

        try:
            # マークダウンコードブロックを除去
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1]

            # JSON部分のみを抽出
            start_idx = content.find('{')
            end_idx = content.rfind('}')

            if start_idx == -1 or end_idx == -1:
                return None

            json_str = content[start_idx:end_idx+1]

            # json_repair を使用して構文エラーを自動修復
            result = json_repair.loads(json_str)

            # バリデーション
            if "search_query" not in result:
                result["search_query"] = ""

            if "filters" not in result:
                result["filters"] = {}

            if "intent" not in result:
                result["intent"] = "find"

            return result

        except Exception as e:
            logger.error(f"[Self-Querying] JSON抽出エラー: {e}")
            return None

    def _get_fallback_result(self, user_query: str) -> Dict[str, Any]:
        """
        LLM解析に失敗した場合のフォールバック

        Args:
            user_query: ユーザーの質問

        Returns:
            基本的な検索条件
        """
        return {
            "search_query": user_query,
            "filters": {},
            "intent": "find"
        }
