# マイグレーション実行手順

## Supabase ダッシュボードでSQLを実行する

1. **Supabase ダッシュボードにアクセス**
   - https://supabase.com/dashboard
   - プロジェクト: `hjkcgulxddtwlljhbocb` を選択

2. **SQL Editor を開く**
   - 左メニューから「SQL Editor」をクリック
   - 「New query」をクリック

3. **SQLファイルの内容をコピー&ペースト**
   - `add_manually_verified_column.sql` の内容を貼り付け
   - 「Run」ボタンをクリック

4. **実行結果を確認**
   - 「Success」メッセージが表示されればOK
   - エラーが出た場合は内容を確認

## 実行が必要なマイグレーション

- [x] `add_manually_verified_column.sql` - 手動検証フラグを追加

## マイグレーション一覧

### add_manually_verified_column.sql
**目的**: 手動で検証・修正された商品を識別するためのフラグを追加

**追加カラム**:
- `manually_verified` (BOOLEAN): 手動検証済みフラグ（デフォルト: false）
- `last_verified_at` (TIMESTAMP): 最終検証日時

**インデックス**:
- `idx_manually_verified`: 検証済みデータの取得を高速化
