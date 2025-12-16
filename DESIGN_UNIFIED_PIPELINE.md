# Unified Document Processing Pipeline - 統合処理パイプライン設計書

**作成日**: 2025-12-16
**更新日**: 2025-12-16
**ステータス**: 確定 (Finalized)
**目的**: 機能の責務（Separation of Concerns）を明確化した、堅牢かつ高精度なドキュメント処理フローの定義

---

## 1. 設計思想 (Design Philosophy)

従来の実行順序が不明確だった問題を解決し、**「機能的役割」**に基づいた明確な処理順序を定義する。
また、入力元（GAS）から渡される `doc_type` を確定情報として扱い、処理の精度向上に活用する。

### コア・コンセプト
1. **機械とAIの分離**: コストのかからない機械的抽出と、高コストなAI解析を明確に分ける。
2. **DocTypeの信頼**: GASから渡される `doc_type` は「正」とし、AIによる再分類は行わず、構造化の指針として利用する。
3. **適材適所**: 構造化（JSON）はClaude、統合・要約（日本語・コンテキスト）はGeminiに任せる。
4. **正しい処理順序の厳守**: Pre-processing → Stage B → Stage C → Stage A → Chunking の順序を絶対に守る。

---

## 2. パイプライン・アーキテクチャ

### 処理フロー概要（正しい順序）

```
┌─────────────────────────────────────────────────────────────┐
│ 入力ソース: GAS / Drive / Gmail                             │
│ - ファイル実体（PDF, Office, 画像）                         │
│ - 確定済み doc_type                                          │
│ - メタデータ（送信者、日時、件名など）                       │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Pre-processing: ライブラリベースのテキスト抽出               │
│ - 技術: pdfplumber, python-docx, openpyxl                   │
│ - コスト: ほぼゼロ                                           │
│ - 挙動: 失敗してもエラーにせず、空文字を返す                 │
└─────────────────────────────────────────────────────────────┘
                        ↓ (条件付き)
┌─────────────────────────────────────────────────────────────┐
│ Stage B: Visual Analysis (視覚解析)                         │
│ - クラス: StageBVisionProcessor                             │
│ - モデル: Gemini 2.5 Pro/Flash                              │
│ - コスト: 高                                                 │
│ - 発動条件:                                                  │
│   ✓ ファイルルート: ドライブ保存のファイルがある場合         │
│   ✓ メールルート: 画像を埋め込んだメールファイルがある場合   │
│   ✓ Pre-processingでテキストが抽出できなかった場合           │
│ - 役割: 視覚情報の言語化（画像、複雑なPDF、HTMLメール）     │
└─────────────────────────────────────────────────────────────┘
                        ↓
                  [統合テキスト]
     (Pre-processing結果 + Stage B結果)
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage C: Structuring (構造化)                               │
│ - クラス: StageCExtractor                                   │
│ - モデル: Claude Haiku 4.5                                  │
│ - 入力: 統合テキスト + 確定済み doc_type                     │
│ - 出力: metadata (JSON), tables (List)                      │
│ - 役割: 指定スキーマに基づくJSON抽出、表データの正規化       │
│ - 重要: doc_typeを判定するのではなく、渡されたdoc_typeの    │
│         スキーマを使ってデータを抽出することに専念           │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage A: Synthesis (統合・要約)                             │
│ - クラス: StageAClassifier (将来: StageASynthesizer)        │
│ - モデル: Gemini 2.5 Flash                                  │
│ - 入力: 統合テキスト + Stage C構造化JSON + doc_type         │
│ - 出力:                                                      │
│   - summary: 人間が読むための要約                           │
│   - tags: 検索用タグ                                        │
│   - relevant_date: 検索用の基準日付                         │
│   - embedding_text: ベクトル化に最適化された文字列           │
│ - 役割: 全情報を統合し、人間と検索エンジンに最適な形に整形   │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Chunking & Embedding                                        │
│ - MetadataChunker: メタデータチャンク生成                   │
│ - OpenAI Embedding: ベクトル化 (text-embedding-3-small)     │
│ - 保存先: search_index テーブル                             │
└─────────────────────────────────────────────────────────────┘
                        ↓
                  [Supabase]
```

---

## 3. コンポーネント定義

### Pre-processing (前処理)

**クラス名**: `LibraryTextExtractor` (または `_extract_text`)
**役割**: ファイルからプログラム的にテキストを引き抜く。
**技術**: pdfplumber, python-docx, openpyxl
**AI使用**: なし
**挙動**: 失敗してもエラーにせず、空文字を返してStage Bに託す。

### Stage B: Visual Analysis (視覚解析)

**クラス名**: `StageBVisionProcessor`
**役割**: 人間が見たままの情報をテキスト化する。
**モデル**: gemini-2.5-pro (精度重視) / gemini-2.5-flash (速度重視)
**発動条件**:
- ファイルルート: ドライブ保存のファイルがある場合
- メールルート: 画像を埋め込んだメールファイルがドライブにある場合
- 入力が画像ファイルである
- 入力がGmailのHTMLスクリーンショットである
- Pre-processingでの抽出テキストが極端に少ない（スキャンPDF等）

### Stage C: Structuring (構造化)

**クラス名**: `StageCExtractor`
**役割**: 非構造化テキストから、意味のあるデータ(JSON)を抽出する。
**モデル**: claude-haiku-4-5-20251001 (Claude Haiku 4.5)
**入力**: 統合テキスト + 確定済み doc_type
**出力**: metadata (JSON), tables (List)
**特記事項**: doc_type を判定するのではなく、渡された doc_type のスキーマを使ってデータを埋めることに専念する。

### Stage A: Synthesis (統合・要約)

**クラス名**: `StageAClassifier` (将来的に `StageASynthesizer` に改名予定)
**役割**: 抽出されたデータと元のテキストを統合し、人間と検索エンジンに最適な形に整形する。
**モデル**: gemini-2.5-flash
**入力**: 統合テキスト + 構造化JSON + doc_type
**出力**:
- summary: 人間が読むための要約
- tags: 検索用タグ
- relevant_date: 検索用の基準日付
- embedding_text: ベクトル化に最適化された文字列

---

## 4. データフロー実装イメージ（正しい順序）

```python
async def process_document(self, file_path, doc_type, workspace):
    """
    正しい処理順序:
    Pre-processing → Stage B → Stage C → Stage A → Chunking
    """

    # ============================================
    # Pre-processing: 機械的抽出
    # ============================================
    # AIを使わず、ライブラリのみで高速に抽出
    raw_text = self.library_extractor.extract(file_path)

    # ============================================
    # Stage B: Visual Analysis (視覚解析)
    # ============================================
    # 条件付き実行: テキストが取れなかった場合や画像の場合のみ発動
    vision_text = ""
    if self._needs_vision_processing(file_path, raw_text):
        vision_text = await self.stageB_vision_processor.process(file_path)

    # テキストを統合 (これが attachment_text になる)
    combined_text = f"{raw_text}\n\n{vision_text}".strip()

    # ============================================
    # Stage C: Structuring (構造化)
    # ============================================
    # doc_type (例: 'timetable') に基づいたスキーマでデータを抜く
    # Claudeが得意な領域
    structured_data = await self.stageC_extractor.extract_metadata(
        text=combined_text,
        file_name=file_name,
        stage1_result={'doc_type': doc_type, 'workspace': workspace},
        workspace=workspace
    )

    # ============================================
    # Stage A: Synthesis (統合・要約)
    # ============================================
    # 全情報を元に、最終的なドキュメント情報を作成
    # Geminiが得意な領域
    final_result = await self.stageA_classifier.classify(
        file_path=file_path,
        doc_types_yaml=self.yaml_string,
        text_content=combined_text,
        structured_metadata=structured_data  # Stage Cの結果を渡す
    )

    # ============================================
    # Chunking & Embedding
    # ============================================
    chunks = self.metadata_chunker.create_metadata_chunks({
        'display_subject': final_result.get('display_subject'),
        'summary': final_result.get('summary'),
        'tags': final_result.get('tags'),
        'document_date': final_result.get('document_date')
    })

    for chunk in chunks:
        embedding = self.llm_client.generate_embedding(chunk['chunk_text'])
        self.db.insert('search_index', {
            'document_id': document_id,
            'chunk_content': chunk['chunk_text'],
            'chunk_type': chunk['chunk_type'],
            'embedding': embedding,
            'search_weight': chunk['search_weight']
        })

    # ============================================
    # Database Update
    # ============================================
    self.db.save(final_result)
```

---

## 5. 移行のメリット

### 堅牢性 (Robustness)
doc_type をAIに推測させないため、分類ミスによる抽出失敗（例：時間割なのに請求書として抽出しようとする等）がなくなる。

### 責務の分離 (Separation of Concerns)
- **Pre-processing**: 文字を読む（機械的）
- **Stage B**: 視覚情報を言語化（AI・条件付き）
- **Stage C**: 意味を抜く（構造化・AI）
- **Stage A**: まとめる（統合・要約・AI）

これらが完全に分離され、デバッグやモデルの差し替えが容易になる。

### コスト最適化
pdfplumberで読めるものはVisionを使わない制御が明確になり、APIコストを削減できる。

### 正しい処理順序の保証
Stage C → Stage A の順序により、構造化データを活用した高精度な要約生成が可能になる。

---

## 6. 対応タスク

- [ ] 既存コードの処理順序を修正（Stage A → Stage C から Stage C → Stage A へ）
- [ ] `StageAClassifier` を `StageASynthesizer` にリネーム（将来）
- [ ] Stage Cのプロンプト修正（doc_type判定ロジックの削除）
- [ ] Pre-processingとStage Bの条件分岐ロジックの明確化
- [ ] 統合テキストの受け渡し方法の標準化

---

## 7. ルート別の処理フロー

### ファイルルート (Classroom/Drive)

```
GAS → Supabase登録
    ↓
Python処理開始
    ↓
Pre-processing (ライブラリ抽出)
    ↓ (ドライブ保存のファイルがある場合)
Stage B (Vision処理) ← 条件付き実行
    ↓
[統合テキスト]
    ↓
Stage C (構造化)
    ↓
Stage A (統合・要約)
    ↓
Chunking & Embedding
    ↓
Supabase保存
```

### メールルート (Gmail)

```
Gmail API → メール取得
    ↓
Pre-processing (HTMLパース)
    ↓ (画像を埋め込んだメールファイルがドライブにある場合)
Stage B (Vision処理) ← 条件付き実行
    ↓
[統合テキスト]
    ↓
Stage C (構造化)
    ↓
Stage A (統合・要約)
    ↓
Chunking & Embedding
    ↓
Supabase保存
```

---

## 8. 重要な注意事項

### 絶対に守るべきルール

1. **処理順序の厳守**: Pre-processing → Stage B → Stage C → Stage A → Chunking の順序を絶対に変更しない
2. **Stage Bの条件付き実行**: ファイル/画像がある場合のみ実行、ない場合はスキップ
3. **doc_typeの信頼**: GASから渡された doc_type を変更しない
4. **Stage Cの責務**: doc_typeの判定ではなく、指定されたスキーマでのデータ抽出に専念
5. **Stage Aの責務**: 構造化データを活用した統合・要約

### 現状のコードとの乖離

**警告**: 現状のコード（two_stage_ingestion.py）は **Stage A → Stage C** の順序で実行されており、これは**明確なルール違反**です。

早急に以下の修正が必要です：
- two_stage_ingestion.py の処理順序を **Stage C → Stage A** に修正
- Stage Aに構造化データを渡すインターフェースの実装

---

**設計書 終わり**
