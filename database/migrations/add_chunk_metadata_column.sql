-- chunk_metadata カラムを追加するマイグレーション
-- 構造化データ（text_blocks, structured_tables, other_text など）を保存

ALTER TABLE "10_ix_search_index"
ADD COLUMN IF NOT EXISTS chunk_metadata jsonb;

-- インデックスを追加（JSON クエリの高速化）
CREATE INDEX IF NOT EXISTS idx_chunk_metadata_gin
ON "10_ix_search_index" USING gin (chunk_metadata jsonb_path_ops);

-- コメント追加
COMMENT ON COLUMN "10_ix_search_index".chunk_metadata IS '構造化データ（text_blocks, structured_tables, weekly_schedule, other_text など）のメタデータ';
