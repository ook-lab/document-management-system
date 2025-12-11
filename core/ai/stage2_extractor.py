"""
Stage 2: 詳細メタデータ抽出 (Claude 4.5 Sonnet)

Stage 1で分類された文書から、詳細な構造化データを抽出します。
"""
import json
import json_repair
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
        workspace: str = "personal",
        tier: str = "stage2_extraction",
        reference_date: str = None
    ) -> Dict:
        """
        詳細メタデータを抽出

        Args:
            full_text: 抽出済みテキスト
            file_name: ファイル名
            stage1_result: Stage 1結果
            workspace: ワークスペース
            tier: モデル階層（デフォルト: "stage2_extraction"、メール用: "email_stage2_extraction"）
            reference_date: 基準日（YYYY-MM-DD形式、Classroom投稿日など）

        Returns:
            抽出結果辞書:
            {
                "doc_type": str,
                "summary": str,
                "document_date": str (YYYY-MM-DD) or None,
                "event_dates": List[str],
                "tags": List[str],
                "metadata": Dict
            }
        """
        doc_type = stage1_result.get("doc_type", "other")

        logger.info(f"[Stage 2] 詳細抽出開始: doc_type={doc_type}, tier={tier}, reference_date={reference_date}")

        prompt = self._build_extraction_prompt(
            full_text=full_text,
            file_name=file_name,
            doc_type=doc_type,
            workspace=workspace,
            tier=tier,
            reference_date=reference_date
        )

        try:
            response = self.llm.call_model(
                tier=tier,
                prompt=prompt
            )

            if not response.get("success"):
                logger.error(f"[Stage 2] 抽出失敗: {response.get('error')}")
                return self._get_fallback_result(full_text, doc_type, stage1_result)

            # JSON抽出（リトライ機能付き）
            content = response.get("content", "")

            # ✅ DEBUG: LLM から得られた生のコンテンツ全体を出力
            logger.debug(f"[Stage 2 Input] Raw LLM response content starts with: {content[:500]}")

            result = self._extract_json_with_retry(content, tier=tier, max_retries=2)
            
            # doc_typeの上書き(Stage 2の方が精度高い可能性)
            result["doc_type"] = result.get("doc_type", doc_type)
            
            metadata_count = len(result.get("metadata", {}))
            logger.info(f"[Stage 2] 抽出完了: {metadata_count}個のメタデータ")
            
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
        tier: str = "stage2_extraction",
        reference_date: str = None
    ) -> str:
        """
        抽出プロンプト生成

        Args:
            reference_date: 基準日（YYYY-MM-DD形式、Classroom投稿日など）
        """
        
        # doc_typeに応じたカスタムフィールド定義
        custom_fields = self._get_custom_fields(doc_type)

        # 表構造抽出テンプレートをロード (Phase 2.2.2)
        table_extraction_guidelines = self._load_table_extraction_template()

        # テキストを適切な長さに切り詰め
        # Claude 4.5 Haikuは200Kトークン対応のため、2025年モデル性能に合わせて大幅拡張
        if tier == "email_stage2_extraction":
            max_text_length = 80000  # メール用: 大幅拡張（20000→80000）原文切断リスク最小化
        else:
            max_text_length = 100000  # PDF用: 大幅拡張（30000→100000）原文切断リスク最小化

        # 切り捨てが発生する場合は警告ログを出力
        truncated_text = full_text[:max_text_length]
        if len(full_text) > max_text_length:
            truncated_text += "\n\n...(以下省略)..."
            logger.warning(f"[Stage 2] テキストが長すぎるため切り詰めました: {len(full_text)} → {max_text_length} 文字")
            logger.warning(f"[Stage 2] 切り捨てられた文字数: {len(full_text) - max_text_length} 文字")

        # 基準日の情報を追加
        reference_date_info = ""
        if reference_date:
            reference_date_info = f"""
# 投稿日・基準日
{reference_date}

**重要**: この日付を基準に、相対的な日付表現（「明日」「明後日」「来週」など）を絶対日付に変換してください。
"""

        prompt = f"""あなたは文書分析の専門家です。以下の文書から詳細な情報を抽出し、JSON形式で回答してください。

# ファイル名
{file_name}

# 文書タイプ (Stage 1判定)
{doc_type}

# ワークスペース
{workspace}
{reference_date_info}
# 文書内容
{truncated_text}

# タスク
以下の文書を構造化データに変換してください:

1. **summary**: 文書の内容を簡潔に要約 (500文字以内、重要な情報は省略しない)
   ※2025年のモデル性能に合わせて制限を緩和。検索精度向上のため詳細な要約を推奨
2. **document_date**: 文書の主要な日付 (YYYY-MM-DD形式、見つからない場合はnull)
3. **event_dates**: イベントや予定の日付リスト (YYYY-MM-DD形式の配列)
   - 「明日」「明後日」などの相対表現は、上記の基準日から計算して絶対日付に変換してください
   - 例: 基準日が2025-12-05で「明後日日曜日」→ 2025-12-07
   - 複数の日付がある場合はすべて抽出してください
4. **tags**: 関連するタグのリスト (3-5個、検索に有用なキーワード)
5. **metadata**: 文書タイプに応じた構造化データ（★生データとして原文を保持）
{custom_fields}
6. **tables**: 文書内の表構造（該当する場合のみ）
   - 文書に表形式のデータがある場合、以下のガイドラインに従って完全に構造化してください
   - 表が存在しない場合は空のリスト [] を設定してください

# 【絶対原則】情報の完全性
- **情報の欠損ゼロ**: 文書内のすべての記載情報を構造化データに含めてください
- **省略・要約の厳禁**: metadata内のフィールドは「生データ」です。要約したり言い換えたりせず、原文そのまま格納してください
- **【最重要】配列フィールドの完全抽出**: `learning_content_blocks` や `monthly_schedule_blocks` などの**表データ**は、表内の**全ての行**を抽出してください。一部の行だけを抽出して残りを省略することは絶対に禁止です。
- **推測や補完は不要**: 記載されている情報のみを忠実に構造化してください
- 日付は必ずYYYY-MM-DD形式で統一してください
- 見つからない情報はnullまたは空のリスト[]を設定してください

# 【重要】表構造の正確なマッピング
文書内の表を見つけたら、以下の基準で適切なフィールドに振り分けてください:

1. **「今月の予定」「◯月の予定表」などの見出しがある表 → monthly_schedule_blocks**
   - 日付、曜日、行事名、時刻、持ち物が記載された月間スケジュール表
   - 各行を date, day_of_week, event, time, notes で構造化

2. **「今週の学習」「各教科の予定」などの見出しがある表 → learning_content_blocks**
   - 教科、担当教員、学習内容、持ち物が記載された学習予定表
   - 各教科を subject, teacher, content, materials で構造化

3. **「5A」「5B」などのクラス名が列見出しにある時間割表 → weekly_timetable_matrix**
   - 横軸に曜日、縦軸に時限、複数クラスの授業が並んだ表
   - 各クラス×各日の組み合わせで class, date, day_of_week, subjects, events, periods, note を構造化
   - subjects は ["1限:国語", "2限:算数", "3限:理科"] のように時限順の配列で記録

4. **上記に当てはまらない表 → structured_tables または weekly_schedule**
   - 持ち物リスト、成績表などは structured_tables へ
   - 単純な日別イベント表は weekly_schedule へ

# 表構造抽出ガイドライン (Phase 2.2.2)
{table_extraction_guidelines}

# 出力形式
以下のJSON形式**のみ**で回答してください（他の説明やマークダウンは不要）:

```json
{{
  "doc_type": "{doc_type}",
  "summary": "文書の要約",
  "document_date": "YYYY-MM-DD",
  "event_dates": ["YYYY-MM-DD", "YYYY-MM-DD"],
  "tags": ["tag1", "tag2", "tag3"],
  "metadata": {{
    "basic_info": {{
      "school_name": "◯◯小学校",
      "grade": "5年生",
      "issue_date": "YYYY-MM-DD"
    }},
    "monthly_schedule_blocks": [
      {{"date": "YYYY-MM-DD", "day_of_week": "月", "event": "運動会", "time": "9:00-15:00", "notes": "弁当持参"}}
    ],
    "learning_content_blocks": [
      {{"subject": "国語", "teacher": "田中先生", "content": "物語文の読解", "materials": "教科書"}}
    ],
    "weekly_timetable_matrix": [
      {{"class": "5A", "date": "YYYY-MM-DD", "day_of_week": "月", "subjects": ["1限:国語", "2限:算数"], "events": [], "note": ""}}
    ],
    "text_blocks": [
      {{"title": "朝会の話", "content": "今週は...（全文）"}}
    ]
  }},
  "tables": []
}}
```

**重要な注意事項**:
- 上記の metadata 構造はあくまで例です。実際の文書の内容に応じて適切なフィールドを使用してください
- monthly_schedule_list, learning_content_list, weekly_timetable_matrix は該当する表が文書内にある場合のみ出力してください
- 該当する表がない場合は、そのフィールドを空の配列 [] にするか、フィールド自体を省略してください
- **JSON構文エラー（カンマ、括弧、引用符の不一致）に十分注意してください**
- すべてのキー名と文字列値は二重引用符で囲んでください
- 配列やオブジェクトの最後の要素の後にカンマを付けないでください

それでは、上記の文書を構造化データに変換し、JSON形式で回答してください。
**重要: 情報の欠損・省略は一切禁止です。原文の全量をJSON構造に落とし込んでください。**

【JSON出力時の重要注意事項 - 構文エラー防止】:
1. **構文チェック**: 出力前に以下を必ず確認してください
   □ 全ての文字列は二重引用符 " で囲まれている
   □ 全てのオブジェクト・配列の括弧（ブレース・ブラケット）が正しく閉じられている
   □ 最後の要素・プロパティの後にカンマ , がない
   □ null値は引用符で囲まれていない
   □ キー名は全て二重引用符で囲まれている

2. **配列の完全性**: monthly_schedule_blocks などの配列は、表の全ての行を抽出してください
   - 例: 表に30日分の予定がある場合、monthly_schedule_blocks には30個のオブジェクトが必要です
   - 一部だけを抽出して残りを省略することは絶対に禁止です

3. **段階的な構築**: 大きな配列を作る際は、各要素を慎重に構築し、カンマの位置に注意してください

それでは、上記の注意事項を守って、JSONを出力してください:"""

        return prompt
    
    def _get_custom_fields(self, doc_type: str) -> str:
        """doc_typeに応じたカスタムフィールド定義"""

        # 育哉-学校関連文書は ikuya_school スキーマを使用
        ikuya_school_fields = """
   【重要】育哉-学校関連文書は ikuya_school スキーマを使用します。

   ★★★ データ振り分けの基本原則 ★★★
   **文章は text_blocks へ、時間割は weekly_schedule へ振り分けてください。**

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
         "date": "YYYY-MM-DD",
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
     "special_events": [
       "特別イベント1",
       "特別イベント2"
     ]
   }

   【データ振り分けルール - 必ず守ること】:

   1. **text_blocks**: すべてのテキストコンテンツをトピックごとに分けたもの
      - 朝会の話、今日のふりかえり、道徳の内容、先生からのメッセージ、連絡事項、お知らせなど
      - 学級通信や学年通信の記事、お知らせ本文、箇条書きの連絡事項など
      - **すべてのテキスト**（長文でも短い箇条書きでも）を text_blocks に含めてください
      - 見出しがない場合は適切なタイトルをつけてください（例: 「連絡事項」「お知らせ」「持ち物について」）
      - title（見出し）と content（本文全文）のペアで記録
      - **content は一切省略せず、原文そのまま全文を記録**
      - 例: [
          {"title": "朝会「マナーとルールについて」", "content": "今週の朝会では、学校生活におけるマナーとルールについて話しました...（全文）"},
          {"title": "今日のふりかえり", "content": "今日は算数の時間に分数の計算を学びました...（全文）"},
          {"title": "連絡事項", "content": "11月20日(水)は遠足のため弁当を持参してください。雨天の場合は通常授業となります。"}
        ]

   2. **weekly_schedule**: 日ごとの時間割・スケジュール（時間割表、週間予定表）
      - 日付、曜日、その日の行事・イベントが記載された表
      - 授業科目が時限ごとに記載された時間割
      - **【重要】表内の全ての日付行・時限行を抽出すること**: 表に5日分の時間割がある場合は、**5日分すべて**を個別のオブジェクトとして抽出してください
      - 各行を1つのオブジェクトとして抽出
      - 【必須フィールド】: date, day_of_week
      - 【任意フィールド】: events (行事), class_schedules (クラス別時間割), note
      - クラス別時間割がある場合は class_schedules 配列を使用:
        * 各クラスごとに {"class": "5A", "subjects": ["1限:国語", "2限:算数"], "periods": [...]} の形式
      - **月間予定表も weekly_schedule へ**: 「今月の予定」「◯月の行事予定」などもこちらに含めてください

   3. **structured_tables**: 上記1-2に当てはまらないその他の表データ
      - 持ち物リスト、成績表、提出物リスト、制服価格表、給食献立など
      - 時間割・予定表でない汎用的な表はすべてこちら
      - table_title（表のタイトル）、table_type（種類）、headers（列名）、rows（行データ）で構造化
      - **【重要】表内の全ての行を抽出すること**

   4. **basic_info**: 学校名、学年、発行日、対象期間などの基本情報
      - 文書の一番上に記載されている学校名や学年、日付を抽出

   5. **special_events**: 特別イベント・行事
      - 通常授業以外の特別な予定

   【絶対原則】:
   - **情報の欠損・省略は一切禁止**
   - 原文の全量を構造化データに落とし込む
   - **要約・言い換えは厳禁**（特に text_blocks の content、note フィールド）
   - **【配列フィールドの完全抽出】**: text_blocks, weekly_schedule, structured_tables などの配列フィールドは、表内の**全ての行**を抽出すること（一部だけを代表例として抽出し、残りを省略することは絶対に禁止）
   - 日付は必ず YYYY-MM-DD 形式で統一
   - 見つからない情報は null または空のリスト [] を設定

   【重要】文章と時間割の振り分け:
   - **文章（記事、お知らせ本文、メッセージ）→ text_blocks**
   - **時間割・予定表（授業、行事スケジュール）→ weekly_schedule**
   - **その他の表（持ち物、価格表、献立など）→ structured_tables**
        """

        fields_map = {
            # 育哉-学校関連文書 - 全て ikuya_school に統合
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
  - text_blocks: すべてのテキストコンテンツをトピックごとに分けたもの（該当する場合のみ）
    【重要】表以外のすべてのテキスト（長文でも短い箇条書きでも）を text_blocks に含めてください
    - 各セクションは「見出し（title）」と「本文（content）」のペアで構成されます
    - 対象となる文章セクション（すべて含める）:
      * 朝会の話（例: 朝会「マナーとルールについて」）
      * 道徳の内容
      * 今日のふりかえり / 今週のふりかえり
      * 先生からのメッセージ / コラム
      * 学習のまとめ
      * 連絡事項 / お知らせ（短い箇条書きでもOK）
      * 持ち物・注意事項
      * その他、すべてのテキストセクション
    - 抽出方法:
      * 見出しがある場合は、見出し（太字、大きな文字、「」で囲まれている部分など）を `title` に設定
      * 見出しがない場合は、適切なタイトルをつける（例: 「連絡事項」「お知らせ」「持ち物について」）
      * その内容全体を `content` に設定（一切省略せず、原文そのまま）
      * content は長文でもOK、短い箇条書きでもOK（複数段落にまたがっても全文を格納）

     例: [
       {"title": "朝会「マナーとルールについて」", "content": "今週の朝会では、学校生活におけるマナーとルールについて話しました。廊下を走らないこと、友達に優しくすること...（全文）"},
       {"title": "今日のふりかえり", "content": "今日は算数の時間に分数の計算を学びました。最初は難しかったですが...（全文）"}
     ]
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
        """
        レスポンスからJSON抽出

        Note: この関数はJSONパースのみを行います。
        リトライロジックは _extract_json_with_retry を使用してください。
        """
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
            # JSON構造が見つからない場合もフォールバック
            logger.error("[JSON Parser] ❌ JSON構造が見つかりません")
            logger.warning("[JSON Parser] フォールバックモード: 最低限のメタデータで保存")
            return {
                "doc_type": "unknown",
                "summary": "JSON構造が見つかりません - 手動レビューが必要です",
                "needs_review": True,
                "extraction_error": "No JSON structure found",
                "raw_content": content[:1000],
                "tags": ["extraction_failed", "no_json_structure"],
                "metadata": {
                    "error_type": "no_json_structure",
                    "error_message": "JSON structure not found in response"
                }
            }

        json_str = content[start_idx:end_idx+1]

        # json_repair を使用して構文エラーを自動修復
        try:
            result = json_repair.loads(json_str)
            logger.info("[JSON Parser] ✅ json_repair でパース成功")
        except Exception as e1:
            # json_repair でも失敗した場合は標準 json.loads を試行
            logger.warning(f"[JSON Parser] json_repair 失敗、標準 json でリトライ: {e1}")
            try:
                result = json.loads(json_str)
            except Exception as e2:
                # 全てのJSON抽出が失敗した場合、フォールバックデータを返す
                logger.error(f"[JSON Parser] ❌ JSON抽出完全失敗: {e2}")
                logger.warning("[JSON Parser] フォールバックモード: 最低限のメタデータで保存し、レビューフラグを立てます")

                # フォールバックデータ: テキスト全文と推測メタデータのみ
                result = {
                    "doc_type": "unknown",
                    "summary": "JSON抽出失敗 - 手動レビューが必要です",
                    "needs_review": True,  # レビューフラグ
                    "extraction_error": str(e2),
                    "raw_content": content[:1000],  # デバッグ用に先頭1000文字を保存
                    "tags": ["extraction_failed"],
                    "metadata": {
                        "error_type": "json_parse_failure",
                        "error_message": str(e2)
                    }
                }
                return result

        # バリデーション
        required_keys = ["doc_type", "summary"]
        for key in required_keys:
            if key not in result:
                logger.warning(f"必須キー欠損: {key}")

        # データ型の正規化
        if "tags" not in result:
            result["tags"] = []

        if "metadata" not in result:
            result["metadata"] = {}

        # Phase 2.2.2: 表構造対応
        if "tables" not in result:
            result["tables"] = []

        return result

    def _extract_json_with_retry(self, content: str, tier: str = "stage2_extraction", max_retries: int = 2) -> Dict:
        """
        レスポンスからJSON抽出（リトライ機能付き）

        JSONパースに失敗した場合、Claudeに修正を要求して最大max_retries回リトライします。

        Args:
            content: Claude からの最初のレスポンス
            tier: モデルティア（リトライ時に使用）
            max_retries: 最大リトライ回数（デフォルト: 2）

        Returns:
            パース成功したJSON辞書

        Raises:
            json.JSONDecodeError: 全てのリトライが失敗した場合
        """
        # 最初のパース試行
        try:
            logger.info("[JSON Parser] 初回パース試行")
            result = self._extract_json(content)
            logger.info("[JSON Parser] ✅ 初回パース成功")
            return result
        except (json.JSONDecodeError, ValueError) as first_error:
            logger.warning(f"[JSON Parser] ⚠️ 初回パース失敗: {first_error}")
            logger.debug(f"[JSON Parser] 失敗したコンテンツ (最初の500文字): {content[:500]}")

            # リトライループ
            last_error = first_error
            last_content = content
            previous_errors = set([str(first_error)])  # エラーの重複を追跡

            for retry_num in range(1, max_retries + 1):
                logger.info(f"[JSON Parser] 🔄 リトライ {retry_num}/{max_retries} を開始")

                try:
                    # Claudeに修正を要求
                    correction_prompt = self._build_json_correction_prompt(last_content, str(last_error))

                    logger.info(f"[JSON Parser] Claude に JSON修正を要求中...")
                    retry_response = self.llm.call_model(
                        tier=tier,
                        prompt=correction_prompt
                    )

                    if not retry_response.get("success"):
                        logger.error(f"[JSON Parser] リトライ {retry_num} のLLM呼び出し失敗: {retry_response.get('error')}")
                        continue

                    retry_content = retry_response.get("content", "")
                    logger.debug(f"[JSON Parser] リトライ {retry_num} レスポンス (最初の300文字): {retry_content[:300]}")

                    # 修正されたJSONをパース
                    result = self._extract_json(retry_content)
                    logger.info(f"[JSON Parser] ✅ リトライ {retry_num} でパース成功!")

                    # データ完全性の簡易チェック
                    if "metadata" in result:
                        metadata_count = len(result["metadata"])
                        logger.info(f"[JSON Parser] リトライ後のメタデータフィールド数: {metadata_count}")

                        # 主要な配列フィールドの要素数をログ出力
                        for array_field in ["monthly_schedule_blocks", "learning_content_blocks", "weekly_schedule"]:
                            if array_field in result.get("metadata", {}):
                                array_length = len(result["metadata"][array_field])
                                logger.info(f"[JSON Parser] リトライ後の {array_field} 要素数: {array_length}")

                                if array_length == 0:
                                    logger.warning(f"[JSON Parser] ⚠️ {array_field} が空です！データ損失の可能性")

                    return result

                except (json.JSONDecodeError, ValueError) as retry_error:
                    current_error = str(retry_error)

                    # 同じエラーが繰り返されているかチェック
                    if current_error in previous_errors:
                        logger.error(f"[JSON Parser] ❌ リトライ {retry_num} で同じエラーが再発: {current_error}")
                        logger.error(f"[JSON Parser] ⚠️ Claudeが構文エラーを修正できていません。リトライを中止します。")
                        break

                    previous_errors.add(current_error)
                    logger.warning(f"[JSON Parser] ⚠️ リトライ {retry_num} もパース失敗: {retry_error}")
                    last_error = retry_error
                    last_content = retry_content if 'retry_content' in locals() else last_content

                    if retry_num == max_retries:
                        logger.error(f"[JSON Parser] ❌ 全 {max_retries} 回のリトライが失敗しました")
                except Exception as unexpected_error:
                    logger.error(f"[JSON Parser] 予期しないエラー (リトライ {retry_num}): {unexpected_error}", exc_info=True)

            # 全てのリトライが失敗した場合、最後のエラーをraise
            logger.error("[JSON Parser] ❌ JSON抽出に完全に失敗しました。フォールバック処理に移行します。")
            raise last_error

    def _build_json_correction_prompt(self, failed_content: str, error_message: str) -> str:
        """
        JSON修正リトライ用のプロンプトを構築

        Args:
            failed_content: パースに失敗したコンテンツ
            error_message: エラーメッセージ

        Returns:
            修正要求プロンプト
        """
        import re

        # エラー箇所周辺を含めるため、2025年モデル性能に合わせて制限を大幅拡張
        max_content_length = 80000  # Claude 4.5 Haikuの性能に合わせて引き上げ

        if len(failed_content) > max_content_length:
            # エラーメッセージから行番号を抽出
            line_match = re.search(r'line (\d+)', error_message)

            if line_match:
                error_line = int(line_match.group(1))
                lines = failed_content.split('\n')

                # エラー行の前後を広く含める
                context_lines = 1000
                start_line = max(0, error_line - context_lines)
                end_line = min(len(lines), error_line + context_lines)

                content_to_send = '\n'.join(lines[start_line:end_line])

                if start_line > 0:
                    content_to_send = f"...(前略: {start_line}行)\n" + content_to_send
                if end_line < len(lines):
                    content_to_send = content_to_send + f"\n...(後略: {len(lines) - end_line}行)"

                logger.info(f"[JSON Parser] エラー箇所周辺を送信: 行{start_line}-{end_line} (全{len(lines)}行中)")
            else:
                # エラー行が特定できない場合は先頭から送る
                content_to_send = failed_content[:max_content_length]
                logger.warning(f"[JSON Parser] エラー行特定不可、先頭{max_content_length}文字を送信")
        else:
            content_to_send = failed_content
            logger.info(f"[JSON Parser] 全文を送信: {len(failed_content)}文字")

        return f"""前回のレスポンスでJSONのパースエラーが発生しました。

# エラー内容
{error_message}

# 前回のレスポンス
{content_to_send}

# 重要な修正タスク

あなたの前回のレスポンスには**JSON構文エラー**があります。以下の手順で修正してください：

## ステップ1: エラー箇所の特定
エラーメッセージを読んで、問題のある行と位置を特定してください。
エラーは "{error_message}" です。

## ステップ2: よくあるエラーパターンをチェック
以下のパターンでエラーがないか確認してください：
1. **配列の最後のカンマ**: `[..., ...,]` ← 最後のカンマを削除
2. **オブジェクトの最後のカンマ**: {{"key": "value",}} ← 最後のカンマを削除
3. **引用符の不一致**: キーと文字列値は必ず二重引用符 `"` で囲む
4. **括弧の不一致**: すべての `{{` に対応する `}}` があるか、`[` に対応する `]` があるか
5. **カンマの欠落**: 要素間にカンマがあるか（最後の要素を除く）

## ステップ3: データの完全保持
**絶対に守ること**:
- 元のJSONに含まれていた**全てのデータ**を保持してください
- `monthly_schedule_blocks` などの配列は、**元の要素数**を維持してください
- フィールドの削除や要素の省略は**絶対に禁止**です
- 構文エラー**のみ**を修正し、データ内容は変更しないでください

## ステップ4: 出力
修正したJSONを出力してください。以下の点に注意：
- 説明文やマークダウンは一切不要
- コードブロック (```) も不要
- 純粋なJSONオブジェクトのみを出力

それでは、修正されたJSONを出力してください（JSON形式のみ、他の文字は一切不要）:"""
    
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
            "error": "Stage 2抽出に失敗しました"
        }