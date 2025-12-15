-- =====================================================
-- unified_search_v2 関数の完全な定義を取得
-- =====================================================

SELECT pg_get_functiondef(oid)
FROM pg_proc
WHERE proname = 'unified_search_v2';
