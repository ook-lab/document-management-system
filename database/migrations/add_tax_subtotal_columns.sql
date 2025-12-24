-- Migration: Add tax_8_subtotal and tax_10_subtotal columns to Rawdata_RECEIPT_shops
-- Date: 2025-12-22
-- Purpose: レシート記載の税率別対象額（税抜小計）を保存するためのカラムを追加

-- Add tax_8_subtotal column (8%対象額 - 税抜)
ALTER TABLE "Rawdata_RECEIPT_shops"
ADD COLUMN IF NOT EXISTS "tax_8_subtotal" int8 NULL;

-- Add tax_10_subtotal column (10%対象額 - 税抜)
ALTER TABLE "Rawdata_RECEIPT_shops"
ADD COLUMN IF NOT EXISTS "tax_10_subtotal" int8 NULL;

-- Add comments for documentation
COMMENT ON COLUMN "Rawdata_RECEIPT_shops"."tax_8_subtotal" IS '8%対象額（税抜） - レシート記載値';
COMMENT ON COLUMN "Rawdata_RECEIPT_shops"."tax_10_subtotal" IS '10%対象額（税抜） - レシート記載値';
