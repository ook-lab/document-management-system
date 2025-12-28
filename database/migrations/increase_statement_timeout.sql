-- ====================================================================
-- Statement Timeout延長（検索クエリのタイムアウト防止）
-- ====================================================================
-- 目的: hybrid_search関数のタイムアウトを防ぐ
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-28
-- ====================================================================

BEGIN;

-- データベース全体のデフォルトタイムアウトを30秒に延長
ALTER DATABASE postgres SET statement_timeout = '30s';

-- 現在のセッションにも即座に適用
SET statement_timeout = '30s';

-- 確認
DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ Statement Timeoutを30秒に延長しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '変更内容:';
    RAISE NOTICE '  - デフォルト: 10秒 → 30秒';
    RAISE NOTICE '  - 対象: hybrid_search など重いクエリ';
    RAISE NOTICE '';
    RAISE NOTICE '効果:';
    RAISE NOTICE '  - 検索タイムアウトエラーを防止';
    RAISE NOTICE '  - 大量データの検索に対応';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  1. Supabaseを再起動（設定反映）';
    RAISE NOTICE '  2. 検索アプリでテスト';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;
