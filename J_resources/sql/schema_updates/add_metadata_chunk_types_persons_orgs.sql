-- 【実行場所】: Supabase SQL Editor
-- 【対象ファイル】: 新規SQL実行
-- 【実行方法】: SupabaseダッシュボードでSQL Editorに貼り付け、実行
-- 【目的】: persons/organizations/people用のchunk_type定義を追加（ドキュメント更新）
-- 【前提】: change_person_org_to_arrays.sqlを先に実行していること

BEGIN;

-- ============================================================
-- chunk_typeのコメント更新（新しいメタデータチャンク対応）
-- ============================================================

COMMENT ON COLUMN document_chunks.chunk_type IS
'チャンク種別:
- title: タイトル専用 (weight=2.0)
- persons: 担当者・関係者 (weight=1.8) ★新規追加
- organizations: 組織名 (weight=1.7) ★新規追加
- summary: サマリー専用 (weight=1.5)
- date: 日付情報 (weight=1.3)
- tags: タグ情報 (weight=1.2)
- people: AI抽出人物 (weight=1.2) ★新規追加
- content_small: 本文小チャンク (weight=1.0)
- content_large: 本文大チャンク (weight=1.0)
- synthetic: 合成チャンク (weight=1.0)';

COMMENT ON COLUMN document_chunks.search_weight IS
'検索時の重み付け係数。高いほど検索結果の上位に表示される。
personsとorganizationsは重要度が高いため、1.7-1.8に設定。';

COMMIT;

-- ============================================================
-- 使用例（Python処理パイプラインでの実装イメージ）
-- ============================================================

-- persons配列をベクトル化してチャンクとして保存する例:
-- INSERT INTO document_chunks (document_id, chunk_index, chunk_text, chunk_type, search_weight, embedding)
-- VALUES (
--   '文書ID',
--   100,  -- メタデータチャンク用の連番
--   '山田太郎 やまだたろう Yamada Taro 山田',  -- 配列を結合したテキスト
--   'persons',
--   1.8,
--   '[ベクトル]'  -- OpenAI Embeddingで生成
-- );

-- organizations配列をベクトル化してチャンクとして保存する例:
-- INSERT INTO document_chunks (document_id, chunk_index, chunk_text, chunk_type, search_weight, embedding)
-- VALUES (
--   '文書ID',
--   101,
--   '東京大学 とうきょうだいがく Tokyo University 東大 UTokyo',
--   'organizations',
--   1.7,
--   '[ベクトル]'
-- );

-- people配列をベクトル化してチャンクとして保存する例:
-- INSERT INTO document_chunks (document_id, chunk_index, chunk_text, chunk_type, search_weight, embedding)
-- VALUES (
--   '文書ID',
--   102,
--   '佐藤花子 鈴木一郎',  -- AIが抽出した人物名
--   'people',
--   1.2,
--   '[ベクトル]'
-- );
