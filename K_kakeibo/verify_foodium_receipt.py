"""Verify the foodium (外税) receipt's 7-element structure"""
from A_common.database.client import DatabaseClient
from loguru import logger


def verify_foodium():
    db = DatabaseClient(use_service_role=True)

    # Get the foodium receipt (ordered by created_at desc, should be second latest)
    receipts = db.client.table("60_rd_receipts").select("*").eq("shop_name", "foodium武蔵小杉").order("created_at", desc=True).limit(1).execute()

    if not receipts.data:
        logger.error("No foodium receipt found!")
        return

    receipt = receipts.data[0]
    logger.info(f"\n{'='*80}")
    logger.info(f"📄 最新foodiumレシート: {receipt['shop_name']} ({receipt['transaction_date']})")
    logger.info(f"   receipt_id: {receipt['id']}")
    logger.info(f"   合計: {receipt['total_amount_check']}円")
    logger.info(f"   小計: {receipt['subtotal_amount']}円")

    # Tax type detection
    if receipt['subtotal_amount'] and receipt['total_amount_check']:
        if receipt['subtotal_amount'] < receipt['total_amount_check']:
            tax_type = "外税"
        else:
            tax_type = "内税"
    else:
        tax_type = "不明"
    logger.info(f"   税表示タイプ: {tax_type}")

    # Get transactions
    transactions = db.client.table("60_rd_transactions").select("*").eq("receipt_id", receipt['id']).execute()
    logger.info(f"\n   商品数: {len(transactions.data)}件")

    for trans in transactions.data:  # Show all items
        # Get standardized item
        std_items = db.client.table("60_rd_standardized_items").select("*").eq("transaction_id", trans['id']).execute()

        if std_items.data:
            std = std_items.data[0]
            logger.info(f"\n   商品: {trans['product_name']}")
            logger.info(f"     1. 数量:      {trans['quantity']}")
            logger.info(f"     2. 表示額:    {trans.get('unit_price', 'N/A')}円")
            logger.info(f"     3. 外or内:    {tax_type}")
            logger.info(f"     4. 税率:      {std['tax_rate']}%")
            logger.info(f"     5. 本体価:    {std['std_unit_price']}円")
            logger.info(f"     6. 税額:      {std['tax_amount']}円")
            logger.info(f"     7. 税込価:    {std['std_amount']}円")

            # Verify calculation
            if tax_type == "外税":
                expected = std['std_unit_price'] + std['tax_amount']
                if expected == std['std_amount']:
                    logger.success(f"     ✅ 計算正しい: {std['std_unit_price']} + {std['tax_amount']} = {std['std_amount']}")
                else:
                    logger.warning(f"     ⚠️  計算ずれ: {std['std_unit_price']} + {std['tax_amount']} = {expected} ≠ {std['std_amount']}")
            else:
                expected = std['std_amount'] - std['tax_amount']
                if expected == std['std_unit_price']:
                    logger.success(f"     ✅ 計算正しい: {std['std_amount']} - {std['tax_amount']} = {std['std_unit_price']}")
                else:
                    logger.warning(f"     ⚠️  計算ずれ: {std['std_amount']} - {std['tax_amount']} = {expected} ≠ {std['std_unit_price']}")


if __name__ == "__main__":
    verify_foodium()
