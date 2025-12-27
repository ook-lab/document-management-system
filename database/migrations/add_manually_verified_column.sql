-- ====================================================================
-- 手動検証フラグを追加
-- manually_verified: 人間が確認・修正した商品を識別
-- last_verified_at: 最後に検証された日時
-- ====================================================================

BEGIN;

-- manually_verified カラムを追加（デフォルトはfalse）
ALTER TABLE "Rawdata_NETSUPER_items"
ADD COLUMN IF NOT EXISTS manually_verified BOOLEAN DEFAULT FALSE;

-- last_verified_at カラムを追加
ALTER TABLE "Rawdata_NETSUPER_items"
ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMP WITH TIME ZONE;

-- インデックスを作成（検証済みデータの取得を高速化）
CREATE INDEX IF NOT EXISTS idx_manually_verified
ON "Rawdata_NETSUPER_items"(manually_verified)
WHERE manually_verified = TRUE;

-- 確認
DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ manually_verified と last_verified_at カラムを追加しました';
    RAISE NOTICE '   - manually_verified: 手動検証フラグ（デフォルト: false）';
    RAISE NOTICE '   - last_verified_at: 最終検証日時';
    RAISE NOTICE '   - インデックス作成: idx_manually_verified';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;
