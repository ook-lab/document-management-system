# Classroom Documents Processing - 完全設計書

**作成日**: 2025-12-16
**目的**: GASからSupabaseに登録されたClassroomドキュメントの処理パイプライン完成

---

## 目次

1. [現状の問題点](#1-現状の問題点)
2. [システムアーキテクチャ](#2-システムアーキテクチャ)
3. [データフロー](#3-データフロー)
4. [実装すべき機能](#4-実装すべき機能)
5. [詳細仕様](#5-詳細仕様)
6. [ファイル整理](#6-ファイル整理)
7. [テスト手順](#7-テスト手順)

---

## 1. 現状の問題点

### 1.1 欠落している機能

**reprocess_classroom_documents_v2.py の現状:**

```
⚠️ 処理順序が間違っている（現状: Stage A → Stage C、正: Pre-processing → Stage B → Stage C → Stage A）
❌ Pre-processing (ファイルダウンロード) - 部分的に実装
❌ Stage B (テキスト抽出・Vision処理) - 完全に欠落
⚠️ Stage C (構造化) - 実装済みだが順序が間違っている
⚠️ Stage A (統合・要約) - 実装済みだが順序が間違っている
❌ チャンク化処理 - 完全に欠落
```

### 1.2 結果として起きている問題

1. **`source_type: 'classroom'` (添付ファイルあり) が処理できない**
   - ファイルダウンロード機能がない
   - PDFテキスト抽出機能がない
   - → 添付ファイル付き投稿が全てスキップされる

2. **`source_type: 'classroom_text'` (テキストのみ) は処理できるが検索できない**
   - Stage A、Cは動作する
   - `summary`は生成される
   - **しかし`search_index`テーブルにデータが入らない**
   - → 検索システムが機能しない

### 1.3 データ検証結果

```python
# Supabaseデータ確認結果
source_documents:
  - display_subject: "小テスト９"
  - summary: "164文字の要約" ✅
  - attachment_text: null (正常)
  - display_post_text: "96文字" ✅

search_index:
  - 該当データ: 0件 ❌ ← 検索不可能
```

---

## 2. システムアーキテクチャ

### 2.1 メインルート1: Classroom/Drive ファイル処理

```
┌─────────────────────────────────────────────────────────────┐
│ GAS (Google Apps Script)                                    │
│ - Classroom API から投稿取得                                │
│ - 基本情報をSupabaseに登録                                  │
│ - display_subject, display_post_text を保存                 │
│ - 添付ファイルはDriveにコピー、URLのみ保存                 │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Supabase: source_documents テーブル                         │
│ - source_type: 'classroom' | 'classroom_text'               │
│ - source_id: Drive file ID or Post ID                       │
│ - source_url: Drive URL (添付ファイルの場合)                │
│ - display_subject: 投稿件名                                 │
│ - display_post_text: 投稿本文                               │
│ - attachment_text: null (この時点では空)                    │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Python: process_queued_documents.py (新名称)                │
│                                                              │
│ ┌─ source_type: 'classroom' (添付ファイルあり) ────────┐   │
│ │ 1. Pre-processing: Drive URL → ダウンロード          │   │
│ │ 2. Stage B: テキスト抽出 (Vision処理)               │   │
│ │ 3. Stage C: Claude構造化 (メタデータ抽出)           │   │
│ │ 4. Stage A: Gemini統合・要約 (タグ付け・日付)       │   │
│ │ 5. チャンク化: subject + post_text + attachment_text │   │
│ │ 6. Supabaseに保存 (attachment_text + search_index)  │   │
│ └──────────────────────────────────────────────────────┘   │
│                                                              │
│ ┌─ source_type: 'classroom_text' (テキストのみ) ───────┐   │
│ │ 1. Pre-processing: スキップ (テキストは既にDBにある) │   │
│ │ 2. Stage B: スキップ (ファイルなし)                  │   │
│ │ 3. Stage C: Claude構造化 (subject + post_text)      │   │
│ │ 4. Stage A: Gemini統合・要約 (タグ付け・日付)       │   │
│ │ 5. チャンク化: subject + post_text                   │   │
│ │ 6. Supabaseに保存 (search_index)                     │   │
│ └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Supabase: search_index テーブル (ベクトル検索用)            │
│ - document_id                                               │
│ - chunk_content: チャンクテキスト                           │
│ - chunk_type: 'title', 'display_subject', 'content', etc.   │
│ - embedding: ベクトル (1536次元)                            │
│ - search_weight: 重み付け (title=2.0, subject=1.5, etc.)    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 メインルート2: Gmail処理

```
┌─────────────────────────────────────────────────────────────┐
│ Python: B_ingestion/gmail/gmail_ingestion.py                │
│ - Gmail API から直接取得                                     │
│ - Vision APIでテキスト抽出                                  │
│ - Stage A, C, チャンク化を全て実行                          │
│ - Supabaseに保存                                            │
└─────────────────────────────────────────────────────────────┘
```

**重要**: Gmail処理は独立した完結したパイプライン

---

## 3. データフロー

### 3.1 GASが登録するデータ

#### A. 添付ファイルあり (`source_type: 'classroom'`)

```json
{
  "source_type": "classroom",
  "source_id": "1a2b3c4d5e6f",  // Drive file ID
  "source_url": "https://drive.google.com/file/d/1a2b3c4d5e6f/view",
  "file_name": "小テスト９.pdf",
  "workspace": "小学６年１組",
  "doc_type": "小学６年１組",
  "display_sender": "田中先生",
  "display_sender_email": "tanaka@example.com",
  "display_sent_at": "2025-12-15T10:30:00Z",
  "display_subject": "小テスト９",
  "display_post_text": "明日までに提出してください。",
  "display_type": "課題",
  "persons": ["太郎"],
  "organizations": ["小学校"],
  "metadata": {
    "original_classroom_id": "xyz789",
    "post_id": "abc123",
    "course_name": "小学６年１組",
    "course_id": "123456"
  }
}
```

**注意**: `attachment_text`は空（null）

#### B. テキストのみ (`source_type: 'classroom_text'`)

```json
{
  "source_type": "classroom_text",
  "source_id": "post_abc123",  // Post ID (ファイルIDではない)
  "source_url": null,
  "file_name": "text_only",
  "workspace": "小学６年１組",
  "doc_type": "小学６年１組",
  "display_sender": "田中先生",
  "display_sent_at": "2025-12-15T10:30:00Z",
  "display_subject": "明日の予定",
  "display_post_text": "明日は体育館で集会があります。9時集合です。",
  "display_type": "お知らせ",
  "persons": ["太郎"],
  "organizations": ["小学校"],
  "metadata": {
    "post_type": "お知らせ",
    "course_name": "小学６年１組"
  }
}
```

**注意**: `attachment_text`は空（null） - これは正常

### 3.2 Pythonが処理すべきデータ

#### A. 添付ファイルあり (`source_type: 'classroom'`)

**入力**:
- `source_url`: Drive URL
- `display_subject`: 投稿件名
- `display_post_text`: 投稿本文

**処理**:
1. **Pre-processing (ファイルダウンロード)**:
   ```python
   # source_urlからファイルダウンロード
   local_path = drive.download_file(file_id, file_name, temp_dir)
   ```

2. **Stage B (Vision処理・新規実装が必要)**:
   ```python
   # テキスト抽出 (two_stage_ingestion.py の _extract_text を流用)
   # ライブラリ抽出 + Vision処理（必要時のみ）
   extraction_result = pdf_processor.extract_text(local_path)
   attachment_text = extraction_result['content']
   ```

3. **Stage C (構造化)**:
   ```python
   # 統合テキストを使って構造化データを抽出
   # 個別パラメータとして渡す（変数肥大化を避ける）
   stage_c_result = stage_c_extractor.extract_metadata(
       file_name=file_name,
       stage1_result={'doc_type': doc_type, 'workspace': workspace},
       workspace=workspace,
       attachment_text=attachment_text,
       display_subject=display_subject,
       display_post_text=display_post_text
   )
   ```

4. **Stage A (統合・要約)**:
   ```python
   # Stage Cの構造化結果を活用して統合・要約
   # display_subject + display_post_text + attachment_text を結合
   text_for_stage_a = f"【件名】\n{display_subject}\n\n【本文】\n{display_post_text}\n\n【添付ファイル】\n{attachment_text}"
   stage_a_result = await stage_a_classifier.classify(
       text_content=text_for_stage_a,
       structured_metadata=stage_c_result  # Stage Cの結果を渡す
   )
   ```

5. **データベース更新**:
   ```python
   update_data = {
       'attachment_text': attachment_text,  # ← これを保存
       'summary': stage_c_result['summary'],
       'metadata': stage_c_result['metadata'],
       'processing_status': 'completed'
   }
   db.update('source_documents', document_id, update_data)
   ```

6. **チャンク化 (新規実装が必要)**:
   ```python
   # two_stage_ingestion.py の Line 454-580 のロジックを移植
   chunks = create_metadata_chunks({
       'display_subject': display_subject,
       'display_post_text': display_post_text,
       'attachment_text': attachment_text,
       'summary': summary,
       'document_date': document_date,
       'tags': tags
   })

   # search_indexに保存
   for chunk in chunks:
       embedding = llm_client.generate_embedding(chunk['chunk_text'])
       db.insert('search_index', {
           'document_id': document_id,
           'chunk_content': chunk['chunk_text'],
           'chunk_type': chunk['chunk_type'],
           'embedding': embedding,
           'search_weight': chunk['search_weight']
       })
   ```

#### B. テキストのみ (`source_type: 'classroom_text'`)

**入力**:
- `display_subject`: 投稿件名
- `display_post_text`: 投稿本文

**処理**:
1. **Pre-processing**: スキップ（テキストは既にDBにある）

2. **Stage B**: スキップ（ファイルなし）

3. **Stage C (構造化)**:
   ```python
   stage_c_result = stage_c_extractor.extract_metadata(
       file_name='text_only',
       stage1_result={'doc_type': doc_type, 'workspace': workspace},
       workspace=workspace,
       display_subject=display_subject,
       display_post_text=display_post_text
   )
   ```

4. **Stage A (統合・要約)**:
   ```python
   # Stage Cの構造化結果を活用
   text_for_stage_a = f"【件名】\n{display_subject}\n\n【本文】\n{display_post_text}"
   stage_a_result = await stage_a_classifier.classify(
       text_content=text_for_stage_a,
       structured_metadata=stage_c_result  # Stage Cの結果を渡す
   )
   ```

5. **チャンク化 (新規実装が必要)**:
   ```python
   chunks = create_metadata_chunks({
       'display_subject': display_subject,
       'display_post_text': display_post_text,
       'summary': summary,
       'document_date': document_date,
       'tags': tags
   })

   # search_indexに保存
   for chunk in chunks:
       embedding = llm_client.generate_embedding(chunk['chunk_text'])
       db.insert('search_index', {
           'document_id': document_id,
           'chunk_content': chunk['chunk_text'],
           'chunk_type': chunk['chunk_type'],
           'embedding': embedding,
           'search_weight': chunk['search_weight']
       })
   ```

---

## 4. 実装すべき機能

### 4.1 優先度1: チャンク化処理の追加（必須）

**現状**: `_reprocess_text_only_document` 関数は Stage A, C までしか実行しない

**追加すべき処理**:

```python
# ============================================
# チャンク化処理（新規追加）
# ============================================
logger.info("[チャンク化] 開始...")

# 既存チャンクを削除（再処理の場合）
try:
    delete_result = self.db.client.table('search_index').delete().eq('document_id', document_id).execute()
    deleted_count = len(delete_result.data) if delete_result.data else 0
    logger.info(f"  既存チャンク削除: {deleted_count}個")
except Exception as e:
    logger.warning(f"  既存チャンク削除エラー（継続）: {e}")

# チャンクデータ準備
document_data = {
    'file_name': file_name,
    'summary': summary,
    'document_date': document_date,
    'tags': tags,
    'display_subject': display_subject,
    'display_post_text': display_post_text,
    'attachment_text': attachment_text  # classroom_textの場合はNone
}

# メタデータチャンク生成
from A_common.processing.metadata_chunker import MetadataChunker
metadata_chunker = MetadataChunker()
metadata_chunks = metadata_chunker.create_metadata_chunks(document_data)

current_chunk_index = 0
for meta_chunk in metadata_chunks:
    meta_text = meta_chunk.get('chunk_text', '')
    meta_type = meta_chunk.get('chunk_type', 'metadata')
    meta_weight = meta_chunk.get('search_weight', 1.0)

    if not meta_text:
        continue

    # Embedding生成
    meta_embedding = self.pipeline.llm_client.generate_embedding(meta_text)

    # search_indexに保存
    meta_doc = {
        'document_id': document_id,
        'chunk_index': current_chunk_index,
        'chunk_content': meta_text,
        'chunk_size': len(meta_text),
        'chunk_type': meta_type,
        'embedding': meta_embedding,
        'search_weight': meta_weight
    }

    try:
        self.db.client.table('search_index').insert(meta_doc).execute()
        current_chunk_index += 1
    except Exception as e:
        logger.error(f"  チャンク保存エラー: {e}")

logger.info(f"[チャンク化] 完了: {current_chunk_index}個のチャンク作成")
```

**参考コード**: `B_ingestion/two_stage_ingestion.py` の Line 454-580

### 4.2 優先度2: 添付ファイル処理の追加（重要）

**新規関数を追加**: `_reprocess_classroom_document_with_attachment`

```python
async def _reprocess_classroom_document_with_attachment(
    self,
    queue_id: str,
    document_id: str,
    doc: Dict[str, Any]
) -> bool:
    """
    添付ファイル付きClassroomドキュメントを再処理

    処理フロー:
    1. Pre-processing: Drive URLからファイルダウンロード
    2. Stage B: テキスト抽出 (Vision処理)
    3. Stage C: Claude構造化 (メタデータ抽出)
    4. Stage A: Gemini統合・要約 (タグ付け・日付)
    5. チャンク化
    """

    file_name = doc.get('file_name', 'unknown')
    source_url = doc.get('source_url', '')
    display_subject = doc.get('display_subject', '')
    display_post_text = doc.get('display_post_text', '')

    # source_urlからfile_idを抽出
    file_id = self._extract_file_id_from_url(source_url)
    if not file_id:
        error_msg = "source_urlが不正です"
        logger.error(f"{error_msg}: {source_url}")
        self._mark_task_failed(queue_id, error_msg)
        return False

    try:
        # ============================================
        # Pre-processing: ファイルダウンロード
        # ============================================
        logger.info("[Pre-processing] ファイルダウンロード開始...")

        # ダウンロード
        temp_dir = Path("./temp")
        temp_dir.mkdir(exist_ok=True)
        local_path = self.pipeline.drive.download_file(file_id, file_name, temp_dir)

        # MIME type推測
        mime_type = self._guess_mime_type(file_name)

        logger.info(f"[Pre-processing] 完了: ファイルダウンロード完了")

        # ============================================
        # Stage B: テキスト抽出 (Vision処理)
        # ============================================
        logger.info("[Stage B] テキスト抽出開始...")

        # テキスト抽出 (ライブラリ + Vision)
        extraction_result = self.pipeline._extract_text(local_path, mime_type)

        if not extraction_result["success"]:
            logger.warning(f"テキスト抽出失敗: {file_name}")
            attachment_text = ""
        else:
            attachment_text = extraction_result["content"]

        logger.info(f"[Stage B] 完了: {len(attachment_text)}文字抽出")

        # ============================================
        # 統合テキスト準備
        # ============================================
        # 全てのテキストソースを結合
        text_parts = []
        if display_subject:
            text_parts.append(f"【件名】\n{display_subject}")
        if display_post_text:
            text_parts.append(f"【本文】\n{display_post_text}")
        if attachment_text:
            text_parts.append(f"【添付ファイル】\n{attachment_text}")

        combined_text = '\n\n'.join(text_parts)

        # ============================================
        # Stage C: Claude構造化 (メタデータ抽出)
        # ============================================
        logger.info("[Stage C] Claude構造化開始...")
        stage_c_result = self.pipeline.stageC_extractor.extract_metadata(
            file_name=file_name,
            stage1_result={'doc_type': doc.get('doc_type', 'unknown'), 'workspace': doc.get('workspace', 'unknown')},
            workspace=doc.get('workspace', 'unknown'),
            attachment_text=attachment_text if attachment_text else None,
            display_subject=display_subject if display_subject else None,
            display_post_text=display_post_text if display_post_text else None,
        )

        document_date = stage_c_result.get('document_date')
        tags = stage_c_result.get('tags', [])
        metadata = stage_c_result.get('metadata', {})

        logger.info(f"[Stage C] 完了")

        # ============================================
        # Stage A: Gemini統合・要約
        # ============================================
        logger.info("[Stage A] Gemini統合・要約開始...")
        stage_a_result = await self.pipeline.stageA_classifier.classify(
            file_path=Path(local_path),
            doc_types_yaml=self.yaml_string,
            mime_type=mime_type,
            text_content=combined_text,
            structured_metadata=stage_c_result  # Stage Cの結果を渡す
        )

        summary = stage_a_result.get('summary', '')
        relevant_date = stage_a_result.get('relevant_date')

        # Stage Cの要約がある場合は優先
        if stage_c_result.get('summary'):
            summary = stage_c_result.get('summary', summary)

        logger.info(f"[Stage A] 完了")

        # ============================================
        # データベース更新
        # ============================================
        update_data = {
            'attachment_text': attachment_text,  # ← 重要: 抽出したテキストを保存
            'summary': summary,
            'metadata': metadata,
            'processing_status': 'completed',
            'processing_stage': 'stage_abc_complete',
            'stagea_classifier_model': 'gemini-2.5-flash',
            'stagec_extractor_model': 'claude-haiku-4-5-20251001',
            'relevant_date': relevant_date
        }

        response = self.db.client.table('source_documents').update(update_data).eq('id', document_id).execute()

        if not response.data:
            error_msg = "データベース更新失敗"
            logger.error(error_msg)
            self._mark_task_failed(queue_id, error_msg)
            return False

        # ============================================
        # チャンク化処理
        # ============================================
        # (4.1のチャンク化コードをここに挿入)

        logger.success(f"✅ 添付ファイル付きドキュメント再処理成功: {file_name}")
        self._mark_task_completed(queue_id, success=True)
        return True

    except Exception as e:
        error_msg = f"添付ファイル処理エラー: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.exception(e)
        self._mark_task_failed(queue_id, error_msg, error_details={'exception': str(e)})
        return False
    finally:
        # 一時ファイル削除
        if local_path and Path(local_path).exists():
            Path(local_path).unlink()
```

**ヘルパー関数**:

```python
def _extract_file_id_from_url(self, url: str) -> str:
    """
    Drive URLからファイルIDを抽出

    例: https://drive.google.com/file/d/1a2b3c4d5e6f/view
        → 1a2b3c4d5e6f
    """
    import re
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    return ""
```

### 4.3 優先度3: メイン処理の分岐修正

**現状**: `_reprocess_file_with_attachment` 関数が存在するが、不完全

**修正**:

```python
async def process_queue_item(self, queue_item: Dict[str, Any]) -> bool:
    """キューアイテムを処理"""

    queue_id = queue_item['id']
    document_id = queue_item['document_id']

    # ドキュメント情報取得
    doc_result = self.db.client.table('source_documents').select('*').eq('id', document_id).execute()

    if not doc_result.data:
        logger.error(f"ドキュメントが見つかりません: {document_id}")
        self._mark_task_failed(queue_id, "ドキュメントが見つかりません")
        return False

    doc = doc_result.data[0]
    source_type = doc.get('source_type', '')

    # source_typeによって処理を分岐
    if source_type == 'classroom':
        # 添付ファイルあり
        return await self._reprocess_classroom_document_with_attachment(queue_id, document_id, doc)

    elif source_type == 'classroom_text':
        # テキストのみ
        return await self._reprocess_text_only_document(queue_id, document_id, doc)

    else:
        error_msg = f"未対応のsource_type: {source_type}"
        logger.error(error_msg)
        self._mark_task_failed(queue_id, error_msg)
        return False
```

---

## 5. 詳細仕様

### 5.1 チャンク化戦略

**メタデータチャンク** (重み付きベクトル検索):

| chunk_type | 内容 | search_weight | 優先度 |
|-----------|------|--------------|--------|
| `title` | file_name | 2.0 | 最高 |
| `display_subject` | display_subject | 1.5 | 高 |
| `display_post_text` | display_post_text | 1.2 | 中高 |
| `summary` | summary | 1.0 | 中 |
| `tags` | tags (カンマ区切り) | 1.0 | 中 |
| `document_date` | document_date (YYYY-MM-DD) | 0.8 | 低 |

**コンテンツチャンク** (attachment_text がある場合):

| chunk_type | 内容 | サイズ | 用途 |
|-----------|------|--------|-----|
| `content_small` | 小チャンク (500文字) | 500 chars | 精密検索 |
| `content_medium` | 中チャンク (2000文字) | 2000 chars | バランス |

**参考**: `A_common/processing/metadata_chunker.py`

### 5.2 エラーハンドリング

#### A. ファイルダウンロード失敗

```python
try:
    local_path = drive.download_file(file_id, file_name, temp_dir)
except Exception as e:
    logger.error(f"ダウンロード失敗: {e}")
    # キューを'failed'にマーク
    self._mark_task_failed(queue_id, f"ダウンロード失敗: {str(e)}")
    return False
```

#### B. テキスト抽出失敗

```python
extraction_result = pdf_processor.extract_text(local_path)
if not extraction_result["success"]:
    # テキスト抽出失敗でも続行
    logger.warning(f"テキスト抽出失敗: {file_name}")
    attachment_text = ""
    # Stage A, C は display_subject + display_post_text のみで実行
```

#### C. チャンク化失敗

```python
try:
    # チャンク化処理
    pass
except Exception as e:
    # チャンク化失敗は致命的エラー
    logger.error(f"チャンク化失敗: {e}")
    self._mark_task_failed(queue_id, f"チャンク化失敗: {str(e)}")
    return False
```

### 5.3 ログ出力

**必須ログ**:

```python
logger.info(f"[Pre-processing] 開始: {file_name}")
logger.info(f"[Pre-processing] 完了: ファイルダウンロード完了")
logger.info(f"[Stage B] 開始")
logger.info(f"[Stage B] 完了: {len(attachment_text)}文字抽出")
logger.info(f"[Stage C] 開始")
logger.info(f"[Stage C] 完了: metadata_fields={len(metadata)}")
logger.info(f"[Stage A] 開始")
logger.info(f"[Stage A] 完了: summary={summary[:50]}...")
logger.info(f"[チャンク化] 開始")
logger.info(f"[チャンク化] 完了: {chunk_count}個のチャンク作成")
logger.success(f"✅ 処理成功: {file_name}")
```

**エラーログ**:

```python
logger.error(f"❌ {error_msg}: {file_name}")
logger.exception(e)  # スタックトレース出力
```

---

## 6. ファイル整理

### 6.1 リネーム

#### A. メインスクリプト

```bash
# 現在
J_resources/scripts/py/reprocess_classroom_documents_v2.py

# 新しい名前（推奨）
J_resources/scripts/py/process_queued_documents.py
```

**理由**:
- "reprocess"は誤解を招く（実際はメイン処理）
- "queued"がGASからの登録データを処理することを明確化

#### B. 共通処理（オプション）

```bash
# 現在
B_ingestion/two_stage_ingestion.py

# 新しい名前（オプション）
B_ingestion/file_ingestion_pipeline.py
```

**理由**:
- "two_stage"は古い名前（現在はStage A/B/C）
- ただし、大規模な変更なので必須ではない

### 6.2 削除対象

```bash
# すでにarchiveフォルダにあるので削除しても問題なし
rm J_resources/scripts/py/archive/daily_sync.py
```

### 6.3 one_timeフォルダ

**維持**: 将来また使う可能性があるのでそのまま

```
J_resources/scripts/py/one_time/
├── reingest_all_data.py        # 全データ再処理（緊急時用）
├── reprocess_single_file.py    # 単一ファイル再処理（デバッグ用）
└── その他のワンタイムスクリプト
```

---

## 7. テスト手順

### 7.1 単体テスト

#### A. テキストのみドキュメント

```bash
# 1. GASでclassroom_textを登録
# 2. Pythonスクリプト実行
python J_resources/scripts/py/process_queued_documents.py

# 3. 確認
# - source_documents: summary が生成されているか
# - search_index: チャンクが作成されているか

# 4. 検索テスト
# Streamlitで「小テスト」と検索してヒットするか確認
```

#### B. 添付ファイル付きドキュメント

```bash
# 1. GASでclassroom (添付ファイルあり) を登録
# 2. Pythonスクリプト実行
python J_resources/scripts/py/process_queued_documents.py

# 3. 確認
# - source_documents: attachment_text が保存されているか
# - search_index: チャンクが作成されているか (件名+本文+添付ファイル)

# 4. 検索テスト
# PDFの内容で検索してヒットするか確認
```

### 7.2 統合テスト

```bash
# 1. 過去3日分のClassroom投稿をGASで一括登録
# 2. Pythonスクリプト実行（全件処理）
# 3. 統計確認
#    - 処理成功: N件
#    - 処理失敗: N件
#    - チャンク総数: N個
```

### 7.3 検証クエリ

```sql
-- 1. 処理状況確認
SELECT
    source_type,
    processing_status,
    COUNT(*) as count
FROM source_documents
WHERE source_type IN ('classroom', 'classroom_text')
GROUP BY source_type, processing_status;

-- 2. チャンク化状況確認
SELECT
    sd.source_type,
    sd.file_name,
    COUNT(si.id) as chunk_count
FROM source_documents sd
LEFT JOIN search_index si ON sd.id = si.document_id
WHERE sd.source_type IN ('classroom', 'classroom_text')
GROUP BY sd.source_type, sd.file_name
HAVING COUNT(si.id) = 0;  -- チャンクが0件のドキュメントを検出

-- 3. attachment_text確認
SELECT
    file_name,
    source_type,
    LENGTH(attachment_text) as text_length,
    LENGTH(display_post_text) as post_length
FROM source_documents
WHERE source_type = 'classroom'
LIMIT 10;
```

---

## 8. 実装チェックリスト

### 8.1 必須実装

- [ ] `_reprocess_text_only_document`にチャンク化処理を追加
- [ ] `_reprocess_classroom_document_with_attachment`関数を新規作成
- [ ] `process_queue_item`でsource_type分岐を実装
- [ ] `_extract_file_id_from_url`ヘルパー関数を実装
- [ ] エラーハンドリング追加（ダウンロード失敗、抽出失敗、チャンク化失敗）
- [ ] ログ出力の充実

### 8.2 推奨実装

- [ ] ファイル名変更: `reprocess_classroom_documents_v2.py` → `process_queued_documents.py`
- [ ] 一時ファイルの自動削除（finally block）
- [ ] 再処理時の既存チャンク削除

### 8.3 テスト

- [ ] テキストのみドキュメントの処理テスト
- [ ] 添付ファイル付きドキュメントの処理テスト
- [ ] 検索機能のテスト（StreamlitまたはSQL）
- [ ] エラーケースのテスト

---

## 9. 参考コード

### 9.1 チャンク化処理の参考

**ファイル**: `B_ingestion/two_stage_ingestion.py`
**行**: 454-580
**内容**: メタデータチャンク生成 + search_indexへの保存

### 9.2 テキスト抽出の参考

**ファイル**: `B_ingestion/two_stage_ingestion.py`
**行**: 131-151 (`_extract_text`メソッド)
**内容**: PDFProcessor、OfficeProcessorの使い方

### 9.3 Stage A/B/C実行の参考

**ファイル**: `B_ingestion/two_stage_ingestion.py`
**行**: 186-320 (`process_file`メソッド)
**内容**: 完全なパイプライン実装例
**警告**: このファイルは現在 **Stage A → Stage C** の順序で実行されており、これは**明確なルール違反**です。正しい順序は **Pre-processing → Stage B → Stage C → Stage A** です。

---

## 10. 注意事項

### 10.1 データの整合性

- `attachment_text`は`source_type: 'classroom'`のみに保存
- `source_type: 'classroom_text'`の場合、`attachment_text`は空（null）が正常
- `display_subject`と`display_post_text`は両方のtypeで使用

### 10.2 パフォーマンス

- Embedding生成はコストが高い（OpenAI API呼び出し）
- バッチ処理の場合、適切なレート制限を考慮
- 一時ファイルは必ず削除（ディスク容量節約）

### 10.3 エラーリカバリ

- `document_reprocessing_queue`テーブルで処理状態を管理
- 失敗したドキュメントは`status: 'failed'`でマーク
- 再実行可能な設計（冪等性）

---

## 付録A: データベーススキーマ

### source_documents

```sql
CREATE TABLE source_documents (
    id UUID PRIMARY KEY,
    source_type VARCHAR,  -- 'classroom', 'classroom_text', 'gmail'
    source_id VARCHAR UNIQUE,
    source_url TEXT,
    file_name VARCHAR,
    workspace VARCHAR,
    doc_type VARCHAR,

    -- テキストフィールド
    attachment_text TEXT,      -- Stage Bで抽出（classroomのみ）
    summary TEXT,              -- Stage A/Cで生成

    -- Classroom固有フィールド
    display_sender VARCHAR,
    display_sender_email VARCHAR,
    display_sent_at TIMESTAMPTZ,
    display_subject TEXT,
    display_post_text TEXT,
    display_type VARCHAR,

    -- メタデータ
    metadata JSONB,
    persons TEXT[],
    organizations TEXT[],

    -- 処理状態
    processing_status VARCHAR,  -- 'pending', 'completed', 'failed'
    processing_stage VARCHAR,

    -- AI モデル情報
    stagea_classifier_model VARCHAR,
    stagec_extractor_model VARCHAR,

    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### search_index

```sql
CREATE TABLE search_index (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES source_documents(id),
    chunk_index INTEGER,
    chunk_content TEXT,
    chunk_size INTEGER,
    chunk_type VARCHAR,  -- 'title', 'display_subject', 'summary', etc.
    embedding vector(1536),
    search_weight FLOAT,  -- 重み付け（タイトル=2.0、通常=1.0）
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### document_reprocessing_queue

```sql
CREATE TABLE document_reprocessing_queue (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES source_documents(id),
    status VARCHAR,  -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);
```

---

## 付録B: 想定される質問と回答

**Q1: `two_stage_ingestion.py`は使わないのか？**

A: `two_stage_ingestion.py`は**参考コード**として使用します。チャンク化ロジックやテキスト抽出ロジックを移植しますが、ファイル自体は変更しません（Gmail処理で使用中のため）。

**Q2: なぜ`full_text`ではなく`attachment_text`なのか？**

A:
- `full_text`は誤解を招く名前（「全文」ではない）
- `attachment_text`は「添付ファイルから抽出したテキスト」を明確に表現
- `display_subject`、`display_post_text`は別々にベクトル化するため、結合しない

**Q3: Gmailの処理は？**

A: Gmailは独立したパイプライン（`B_ingestion/gmail/gmail_ingestion.py`）で処理します。今回の設計書の対象外です。

**Q4: 既存のドキュメントを再処理したい場合は？**

A: `document_reprocessing_queue`テーブルにレコードを挿入すれば、自動的に再処理されます。

```sql
INSERT INTO document_reprocessing_queue (document_id, status)
SELECT id, 'pending'
FROM source_documents
WHERE source_type IN ('classroom', 'classroom_text')
AND processing_status = 'pending';
```

---

**設計書 終わり**

実装に不明点があれば、このドキュメントを参照してください。
