"""
トランザクション処理モジュール

- Gemini OCRの結果を正規化
- エイリアス変換・辞書マッチング
- イベント期間判定 → シチュエーション自動設定
- Supabaseへの登録
"""

from datetime import datetime, date
from typing import Dict, List, Optional
from supabase import create_client, Client
from loguru import logger

from .config import SUPABASE_URL, SUPABASE_KEY


class TransactionProcessor:
    """トランザクション処理クラス"""

    def __init__(self):
        self.db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

        # マスタデータをキャッシュ
        self.aliases = self._load_aliases()
        self.product_dict = self._load_product_dictionary()
        self.events = self._load_events()
        self.situations = self._load_situations()
        self.categories = self._load_categories()

    def process(
        self,
        ocr_result: Dict,
        file_name: str,
        drive_file_id: str,
        model_name: str = "gemini-2.5-flash",
        source_folder: str = "INBOX"
    ) -> Dict:
        """
        OCR結果を処理してDBに登録

        Args:
            ocr_result: Gemini OCRの結果
            file_name: ファイル名
            drive_file_id: Google DriveのファイルID
            model_name: 使用したGeminiモデル名
            source_folder: ソースフォルダ（INBOX_EASY/INBOX_HARD）

        Returns:
            Dict: 処理結果
                - success: {"transaction_ids": [...]}
                - error: {"error": "...", "message": "..."}
        """
        try:
            # エラーチェック
            if "error" in ocr_result:
                self._log_processing_error(file_name, drive_file_id, ocr_result, model_name)
                return ocr_result

            # トランザクション日付
            trans_date = datetime.strptime(ocr_result["transaction_date"], "%Y-%m-%d").date()

            # イベント期間判定 → シチュエーション確定
            situation_id = self._determine_situation(trans_date)

            # 各商品を正規化（税率決定のみ、税額はまだ計算しない）
            normalized_items = []
            for item in ocr_result["items"]:
                normalized = self._normalize_item(item, ocr_result["shop_name"])
                normalized_items.append({
                    "raw_item": item,
                    "normalized": normalized
                })

            # 税額を按分計算
            items_with_tax = self._calculate_and_distribute_tax(
                normalized_items,
                ocr_result.get("tax_summary")
            )

            # DB登録
            transaction_ids = []
            for item_data in items_with_tax:
                item = item_data["raw_item"]
                normalized = item_data["normalized"]

                trans_id = self._insert_transaction(
                    transaction_date=trans_date.isoformat(),
                    shop_name=ocr_result["shop_name"],
                    product_name=normalized["product_name"],
                    quantity=item.get("quantity", 1),
                    unit_price=item["unit_price"],
                    total_amount=item["total_amount"],
                    category_id=normalized.get("category_id"),
                    situation_id=situation_id,
                    tax_rate=normalized["tax_rate"],
                    tax_amount=normalized["tax_amount"],
                    needs_tax_review=item_data.get("needs_review", False),
                    image_path=f"99_Archive/{trans_date.strftime('%Y-%m')}/{file_name}",
                    drive_file_id=drive_file_id,
                    ocr_model=model_name,
                    source_folder=source_folder
                )

                transaction_ids.append(trans_id)

            # 処理ログ記録
            processing_log_id = self._log_processing_success(file_name, drive_file_id, transaction_ids, model_name)

            # 税額サマリー保存
            if "tax_summary" in ocr_result:
                self._save_tax_summary(
                    processing_log_id=processing_log_id,
                    tax_summary=ocr_result["tax_summary"],
                    items_with_tax=items_with_tax
                )

            logger.info(f"Processed {len(transaction_ids)} transactions from {file_name} using {model_name}")

            return {
                "success": True,
                "transaction_ids": transaction_ids
            }

        except Exception as e:
            logger.error(f"Failed to process {file_name}: {e}")
            self._log_processing_error(file_name, drive_file_id, {"error": str(e)}, model_name)
            return {
                "error": "processing_failed",
                "message": str(e)
            }

    def _normalize_item(self, item: Dict, shop_name: str) -> Dict:
        """
        商品情報を正規化（税率のみ決定、税額は後で按分計算）

        Priority:
        1. エイリアス変換
        2. 商品辞書マッチング（税率も取得）
        3. そのまま使用（Geminiの推測税率を使用）

        Args:
            item: {"product_name": "...", "tax_rate": 10, ...}
            shop_name: 店舗名

        Returns:
            Dict: {"product_name": "正規化後", "category_id": "...", "tax_rate": 10, "tax_rate_fixed": True/False}
        """
        product_name = item["product_name"]
        gemini_tax_rate = item.get("tax_rate", 10)  # Geminiの推測税率（デフォルト10%）

        # 1. エイリアス変換
        product_name = self.aliases.get(product_name.lower(), product_name)

        # 2. 商品辞書マッチング
        for entry in self.product_dict:
            if entry["raw_keyword"].lower() in product_name.lower():
                # 辞書に登録されている税率を優先（確定）
                return {
                    "product_name": entry["official_name"],
                    "category_id": entry["category_id"],
                    "tax_rate": entry.get("tax_rate", 10),
                    "tax_rate_fixed": True  # 辞書由来の税率は確定
                }

        # 3. マッチしなければGeminiの推測を使用（暫定）
        return {
            "product_name": product_name,
            "category_id": None,
            "tax_rate": gemini_tax_rate,
            "tax_rate_fixed": False  # Gemini推測の税率は調整可能
        }

    def _determine_situation(self, trans_date: date) -> str:
        """
        取引日からシチュエーションを判定

        Args:
            trans_date: 取引日

        Returns:
            str: situation_id（イベント期間中なら該当シチュエーション、それ以外は「日常」）
        """
        # イベント期間に該当するかチェック
        for event in self.events:
            if event["start_date"] <= trans_date <= event["end_date"]:
                logger.info(f"Date {trans_date} matches event: {event['name']}")
                return event["situation_id"]

        # デフォルトは「日常」
        default_situation = next(
            (s for s in self.situations if s["name"] == "日常"),
            self.situations[0]
        )
        return default_situation["id"]

    def _insert_transaction(self, **kwargs) -> str:
        """トランザクションをDBに登録"""
        result = self.db.table("money_transactions").insert(kwargs).execute()
        return result.data[0]["id"]

    def _log_processing_success(self, file_name: str, drive_file_id: str, transaction_ids: List[str], model_name: str = None) -> str:
        """処理成功をログに記録"""
        log_data = {
            "file_name": file_name,
            "drive_file_id": drive_file_id,
            "status": "success",
            "transaction_ids": transaction_ids
        }
        if model_name:
            log_data["ocr_model"] = model_name

        result = self.db.table("money_image_processing_log").insert(log_data).execute()
        return result.data[0]["id"]

    def _log_processing_error(self, file_name: str, drive_file_id: str, error_info: Dict, model_name: str = None):
        """処理エラーをログに記録"""
        log_data = {
            "file_name": file_name,
            "drive_file_id": drive_file_id,
            "status": "failed",
            "error_message": error_info.get("message", error_info.get("error"))
        }
        if model_name:
            log_data["ocr_model"] = model_name

        self.db.table("money_image_processing_log").insert(log_data).execute()

    def _calculate_and_distribute_tax(self, normalized_items: List[Dict], tax_summary: Dict) -> List[Dict]:
        """
        税額を按分計算

        重要な前提：
        - 税込合計額（支払い金額）が絶対に正しい
        - レシート記載の8%/10%対象税込額から税額を逆算
        - 各商品に税額を按分（端数は最初の商品に加算）

        Args:
            normalized_items: 正規化済み商品リスト
            tax_summary: レシート記載の税額サマリー

        Returns:
            List[Dict]: 税額が計算された商品リスト
        """
        # 商品を8%と10%にグループ化
        items_8 = []
        items_10 = []

        for item_data in normalized_items:
            if item_data["normalized"]["tax_rate"] == 8:
                items_8.append(item_data)
            else:
                items_10.append(item_data)

        # 各グループの税込合計を計算
        total_8 = sum(item["raw_item"]["total_amount"] for item in items_8)
        total_10 = sum(item["raw_item"]["total_amount"] for item in items_10)

        needs_review = False

        # tax_summaryがある場合は整合性チェック
        if tax_summary:
            receipt_total_8 = tax_summary.get("tax_8_subtotal", 0) + tax_summary.get("tax_8_amount", 0)
            receipt_total_10 = tax_summary.get("tax_10_subtotal", 0) + tax_summary.get("tax_10_amount", 0)

            # 整合性チェック（±数円程度の誤差は許容）
            if abs(total_8 - receipt_total_8) > 5:
                logger.warning(f"8% total mismatch: calculated={total_8}, receipt={receipt_total_8}")
                needs_review = True

            if abs(total_10 - receipt_total_10) > 5:
                logger.warning(f"10% total mismatch: calculated={total_10}, receipt={receipt_total_10}")
                needs_review = True

            # レシート記載値を使用
            if receipt_total_8 > 0:
                total_8 = receipt_total_8
            if receipt_total_10 > 0:
                total_10 = receipt_total_10

        # 税額を計算（グループ全体で）
        # 8%税額 = 8%対象税込額 × (8/108)
        # 10%税額 = 10%対象税込額 × (10/110)
        tax_8_total = round(total_8 * 8 / 108) if total_8 > 0 else 0
        tax_10_total = round(total_10 * 10 / 110) if total_10 > 0 else 0

        # 各商品に税額を按分
        self._distribute_tax_to_items(items_8, tax_8_total)
        self._distribute_tax_to_items(items_10, tax_10_total)

        # needs_reviewフラグを設定
        result = normalized_items
        if needs_review:
            for item in result:
                item["needs_review"] = True

        return result

    def _distribute_tax_to_items(self, items: List[Dict], total_tax: int):
        """
        税額を各商品に按分（端数は最初の商品に加算）

        例：5円の商品×2、税額1円の場合
        - 商品1: 1円
        - 商品2: 0円

        Args:
            items: 商品リスト
            total_tax: 配分する税額合計
        """
        if not items or total_tax == 0:
            for item in items:
                item["normalized"]["tax_amount"] = 0
            return

        # 各商品の税込額の比率で按分
        total_amount = sum(item["raw_item"]["total_amount"] for item in items)

        distributed_tax = []
        for item in items:
            item_amount = item["raw_item"]["total_amount"]
            # 比率で按分（切り捨て）
            tax = int(total_tax * item_amount / total_amount)
            distributed_tax.append(tax)

        # 端数を計算
        remainder = total_tax - sum(distributed_tax)

        # 端数を最初の商品に加算
        if remainder != 0 and len(distributed_tax) > 0:
            distributed_tax[0] += remainder

        # 各商品に税額を設定
        for i, item in enumerate(items):
            item["normalized"]["tax_amount"] = distributed_tax[i]

        logger.debug(f"Distributed {total_tax}円 tax: {distributed_tax} (remainder={remainder})")

    def _save_tax_summary(self, processing_log_id: str, tax_summary: Dict, items_with_tax: List[Dict]):
        """
        税額サマリーを保存

        Args:
            processing_log_id: 処理ログID
            tax_summary: レシート記載の税額サマリー
            items_with_tax: 税額計算済み商品リスト
        """
        # 計算した税額を集計
        calculated_tax_8 = sum(
            item["normalized"]["tax_amount"]
            for item in items_with_tax
            if item["normalized"]["tax_rate"] == 8
        )
        calculated_tax_10 = sum(
            item["normalized"]["tax_amount"]
            for item in items_with_tax
            if item["normalized"]["tax_rate"] == 10
        )

        # レシート記載の税額
        actual_tax_8 = tax_summary.get("tax_8_amount", 0)
        actual_tax_10 = tax_summary.get("tax_10_amount", 0)

        # 差分計算（理論的には±1円以内になるはず）
        tax_8_diff = calculated_tax_8 - actual_tax_8 if actual_tax_8 > 0 else 0
        tax_10_diff = calculated_tax_10 - actual_tax_10 if actual_tax_10 > 0 else 0

        # 整合性フラグ（±1円以内なら一致とみなす）
        matches = abs(tax_8_diff) <= 1 and abs(tax_10_diff) <= 1

        # サマリー保存
        summary_data = {
            "processing_log_id": processing_log_id,
            "tax_8_subtotal": tax_summary.get("tax_8_subtotal"),
            "tax_8_amount": actual_tax_8,
            "tax_10_subtotal": tax_summary.get("tax_10_subtotal"),
            "tax_10_amount": actual_tax_10,
            "total_amount": tax_summary.get("total_amount"),
            "calculated_tax_8_amount": calculated_tax_8,
            "calculated_tax_10_amount": calculated_tax_10,
            "calculated_matches_actual": matches,
            "tax_8_diff": tax_8_diff,
            "tax_10_diff": tax_10_diff
        }

        self.db.table("money_receipt_tax_summary").insert(summary_data).execute()

        if matches:
            logger.info(f"Tax calculation successful: 8%={calculated_tax_8}円, 10%={calculated_tax_10}円")
        else:
            logger.warning(f"Tax diff: 8%={tax_8_diff}円, 10%={tax_10_diff}円")

    # ========================================
    # マスタデータ読み込み
    # ========================================
    def _load_aliases(self) -> Dict[str, str]:
        """エイリアステーブルを読み込み"""
        result = self.db.table("money_aliases").select("*").execute()
        return {row["input_word"].lower(): row["correct_word"] for row in result.data}

    def _load_product_dictionary(self) -> List[Dict]:
        """商品辞書を読み込み"""
        result = self.db.table("money_product_dictionary").select("*").execute()
        return result.data

    def _load_events(self) -> List[Dict]:
        """イベント期間を読み込み"""
        result = self.db.table("money_events").select("*").execute()

        # 日付をdateオブジェクトに変換
        for event in result.data:
            event["start_date"] = datetime.strptime(event["start_date"], "%Y-%m-%d").date()
            event["end_date"] = datetime.strptime(event["end_date"], "%Y-%m-%d").date()

        return result.data

    def _load_situations(self) -> List[Dict]:
        """シチュエーション一覧を読み込み"""
        result = self.db.table("money_situations").select("*").execute()
        return result.data

    def _load_categories(self) -> List[Dict]:
        """カテゴリ一覧を読み込み"""
        result = self.db.table("money_categories").select("*").execute()
        return result.data
