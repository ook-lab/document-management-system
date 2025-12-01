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
以下の文書を構造化データに変換してください:

1. **summary**: 文書の内容を2-3文で要約 (100文字以内)
   ※これは検索用インデックスのため、要約してOKです
2. **document_date**: 文書の日付 (YYYY-MM-DD形式、見つからない場合はnull)
3. **tags**: 関連するタグのリスト (3-5個、検索に有用なキーワード)
4. **metadata**: 文書タイプに応じた構造化データ（★生データとして原文を保持）
{custom_fields}
5. **tables**: 文書内の表構造（該当する場合のみ）
   - 文書に表形式のデータがある場合、以下のガイドラインに従って完全に構造化してください
   - 表が存在しない場合は空のリスト [] を設定してください
6. **extraction_confidence**: 抽出の信頼度 (0.0-1.0)

# 【絶対原則】情報の完全性
- **情報の欠損ゼロ**: 文書内のすべての記載情報を構造化データに含めてください
- **省略・要約の厳禁**: metadata内のフィールドは「生データ」です。要約したり言い換えたりせず、原文そのまま格納してください
- **推測や補完は不要**: 記載されている情報のみを忠実に構造化してください
- 日付は必ずYYYY-MM-DD形式で統一してください
- 見つからない情報はnullまたは空のリスト[]を設定してください
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

それでは、上記の文書を構造化データに変換し、JSON形式で回答してください。
**重要: 情報の欠損・省略は一切禁止です。原文の全量をJSON構造に落とし込んでください。**"""
        
        return prompt
    
    def _get_custom_fields(self, doc_type: str) -> str:
        """doc_typeに応じたカスタムフィールド定義"""

        # 学校関連文書は ikuya_school スキーマに統合
        ikuya_school_fields = """
   【重要】学校関連文書は ikuya_school スキーマに統合されています。

   metadataフィールドの構造:
   {
     "basic_info": {
       "school_name": "学校名",
       "grade": "学年（例: 5年生）",
       "issue_date": "発行日（YYYY-MM-DD）",
       "period": "対象期間（例: 2024年11月18日-21日）",
       "document_title": "文書タイトル",
       "document_number": "文書番号（例: 第12号）"
     },
     "text_blocks": [
       {
         "title": "見出し（例: 朝会「マナーとルールについて」）",
         "content": "本文（原文そのまま、一切省略せず）"
       }
     ],
     "weekly_schedule": [
       {
         "date": "MM-DD または YYYY-MM-DD",
         "day": "曜日（月、火など）",
         "day_of_week": "曜日フル（月曜日など）",
         "events": ["行事1", "行事2"],
         "class_schedules": [
           {
             "class": "5A",
             "subjects": ["1限:国語", "2限:算数", "3限:理科"],
             "periods": [
               {"period": 1, "subject": "国語", "time": "8:45-9:30"},
               {"period": 2, "subject": "算数", "time": "9:40-10:25"}
             ]
           },
           {
             "class": "5B",
             "subjects": ["1限:算数", "2限:国語", "3限:社会"]
           }
         ],
         "note": "持ち物や連絡事項（原文そのまま）"
       }
     ],
     "monthly_schedule_blocks": [
       {
         "date": "MM-DD または YYYY-MM-DD",
         "day_of_week": "曜日（月、火など）",
         "event": "イベント・行事の内容",
         "time": "時刻（例: 7:45 集合、11:30 下校）",
         "notes": "持ち物、場所などの補足情報"
       }
     ],
     "learning_content_blocks": [
       {
         "subject": "教科名（国語、算数など）",
         "teacher": "担当教員名",
         "content": "学習内容の詳細（原文そのまま）",
         "materials": "持ち物・準備物"
       }
     ],
     "structured_tables": [
       {
         "table_title": "表のタイトル",
         "table_type": "requirements/events/scores など",
         "headers": ["列1", "列2", "列3"],
         "rows": [
           {"列1": "値1", "列2": "値2", "列3": "値3"},
           {"列1": "値4", "列2": "値5", "列3": "値6"}
         ]
       }
     ],
     "important_notes": [
       "短い箇条書きの連絡事項1（原文そのまま）",
       "短い箇条書きの連絡事項2（原文そのまま）"
     ],
     "special_events": [
       "特別イベント1",
       "特別イベント2"
     ]
   }

   【データ振り分けルール - 必ず守ること】:

   1. **basic_info**: 学校名、学年、発行日、対象期間などの基本情報
      - 文書の一番上に記載されている学校名や学年、日付を抽出

   2. **weekly_schedule**: 時間割表（曜日・時限・クラスで構成される表）
      ★これが最も重要★ 以下の条件に当てはまる表は必ず weekly_schedule に構造化してください:
      - 横軸に「月・火・水・木・金」などの曜日がある
      - 縦軸に「1限・2限・3限」などの時限がある
      - 「5A」「5B」などのクラス名が列見出しにある
      - 各セルに科目名（国語、算数、理科など）が入っている

      抽出方法:
      - 各日付について、class_schedules フィールドを作成
      - クラスごとに subjects 配列を作成（時限順に「1限:国語」形式で記録）
      - periods フィールドには {period, subject, time} の詳細情報を記録
      - 科目名に括弧書きの説明がある場合もそのまま含める（例: 「算数（持ち物:定規）」）
      - 朝の時間は period を "朝" または 0 として記録

   3. **structured_tables**: その他の表データ（weekly_schedule 以外）
      - 持ち物リスト、イベント一覧、成績表、提出物リストなど
      - table_title（表のタイトル）、table_type（種類）、headers（列名）、rows（行データ）で構造化
      - rows は配列形式で、各行をオブジェクトとして記録

   4. **text_blocks**: まとまった文章セクション（見出し+本文）
      - 朝会の話、今日のふりかえり、道徳の内容、先生からのメッセージなど
      - 見出しが明確にあり、その後に長めの文章が続く場合
      - title（見出し）と content（本文全文）のペアで記録
      - content は一切省略せず、原文そのまま全文を記録

   5. **important_notes**: 短い箇条書きの連絡事項
      - 「11月20日(水)は遠足のため弁当を持参してください」のような短い文
      - 原文そのまま配列に格納（要約・言い換え厳禁）

   6. **special_events**: 特別イベント・行事
      - 通常授業以外の特別な予定

   【絶対原則】:
   - 情報の欠損・省略は一切禁止
   - 原文の全量を構造化データに落とし込む
   - 要約・言い換えは厳禁（特に text_blocks の content、important_notes、note フィールド）
   - 日付は必ず YYYY-MM-DD 形式で統一
   - 見つからない情報は null または空のリスト [] を設定
        """

        fields_map = {
            # 学校関連文書 - 全て ikuya_school に統合
            "ikuya_school": ikuya_school_fields,
            # 旧タイプ（後方互換性のため一時的にサポート）
            "timetable": ikuya_school_fields,
            "school_notice": ikuya_school_fields,
            "class_newsletter": ikuya_school_fields,
            "homework": ikuya_school_fields,
            "test_exam": ikuya_school_fields,
            "report_card": ikuya_school_fields,
            "school_event": ikuya_school_fields,
            "parent_teacher_meeting": ikuya_school_fields,
            "notice": ikuya_school_fields,

            # 以下は既存の定義を保持
            "timetable_old": """
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
     ※科目名だけでなく、括弧内の説明（例: 「算数（持ち物:定規）」）や詳細情報も全て含めてください
   - special_events: 特別な予定やイベント（該当する場合のみ）
     ※原文そのままリスト化してください。省略・要約は厳禁です
   - important_notes: 連絡事項・注意事項のリスト（該当する場合のみ）
     【絶対原則: 情報の完全性】
     - 時間割表の外に記載されている**全ての**文章・段落を、原文そのままリスト化してください
     - 対象: 連絡事項、持ち物、注意事項、行事の詳細、保護者へのお知らせ、コメント、備考など
     - **要約・省略・言い換えは厳禁**: 「11月20日(水)は遠足のため弁当を持参してください。雨天の場合は通常授業となります」のように、
       文書に書かれている文章を一切省略せず、そのまま格納してください
     - 文末の「です・ます」などもそのまま残してください
     - 1つの段落が長くても、全文を1つの配列要素として入れてください
     例: ["11月20日(水)は遠足のため弁当を持参してください。雨天の場合は通常授業となります。",
          "体操服は毎週金曜日に持ち帰り、週末に洗濯をお願いします。",
          "漢字テストは11月22日(金)の1時間目に実施します。範囲は教科書p.50-60です。"]
   - text_blocks: 文章セクション（記事ブロック）のリスト（該当する場合のみ）
     【役割分担: 表データとまとまった文章を分離】
     - 表以外の場所にある、まとまった文章セクションを抽出してください
     - 各セクションは「見出し（title）」と「本文（content）」のペアで構成されます
     - 対象となる文章セクション:
       * 朝会の話（例: 朝会「マナーとルールについて」）
       * 道徳の内容
       * 今日のふりかえり / 今週のふりかえり
       * 先生からのメッセージ / コラム
       * 学習のまとめ
       * その他、見出しと本文が明確にセットになっている記事・エッセイ的な文章
     - 抽出方法:
       * 見出し（太字、大きな文字、「」で囲まれている部分など）を `title` に設定
       * その直後に続く文章全体を `content` に設定（一切省略せず、原文そのまま）
       * content は長文でもOK（複数段落にまたがっても全文を格納）
     例: [
       {"title": "朝会「マナーとルールについて」", "content": "今週の朝会では、学校生活におけるマナーとルールについて話しました。廊下を走らないこと、友達に優しくすること...（全文）"},
       {"title": "今日のふりかえり", "content": "今日は算数の時間に分数の計算を学びました。最初は難しかったですが...（全文）"}
     ]
     ※important_notes との使い分け: 短い箇条書きは important_notes、見出し付きのまとまった文章は text_blocks へ
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
     ※箇条書き部分を原文そのままリスト化。省略・要約は厳禁
   - important_points: 重要事項リスト
     ※原文の文章をそのまま格納。要約・言い換えは厳禁
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
     ※noteフィールド: 原文の記載内容を一切省略せず、そのまま格納してください（要約・言い換え厳禁）

     【重要】class_schedulesの完全抽出:
     - 文書内に「5A」「5B」などのクラス名が列として並んでいる表形式の時間割を探してください
     - 表のヘッダー行に「5A  5B」「朝 1 2 3...」などが含まれている場合、それは確実にクラス別時間割です
     - 各日付の行で、5Aの列と5Bの列に異なる科目が記載されている場合、必ずclass_schedulesに抽出してください
     - subjects配列には、順番に「1限:家庭」「2限:家庭」「3限:算数」のように時限番号と科目名を記録してください
     - 科目名に括弧書きの説明（例: 「算数（持ち物:コンパス）」）がある場合、それも含めて記録してください
     - 朝の時間は「0限:朝会」や「朝:朝読書」のように記録してください
     - class_schedulesが抽出できる場合は、必ず各日のclass_schedulesフィールドに記録してください（省略しないでください）
            """,
            
            "homework": """
   - subject: 科目
   - assignment_date: 課題が出された日 (YYYY-MM-DD)
   - due_date: 提出期限 (YYYY-MM-DD)
   - instructions: 課題内容・指示
     ※原文の指示内容を一切省略せず、そのまま記録してください（要約・言い換え厳禁）
   - pages: ページ範囲 (例: "p.12-15")
            """,
            
            "test": """
   - subject: 科目
   - test_date: テスト日 (YYYY-MM-DD)
   - test_type: テストの種類 (例: "中間テスト", "単元テスト")
   - scope: 出題範囲
     ※原文の範囲記述を一切省略せず記録（要約・言い換え厳禁）
   - points: 満点
   - score: 得点 (記載があれば)
            """,

            "report_card": """
   - academic_year: 年度
   - semester: 学期
   - grade: 学年
   - subjects: 科目別成績リスト
   - overall_comments: 総合所見
     ※原文の所見を一切省略せず、そのまま記録してください（要約・言い換え厳禁）
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
     ※原文の条項を一切省略せず、そのまま記録してください（要約・言い換え厳禁）
            """,

            "meeting_minutes": """
   - meeting_date: 会議日 (YYYY-MM-DD)
   - attendees: 参加者リスト
   - agenda: 議題リスト
     ※原文の議題を一切省略せず記録（要約・言い換え厳禁）
   - decisions: 決定事項リスト
     ※原文の決定内容を一切省略せず記録（要約・言い換え厳禁）
   - action_items: アクションアイテム (担当者と期限付き)
     ※原文のアクション内容を一切省略せず記録（要約・言い換え厳禁）
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
     ※原文の診断内容を一切省略せず記録（要約・言い換え厳禁）
   - medications: 処方薬リスト
            """,

            "condo_minutes": """
   - meeting_date: 理事会日 (YYYY-MM-DD)
   - attendees: 出席者
   - agenda: 議題リスト
     ※原文の議題を一切省略せず記録（要約・言い換え厳禁）
   - decisions: 決定事項
     ※原文の決定内容を一切省略せず記録（要約・言い換え厳禁）
   - next_meeting: 次回予定 (YYYY-MM-DD)
            """,

            "report": """
   - report_type: レポート種類
   - author: 作成者
   - date: 作成日 (YYYY-MM-DD)
   - key_findings: 主要な発見・結論リスト
     ※原文の発見・結論を一切省略せず記録（要約・言い換え厳禁）
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
     ※原文の重要事項を一切省略せず記録（要約・言い換え厳禁）
   - event_info: イベント情報 (案内の場合)
     ※原文のイベント情報を一切省略せず記録（要約・言い換え厳禁）
            """,

            "other": """
   - 文書の内容に応じて適切なフィールドを自由に設定してください
   - 可能な限り構造化された情報を抽出してください
   - **重要**: テキスト情報は一切省略せず、原文そのまま格納してください（要約・言い換え厳禁）
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