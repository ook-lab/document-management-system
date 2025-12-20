"""
7要素データ構造の検証スクリプト

DB に保存された商品データが7要素構造になっているか確認
"""
from A_common.database.client import DatabaseClient
from loguru import logger
import json


def verify_7_elements():
    """7要素データ構造を検証"""
    db = DatabaseClient(use_service_role=True)

    # レシート一覧を取得
    receipts = db.client.table("60_rd_receipts").select("*").limit(3).execute()

    for receipt in receipts.data:
        logger.info(f"\n{'='*80}")
        logger.info(f"📄 レシート: {receipt['shop_name']} ({receipt['transaction_date']})")
        logger.info(f"   receipt_id: {receipt['id']}")
        logger.info(f"   合計: {receipt['total_amount_check']}円")
        logger.info(f"   小計: {receipt['subtotal_amount']}円")

        # 外税 or 内税判定
        if receipt['subtotal_amount'] and receipt['total_amount_check']:
            if receipt['subtotal_amount'] < receipt['total_amount_check']:
                tax_type = "外税"
            else:
                tax_type = "内税"
        else:
            tax_type = "不明"
        logger.info(f"   税表示タイプ: {tax_type}")

        # トランザクションを取得
        transactions = db.client.table("60_rd_transactions").select("*").eq("receipt_id", receipt['id']).execute()

        logger.info(f"\n   商品一覧:")
        for trans in transactions.data:
            # 正規化アイテムを取得
            std_items = db.client.table("60_rd_standardized_items").select("*").eq("transaction_id", trans['id']).execute()

            if std_items.data:
                std = std_items.data[0]
                logger.info(f"\n   商品: {trans['product_name']}")
                logger.info(f"     1. 数量:      {trans['quantity']}")
                logger.info(f"     2. 表示額:    {trans.get('unit_price', 'N/A')}円 (※unit_priceから推測)")
                logger.info(f"     3. 外or内:    (レシートレベルで{tax_type})")
                logger.info(f"     4. 税率:      {std['tax_rate']}%")
                logger.info(f"     5. 本体価:    {std['std_unit_price']}円")
                logger.info(f"     6. 税額:      {std['tax_amount']}円")
                logger.info(f"     7. 税込価:    {std['std_amount']}円")

                # 計算検証
                if tax_type == "外税":
                    expected_total = std['std_unit_price'] + std['tax_amount']
                    if expected_total == std['std_amount']:
                        logger.success(f"     ✅ 計算正しい: {std['std_unit_price']} + {std['tax_amount']} = {std['std_amount']}")
                    else:
                        logger.warning(f"     ⚠️  計算ずれ: {std['std_unit_price']} + {std['tax_amount']} ≠ {std['std_amount']}")
                else:
                    expected_base = std['std_amount'] - std['tax_amount']
                    if expected_base == std['std_unit_price']:
                        logger.success(f"     ✅ 計算正しい: {std['std_amount']} - {std['tax_amount']} = {std['std_unit_price']}")
                    else:
                        logger.warning(f"     ⚠️  計算ずれ: {std['std_amount']} - {std['tax_amount']} ≠ {std['std_unit_price']}")


if __name__ == "__main__":
    verify_7_elements()
