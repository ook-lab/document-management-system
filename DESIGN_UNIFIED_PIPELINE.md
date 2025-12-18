# Unified Document Processing Pipeline - 統合処理パイプライン設計書 (v2.0)

**作成日**: 2025-12-16
**更新日**: 2025-12-18
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
4. **正しい処理順序の厳守**: Stage E → F → G → H → I → J → K の順序を絶対に守る。
5. **視覚解析と書式整形の分離**: 画像からテキスト抽出する際に情報が省略されないよう、視覚的に捉える工程と文章化する工程を分離。

---

## 2. パイプライン・アーキテクチャ (v2.0)

### 処理フロー概要（新ステージ定義）

```
┌─────────────────────────────────────────────────────────────┐
│ 入力ソース: GAS / Drive / Gmail                             │
│ - ファイル実体（PDF, Office, 画像）                         │
│ - 確定済み doc_type                                          │
│ - メタデータ（送信者、日時、件名など）                       │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage E: Pre-processing (前処理)                            │
│ - 技術: pdfplumber, python-docx, openpyxl                   │
│ - コスト: ほぼゼロ                                           │
│ - 挙動: 失敗してもエラーにせず、空文字を返す                 │
│ - 役割: ライブラリベースのテキスト抽出                       │
└─────────────────────────────────────────────────────────────┘
                        ↓ (条件付き)
┌─────────────────────────────────────────────────────────────┐
│ Stage F: Visual Analysis (視覚解析)                         │
│ - モデル: Gemini 2.5 Pro/Flash                              │
│ - コスト: 高                                                 │
│ - 発動条件:                                                  │
│   ✓ ファイルがドライブに保存されている場合                   │
│   ✓ 画像を埋め込んだメールファイルがある場合                 │
│   ✓ Pre-processingでテキストが抽出できなかった場合           │
│ - 役割: 視覚情報をそのまま捉える（OCR、レイアウト認識）     │
│ - 出力: 生のOCR結果、レイアウト情報（整形されていない）      │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage G: Text Formatting (書式整形)                         │
│ - モデル: Gemini 2.5 Flash (予定)                           │
│ - 役割: Stage F で抽出した生テキストをAIが読める形式に整形  │
│ - 処理内容:                                                  │
│   - 省略された文字の補完                                     │
│   - レイアウト情報を使った文章の再構成                       │
│   - 表構造の整形                                             │
│   - 読みやすい文章への変換                                   │
│ - 重要性: Stage F から Stage H への橋渡し                   │
│          視覚情報を失わずに構造化に渡すための重要工程        │
└─────────────────────────────────────────────────────────────┘
                        ↓
                  [統合テキスト]
     (Stage E結果 + Stage F/G結果)
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage H: Structuring (構造化)                               │
│ - モデル: Claude Haiku 4.5                                  │
│ - 入力: 統合テキスト + 確定済み doc_type                     │
│ - 出力: metadata (JSON), tables (List)                      │
│ - 役割: 指定スキーマに基づくJSON抽出、表データの正規化       │
│ - 重要: doc_typeを判定するのではなく、渡されたdoc_typeの    │
│         スキーマを使ってデータを抽出することに専念           │
│ - 元名称: Stage C                                           │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage I: Synthesis (統合・要約)                             │
│ - モデル: Gemini 2.5 Flash                                  │
│ - 入力: 統合テキスト + Stage H構造化JSON + doc_type         │
│ - 出力:                                                      │
│   - summary: 人間が読むための要約                           │
│   - tags: 検索用タグ                                        │
│   - relevant_date: 検索用の基準日付                         │
│ - 役割: 全情報を統合し、人間と検索エンジンに最適な形に整形   │
│ - 元名称: Stage A                                           │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage J: Chunking (チャンク化)                              │
│ - 入力: Stage H構造化データ + Stage I要約・タグ             │
│ - 処理: MetadataChunker でメタデータチャンク生成            │
│ - 出力: チャンクリスト（chunk_text, chunk_type等）          │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage K: Embedding (ベクトル化)                             │
│ - モデル: OpenAI text-embedding-3-small (1536次元)          │
│ - 入力: Stage J チャンクリスト                              │
│ - 出力: ベクトルデータ                                       │
│ - 保存先: search_index テーブル                             │
└─────────────────────────────────────────────────────────────┘
                        ↓
                  [Supabase]
```

---

## 3. ステージ詳細定義

### Stage E: Pre-processing (前処理)

**役割**: ファイルからプログラム的にテキストを引き抜く。
**技術**: pdfplumber, python-docx, openpyxl
**AI使用**: なし
**挙動**: 失敗してもエラーにせず、空文字を返してStage Fに託す。

### Stage F: Visual Analysis (視覚解析)

**役割**: 人間が見たままの視覚情報をそのまま捉える（OCR、レイアウト認識）
**モデル**: gemini-2.5-pro (精度重視) / gemini-2.5-flash (速度重視)
**発動条件**:
- ファイルがドライブに保存されている場合
- 画像を埋め込んだメールファイルがある場合
- 入力が画像ファイルである
- 入力がGmailのHTMLスクリーンショットである
- Pre-processingでの抽出テキストが極端に少ない（スキャンPDF等）

**出力**: 生のOCR結果、レイアウト情報（整形されていない状態）

### Stage G: Text Formatting (書式整形)

**役割**: Stage F で抽出した生テキストをAIが読める形式に整形
**モデル**: gemini-2.5-flash (予定)
**重要性**:
- 画像からテキスト抽出する際に、情報が省略されたり間引かれることが多い
- 視覚的に捉えた情報を失わずに構造化（Stage H）に渡すための重要工程
- **Stage F と G を分離した理由**: 「視覚的に捉える工程」と「それを文章にする工程」を明確に分ける

**処理内容**:
- 省略された文字の補完
- レイアウト情報を使った文章の再構成
- 表構造の整形
- 読みやすい文章への変換

### Stage H: Structuring (構造化)

**役割**: 非構造化テキストから、意味のあるデータ(JSON)を抽出する。
**モデル**: claude-haiku-4-5-20251001 (Claude Haiku 4.5)
**入力**: 統合テキスト + 確定済み doc_type
**出力**: metadata (JSON), tables (List)
**特記事項**: doc_type を判定するのではなく、渡された doc_type のスキーマを使ってデータを埋めることに専念する。
**元名称**: Stage C

### Stage I: Synthesis (統合・要約)

**役割**: 抽出されたデータと元のテキストを統合し、人間と検索エンジンに最適な形に整形する。
**モデル**: gemini-2.5-flash
**入力**: 統合テキスト + 構造化JSON + doc_type
**出力**:
- summary: 人間が読むための要約
- tags: 検索用タグ
- relevant_date: 検索用の基準日付
**元名称**: Stage A

### Stage J: Chunking (チャンク化)

**役割**: メタデータからチャンクを生成
**入力**: Stage H構造化データ + Stage I要約・タグ
**処理**: MetadataChunker でメタデータチャンク生成

### Stage K: Embedding (ベクトル化)

**役割**: チャンクをベクトル化
**モデル**: text-embedding-3-small (1536次元)
**入力**: Stage J チャンクリスト
**保存先**: search_index テーブル

---

## 4. データフロー実装イメージ

```python
async def process_document(self, file_path, doc_type, workspace):
    """
    正しい処理順序:
    Stage E → F → G → H → I → J → K
    """

    # ============================================
    # Stage E: Pre-processing (機械的抽出)
    # ============================================
    raw_text = self.library_extractor.extract(file_path)

    # ============================================
    # Stage F: Visual Analysis (視覚解析)
    # ============================================
    vision_raw = ""
    if self._needs_vision_processing(file_path, raw_text):
        vision_raw = await self.stageF_vision_analyzer.process(file_path)

    # ============================================
    # Stage G: Text Formatting (書式整形)
    # ============================================
    vision_formatted = ""
    if vision_raw:
        vision_formatted = await self.stageG_text_formatter.format(vision_raw)

    # テキストを統合
    combined_text = f"{raw_text}\n\n{vision_formatted}".strip()

    # ============================================
    # Stage H: Structuring (構造化)
    # ============================================
    structured_data = await self.stageH_extractor.extract_metadata(
        text=combined_text,
        file_name=file_name,
        stage1_result={'doc_type': doc_type, 'workspace': workspace},
        workspace=workspace
    )

    # ============================================
    # Stage I: Synthesis (統合・要約)
    # ============================================
    synthesis_result = await self.stageI_synthesizer.synthesize(
        file_path=file_path,
        text_content=combined_text,
        structured_metadata=structured_data
    )

    # ============================================
    # Stage J: Chunking (チャンク化)
    # ============================================
    chunks = self.stageJ_chunker.create_chunks({
        'summary': synthesis_result.get('summary'),
        'tags': synthesis_result.get('tags'),
        'metadata': structured_data
    })

    # ============================================
    # Stage K: Embedding (ベクトル化)
    # ============================================
    for chunk in chunks:
        embedding = self.stageK_embedder.generate_embedding(chunk['chunk_text'])
        self.db.insert('search_index', {
            'document_id': document_id,
            'chunk_content': chunk['chunk_text'],
            'embedding': embedding
        })
```

---

## 5. ステージ対応表（旧 → 新）

| 旧名称 | 新名称 | 役割 |
|--------|--------|------|
| Pre-processing | **Stage E** | 前処理 |
| Stage B (前半) | **Stage F** | 視覚解析 |
| Stage B (後半) | **Stage G** | 書式整形 |
| Stage C | **Stage H** | 構造化 |
| Stage A | **Stage I** | 統合・要約 |
| Chunking | **Stage J** | チャンク化 |
| Embedding | **Stage K** | ベクトル化 |

---

## 6. 重要な注意事項

### 絶対に守るべきルール

1. **処理順序の厳守**: Stage E → F → G → H → I → J → K の順序を絶対に変更しない
2. **Stage F/Gの条件付き実行**: ファイル/画像がある場合のみ実行、ない場合はスキップ
3. **doc_typeの信頼**: GASから渡された doc_type を変更しない
4. **Stage Hの責務**: doc_typeの判定ではなく、指定されたスキーマでのデータ抽出に専念
5. **Stage Iの責務**: 構造化データを活用した統合・要約
6. **Stage FとGの分離**: 視覚情報を失わないために、視覚解析と書式整形は必ず分離する

### TwoStageIngestionPipelineの廃止

**警告**: `TwoStageIngestionPipeline` クラスは旧設計に基づいており、**廃止対象**です。

今後は `process_queued_documents.py` に直接 Stage E-K を実装します。

---

## 7. 移行のメリット

### Stage FとGの分離による精度向上
- 画像からテキスト抽出する際の情報損失を最小化
- OCRで省略された文字を補完する工程が明確化
- レイアウト情報を活用した文章再構成が可能

### 堅牢性 (Robustness)
doc_type をAIに推測させないため、分類ミスによる抽出失敗がなくなる。

### 責務の分離 (Separation of Concerns)
各ステージが明確な役割を持ち、デバッグやモデルの差し替えが容易になる。

### コスト最適化
pdfplumberで読めるものはVisionを使わない制御が明確になり、APIコストを削減できる。

---

**設計書 終わり**
