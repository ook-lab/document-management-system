# 重複検知機能（content_hash）ドキュメント

## 概要

重複検知機能は、PDFファイルの内容ハッシュ値（SHA256）に基づき、既にデータベースに存在するファイルはAI処理をスキップする機能です。これにより、**コスト削減**と**処理効率化**を実現します。

## 目的

- 💰 **AI処理コストの削減**: 同一ファイルを複数回処理しない
- ⚡ **処理時間の短縮**: 重複ファイルは即座にスキップ
- 🛡️ **データ整合性の確保**: 同一内容のファイルは1回のみ処理

## アーキテクチャ

### 処理フロー

```
新規ファイル検出
    ↓
ファイルダウンロード（一時）
    ↓
SHA256ハッシュ計算
    ↓
データベースで重複チェック
    ↓
┌─────────┴─────────┐
│                   │
重複あり          重複なし
│                   │
↓                   ↓
AI処理スキップ    AI処理実行
Archive移動       ↓
                  Supabase保存
                  ↓
                  Archive移動
```

### 技術仕様

#### 1. ハッシュアルゴリズム: SHA256

**選定理由**:
- ✅ 衝突耐性が高い（実質的に衝突なし）
- ✅ 標準ライブラリで利用可能（`hashlib`）
- ✅ パフォーマンスと安全性のバランスが良い

**実装**:
```python
import hashlib

def calculate_content_hash(pdf_path: str) -> str:
    sha256_hash = hashlib.sha256()

    with open(pdf_path, 'rb') as f:
        # 64KBずつ読み込み（メモリ効率的）
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()
```

#### 2. データベーススキーマ

**documentsテーブル**:
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    content_hash TEXT,  -- SHA256ハッシュ値（64文字）
    ...
);

-- パフォーマンス向上のためのインデックス
CREATE INDEX idx_documents_content_hash
ON documents(content_hash)
WHERE content_hash IS NOT NULL;
```

#### 3. 重複チェックロジック

**DatabaseClient.check_duplicate_hash()**:
```python
def check_duplicate_hash(self, content_hash: str) -> bool:
    response = (
        self.client.table('source_documents')
        .select('id, file_name, content_hash')
        .eq('content_hash', content_hash)
        .limit(1)
        .execute()
    )

    return bool(response.data and len(response.data) > 0)
```

## 実装されたファイル

### 1. `core/processors/pdf.py`

**追加関数**: `calculate_content_hash(pdf_path: str) -> str`

```python
def calculate_content_hash(pdf_path: str) -> str:
    """
    PDFファイルの内容全体からSHA256ハッシュを計算

    Args:
        pdf_path: PDFファイルのローカルパス

    Returns:
        SHA256ハッシュ値（16進数文字列、64文字）

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        IOError: ファイル読み込みエラー
    """
```

**特徴**:
- ✅ 大きなファイルでもメモリ効率的（64KBずつ読み込み）
- ✅ バイナリ全体をハッシュ化（メタデータ変更も検知）

### 2. `core/database/client.py`

**追加メソッド**: `check_duplicate_hash(content_hash: str) -> bool`

```python
def check_duplicate_hash(self, content_hash: str) -> bool:
    """
    content_hashが既にデータベースに存在するかチェック

    Args:
        content_hash: SHA256ハッシュ値

    Returns:
        True: 重複あり（既に存在する）
        False: 重複なし（新規）
    """
```

**動作**:
- データベースから`content_hash`で検索
- インデックスを利用した高速検索
- 既存ファイル名をログに記録

### 3. `scripts/inbox_monitor.py`

**追加メソッド**: `check_duplicate_by_hash(file_meta: Dict) -> Optional[str]`

```python
def check_duplicate_by_hash(self, file_meta: Dict[str, Any]) -> Optional[str]:
    """
    ファイルのcontent_hashを計算し、重複をチェック

    Returns:
        content_hash: 重複していない場合はハッシュ値を返す
        None: 重複している場合はNoneを返す
    """
```

**統合処理**:
```python
# 重複チェック
content_hash = self.check_duplicate_by_hash(file_meta)

if content_hash is None:
    # 重複ファイル：AI処理をスキップ
    stats['duplicates_skipped'] += 1
    logger.info(f"💰 コスト削減: {file_name} のAI処理をスキップしました")

    # Archiveに移動
    self.move_to_archive(file_id, file_name)
    continue

# 新規ファイル：AI処理実行
success = await self.process_file(file_meta)
```

### 4. `database/schema_updates/v5_add_hash_index.sql`

**目的**: `content_hash`カラムにインデックスを追加

```sql
CREATE INDEX IF NOT EXISTS idx_documents_content_hash
ON documents(content_hash)
WHERE content_hash IS NOT NULL;
```

**効果**:
- 重複チェックのクエリが高速化
- O(n) → O(log n) の検索速度

## セットアップ手順

### 1. データベースマイグレーション

Supabase SQL Editorで以下を実行:

```bash
# ファイルを開く
cat database/schema_updates/v5_add_hash_index.sql
```

実行後、確認クエリ:
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'documents'
AND indexname = 'idx_documents_content_hash';
```

### 2. コードデプロイ

```bash
git pull origin main
```

### 3. 動作確認

#### ローカルテスト

```bash
# テストPDFファイルを2回アップロード（同一ファイル）
# InBoxフォルダに配置

# inbox_monitorを実行
python scripts/inbox_monitor.py
```

#### 期待される出力

**1回目の処理**:
```
🆕 1 件の新規ファイルを検出:
  - test.pdf
🔍 重複チェック: test.pdf をダウンロード中...
   計算されたハッシュ: 5d41402abc4b2a76...
✅ 重複なし: test.pdf は新規ファイルです
⚙️  ファイル処理開始: test.pdf
✅ ファイル処理成功: test.pdf
```

**2回目の処理（同一ファイル）**:
```
🆕 1 件の新規ファイルを検出:
  - test.pdf (再アップロード)
🔍 重複チェック: test.pdf をダウンロード中...
   計算されたハッシュ: 5d41402abc4b2a76...
⚠️  重複検知: content_hash=5d41402abc4b2a76... は既に存在します
   既存ファイル: test.pdf
⚠️  重複検知: test.pdf は既に処理済みです（AI処理スキップ）
💰 コスト削減: test.pdf のAI処理をスキップしました
```

**サマリー**:
```
📊 InBox自動監視システム 完了サマリー
新規ファイル検出数: 1
重複によりスキップ: 1 件 💰
AI処理成功数: 0
AI処理失敗数: 0
アーカイブ成功数: 1
```

## パフォーマンス

### ハッシュ計算

| ファイルサイズ | 計算時間 (目安) |
|--------------|----------------|
| 1 MB | ~0.01秒 |
| 10 MB | ~0.1秒 |
| 100 MB | ~1秒 |

### 重複チェック

- **インデックスあり**: O(log n) - 数ミリ秒
- **インデックスなし**: O(n) - データ量に比例

### コスト削減効果

**AI処理コスト（目安）**:
- Gemini (Stage 1): ~$0.001 / ファイル
- Claude (Stage 2): ~$0.01 / ファイル
- **合計**: ~$0.011 / ファイル

**重複ファイルが10%の場合**:
- 1,000ファイル処理時
- 100ファイルがスキップ
- **削減コスト**: $1.1

## エラーハンドリング

### ハッシュ計算失敗

```python
except Exception as e:
    logger.error(f"❌ 重複チェックエラー: {file_name} - {e}")
    # エラー時は処理を続行（安全側に倒す）
    return "error_skip_hash_check"
```

**動作**:
- エラー時はAI処理を実行
- 誤ってスキップするよりも、重複処理の方が安全

### データベース接続エラー

```python
except Exception as e:
    print(f"Error checking duplicate hash: {e}")
    # エラー時は重複なしとして扱う
    return False
```

## モニタリング

### ログ出力

重複検知時のログ:
```
⚠️  重複検知: content_hash=5d41402abc4b2a76... は既に存在します
   既存ファイル: test.pdf
💰 コスト削減: test.pdf のAI処理をスキップしました
```

### 統計情報

毎回の実行後にサマリーを出力:
```
重複によりスキップ: 5 件 💰
```

### クエリでの確認

```sql
-- 重複ファイルの統計
SELECT
    content_hash,
    COUNT(*) as duplicate_count,
    ARRAY_AGG(file_name) as file_names
FROM documents
WHERE content_hash IS NOT NULL
GROUP BY content_hash
HAVING COUNT(*) > 1;
```

## トラブルシューティング

### 問題: 同一ファイルが重複して処理される

**原因**: インデックスが作成されていない

**解決策**:
```sql
-- インデックス確認
SELECT * FROM pg_indexes
WHERE tablename = 'documents';

-- インデックス再作成
DROP INDEX IF EXISTS idx_documents_content_hash;
CREATE INDEX idx_documents_content_hash
ON documents(content_hash)
WHERE content_hash IS NOT NULL;
```

### 問題: content_hashがNULLのまま

**原因**: 古いデータが処理された時にハッシュが計算されていない

**解決策**:
- 既存データは再処理不要（将来のファイルのみが対象）
- 必要であれば手動でハッシュを計算・更新

```python
# バックフィルスクリプト（必要な場合）
for doc in old_documents:
    file_path = download_file(doc['source_id'])
    content_hash = calculate_content_hash(file_path)
    update_document(doc['id'], {'content_hash': content_hash})
```

### 問題: ファイル名が異なる同一ファイルが別々に処理される

**回答**: これは**正常な動作**です

**理由**:
- `content_hash`は**内容**を比較
- ファイル名やメタデータが異なっても、内容が同じなら重複と判定
- これが重複検知の目的

**例**:
```
report_2024.pdf → ハッシュ: abc123...
report_final.pdf → 内容同じ → ハッシュ: abc123... → 重複！
```

## ベストプラクティス

### 1. インデックスの定期メンテナンス

```sql
-- 統計情報の更新
ANALYZE documents;

-- インデックスの再構築（必要な場合）
REINDEX INDEX idx_documents_content_hash;
```

### 2. content_hashの活用

重複検知以外の用途:
- データ整合性チェック
- ファイル変更検知
- バックアップ検証

### 3. ログ監視

重複率が異常に高い場合:
- システムエラーの可能性
- ユーザー操作ミスの可能性
- 要調査

## まとめ

重複検知機能により、以下が実現されました:

✅ **AI処理コストの削減**: 同一ファイルは1回のみ処理
✅ **処理時間の短縮**: 重複ファイルは即座にスキップ
✅ **データ整合性**: SHA256による確実な重複検知
✅ **パフォーマンス**: インデックスによる高速検索
✅ **監視**: 詳細なログと統計情報

**実装ファイル**:
- `core/processors/pdf.py` (+31行)
- `core/database/client.py` (+35行)
- `scripts/inbox_monitor.py` (+48行)
- `database/schema_updates/v5_add_hash_index.sql` (新規)

**効果**:
- 重複ファイル10%の場合、コスト10%削減
- 処理時間も同様に短縮
- データベースの整合性向上
