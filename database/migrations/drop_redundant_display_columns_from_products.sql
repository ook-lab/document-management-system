-- ============================================
-- 冗長なdisplay_*カラムの削除
-- Rawdata_NETSUPER_items テーブルから display_sender と display_subject を削除
-- ============================================
--
-- 理由:
-- - display_sender は organization カラムと100%重複
-- - display_subject は product_name + " - " + organization で動的生成可能
--
-- 実行日: 2025-12-22
-- ============================================

-- display_sender カラムを削除
ALTER TABLE "Rawdata_NETSUPER_items"
DROP COLUMN IF EXISTS display_sender;

-- display_subject カラムを削除
ALTER TABLE "Rawdata_NETSUPER_items"
DROP COLUMN IF EXISTS display_subject;

-- 確認
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'Rawdata_NETSUPER_items'
  AND column_name IN ('display_sender', 'display_subject');
-- 結果が0行であれば削除成功
