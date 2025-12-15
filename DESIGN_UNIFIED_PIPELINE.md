承知いたしました。DESIGN_REPROCESS_COMPLETE.md は変更せず、新しい設計思想に基づいた新・統一パイプラインの設計書を別紙として作成します。
ファイル名は DESIGN_UNIFIED_PIPELINE.md とします。
この設計書は、先ほどの議論（機能の分離、doc_type固定、フローの最適化）を反映した「あるべき姿」の定義書となります。

DESIGN_UNIFIED_PIPELINE.md
Markdown


# Unified Document Processing Pipeline - 統合処理パイプライン設計書

**作成日**: 2025-12-16
**ステータス**: 策定中 (Draft)
**目的**: 機能の責務（Separation of Concerns）を明確化した、堅牢かつ高精度なドキュメント処理フローの定義

---

## 1. 設計思想 (Design Philosophy)

従来の「Stage 1/2」という実行順序依存の命名を廃止し、**「機能的役割」**に基づいた4つのステップに分離する。
また、入力元（GAS）から渡される `doc_type` を確定情報として扱い、処理の精度向上に活用する。

### コア・コンセプト
1. **機械とAIの分離**: コストのかからない機械的抽出と、高コストなAI解析を明確に分ける。
2. **DocTypeの信頼**: GASから渡される `doc_type` は「正」とし、AIによる再分類は行わず、構造化の指針として利用する。
3. **適材適所**: 構造化（JSON）はClaude、統合・要約（日本語・コンテキスト）はGeminiに任せる。

---

## 2. パイプライン・アーキテクチャ

### 処理フロー概要

```mermaid
graph TD
    %% 入力ソース
    subgraph Input [入力ソース]
        Source[GAS / Drive / Gmail]
        DocType[確定済み doc_type]
        File[ファイル実体]
    end

    %% Step 0: 前処理
    subgraph Step0 [Step 0: Pre-processing]
        File -->|PDF/Office| Extractor[Library Text Extractor]
        Note0[役割: pdfplumber/python-docx<br>機械的なテキスト抽出<br>コスト: ほぼゼロ]
    end

    %% Step 1: 視覚解析
    subgraph Step1 [Step 1: Visual Analysis (Stage B)]
        File -->|画像/複雑なPDF| VisionAI[Gemini Vision Processor]
        Note1[役割: Gemini 2.5 Pro/Flash<br>視覚情報の言語化<br>コスト: 高]
    end

    %% テキスト統合
    Extractor --> RawText[Raw Text]
    VisionAI -.->|必要時のみ| VisionText[Vision Text]
    RawText & VisionText --> CombinedText[統合テキスト]

    %% Step 2: 構造化
    subgraph Step2 [Step 2: Structuring (Stage C)]
        CombinedText --> Structurer[Structure Extractor]
        DocType -->|スキーマ指定| Structurer
        Note2[役割: Claude Haiku 4.5<br>指定スキーマに基づくJSON抽出<br>表データの正規化]
    end

    %% Step 3: 統合・仕上げ
    subgraph Step3 [Step 3: Synthesis (Stage A)]
        CombinedText --> Synthesizer[Synthesis Classifier]
        Structurer -->|Structured JSON| Synthesizer
        DocType -->|文脈ヒント| Synthesizer
        Note3[役割: Gemini 2.5 Flash<br>人間向け要約<br>タグ付け・日付正規化<br>Embedding用テキスト生成]
    end

    %% 出力
    Synthesizer --> Database[(Supabase)]



3. コンポーネント定義
各ステップのクラス名、役割、使用モデルを定義します。
Step 0: Pre-processing (前処理)
クラス名: LibraryTextExtractor (または _extract_text)
役割: ファイルからプログラム的にテキストを引き抜く。
技術: pdfplumber, python-docx, openpyxl
AI使用: なし
挙動: 失敗してもエラーにせず、空文字を返してStep 1に託す。
Step 1: Visual Analysis (視覚解析 - 旧Stage B)
クラス名: StageBVisionProcessor
役割: 人間が見たままの情報をテキスト化する。
モデル: gemini-2.5-pro (精度重視) / gemini-2.5-flash (速度重視)
発動条件:
入力が画像ファイルである
入力がGmailのHTMLスクリーンショットである
Step 0での抽出テキストが極端に少ない（スキャンPDF等）
Step 2: Structuring (構造化 - 旧Stage C)
クラス名: StageCExtractor
役割: 非構造化テキストから、意味のあるデータ(JSON)を抽出する。
モデル: claude-3-haiku-20240307 (または 4.5 Haiku)
入力: 統合テキスト + 確定済み doc_type
出力: metadata (JSON), tables (List)
特記事項: doc_type を判定するのではなく、渡された doc_type のスキーマを使ってデータを埋めることに専念する。
Step 3: Synthesis (統合・要約 - 旧Stage A)
クラス名: StageASynthesizer
役割: 抽出されたデータと元のテキストを統合し、人間と検索エンジンに最適な形に整形する。
モデル: gemini-2.5-flash
入力: 統合テキスト + 構造化JSON + doc_type
出力:
summary: 人間が読むための要約
tags: 検索用タグ
normalized_date: 検索用の基準日付
embedding_text: ベクトル化に最適化された文字列

4. データフロー実装イメージ
Python


async def process_document(self, file_path, doc_type, workspace):
    # --- Step 0: Pre-processing (機械的抽出) ---
    # AIを使わず、ライブラリのみで高速に抽出
    raw_text = self.library_extractor.extract(file_path)

    # --- Step 1: Visual Analysis (視覚解析) ---
    # テキストが取れなかった場合や画像の場合のみ発動
    vision_text = ""
    if self._needs_vision_processing(file_path, raw_text):
        vision_text = await self.vision_processor.process(file_path)
    
    # テキストを統合 (これが attachment_text になる)
    combined_text = f"{raw_text}\n\n{vision_text}".strip()

    # --- Step 2: Structuring (構造化) ---
    # doc_type (例: 'timetable') に基づいたスキーマでデータを抜く
    # Claudeが得意な領域
    structured_data = await self.structure_extractor.extract(
        text=combined_text,
        schema_type=doc_type  # 確定値として渡す
    )

    # --- Step 3: Synthesis (統合・要約) ---
    # 全情報を元に、最終的なドキュメント情報を作成
    # Geminiが得意な領域
    final_result = await self.synthesizer.synthesize(
        raw_text=combined_text,
        structured_data=structured_data,
        doc_context=doc_type
    )

    # --- Database Update ---
    # DB保存 (attachment_text, metadata, summary...)
    self.db.save(final_result)



5. 移行のメリット
堅牢性 (Robustness)
doc_type をAIに推測させないため、分類ミスによる抽出失敗（例：時間割なのに請求書として抽出しようとする等）がなくなる。
責務の分離 (Separation of Concerns)
「文字を読む(0,1)」「意味を抜く(2)」「まとめる(3)」が完全に分離され、デバッグやモデルの差し替えが容易になる。
コスト最適化
pdfplumberで読めるものはVisionを使わない制御が明確になり、APIコストを削減できる。

6. 対応タスク
[ ] pipelines/unified_ingestion_pipeline.py (仮) の新規作成
[ ] StageASynthesizer クラスの実装 (Classifierからの改修)
[ ] StageCExtractor のプロンプト修正 (doc_type判定ロジックの削除)



---

この設計書でよろしいでしょうか？
よろしければ、このファイルをプロジェクトに追加します。



