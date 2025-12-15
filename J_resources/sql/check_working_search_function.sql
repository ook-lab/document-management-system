-- =====================================================
-- 動作する検索関数を探す
-- =====================================================

-- 1. unified_search_v2 関数の定義を確認
SELECT pg_get_functiondef(oid)
FROM pg_proc
WHERE proname = 'unified_search_v2';

-- 2. hybrid_search_2tier_final_v2 関数の定義を確認
SELECT pg_get_functiondef(oid)
FROM pg_proc
WHERE proname = 'hybrid_search_2tier_final_v2';

-- 3. search_documents_final 関数の定義を確認
SELECT pg_get_functiondef(oid)
FROM pg_proc
WHERE proname = 'search_documents_final'
LIMIT 1;
