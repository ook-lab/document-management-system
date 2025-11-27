# トランザクション管理・ロールバック機能ドキュメント

## 概要

トランザクション管理・ロールバック機能は、ユーザーがReview UIで行うメタデータ修正の**安全性を確保**し、**修正前の状態に戻せる**仕組みです。全ての修正操作は`correction_history`テーブルに記録され、ワンクリックでロールバックできます。

## 目的

- 🔄 **修正履歴の記録**: 誰が、いつ、何を修正したかを完全に記録
- ⏮️ **ロールバック機能**: 修正前の状態に簡単に戻せる
- 🛡️ **データ安全性の確保**: 誤った修正を即座に元に戻せる
- 📊 **修正パターンの分析**: 頻繁に修正されるフィールドを特定

## アーキテクチャ

### データフロー

```
ユーザーがReview UIで修正
    ↓
record_correction()実行
    ↓
┌─────────────────────────────┐
│ Step 1: 現在の状態を取得     │
│  - old_metadata             │
│  - old_doc_type             │
└─────────────────────────────┘
    ↓
┌─────────────────────────────┐
│ Step 2: correction_history  │
│  テーブルに履歴を記録       │
│  - old_metadata (修正前)    │
│  - new_metadata (修正後)    │
│  - corrector_email          │
│  - corrected_at             │
└─────────────────────────────┘
    ↓
┌─────────────────────────────┐
│ Step 3: documents更新       │
│  - metadata = new_metadata  │
│  - latest_correction_id設定 │
└─────────────────────────────┘
    ↓
完了（修正履歴付き）
```

### ロールバックフロー

```
ユーザーがロールバックボタン押下
    ↓
rollback_document()実行
    ↓
┌─────────────────────────────┐
│ Step 1: 最新の修正IDを取得  │
│  documents.latest_correction_id
└─────────────────────────────┘
    ↓
┌─────────────────────────────┐
│ Step 2: 修正履歴から        │
│  old_metadataを取得         │
└─────────────────────────────┘
    ↓
┌─────────────────────────────┐
│ Step 3: documentsを更新     │
│  - metadata = old_metadata  │
│  - latest_correction_id = NULL
└─────────────────────────────┘
    ↓
完了（修正前の状態に復元）
```

## データベーススキーマ

### 1. `correction_history` テーブル（新規）

修正履歴を記録するテーブル

```sql
CREATE TABLE correction_history (
    id BIGSERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    old_metadata JSONB NOT NULL,      -- 修正前のメタデータ
    new_metadata JSONB NOT NULL,      -- 修正後のメタデータ
    corrector_email TEXT,             -- 修正者のメールアドレス
    corrected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    correction_type TEXT DEFAULT 'manual',  -- 'manual' or 'automatic'
    notes TEXT                        -- 修正に関するメモ
);
```

**インデックス**:
- `idx_correction_history_document_id`: document_id での高速検索
- `idx_correction_history_corrector`: 修正者別の検索
- `idx_correction_history_corrected_at`: 日付範囲での検索

### 2. `documents` テーブルの拡張

最新の修正履歴へのリンクを追加

```sql
ALTER TABLE documents
ADD COLUMN latest_correction_id BIGINT REFERENCES correction_history(id);
```

**インデックス**:
- `idx_documents_latest_correction_id`: ロールバック可能なドキュメントの高速検索

## 実装されたファイル

### 1. `database/schema_updates/v7_add_correction_history.sql` (新規)

**目的**: correction_historyテーブルとヘルパー関数を作成

**主要な内容**:

#### テーブル作成
```sql
CREATE TABLE IF NOT EXISTS correction_history (
    id BIGSERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    old_metadata JSONB NOT NULL,
    new_metadata JSONB NOT NULL,
    corrector_email TEXT,
    corrected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    correction_type TEXT DEFAULT 'manual',
    notes TEXT
);
```

#### ロールバック用PL/pgSQL関数
```sql
CREATE OR REPLACE FUNCTION rollback_document_metadata(p_document_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_latest_correction_id BIGINT;
    v_old_metadata JSONB;
BEGIN
    -- 最新の修正履歴IDを取得
    SELECT latest_correction_id INTO v_latest_correction_id
    FROM documents
    WHERE id = p_document_id;

    -- 修正前のメタデータを取得
    SELECT old_metadata INTO v_old_metadata
    FROM correction_history
    WHERE id = v_latest_correction_id;

    -- documentsテーブルを更新（ロールバック）
    UPDATE documents
    SET metadata = v_old_metadata,
        latest_correction_id = NULL
    WHERE id = p_document_id;

    RETURN v_old_metadata;
END;
$$ LANGUAGE plpgsql;
```

### 2. `core/database/client.py` (修正, +180行)

**追加メソッド**:

#### `record_correction()` - 修正履歴の記録

```python
def record_correction(
    self,
    doc_id: str,
    new_metadata: Dict[str, Any],
    new_doc_type: Optional[str] = None,
    corrector_email: Optional[str] = None,
    notes: Optional[str] = None
) -> bool:
    """
    ドキュメントのメタデータを更新し、修正履歴を記録

    処理フロー:
    1. 現在のドキュメントを取得（old_metadata）
    2. correction_historyに履歴を記録
    3. documentsテーブルを更新（latest_correction_id設定）
    """
```

**使用例**:
```python
from core.database.client import DatabaseClient

db = DatabaseClient()

success = db.record_correction(
    doc_id="123e4567-e89b-12d3-a456-426614174000",
    new_metadata={"school_name": "〇〇小学校", "grade": "5年生"},
    new_doc_type="timetable",
    corrector_email="user@example.com",
    notes="学年情報を修正"
)
```

#### `rollback_document()` - ロールバック実行

```python
def rollback_document(self, doc_id: str) -> bool:
    """
    ドキュメントのメタデータを最新の修正前の状態にロールバック

    処理フロー:
    1. 現在のドキュメントからlatest_correction_idを取得
    2. correction_historyからold_metadataを取得
    3. documentsテーブルをold_metadataで更新
    4. latest_correction_idをNULLにクリア
    """
```

**使用例**:
```python
success = db.rollback_document(doc_id="123e4567-e89b-12d3-a456-426614174000")

if success:
    print("ロールバック成功！")
```

#### `get_correction_history()` - 修正履歴の取得

```python
def get_correction_history(
    self,
    doc_id: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    ドキュメントの修正履歴を取得（新しい順）
    """
```

**使用例**:
```python
history = db.get_correction_history(doc_id="123e4567-...", limit=5)

for correction in history:
    print(f"修正日時: {correction['corrected_at']}")
    print(f"修正前: {correction['old_metadata']}")
    print(f"修正後: {correction['new_metadata']}")
```

### 3. `ui/review_ui.py` (修正, +50行)

**修正内容**:

#### 保存ボタンのロジック変更

**変更前** (修正履歴なし):
```python
success = db_client.update_document_metadata(
    doc_id=doc_id,
    new_metadata=edited_metadata,
    new_doc_type=doc_type
)
```

**変更後** (修正履歴を記録):
```python
success = db_client.record_correction(
    doc_id=doc_id,
    new_metadata=edited_metadata,
    new_doc_type=doc_type,
    corrector_email=None,  # 将来的に認証情報から取得
    notes="Review UIからの手動修正"
)
```

#### 修正履歴・ロールバック機能の追加

```python
# 修正履歴とロールバック機能（Phase 2）
latest_correction_id = selected_doc.get('latest_correction_id')
if latest_correction_id:
    with st.expander("📜 修正履歴とロールバック", expanded=False):
        correction_history = db_client.get_correction_history(doc_id, limit=5)

        if correction_history:
            st.markdown(f"**修正回数**: {len(correction_history)}回")

            # ロールバックボタン
            if st.button("⏮️ ロールバック（元に戻す）"):
                rollback_success = db_client.rollback_document(doc_id)

                if rollback_success:
                    st.success("✅ ロールバックに成功しました！")
                    st.rerun()
```

**UI機能**:
- 📜 修正履歴の表示（最新5件）
- 📊 修正前後の差分表示（JSON形式）
- ⏮️ ワンクリックロールバックボタン
- 👤 修正者情報の表示

## セットアップ手順

### 1. データベースマイグレーション

Supabase SQL Editorで以下を実行:

```bash
# ファイルを開く
cat database/schema_updates/v7_add_correction_history.sql
```

Supabase SQL Editorにコピー&ペーストして実行。

**確認クエリ**:
```sql
-- テーブル作成確認
SELECT table_name
FROM information_schema.tables
WHERE table_name IN ('correction_history', 'documents');

-- カラム確認
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'correction_history';

-- 関数確認
SELECT routine_name
FROM information_schema.routines
WHERE routine_name = 'rollback_document_metadata';
```

### 2. コードデプロイ

```bash
git pull origin main
```

### 3. 動作確認

#### Review UIで修正を実行

1. Review UIを起動:
   ```bash
   streamlit run ui/review_ui.py
   ```

2. ドキュメントを選択して編集

3. 「💾 保存」ボタンを押下

**期待される動作**:
```
✅ 保存に成功しました！修正履歴が記録されました。
```

**ログ出力**:
```
✅ 修正履歴を記録: correction_id=1
✅ ドキュメント更新成功: doc_id=123e4567-...
```

#### ロールバックを実行

1. 同じドキュメントで「📜 修正履歴とロールバック」を展開

2. 「⏮️ ロールバック（元に戻す）」ボタンを押下

**期待される動作**:
```
✅ ロールバックに成功しました！前の状態に戻りました。
```

**ログ出力**:
```
✅ ロールバック成功: doc_id=123e4567-..., correction_id=1
```

## 統計とモニタリング

### 修正履歴の統計

#### 修正回数が多いドキュメント

```sql
-- ドキュメント別の修正回数
SELECT
    d.id,
    d.file_name,
    d.doc_type,
    COUNT(ch.id) as correction_count,
    MAX(ch.corrected_at) as last_corrected_at
FROM documents d
LEFT JOIN correction_history ch ON d.id = ch.document_id
GROUP BY d.id, d.file_name, d.doc_type
HAVING COUNT(ch.id) > 0
ORDER BY correction_count DESC
LIMIT 20;
```

**用途**: どのドキュメントが頻繁に修正されているかを特定

#### 修正者別の統計

```sql
-- 修正者別の統計
SELECT
    corrector_email,
    COUNT(*) as correction_count,
    MIN(corrected_at) as first_correction,
    MAX(corrected_at) as last_correction
FROM correction_history
WHERE corrector_email IS NOT NULL
GROUP BY corrector_email
ORDER BY correction_count DESC;
```

**用途**: 誰が最も多く修正しているかを把握

#### doc_type別の修正パターン

```sql
-- doc_type別の修正頻度
SELECT
    d.doc_type,
    COUNT(ch.id) as correction_count,
    ROUND(AVG(COUNT(ch.id)) OVER (PARTITION BY d.doc_type), 2) as avg_corrections_per_doc
FROM documents d
LEFT JOIN correction_history ch ON d.id = ch.document_id
GROUP BY d.doc_type, d.id
HAVING COUNT(ch.id) > 0
ORDER BY correction_count DESC;
```

**用途**: どのdoc_typeが修正が多いか（AI精度が低い可能性）

### ロールバック可能なドキュメント

```sql
-- ロールバック可能なドキュメント一覧
SELECT
    d.id,
    d.file_name,
    d.doc_type,
    d.latest_correction_id,
    ch.corrected_at as can_rollback_to
FROM documents d
JOIN correction_history ch ON d.latest_correction_id = ch.id
ORDER BY ch.corrected_at DESC
LIMIT 10;
```

## 使用例

### ケース1: 誤って修正してしまった場合

**シナリオ**: ユーザーが「学年」を「5年生」→「6年生」に誤って変更してしまった

**対処**:
1. Review UIで該当ドキュメントを開く
2. 「📜 修正履歴とロールバック」を展開
3. 「⏮️ ロールバック（元に戻す）」をクリック
4. 即座に「5年生」に戻る

### ケース2: 修正パターンの分析

**シナリオ**: どのフィールドがよく修正されているかを知りたい

**SQL**:
```sql
-- 修正前後の差分を分析（簡易版）
SELECT
    document_id,
    old_metadata->'grade' as old_grade,
    new_metadata->'grade' as new_grade,
    corrected_at
FROM correction_history
WHERE old_metadata->'grade' IS DISTINCT FROM new_metadata->'grade'
ORDER BY corrected_at DESC
LIMIT 20;
```

**結果**: 「grade」フィールドが頻繁に修正されている → AI promptを改善

### ケース3: 自動修正ツールの開発

**シナリオ**: 特定のパターンの修正を自動化したい

**実装**:
```python
from core.database.client import DatabaseClient

db = DatabaseClient()

# 全ドキュメントをチェック
documents = db.get_documents_for_review(limit=1000)

for doc in documents:
    metadata = doc['metadata']

    # 自動修正ロジック（例: gradeフォーマットの統一）
    if 'grade' in metadata:
        old_grade = metadata['grade']
        new_grade = normalize_grade_format(old_grade)  # 独自関数

        if old_grade != new_grade:
            metadata['grade'] = new_grade

            # 修正履歴を記録
            db.record_correction(
                doc_id=doc['id'],
                new_metadata=metadata,
                corrector_email="system@auto.com",
                notes=f"自動修正: {old_grade} → {new_grade}"
            )
```

## ベストプラクティス

### 1. 修正前のレビュー

大きな変更を行う前に:
- 修正内容を「🔍 変更を確認」ボタンで確認
- JSON差分を目視チェック
- 問題があればすぐにロールバック可能

### 2. 修正理由の記録

将来的に`notes`フィールドを活用:
```python
db.record_correction(
    doc_id=doc_id,
    new_metadata=metadata,
    notes="OCRミスによる「5年」→「5年生」への修正"
)
```

### 3. 定期的な履歴クリーンアップ

古い修正履歴の削除（オプション）:
```sql
-- 1年以上前の修正履歴を削除
DELETE FROM correction_history
WHERE corrected_at < NOW() - INTERVAL '1 year'
AND document_id NOT IN (
    SELECT document_id FROM documents WHERE latest_correction_id IS NOT NULL
);
```

### 4. バックアップとアーカイブ

重要なドキュメントの修正履歴は定期的にエクスポート:
```sql
-- 重要ドキュメントの修正履歴をエクスポート
COPY (
    SELECT *
    FROM correction_history
    WHERE document_id IN (SELECT id FROM documents WHERE doc_type = 'contract')
) TO '/tmp/correction_history_backup.csv' CSV HEADER;
```

## トラブルシューティング

### 問題: ロールバックボタンが表示されない

**原因**: `latest_correction_id` が NULL（修正履歴がない）

**確認**:
```sql
SELECT latest_correction_id
FROM documents
WHERE id = '123e4567-...';
```

**解決策**: 少なくとも1回保存してから確認

### 問題: ロールバックが失敗する

**原因**: 修正履歴レコードが削除された、またはデータ不整合

**確認**:
```sql
-- 整合性チェック
SELECT
    d.id,
    d.latest_correction_id,
    ch.id as correction_id
FROM documents d
LEFT JOIN correction_history ch ON d.latest_correction_id = ch.id
WHERE d.latest_correction_id IS NOT NULL
AND ch.id IS NULL;
```

**解決策**:
```sql
-- latest_correction_idをクリア
UPDATE documents
SET latest_correction_id = NULL
WHERE id = '123e4567-...';
```

### 問題: 修正履歴が記録されない

**原因**: `record_correction()` ではなく `update_document_metadata()` を使用している

**確認**:
- `ui/review_ui.py` のコードを確認
- `db_client.record_correction(...)` が呼ばれているか

**解決策**: 最新のコードに更新

### 問題: パフォーマンスが低下

**原因**: `correction_history` テーブルが肥大化

**確認**:
```sql
-- テーブルサイズ確認
SELECT
    pg_size_pretty(pg_total_relation_size('correction_history')) as total_size,
    COUNT(*) as record_count
FROM correction_history;
```

**解決策**:
```sql
-- 古い履歴を削除
DELETE FROM correction_history
WHERE corrected_at < NOW() - INTERVAL '1 year';

-- VACUUM実行
VACUUM ANALYZE correction_history;
```

## まとめ

トランザクション管理・ロールバック機能により、以下が実現されました:

✅ **修正履歴の完全記録**: 誰が、いつ、何を修正したかを記録
✅ **ワンクリックロールバック**: 修正前の状態に即座に復元
✅ **データ安全性の確保**: 誤った修正を元に戻せる安心感
✅ **修正パターンの可視化**: AIの改善ポイントを特定
✅ **監査証跡**: コンプライアンス要件に対応

**実装ファイル**:
- `database/schema_updates/v7_add_correction_history.sql` (新規)
- `core/database/client.py` (+180行)
- `ui/review_ui.py` (+50行)

**効果**:
- ユーザーの安心感向上（いつでも元に戻せる）
- データ品質の継続的改善（修正パターン分析）
- 運用の透明性向上（誰が何を修正したか記録）
- トラブル対応の迅速化（問題のあるドキュメントを即座にロールバック）
