# チャンク分割への移行ガイド

## 概要

このガイドでは、既存の「1文書1embedding」システムから「1文書複数チャンク（複数embedding）」システムへの移行手順を説明します。

## 移行の目的

### 解決する問題

従来のシステムでは、長いPDFファイル（例：10ページ以上）を1つのembeddingにまとめていたため、以下の問題がありました：

1. **検索精度の低下**: 長い文書の中の具体的な記述が埋もれてしまう
2. **後半の情報が検索されない**: embeddingが文書の前半に偏る、またはテキストが切り詰められている
3. **お目当ての具体的な記述が出てこない**: 「12月4日の予定」など、文書内の特定の日付や内容が検索にヒットしない

### 解決策

**チャンク分割**: 1つの文書を500-1000文字程度の小さなチャンクに分割し、各チャンクに対して個別のembeddingを生成することで、文書の全体をカバーし、検索精度を大幅に向上させます。

## アーキテクチャ変更

### 変更前（1文書1embedding）

```
documents テーブル
├── id (UUID)
├── file_name
├── full_text (全ページのテキスト)
├── embedding (1536次元ベクトル) ← 文書全体で1つのみ
└── metadata (JSONB)
```

**問題点**:
- 長いPDFの後半部分が検索でヒットしない
- 文書内の具体的な記述（例：特定の日付の予定）が埋もれる

### 変更後（1文書複数チャンク）

```
documents テーブル
├── id (UUID)
├── file_name
├── full_text
├── metadata (JSONB)
├── chunk_count (INTEGER) ← 新規追加
└── chunking_strategy (VARCHAR) ← 新規追加

document_chunks テーブル（新規）
├── id (UUID)
├── document_id (FK → documents.id)
├── chunk_index (INTEGER)
├── chunk_text (TEXT) ← チャンクごとのテキスト
├── chunk_size (INTEGER)
├── embedding (1536次元ベクトル) ← チャンクごとに1つ
├── page_numbers (INTEGER[])
└── section_title (TEXT)
```

**改善点**:
- ✅ 長いPDFの後半部分も確実に検索できる
- ✅ 文書内の具体的な記述が検索にヒットする
- ✅ ページごとの情報も保持される

## 移行手順

### ステップ1: データベーススキーマの更新

Supabase SQL Editorで以下のSQLを実行してください：

```bash
# SQLファイルの内容を確認
cat database/schema_updates/add_document_chunks.sql
```

Supabase SQL Editorに上記SQLをコピー&ペーストして実行します。

**実行内容**:
- `document_chunks` テーブルを作成
- インデックスを作成（高速検索のため）
- `match_document_chunks` 関数を作成（ベクトル検索用）
- `documents` テーブルに `chunk_count`, `chunking_strategy` カラムを追加

### ステップ2: 既存データの移行

既存の文書データをチャンク形式に移行します：

```bash
# 移行スクリプトを実行
python scripts/migrate_to_chunks.py
```

**実行内容**:
1. 既存の `documents` テーブルから `full_text` を読み込み
2. 各文書を800文字ずつのチャンクに分割（100文字のオーバーラップあり）
3. 各チャンクのembeddingを生成
4. `document_chunks` テーブルに保存
5. `documents.chunk_count` を更新

**処理時間の目安**:
- 100文書: 約10-15分
- 1000文書: 約2-3時間

**注意事項**:
- 既にチャンクが存在する文書はスキップされます（`skip_existing=True`）
- embedding生成にはGoogle AI API（text-embedding-004）を使用します

### ステップ3: 検索動作の確認

移行後、検索が正しく動作するか確認します：

```bash
# アプリケーションを起動
python app.py
```

ブラウザで `http://localhost:8080` にアクセスし、以下のクエリでテストしてください：

**テストクエリ例**:
- 「12月4日の予定は？」
- 「学年通信の後半に書かれている内容は？」
- 「ますみ 25ー06.pdf の3ページ目の内容は？」

**期待される動作**:
- 文書の後半部分の情報も正しく検索される
- マッチしたチャンクのテキストが結果に含まれる
- 検索精度が向上する

## チャンク分割の設定

### デフォルト設定

`core/utils/chunking.py` の `TextChunker` クラスで以下のパラメータを設定できます：

```python
TextChunker(
    chunk_size=800,        # 目標チャンクサイズ（文字数）
    chunk_overlap=100,     # チャンク間のオーバーラップ（文字数）
    min_chunk_size=100     # 最小チャンクサイズ
)
```

### チャンク分割の仕組み

1. **セクション分割**: ページ区切り、見出し、段落で大きく分割
2. **文単位分割**: 各セクションを句読点で文単位に分割
3. **チャンクサイズ調整**: 文を結合してチャンクサイズに収める
4. **オーバーラップ**: 隣接するチャンク間で100文字のオーバーラップを設ける（文脈の連続性を確保）

## トラブルシューティング

### Q1: 移行スクリプトでエラーが発生する

**原因**: API制限、ネットワークエラー、データベース接続エラー

**対処法**:
```bash
# エラーログを確認
python scripts/migrate_to_chunks.py 2>&1 | tee migration.log

# 特定の文書から再開する場合は、スクリプトを編集して skip_existing=True を確認
```

### Q2: 検索結果に matched_chunk_text が表示されない

**原因**: チャンク検索に失敗している、または `match_document_chunks` 関数が存在しない

**対処法**:
```sql
-- Supabase SQL Editorで関数の存在を確認
SELECT proname FROM pg_proc WHERE proname = 'match_document_chunks';

-- 関数が存在しない場合は、ステップ1のSQLを再実行
```

### Q3: 移行後も検索精度が改善しない

**原因**:
- チャンクサイズが大きすぎる
- embedding生成に失敗している

**対処法**:
```bash
# チャンク統計を確認
python -c "
from core.database.client import DatabaseClient
db = DatabaseClient()
docs = db.get_documents_for_review(limit=10)
for doc in docs:
    print(f'{doc[\"file_name\"]}: {doc.get(\"chunk_count\", 0)} チャンク')
"

# チャンクサイズを調整（chunking.py を編集）
# chunk_size=800 → chunk_size=500 に変更して再移行
```

## パフォーマンスへの影響

### データベースサイズ

- **変更前**: 1000文書 → 約50MB（embedding含む）
- **変更後**: 1000文書 × 平均10チャンク → 約500MB（embedding含む）

**結論**: データベースサイズは約10倍に増加しますが、検索精度が大幅に向上します。

### 検索速度

- **チャンク検索**: 約50-100ms（インデックスあり）
- **文書マージ**: 約10-20ms
- **合計**: 約60-120ms（従来とほぼ同等）

**結論**: ivfflatインデックスにより、検索速度への影響は最小限です。

## 今後の拡張

チャンク分割システムをさらに改善するためのアイデア：

1. **意味的チャンク分割**: 文のembeddingを使って意味的な区切りでチャンク分割
2. **動的チャンクサイズ**: 文書の種類に応じてチャンクサイズを自動調整
3. **ハイライト表示**: マッチしたチャンクのテキストをUIでハイライト表示
4. **チャンク再ランキング**: 複数のチャンクが同一文書からマッチした場合、スコアを統合

## まとめ

チャンク分割への移行により、以下のメリットが得られます：

✅ **長いPDFの後半部分も確実に検索できる**
✅ **文書内の具体的な記述が検索にヒットする**
✅ **検索精度が大幅に向上する**

移行手順に従って、システムをアップグレードしてください。
