"""
Stage 2: 詳細メタデータ抽出 (Claude 4.5 Sonnet)

Stage 1で分類された文書から、詳細な構造化データを抽出します。
"""
import json
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from config.model_tiers import ModelTier
from core.ai.llm_client import LLMClient


class Stage2Extractor:
    """Stage 2抽出器 (Claude 4.5 Sonnet)"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client if llm_client else LLMClient()
        self.confidence_threshold = 0.7
        self._table_extraction_template = None

    def _load_table_extraction_template(self) -> str:
        """
        表構造抽出プロンプトテンプレートをロード

        Returns:
            table_extraction_v1.mdの内容
        """
        if self._table_extraction_template is not None:
            return self._table_extraction_template

        try:
            template_path = Path(__file__).parent / "prompts" / "table_extraction_v1.md"

            if not template_path.exists():
                logger.warning(f"表抽出テンプレートが見つかりません: {template_path}")
                return ""

            with open(template_path, 'r', encoding='utf-8') as f:
                self._table_extraction_template = f.read()

            logger.info(f"[Stage 2] 表抽出テンプレートをロード: {len(self._table_extraction_template)} 文字")
            return self._table_extraction_template

        except Exception as e:
            logger.error(f"表抽出テンプレートの読み込みエラー: {e}", exc_info=True)
            return ""

    def extract_metadata(
        self,
        full_text: str,
        file_name: str,
        stage1_result: Dict,
        workspace: str = "personal"
    ) -> Dict:
        """
        詳細メタデータを抽出
        
        Args:
            full_text: 抽出済みテキスト
            file_name: ファイル名
            stage1_result: Stage 1結果
            workspace: ワークスペース
        
        Returns:
            抽出結果辞書:
            {
                "doc_type": str,
                "summary": str,
                "document_date": str (YYYY-MM-DD) or None,
                "tags": List[str],
                "metadata": Dict,
                "extraction_confidence": float
            }
        """
        doc_type = stage1_result.get("doc_type", "other")
        
        logger.info(f"[Stage 2] 詳細抽出開始: doc_type={doc_type}")
        
        prompt = self._build_extraction_prompt(
            full_text=full_text,
            file_name=file_name,
            doc_type=doc_type,
            workspace=workspace,
            stage1_confidence=stage1_result.get("confidence", 0.0)
        )
        
        try:
            response = self.llm.call_model(
                tier="stage2_extraction",
                prompt=prompt
            )
            
            if not response.get("success"):
                logger.error(f"[Stage 2] 抽出失敗: {response.get('error')}")
                return self._get_fallback_result(full_text, doc_type, stage1_result)
            
            # JSON抽出
            content = response.get("content", "")
            result = self._extract_json(content)
            
            # doc_typeの上書き(Stage 2の方が精度高い可能性)
            result["doc_type"] = result.get("doc_type", doc_type)
            
            # Stage 1情報も保持
            result["stage1_doc_type"] = stage1_result.get("doc_type")
            result["stage1_confidence"] = stage1_result.get("confidence")
            
            metadata_count = len(result.get("metadata", {}))
            logger.info(f"[Stage 2] 抽出完了: {metadata_count}個のメタデータ, confidence={result.get('extraction_confidence')}")
            
            return result
            
        except Exception as e:
            logger.error(f"[Stage 2] 抽出エラー: {e}", exc_info=True)
            return self._get_fallback_result(full_text, doc_type, stage1_result)
    
    def _build_extraction_prompt(
        self,
        full_text: str,
        file_name: str,
        doc_type: str,
        workspace: str,
        stage1_confidence: float
    ) -> str:
        """抽出プロンプト生成"""
        
        # doc_typeに応じたカスタムフィールド定義
        custom_fields = self._get_custom_fields(doc_type)

        # 表構造抽出テンプレートをロード (Phase 2.2.2)
        table_extraction_guidelines = self._load_table_extraction_template()

        # テキストを適切な長さに切り詰め (Claudeのコンテキスト制限を考慮)
        max_text_length = 8000
        truncated_text = full_text[:max_text_length]
        if len(full_text) > max_text_length:
            truncated_text += "\n\n...(以下省略)..."

        prompt = f"""あなたは文書分析の専門家です。以下の文書から詳細な情報を抽出し、JSON形式で回答してください。

# ファイル名
{file_name}

# 文書タイプ (Stage 1判定)
{doc_type} (信頼度: {stage1_confidence:.2f})

# ワークスペース
{workspace}

# 文書内容
{truncated_text}

# タスク
以下の情報を正確に抽出してください:

1. **summary**: 文書の内容を2-3文で要約 (100文字以内)
2. **document_date**: 文書の日付 (YYYY-MM-DD形式、見つからない場合はnull)
3. **tags**: 関連するタグのリスト (3-5個、検索に有用なキーワード)
4. **metadata**: 文書タイプに応じた構造化データ
{custom_fields}
5. **tables**: 文書内の表構造（該当する場合のみ）
   - 文書に表形式のデータがある場合、以下のガイドラインに従って抽出してください
   - 表が存在しない場合は空のリスト [] を設定してください
6. **extraction_confidence**: 抽出の信頼度 (0.0-1.0)

# 重要な注意事項
- 文書に記載されている情報のみを抽出してください（推測や補完は不要）
- 日付は必ずYYYY-MM-DD形式で統一してください
- 見つからない情報はnullまたは空のリスト[]を設定してください
- metadataの各フィールドは文書内容に基づいて正確に抽出してください
- **【特に重要】学年通信などで「5A」「5B」のようなクラス名が列見出しにある表形式の時間割を見つけた場合、
  必ずweekly_scheduleの各日にclass_schedulesフィールドを追加し、クラスごとの科目を抽出してください。
  例: "class_schedules": [{{"class": "5A", "subjects": ["1限:家庭", "2限:家庭", "3限:算数"]}}, {{"class": "5B", "subjects": ["1限:算数", "2限:国語", "3限:家庭"]}}]**

# 表構造抽出ガイドライン (Phase 2.2.2)
{table_extraction_guidelines}

# 出力形式
以下のJSON形式**のみ**で回答してください（他の説明やマークダウンは不要）:

```json
{{
  "doc_type": "{doc_type}",
  "summary": "文書の要約",
  "document_date": "YYYY-MM-DD",
  "tags": ["tag1", "tag2", "tag3"],
  "metadata": {{
    // doc_typeに応じたカスタムフィールド
  }},
  "tables": [
    {{
      "table_type": "daily_schedule",
      "headers": ["日付", "曜日", "1限", "2限"],
      "rows": [...]
      // 表構造抽出ガイドラインに従った構造
    }}
  ],
  "extraction_confidence": 0.95
}}
```

それでは、上記の文書から情報を抽出してJSON形式で回答してください。"""
        
        return prompt
    
    def _get_custom_fields(self, doc_type: str) -> str:
        """doc_typeに応じたカスタムフィールド定義"""
        
        fields_map = {
            "timetable": """
   - school_name: 学校名
   - grade: 学年 (例: "5年生")
   - period: 対象期間 (例: "2024年11月18日-21日")
   - daily_schedule: 日別時間割（必須）
     各日の構造: {
       "date": "YYYY-MM-DD",
       "day_of_week": "月曜日",
       "periods": [
         {"period": 1, "subject": "国語", "time": "8:45-9:30"},
         {"period": 2, "subject": "算数", "time": "9:40-10:25"},
         ...
       ]
     }
   - special_events: 特別な予定やイベント（該当する場合のみ）
     【重要】daily_scheduleは通常授業を含む全ての時間割を抽出してください。
   算数、国語、理科、社会などの通常科目も必ず含めてください。
            """,
            
            "notice": """
   - school_name: 学校名
   - grade: 学年
   - notice_type: お知らせの種類 (例: "行事案内", "提出物", "注意事項", "学年通信")
   - event_date: イベント日 (YYYY-MM-DD)
   - deadline: 提出期限 (YYYY-MM-DD)
   - requirements: 必要な持ち物・準備リスト
   - important_points: 重要事項リスト
   - weekly_schedule: 週間予定・時間割（表形式で記載されている場合）
     各日の構造: {
       "date": "MM-DD",
       "day": "曜日",
       "events": ["行事1", "行事2"],
       "class_schedules": [  // クラスごとの授業がある場合
         {"class": "5A", "subjects": ["1限:国語", "2限:算数", ...]},
         {"class": "5B", "subjects": ["1限:算数", "2限:国語", ...]}
       ],
       "note": "持ち物や連絡事項"
     }

     【重要】class_schedulesの抽出方法:
     - 文書内に「5A」「5B」などのクラス名が列として並んでいる表形式の時間割を探してください
     - 表のヘッダー行に「5A  5B」「朝 1 2 3...」などが含まれている場合、それは確実にクラス別時間割です
     - 各日付の行で、5Aの列と5Bの列に異なる科目が記載されている場合、必ずclass_schedulesに抽出してください
     - subjects配列には、順番に「1限:家庭」「2限:家庭」「3限:算数」のように時限番号と科目名を記録してください
     - 朝の時間は「0限:朝会」や「朝:朝読書」のように記録してください
     - class_schedulesが抽出できる場合は、必ず各日のclass_schedulesフィールドに記録してください（省略しないでください）
            """,
            
            "homework": """
   - subject: 科目
   - assignment_date: 課題が出された日 (YYYY-MM-DD)
   - due_date: 提出期限 (YYYY-MM-DD)
   - instructions: 課題内容・指示
   - pages: ページ範囲 (例: "p.12-15")
            """,
            
            "test": """
   - subject: 科目
   - test_date: テスト日 (YYYY-MM-DD)
   - test_type: テストの種類 (例: "中間テスト", "単元テスト")
   - scope: 出題範囲
   - points: 満点
   - score: 得点 (記載があれば)
            """,
            
            "report_card": """
   - academic_year: 年度
   - semester: 学期
   - grade: 学年
   - subjects: 科目別成績リスト
   - overall_comments: 総合所見
            """,
            
            "invoice": """
   - invoice_number: 請求書番号
   - amount: 金額 (数値)
   - currency: 通貨 (JPY等)
   - vendor: 発行元
   - due_date: 支払期限 (YYYY-MM-DD)
   - items: 明細リスト
            """,
            
            "contract": """
   - contract_number: 契約番号
   - parties: 契約当事者リスト
   - start_date: 契約開始日 (YYYY-MM-DD)
   - end_date: 契約終了日 (YYYY-MM-DD)
   - amount: 契約金額 (数値)
   - terms: 主要条項
            """,
            
            "meeting_minutes": """
   - meeting_date: 会議日 (YYYY-MM-DD)
   - attendees: 参加者リスト
   - agenda: 議題リスト
   - decisions: 決定事項リスト
   - action_items: アクションアイテム (担当者と期限付き)
            """,
            
            "receipt": """
   - merchant: 店舗名
   - amount: 金額 (数値)
   - currency: 通貨
   - purchase_date: 購入日 (YYYY-MM-DD)
   - items: 購入品リスト
            """,
            
            "medical_record": """
   - patient_name: 患者名
   - visit_date: 受診日 (YYYY-MM-DD)
   - hospital: 医療機関名
   - diagnosis: 診断名
   - medications: 処方薬リスト
            """,
            
            "condo_minutes": """
   - meeting_date: 理事会日 (YYYY-MM-DD)
   - attendees: 出席者
   - agenda: 議題リスト
   - decisions: 決定事項
   - next_meeting: 次回予定 (YYYY-MM-DD)
            """,
            
            "report": """
   - report_type: レポート種類
   - author: 作成者
   - date: 作成日 (YYYY-MM-DD)
   - key_findings: 主要な発見・結論リスト
            """,

            "cram_school_text": """
   - cram_school_name: 塾名 (例: "〇〇塾", "〇〇ゼミ")
   - subject: 科目 (数学/国語/英語/理科/社会 など)
   - grade: 対象学年 (例: "中学2年")
   - chapter: 章・単元 (例: "第3章 二次方程式")
   - difficulty: 難易度 (基礎/標準/応用/発展)
   - page_range: ページ範囲 (例: "p.45-60")
            """,

            "cram_school_test": """
   - cram_school_name: 塾名
   - test_name: テスト名 (例: "第2回模試", "実力テスト")
   - subject: 科目
   - test_date: 実施日 (YYYY-MM-DD)
   - grade: 学年
   - max_score: 満点
   - score: 得点 (記載があれば)
   - deviation_value: 偏差値 (記載があれば)
   - rank: 順位 (記載があれば)
            """,

            "cram_school_notice": """
   - cram_school_name: 塾名
   - notice_type: 種別 (お知らせ/請求書/案内/その他)
   - notice_date: 通知日 (YYYY-MM-DD)
   - subject: 件名
   - amount: 金額 (請求書の場合、数値)
   - payment_due: 支払期限 (YYYY-MM-DD)
   - important_items: 重要事項リスト
   - event_info: イベント情報 (案内の場合)
            """,

            "other": """
   - 文書の内容に応じて適切なフィールドを自由に設定してください
   - 可能な限り構造化された情報を抽出してください
            """
        }
        
        return fields_map.get(doc_type, fields_map["other"])
    
    def _extract_json(self, content: str) -> Dict:
        """レスポンスからJSON抽出"""
        try:
            # マークダウンコードブロックを除去
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                # 最初のコードブロックを取得
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1]
            
            # JSON部分のみを抽出（先頭の{から最後の}まで）
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            
            if start_idx == -1 or end_idx == -1:
                raise ValueError("JSON構造が見つかりません")
            
            json_str = content[start_idx:end_idx+1]
            result = json.loads(json_str)
            
            # バリデーション
            required_keys = ["doc_type", "summary", "extraction_confidence"]
            for key in required_keys:
                if key not in result:
                    logger.warning(f"必須キー欠損: {key}")
            
            # データ型の正規化
            if "extraction_confidence" in result:
                result["extraction_confidence"] = float(result["extraction_confidence"])
                result["extraction_confidence"] = max(0.0, min(1.0, result["extraction_confidence"]))
            
            if "tags" not in result:
                result["tags"] = []

            if "metadata" not in result:
                result["metadata"] = {}

            # Phase 2.2.2: 表構造対応
            if "tables" not in result:
                result["tables"] = []

            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}")
            logger.debug(f"パース失敗した内容: {content[:500]}")
            raise
        except Exception as e:
            logger.error(f"JSON抽出エラー: {e}")
            raise
    
    def _get_fallback_result(self, full_text: str, doc_type: str, stage1_result: Dict) -> Dict:
        """フォールバック結果"""
        summary = full_text[:200] + "..." if len(full_text) > 200 else full_text

        return {
            "doc_type": doc_type,
            "summary": summary,
            "document_date": None,
            "tags": [],
            "metadata": {},
            "tables": [],  # Phase 2.2.2
            "extraction_confidence": 0.2,
            "stage1_doc_type": stage1_result.get("doc_type"),
            "stage1_confidence": stage1_result.get("confidence"),
            "error": "Stage 2抽出に失敗しました"
        }