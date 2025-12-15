# テキストのみドキュメント対応 - 技術仕様

## 概要

`reprocess_classroom_documents_v2.py` を修正し、Google Classroomのテキストのみ投稿（お知らせなど）もStage 1とStage 2の処理を確実に実行できるようにしました。

---

## 問題点

### 修正前の状態

ユーザーが示したドキュメント（ID: `5110106b-761c-4735-a7db-2895f2990225`）:

```json
{
  "source_type": "classroom_text",
  "source_id": "828984747050",
  "file_name": "text_only",
  "doc_type": "2025_5B",
  "workspace": "ikuya_classroom",
  "full_text": "【学級閉鎖のご報告】\n\n本日2年A組は発熱者、インフルエンザ罹患者が増加したため学級閉鎖といたしました。...",
  "stage1_doc_type": null,
  "stage1_workspace": null,
  "stage1_confidence": null,
  "processing_status": "pending"
}
```

**問題:**
- `stage1_doc_type`, `stage1_workspace`, `stage1_confidence` がすべて `null`
- Stage 1（Gemini分類）が実行されていない
- Stage 2（Claude詳細抽出）も実行されていない
- `doc_type` と `workspace` が直接設定されている（2段階処理を経ていない）

**原因:**
- `reprocess_classroom_documents_v2.py` がGoogle Driveのファイルダウンロードを前提としていた
- `source_type="classroom_text"` のドキュメントにはファイルIDがないため、処理できなかった

---

## 解決策

### 修正内容

#### 1. **ドキュメントタイプの判定を追加**

`_reprocess_document()` メソッドで、`source_type` を確認:

```python
source_type = doc.get('source_type', '')

if source_type == 'classroom_text':
    logger.info("📝 テキストのみドキュメントを検出（classroom_text）")
    return await self._reprocess_text_only_document(
        queue_id=queue_id,
        document_id=document_id,
        doc=doc,
        preserve_workspace=preserve_workspace
    )
```

#### 2. **テキストのみドキュメント専用処理メソッド**

新しいメソッド `_reprocess_text_only_document()` を追加:

```python
async def _reprocess_text_only_document(
    self,
    queue_id: str,
    document_id: str,
    doc: Dict[str, Any],
    preserve_workspace: bool = True
) -> bool:
    """
    テキストのみのドキュメント（classroom_text）を再処理
    """
```

**処理フロー:**

1. **データベースから `full_text` を取得**
   ```python
   full_text = doc.get('full_text', '')
   if not full_text:
       error_msg = "full_textが空です"
       return False
   ```

2. **Stage 1: Gemini分類**
   ```python
   stage1_result = await stage1_classifier.classify(
       file_path=PathLib("dummy"),  # ダミーパス
       doc_types_yaml=yaml_string,
       mime_type="text/plain",      # テキストのみを示す
       text_content=full_text       # テキストを渡す
   )
   ```

3. **Stage 2: Claude詳細抽出**
   ```python
   stage2_result = stage2_extractor.extract_metadata(
       full_text=full_text,
       file_name=file_name,
       stage1_result=stage1_result,
       workspace=stage1_workspace
   )
   ```

4. **Embedding生成**
   ```python
   combined_text = full_text[:7000] + "\n\n[メタデータ]\n" + metadata_text[:1000]
   embedding = self.pipeline.llm_client.generate_embedding(combined_text)
   ```

5. **データベース更新**
   ```python
   update_data = {
       'stage1_doc_type': stage1_doc_type,
       'stage1_workspace': stage1_workspace,
       'stage1_confidence': stage1_confidence,
       'doc_type': doc_type,
       'workspace': stage1_workspace,
       'summary': summary,
       'metadata': metadata,
       'embedding': embedding,
       'confidence': final_confidence,
       'processing_status': 'completed',
       'processing_stage': 'stage1_and_stage2',
       'stage1_model': 'gemini-2.5-flash',
       'stage2_model': 'claude-haiku-4-5-20251001'
   }
   ```

---

## 実行方法

### ステップ1: テキストのみドキュメントをキューに追加

```bash
cd document_management_system

# テキストのみドキュメントをキューに追加
python reprocess_classroom_documents_v2.py --populate-only --limit=100
```

### ステップ2: キューから処理

```bash
# 処理実行
python reprocess_classroom_documents_v2.py --process-queue --limit=50
```

### ログ出力例

```
================================================================================
[1/50] 処理開始: text_only
Queue ID: 12345678-abcd-...
Document ID: 5110106b-761c-4735-a7db-2895f2990225
================================================================================

📝 テキストのみドキュメントを検出（classroom_text）
テキスト長: 123文字

[Stage 1] Gemini分類開始...
[Stage 1] 完了: doc_type=school_newsletter, workspace=family, confidence=0.92

[Stage 2] Claude詳細抽出開始...
[Stage 2] 完了: doc_type=school_newsletter, confidence=0.88

[Embedding] 生成開始...
[Embedding] 生成完了

✅ テキストのみドキュメント再処理成功: text_only
  Stage1: school_newsletter (confidence=0.92)
  Stage2: school_newsletter (confidence=0.88)
  最終信頼度: 0.89
```

---

## データベースの変更内容

### 処理前（問題のある状態）

```json
{
  "stage1_doc_type": null,
  "stage1_workspace": null,
  "stage1_confidence": null,
  "doc_type": "2025_5B",
  "workspace": "ikuya_classroom",
  "processing_status": "pending",
  "processing_stage": null,
  "stage1_model": null,
  "stage2_model": null
}
```

### 処理後（正常な状態）

```json
{
  "stage1_doc_type": "school_newsletter",
  "stage1_workspace": "family",
  "stage1_confidence": 0.92,
  "doc_type": "school_newsletter",
  "workspace": "family",
  "processing_status": "completed",
  "processing_stage": "stage1_and_stage2",
  "stage1_model": "gemini-2.5-flash",
  "stage2_model": "claude-haiku-4-5-20251001",
  "confidence": 0.89,
  "summary": "2年A組の学級閉鎖に関するお知らせ",
  "metadata": {
    "post_type": "お知らせ",
    "topic": "学級閉鎖",
    "grade": "2年A組",
    "reason": "インフルエンザ",
    ...
  },
  "embedding": [0.123, 0.456, ...]
}
```

---

## 対応するドキュメントタイプ

この修正により、以下のタイプのドキュメントが処理可能になります:

| `source_type` | 説明 | 処理方法 |
|---------------|------|----------|
| `drive` | Google Driveのファイル | ファイルをダウンロード → Stage1 → Stage2 |
| `email_attachment` | メール添付ファイル | ファイルをダウンロード → Stage1 → Stage2 |
| `classroom_text` | Google Classroomのテキスト投稿 | **full_textを直接使用 → Stage1 → Stage2** ✅ |

---

## 技術的な詳細

### Stage1Classifier の使い方

`classify()` メソッドは以下のパラメータを受け取ります:

```python
async def classify(
    self,
    file_path: Path,              # ファイルパス（PDFの場合のみ使用）
    doc_types_yaml: str,          # 分類定義（YAML形式）
    mime_type: Optional[str],     # MIMEタイプ
    text_content: Optional[str]   # テキストコンテンツ
) -> Dict[str, Any]:
```

**テキストのみの場合:**
- `mime_type != "application/pdf"` かつ `text_content` が指定されている場合
- ファイルをアップロードせず、テキストをプロンプトに埋め込む

```python
# テキストをプロンプトに追加
prompt += f"\n\n**ファイル内容:**\n{text_content[:5000]}"
response = self.client.call_model(
    tier=self.tier,
    prompt=prompt,
    file_path=None  # ファイルアップロードをスキップ
)
```

### Stage2Extractor の使い方

`extract_metadata()` メソッドは既に `full_text` を直接受け取る設計:

```python
def extract_metadata(
    self,
    full_text: str,              # 抽出済みテキスト ✅
    file_name: str,
    stage1_result: Dict,
    workspace: str = "personal",
    tier: str = "stage2_extraction"
) -> Dict:
```

---

## まとめ

### 修正内容
1. ✅ テキストのみドキュメント（`classroom_text`）の検出ロジックを追加
2. ✅ `_reprocess_text_only_document()` メソッドを新規作成
3. ✅ Stage 1（Gemini）をテキストベースで実行
4. ✅ Stage 2（Claude）をテキストベースで実行
5. ✅ Embeddingを生成
6. ✅ データベースに結果を保存（stage1_*, stage2_* フィールドを含む）

### 効果
- Google Classroomのテキストのみ投稿も、2段階パイプラインで確実に処理される
- `stage1_doc_type`, `stage1_workspace`, `stage1_confidence` が正しく設定される
- メタデータの抽出とEmbeddingの生成が行われる
- 検索精度が向上する

---

**作成日:** 2025-12-09
**バージョン:** v2.1
