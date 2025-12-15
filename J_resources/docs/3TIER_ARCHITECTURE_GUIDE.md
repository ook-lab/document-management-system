# 3層テーブル構造 実装ガイド

**作成日**: 2025-12-14
**目的**: データ層・処理層・検索層を分離し、メンテナンス性・パフォーマンス・拡張性を向上させる

---

## 📋 目次

1. [設計コンセプト](#設計コンセプト)
2. [3層構造の詳細](#3層構造の詳細)
3. [実装手順](#実装手順)
4. [メリット](#メリット)
5. [移行チェックリスト](#移行チェックリスト)

---

## 🎯 設計コンセプト

従来の77列の巨大な`documents`テーブルを、役割ごとに3つのテーブルに分割します。

### Before（従来）
```
documents (77列)
├── ファイル情報
├── Classroom固有フィールド
├── 処理ステータス
├── AIモデル情報
├── エラーログ
└── メタデータ
```

### After（3層構造）
```
1. source_documents（データ層）
   └── GASから送られてきた元データを保管

2. process_logs（処理層）
   └── AIやGASの処理履歴・ログを記録

3. search_index（検索層）
   └── ベクトル検索用の最適化されたデータ
```

---

## 🏗️ 3層構造の詳細

### 1️⃣ データ層：`source_documents`

**役割**: 「原本（倉庫）」
**特徴**: GASから送られてきたデータをそのまま保存

#### 主なカラム
- **ソース情報**: `source_type`, `source_id`, `source_url`, `ingestion_route`
- **ファイル情報**: `file_name`, `file_type`, `file_size_bytes`
- **分類**: `workspace`, `doc_type`
- **コンテンツ**: `full_text`, `summary`
- **Classroom固有**: `classroom_sender`, `classroom_sender_email`, `classroom_sent_at`, `classroom_subject`, `classroom_post_text`, `classroom_type`
- **担当者・組織**: `persons[]`, `organizations[]`
- **メタデータ**: `metadata`, `tags`, `document_date`

#### 使用例
- 将来AIモデルを変更する際の元データ
- データの再処理が必要な場合の参照元
- 監査・トレーサビリティの確保

---

### 2️⃣ 処理層：`process_logs`

**役割**: 「管理ノート（履歴）」
**特徴**: いつ、誰が、どのモデルを使って処理したかを記録

#### 主なカラム
- **関連**: `document_id` (FK to source_documents)
- **ステータス**: `processing_status`, `processing_stage`
- **AIモデル**: `stageA_classifier_model`, `stageB_vision_model`, `stageC_extractor_model`
- **パフォーマンス**: `processing_duration_ms`, `inference_time`
- **エラー**: `error_message`, `retry_count`
- **監査**: `version`, `updated_by`, `processed_at`

#### 使用例
- 「なんか検索がおかしいな？」と思った時のデバッグ
- AIモデルのパフォーマンス分析
- エラー発生時の原因追跡

---

### 3️⃣ 検索層：`search_index`

**役割**: 「ショールーム（検索用）」
**特徴**: 必要な情報だけに絞り込まれた、スリムで高速なテーブル

#### 主なカラム
- **関連**: `document_id` (FK to source_documents)
- **チャンク**: `chunk_index`, `chunk_content`, `chunk_size`
- **種別**: `chunk_type`, `search_weight`
- **ベクトル**: `embedding` (vector 1536次元)
- **メタデータ**: `page_numbers`, `section_title`

#### chunk_type の種類
| chunk_type | 説明 | 重み (search_weight) |
|------------|------|---------------------|
| `title` | タイトル専用 | 2.0 |
| `summary` | サマリー専用 | 1.5 |
| `date` | 日付情報 | 1.3 |
| `tags` | タグ情報 | 1.2 |
| `content_small` | 本文小チャンク | 1.0 |
| `content_large` | 本文大チャンク | 1.0 |
| `synthetic` | 合成チャンク | 1.0 |

---

## 🚀 実装手順

### Step 1: Supabaseでマイグレーション実行

1. Supabaseダッシュボードにログイン
2. SQL Editorを開く
3. 以下のファイルを実行

```bash
database/migration_3tier_structure.sql
```

このSQLは以下を自動で実行します：
- ✅ 3つの新テーブル作成（`source_documents`, `process_logs`, `search_index`）
- ✅ 既存`documents`テーブルからのデータ移行
- ✅ インデックス作成
- ✅ 検索関数の更新（`unified_search_v2`）
- ✅ 互換性ビュー作成（既存アプリ用）

### Step 2: GASコードの更新

1. Google Apps Scriptエディタを開く
2. 既存のコードを以下に置き換え

```bash
gas/ClassroomToSupabase_3tier.gs
```

主な変更点：
- テーブル名: `documents` → `source_documents`
- Classroom固有フィールドを直接カラムとして送信
- `persons`と`organizations`を配列として送信

### Step 3: 検索関数の更新（オプション）

既存のアプリケーションで`unified_search`を使用している場合、`unified_search_v2`に更新してください。

```sql
-- 旧関数
SELECT * FROM unified_search(...)

-- 新関数（3層構造対応）
SELECT * FROM unified_search_v2(...)
```

**互換性**: 既存の`documents`テーブルはビューとして残るため、既存アプリは動作し続けます。

---

## 🎁 メリット

### 1. 検索が爆速になる
- `search_index`には「余計な管理データ」や「巨大なログ」が入っていない
- データベースが身軽になり、検索レスポンスが向上

### 2. エラー対応が楽になる
- `process_logs`を見れば、「どのデータがエラーになったか」が一発で分かる
- データ層を汚さずにエラー管理が可能

### 3. 再利用しやすい
- 「ベクトル化のモデルを最新にしたい！」と思ったとき
- `search_index`のデータだけを捨てて、`source_documents`（原本）から作り直すことが簡単

### 4. スケーラブル
- 各層が独立しているため、将来の拡張が容易
- 例: Gmail、Slack、Notionなど他のデータソースを追加する際も`source_documents`に追加するだけ

---

## ✅ 移行チェックリスト

### 実行前
- [ ] データベースのバックアップを取得
- [ ] Supabase URLとAPIキーを確認
- [ ] GASのスクリプトプロパティを確認

### マイグレーション実行
- [ ] `migration_3tier_structure.sql`をSupabaseで実行
- [ ] エラーがないことを確認
- [ ] 3つの新テーブルが作成されたことを確認
  - [ ] `source_documents`
  - [ ] `process_logs`
  - [ ] `search_index`

### GAS更新
- [ ] `ClassroomToSupabase_3tier.gs`をGASにコピー
- [ ] スクリプトプロパティ確認:
  - [ ] `SUPABASE_URL`
  - [ ] `SUPABASE_KEY`
  - [ ] `DEST_FOLDER_ID`
  - [ ] `WORKSPACE_NAME`
  - [ ] `SERVICE_ACCOUNT_EMAIL`
  - [ ] `PERSONS` (カンマ区切り)
  - [ ] `ORGANIZATIONS` (カンマ区切り)
- [ ] テスト実行（1クラスのみ）
- [ ] データが`source_documents`に入ることを確認

### 検索機能確認
- [ ] `unified_search_v2`が正常に動作することを確認
- [ ] 既存の検索結果と比較

### 移行完了
- [ ] 旧`documents`テーブルのバックアップ
- [ ] 旧`document_chunks`テーブルのバックアップ
- [ ] 運用開始

---

## 🔧 トラブルシューティング

### Q1: マイグレーション実行時にエラーが出る
**A**: 既存の`documents`テーブルに必要なカラムが存在しない可能性があります。エラーメッセージを確認し、該当するカラムをスキップするか、SQLを修正してください。

### Q2: GASから送信できない
**A**: テーブル名が`source_documents`になっているか確認してください。また、Supabase側のRLS（Row Level Security）設定を確認してください。

### Q3: 検索結果が表示されない
**A**: `search_index`テーブルにデータが入っているか確認してください。また、`embedding`カラムにNULLがないかチェックしてください。

---

## 📚 関連ドキュメント

- [マイグレーションSQL](../database/migration_3tier_structure.sql)
- [GASコード（3層構造対応）](../gas/ClassroomToSupabase_3tier.gs)
- [既存スキーマ（v4）](../database/schema_v4_unified.sql)

---

## 🎉 まとめ

3層構造への移行により、以下が実現します：

1. **データの整理**: 元データ、ログ、検索データが明確に分離
2. **パフォーマンス向上**: 検索が高速化
3. **メンテナンス性向上**: エラー追跡とデバッグが容易
4. **拡張性**: 将来の機能追加が簡単

この設計は、データベース設計のベストプラクティスに沿った、プロフェッショナルな実装です。
