# テーブル分析レポート

**作成日:** 2025-12-14
**目的:** 各テーブルの役割を明確化し、不要なテーブルを特定

---

## 📊 テーブル一覧と分類

### ✅ **稼働中（核心テーブル）**

| テーブル名 | 件数 | 役割 | 重要度 |
|-----------|------|------|--------|
| `source_documents` | 23 | 🏛️ **データ層** - GASからの元データ保管 | ⭐⭐⭐ |
| `process_logs` | 23 | 📊 **処理層** - AIやGASの処理履歴 | ⭐⭐⭐ |
| `search_index` | 543 | 🔍 **検索層** - ベクトル検索用データ | ⭐⭐⭐ |

**結論:** この3つは**絶対に削除してはいけません**。システムの核心です。

---

### 🔄 **稼働中（補助テーブル）**

| テーブル名 | 件数 | 役割 | 重要度 |
|-----------|------|------|--------|
| `document_reprocessing_queue` | 23 | ♻️ ドキュメント再処理キュー | ⭐⭐ |

**詳細:**
- **用途:** ドキュメントを再処理する際のキュー管理
- **カラム:** `status`, `reprocess_reason`, `reprocess_type`, `priority`, `attempt_count`
- **結論:** 稼働中。再処理機能を使っているなら**保持すべき**

---

### 💾 **バックアップ（Legacy）**

| テーブル名 | 件数 | 役割 | 削除可否 |
|-----------|------|------|---------|
| `documents_legacy` | 23 | 旧documentsテーブルのバックアップ | 🟡 後で削除可 |
| `document_chunks_legacy` | 543 | 旧document_chunksテーブルのバックアップ | 🟡 後で削除可 |

**詳細:**
- **用途:** 3層構造マイグレーション前の元データ
- **結論:**
  - ✅ 新システムが安定動作したら削除してOK
  - ⚠️ 今すぐ削除は危険（念のため1〜2週間保持推奨）

---

### ❌ **未使用（削除候補）**

| テーブル名 | 件数 | 役割 | 削除推奨 |
|-----------|------|------|---------|
| `attachments` | 0 | メール添付ファイル管理 | 🔴 削除推奨 |
| `corrections` | 0 | ドキュメント修正管理 | 🔴 削除推奨 |
| `small_chunks` | 0 | 小チャンク（search_indexと重複） | 🔴 削除推奨 |
| `correction_history` | 0 | 修正履歴詳細 | 🔴 削除推奨 |
| `emails` | 0 | メール管理 | 🔴 削除推奨 |
| `hypothetical_questions` | 0 | 仮想質問生成 | 🔴 削除推奨 |

**詳細:**

#### `attachments`
- **想定用途:** メールの添付ファイルを管理
- **外部キー:** `email_id`, `document_id`
- **現状:** データなし、メール機能未使用
- **削除影響:** なし

#### `corrections`
- **想定用途:** ドキュメントのメタデータ修正を記録
- **外部キー:** `document_id`
- **現状:** データなし
- **削除影響:** なし

#### `small_chunks`
- **想定用途:** 小チャンク管理
- **現状:** データなし、`search_index`で代替可能
- **削除影響:** なし

#### `correction_history`
- **想定用途:** 修正履歴の詳細記録
- **外部キー:** `document_id`
- **現状:** データなし
- **削除影響:** なし

#### `emails`
- **想定用途:** Gmail統合
- **カラム:** `gmail_id`, `thread_id`, `subject`, `sender_email`, `body_text`, `embedding`
- **現状:** データなし、Gmail機能未実装
- **削除影響:** なし
- **将来:** Gmail統合したい場合は再作成すればOK

#### `hypothetical_questions`
- **想定用途:** ドキュメントから仮想質問を生成（検索改善用）
- **外部キー:** `document_id`
- **現状:** データなし
- **削除影響:** なし

---

## 🎯 推奨アクション

### 即座に削除してOK（データなし）
```sql
-- これらのテーブルは現在未使用
DROP TABLE IF EXISTS attachments CASCADE;
DROP TABLE IF EXISTS corrections CASCADE;
DROP TABLE IF EXISTS small_chunks CASCADE;
DROP TABLE IF EXISTS correction_history CASCADE;
DROP TABLE IF EXISTS emails CASCADE;
DROP TABLE IF EXISTS hypothetical_questions CASCADE;
```

### 保留（稼働確認後に削除）
```sql
-- 新システムが安定動作したら削除（1〜2週間後）
DROP TABLE IF EXISTS documents_legacy CASCADE;
DROP TABLE IF EXISTS document_chunks_legacy CASCADE;
```

### 保持（削除しない）
- `source_documents` ⭐⭐⭐
- `process_logs` ⭐⭐⭐
- `search_index` ⭐⭐⭐
- `document_reprocessing_queue` ⭐⭐

---

## 📈 削除後のテーブル構成

### 最終的なクリーンな構成

```
【3層構造の核心】
1. source_documents     (データ層)
2. process_logs         (処理層)
3. search_index         (検索層)

【補助システム】
4. document_reprocessing_queue  (再処理管理)

【バックアップ（一時）】
5. documents_legacy           (マイグレーション後削除予定)
6. document_chunks_legacy     (マイグレーション後削除予定)
```

**合計:** 6テーブル（将来的には4テーブルに削減）

---

## ✅ 次のステップ

1. ✅ **未使用テーブルを削除**（6テーブル）
2. ⏳ **新システムの安定稼働を確認**（1〜2週間）
3. ✅ **Legacyテーブルを削除**（2テーブル）
4. 🎉 **最終的に4テーブルの美しいシステムが完成**

---

## 🛡️ 安全性チェック

### 削除前の確認事項

- [x] データ件数が0件であることを確認
- [x] 外部キー参照がないことを確認
- [x] アプリケーションコードで使用されていないことを確認
- [x] バックアップ（Legacyテーブル）が存在することを確認

すべてクリアしています。安全に削除できます。
