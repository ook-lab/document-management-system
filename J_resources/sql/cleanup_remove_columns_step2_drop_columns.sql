-- =========================================
-- 不要なカラムを削除（断捨離）
-- 実行場所: Supabase SQL Editor
-- 目的: metadata JSONB カラムで管理するため、トップレベルカラムを削除
--
-- 重要: このスクリプトは、以下の前提条件が満たされている場合のみ実行してください：
-- 1. Python コードの修正が完了している
-- 2. step1_update_search_function.sql が実行済みである
-- 3. アプリケーションの動作確認が完了している
-- =========================================

BEGIN;

-- バックアップの作成を推奨（本番環境で実行する前に）
-- pg_dump または Supabase の Backup 機能を使用してバックアップを取得してください

-- =========================================
-- ステップ1: カラムの削除
-- =========================================

-- 日付関連（metadata 内で管理）
ALTER TABLE documents DROP COLUMN IF EXISTS year;
ALTER TABLE documents DROP COLUMN IF EXISTS month;

-- 金額（metadata 内で管理）
ALTER TABLE documents DROP COLUMN IF EXISTS amount;

-- 学校関連（metadata 内で管理）
ALTER TABLE documents DROP COLUMN IF EXISTS grade_level;
ALTER TABLE documents DROP COLUMN IF EXISTS school_name;

-- ファイル情報（不要）
ALTER TABLE documents DROP COLUMN IF EXISTS file_size_bytes;

-- イベント日付・表データ（metadata 内で管理）
ALTER TABLE documents DROP COLUMN IF EXISTS event_dates;
ALTER TABLE documents DROP COLUMN IF EXISTS extracted_tables;

-- タイムスタンプ（不要）
ALTER TABLE documents DROP COLUMN IF EXISTS last_edited_at;

-- Stage1 関連（不要）
ALTER TABLE documents DROP COLUMN IF EXISTS stage1_confidence;
ALTER TABLE documents DROP COLUMN IF EXISTS stage1_needs_processing;

-- レビュー状態（review_status カラムで管理）
ALTER TABLE documents DROP COLUMN IF EXISTS reviewed;
ALTER TABLE documents DROP COLUMN IF EXISTS is_reviewed;

COMMIT;

-- =========================================
-- 実行後の確認
-- =========================================
-- カラムが削除されたことを確認
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'documents'
-- ORDER BY ordinal_position;

-- =========================================
-- ロールバック方法（念のため）
-- =========================================
-- カラムを削除した後は、データを復元できません。
-- バックアップから復元する必要があります。
-- pg_restore または Supabase の Restore 機能を使用してください。
