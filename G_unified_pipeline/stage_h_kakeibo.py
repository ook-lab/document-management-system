"""
Stage H: Kakeibo Structuring (家計簿構造化)

家計簿レシート専用のStage H処理
- 税額按分計算
- 商品分類
- マスタデータとの紐付け
"""

from typing import Dict, Any, List
from loguru import logger
from datetime import date

from A_common.database.client import DatabaseClient


class StageHKakeibo:
    """家計簿専用のStage H（税額按分・分類）"""

    def __init__(self, db_client: DatabaseClient):
        """
        Args:
            db_client: データベースクライアント
        """
        self.db = db_client

        # マスタデータをロード
        self.aliases = self._load_aliases()
        self.product_dict = self._load_product_dictionary()
        self.situations = self._load_situations()
        self.categories = self._load_categories()

    def process(
        self,
        stage_g_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Stage Gの出力から最終データを生成

        Args:
            stage_g_output: Stage Gの構造化データ

        Returns:
            Dict: 最終データ（DB保存可能な形式）
        """
        try:
            # 0. 値引きを適用（商品金額を値引き後に更新）
            items_with_discounts = self._apply_discounts(stage_g_output.get("items", []))

            # 1. 商品を正規化（マスタとの紐付け）
            normalized_items = []
            for item in items_with_discounts:
                # 値引き行はスキップ（別途保存）
                if item.get("line_type") == "DISCOUNT":
                    normalized_items.append({
                        "raw_item": item,
                        "normalized": {
                            "product_name": item.get("product_name", "値引"),
                            "category_id": None,
                            "tax_rate": 10,  # デフォルト
                            "tax_rate_source": "discount",
                            "is_discount": True
                        }
                    })
                    continue

                normalized = self._normalize_item(
                    item,
                    stage_g_output["shop_info"]["name"]
                )
                normalized_items.append({
                    "raw_item": item,
                    "normalized": normalized
                })

            # 2. シチュエーション判定
            trans_date = date.fromisoformat(stage_g_output["transaction_info"]["date"])
            situation_id = self._determine_situation(trans_date)

            # 3. 税額を按分計算
            items_with_tax = self._calculate_and_distribute_tax(
                normalized_items,
                stage_g_output.get("amounts", {})
            )

            # 4. 最終データを構築
            result = {
                "receipt": {
                    **stage_g_output["shop_info"],
                    **stage_g_output["transaction_info"],
                    **stage_g_output.get("amounts", {}),
                    "situation_id": situation_id
                },
                "items": items_with_tax,
                "payment": stage_g_output.get("payment", {}),
                "other_info": stage_g_output.get("other_info", {})
            }

            logger.info(f"Stage H completed: {len(items_with_tax)} items processed")
            return result

        except Exception as e:
            logger.error(f"Stage H failed: {e}")
            raise

    def _apply_discounts(self, items: List[Dict]) -> List[Dict]:
        """
        値引き行を処理して商品金額を更新

        Args:
            items: Stage Gで抽出された全明細行（商品+値引き）

        Returns:
            List[Dict]: 値引き適用後の明細行リスト
        """
        # 値引き行を抽出
        discount_lines = [item for item in items if item.get("line_type") == "DISCOUNT"]
        product_lines = [item for item in items if item.get("line_type") != "DISCOUNT"]

        # 行番号でインデックスを作成（値引き適用先の検索用）
        items_by_line = {item.get("line_number"): item for item in items}

        # 各値引きを適用
        for discount in discount_lines:
            discount_amount = discount.get("amount", 0)  # 負の値
            applied_to_line = discount.get("discount_applied_to")

            if applied_to_line and applied_to_line in items_by_line:
                # 明示的に値引き適用先が指定されている場合
                target = items_by_line[applied_to_line]
                if target.get("line_type") != "DISCOUNT":
                    original_amount = target.get("amount", 0)
                    target["amount"] = original_amount + discount_amount
                    target["original_amount"] = original_amount  # 元の金額を保持
                    target["applied_discount"] = discount_amount
                    logger.info(f"Applied discount {discount_amount}円 to {target.get('product_name')}: {original_amount}円 → {target['amount']}円")
            else:
                # 値引き適用先が不明な場合は、直前の商品に適用（ヒューリスティック）
                discount_line_num = discount.get("line_number")
                if discount_line_num:
                    # 値引き行より前の商品を探す
                    for i in range(discount_line_num - 1, 0, -1):
                        if i in items_by_line and items_by_line[i].get("line_type") != "DISCOUNT":
                            target = items_by_line[i]
                            original_amount = target.get("amount", 0)
                            target["amount"] = original_amount + discount_amount
                            target["original_amount"] = original_amount
                            target["applied_discount"] = discount_amount
                            logger.info(f"Applied discount {discount_amount}円 to previous item {target.get('product_name')}: {original_amount}円 → {target['amount']}円")
                            break

        return items

    def _normalize_item(self, item: Dict, shop_name: str) -> Dict:
        """
        商品名を正規化し、カテゴリ・税率を判定

        Args:
            item: 商品データ（Stage Gの出力）
            shop_name: 店舗名

        Returns:
            Dict: {"product_name": "正規化後", "category_id": "...", "tax_rate": 10}
        """
        product_name = item["product_name"]
        receipt_tax_mark = item.get("tax_mark")  # レシートの税率マーク

        # 1. エイリアス変換
        product_name = self.aliases.get(product_name.lower(), product_name)

        # 2. 商品辞書マッチング
        for entry in self.product_dict:
            if entry["raw_keyword"].lower() in product_name.lower():
                return {
                    "product_name": entry["official_name"],
                    "category_id": entry["category_id"],
                    "tax_rate": entry["tax_rate"],
                    "tax_rate_source": "master",  # マスタから取得
                    "tax_amount": None  # 後で計算
                }

        # 3. レシートのマークから税率を判定
        if receipt_tax_mark == "※" or "8%" in str(receipt_tax_mark):
            tax_rate = 8
            tax_rate_source = "receipt_mark"
        elif receipt_tax_mark == "★" or "10%" in str(receipt_tax_mark):
            tax_rate = 10
            tax_rate_source = "receipt_mark"
        else:
            # デフォルト10%（あとで要レビュー）
            tax_rate = 10
            tax_rate_source = "default"

        return {
            "product_name": product_name,
            "category_id": None,
            "tax_rate": tax_rate,
            "tax_rate_source": tax_rate_source,
            "tax_amount": None
        }

    def _determine_situation(self, trans_date: date) -> str:
        """
        取引日からシチュエーションを判定

        Args:
            trans_date: 取引日

        Returns:
            str: シチュエーションID
        """
        weekday = trans_date.weekday()  # 0=月曜, 6=日曜

        # 土日
        if weekday >= 5:
            for s in self.situations:
                if s["name"] == "週末":
                    return s["id"]

        # 平日
        for s in self.situations:
            if s["name"] == "平日":
                return s["id"]

        # デフォルト（最初のシチュエーション）
        return self.situations[0]["id"] if self.situations else None

    def _calculate_and_distribute_tax(
        self,
        normalized_items: List[Dict],
        amounts: Dict
    ) -> List[Dict]:
        """
        税額を按分計算（内税・外税対応）

        Args:
            normalized_items: 正規化済み商品リスト
            amounts: Stage Gで抽出した金額情報

        Returns:
            List[Dict]: 税額が計算された商品リスト
        """
        # 【重要】内税・外税の判定
        # Stage Gで判定済みの場合はそれを優先
        tax_type = amounts.get("tax_display_type")

        if tax_type:
            logger.info(f"Stage Gで判定済み: tax_display_type={tax_type}")
        else:
            # フォールバック: 小計と合計の比較で判定
            subtotal = amounts.get("subtotal")
            total = amounts.get("total")

            if subtotal is not None and total is not None and subtotal < total:
                tax_type = "excluded"  # 外税
                logger.info(f"外税レシート検出: 小計={subtotal}円 < 合計={total}円")
            else:
                tax_type = "included"  # 内税
                logger.info(f"内税レシート検出: 小計={subtotal}円 = 合計={total}円")

        # 商品を8%と10%にグループ化
        items_8 = []
        items_10 = []

        for item_data in normalized_items:
            if item_data["normalized"]["tax_rate"] == 8:
                items_8.append(item_data)
            else:
                items_10.append(item_data)

        # レシート記載の税額を使用（優先）
        tax_8_amount = amounts.get("tax_8_amount") or 0
        tax_10_amount = amounts.get("tax_10_amount") or 0

        # レシート記載がない場合のみ逆算（通常は記載されている）
        if tax_8_amount == 0:
            total_8 = sum(item["raw_item"]["amount"] or 0 for item in items_8)
            if total_8 > 0:
                if tax_type == "excluded":
                    tax_8_amount = round(total_8 * 8 / 100)  # 外税：本体価格×税率
                else:
                    tax_8_amount = round(total_8 * 8 / 108)  # 内税：税込額から逆算
                logger.warning(f"8% tax not in receipt, calculated: {tax_8_amount}円 (type={tax_type})")

        if tax_10_amount == 0:
            total_10 = sum(item["raw_item"]["amount"] or 0 for item in items_10)
            if total_10 > 0:
                if tax_type == "excluded":
                    tax_10_amount = round(total_10 * 10 / 100)  # 外税：本体価格×税率
                else:
                    tax_10_amount = round(total_10 * 10 / 110)  # 内税：税込額から逆算
                logger.warning(f"10% tax not in receipt, calculated: {tax_10_amount}円 (type={tax_type})")

        # 各商品に税額を按分（内外タイプを渡す）
        self._distribute_tax_to_items(items_8, tax_8_amount, tax_type)
        self._distribute_tax_to_items(items_10, tax_10_amount, tax_type)

        return normalized_items

    def _distribute_tax_to_items(self, items: List[Dict], total_tax: int, tax_type: str):
        """
        商品データの7要素を設定
        1. 数量
        2. 表示額
        3. 外or内
        4. 税率
        5. 本体価
        6. 税額
        7. 税込価

        Args:
            items: 商品リスト
            total_tax: グループ全体の税額
            tax_type: "included"（内税）or "excluded"（外税）
        """
        if not items or total_tax == 0:
            # 税額が0の場合も7要素を設定
            for item in items:
                quantity = item["raw_item"].get("quantity", 1)
                displayed_amount = item["raw_item"].get("amount") or 0

                # 7要素を設定
                item["normalized"]["quantity"] = quantity  # 1. 数量
                item["normalized"]["displayed_amount"] = displayed_amount  # 2. 表示額
                item["normalized"]["tax_display_type"] = tax_type  # 3. 外or内
                # 4. 税率 は _normalize_item で既に設定済み
                item["normalized"]["tax_amount"] = 0  # 6. 税額

                if tax_type == "excluded":
                    # 外税：表示額 = 本体価
                    item["normalized"]["base_price"] = displayed_amount  # 5. 本体価
                    item["normalized"]["tax_included_amount"] = displayed_amount  # 7. 税込価
                else:
                    # 内税：表示額 = 税込額
                    item["normalized"]["tax_included_amount"] = displayed_amount  # 7. 税込価
                    item["normalized"]["base_price"] = displayed_amount  # 5. 本体価
            return

        # 各商品の表示額の比率で税額を按分
        total_amount = sum(item["raw_item"].get("amount") or 0 for item in items)

        if total_amount == 0:
            # 全商品の amount が 0 or None の場合、均等割
            logger.warning("All items have zero or null amount, distributing tax equally")
            per_item_tax = total_tax // len(items)
            for item in items:
                quantity = item["raw_item"].get("quantity", 1)
                item["normalized"]["quantity"] = quantity
                item["normalized"]["displayed_amount"] = 0
                item["normalized"]["tax_display_type"] = tax_type
                item["normalized"]["tax_amount"] = per_item_tax
                item["normalized"]["base_price"] = 0
                item["normalized"]["tax_included_amount"] = 0
            return

        # 税額を按分計算
        distributed_tax = []
        for item in items:
            item_amount = item["raw_item"].get("amount") or 0
            # 比率で按分（切り捨て）
            tax = int(total_tax * item_amount / total_amount)
            distributed_tax.append(tax)

        # 端数を計算して最初の商品に加算
        remainder = total_tax - sum(distributed_tax)
        if remainder > 0:
            distributed_tax[0] += remainder

        # 各商品に7要素を設定
        for i, item in enumerate(items):
            quantity = item["raw_item"].get("quantity", 1)
            displayed_amount = item["raw_item"].get("amount") or 0
            tax_amount = distributed_tax[i]

            # 7要素を設定
            item["normalized"]["quantity"] = quantity  # 1. 数量
            item["normalized"]["displayed_amount"] = displayed_amount  # 2. 表示額
            item["normalized"]["tax_display_type"] = tax_type  # 3. 外or内
            # 4. 税率 は _normalize_item で既に設定済み
            item["normalized"]["tax_amount"] = tax_amount  # 6. 税額

            if tax_type == "excluded":
                # 外税：表示額 = 本体価
                item["normalized"]["base_price"] = displayed_amount  # 5. 本体価
                item["normalized"]["tax_included_amount"] = displayed_amount + tax_amount  # 7. 税込価
            else:
                # 内税：表示額 = 税込額
                item["normalized"]["tax_included_amount"] = displayed_amount  # 7. 税込価
                item["normalized"]["base_price"] = displayed_amount - tax_amount  # 5. 本体価

        logger.debug(f"Distributed {total_tax}円 tax ({tax_type}): {distributed_tax}")

    # ========================================
    # マスタデータ読み込み
    # ========================================

    def _load_aliases(self) -> Dict[str, str]:
        """エイリアステーブルを読み込み"""
        result = self.db.client.table("60_ms_ocr_aliases").select("*").execute()
        return {row["ocr_text"].lower(): row["official_name"] for row in result.data}

    def _load_product_dictionary(self) -> List[Dict]:
        """商品辞書を読み込み"""
        result = self.db.client.table("60_ms_product_dict").select("*").execute()
        return result.data

    def _load_situations(self) -> List[Dict]:
        """シチュエーションマスタを読み込み"""
        result = self.db.client.table("60_ms_situations").select("*").execute()
        return result.data

    def _load_categories(self) -> List[Dict]:
        """カテゴリマスタを読み込み"""
        result = self.db.client.table("60_ms_categories").select("*").execute()
        return result.data
