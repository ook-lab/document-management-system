"""
家計簿データのDB保存ハンドラー

Stage Hで処理された家計簿データを3層構造のDBに保存する
- 60_rd_receipts（親）
- 60_rd_transactions（子）
- 60_rd_standardized_items（孫）
- 99_lg_image_proc_log（処理ログ）
"""

from typing import Dict, List
from loguru import logger
from datetime import datetime

from A_common.database.client import DatabaseClient


class KakeiboDBHandler:
    """家計簿データのDB保存専用ハンドラー"""

    def __init__(self, db_client: DatabaseClient):
        """
        Args:
            db_client: データベースクライアント
        """
        self.db = db_client

    def save_receipt(
        self,
        stage_h_output: Dict,
        file_name: str,
        drive_file_id: str,
        model_name: str,
        source_folder: str
    ) -> Dict:
        """
        レシートデータを3層構造でDBに保存

        Args:
            stage_h_output: Stage Hの出力
            file_name: ファイル名
            drive_file_id: Google DriveのファイルID
            model_name: 使用したモデル名
            source_folder: ソースフォルダ

        Returns:
            Dict: {"receipt_id": "...", "transaction_ids": [...], ...}
        """
        try:
            # 1. レシート（親）を登録
            receipt_id = self._insert_receipt(
                stage_h_output["receipt"],
                file_name,
                drive_file_id,
                model_name,
                source_folder
            )

            # 2. トランザクション（子）と正規化アイテム（孫）を登録
            transaction_ids = []
            standardized_ids = []

            for line_num, item_data in enumerate(stage_h_output["items"], start=1):
                item = item_data["raw_item"]
                normalized = item_data["normalized"]

                # 子テーブルに登録
                transaction_id = self._insert_transaction(
                    receipt_id=receipt_id,
                    line_number=line_num,
                    ocr_raw_text=item.get("line_text", ""),
                    product_name=item["product_name"],
                    quantity=item.get("quantity", 1),
                    unit_price=item.get("unit_price"),
                    amount=item["amount"]
                )
                transaction_ids.append(transaction_id)

                # 孫テーブルに登録（7要素を使用）
                std_id = self._insert_standardized_item(
                    transaction_id=transaction_id,
                    receipt_id=receipt_id,
                    normalized=normalized,
                    situation_id=stage_h_output["receipt"]["situation_id"],
                    base_price=normalized.get("base_price", 0),
                    tax_included_amount=normalized.get("tax_included_amount", 0),
                    tax_amount=normalized.get("tax_amount", 0)
                )
                standardized_ids.append(std_id)

            # 3. 処理ログを記録
            log_id = self._log_processing_success(
                file_name=file_name,
                drive_file_id=drive_file_id,
                receipt_id=receipt_id,
                transaction_ids=transaction_ids,
                model_name=model_name
            )

            logger.info(f"Saved receipt {receipt_id} with {len(transaction_ids)} items")

            return {
                "success": True,
                "receipt_id": receipt_id,
                "transaction_ids": transaction_ids,
                "standardized_ids": standardized_ids,
                "log_id": log_id
            }

        except Exception as e:
            logger.error(f"Failed to save receipt: {e}")
            # エラーログを記録
            self._log_processing_error(
                file_name=file_name,
                drive_file_id=drive_file_id,
                error_info={"error": str(e)},
                model_name=model_name
            )
            raise

    def _insert_receipt(
        self,
        receipt_data: Dict,
        file_name: str,
        drive_file_id: str,
        model_name: str,
        source_folder: str
    ) -> str:
        """レシート情報をDBに登録（親テーブル）"""
        trans_date = datetime.strptime(receipt_data["date"], "%Y-%m-%d").date()

        data = {
            "transaction_date": receipt_data["date"],
            "shop_name": receipt_data["name"],
            "total_amount_check": receipt_data.get("total"),
            "subtotal_amount": receipt_data.get("subtotal"),
            "image_path": f"99_Archive/{trans_date.strftime('%Y-%m')}/{file_name}",
            "drive_file_id": drive_file_id,
            "source_folder": source_folder,
            "ocr_model": model_name,
            "workspace": "household",
            "is_verified": False
        }

        result = self.db.client.table("60_rd_receipts").insert(data).execute()
        return result.data[0]["id"]

    def _insert_transaction(
        self,
        receipt_id: str,
        line_number: int,
        ocr_raw_text: str,
        product_name: str,
        quantity: int,
        unit_price: int,
        amount: int
    ) -> str:
        """トランザクション情報をDBに登録（子テーブル）"""
        data = {
            "receipt_id": receipt_id,
            "line_number": line_number,
            "line_type": "item",  # デフォルト値
            "ocr_raw_text": ocr_raw_text,
            "product_name": product_name,
            "item_name": product_name,  # product_nameと同じ値を設定
            "quantity": quantity,
            "unit_price": unit_price
            # amount カラムは存在しないため除外
        }

        result = self.db.client.table("60_rd_transactions").insert(data).execute()
        return result.data[0]["id"]

    def _insert_standardized_item(
        self,
        transaction_id: str,
        receipt_id: str,
        normalized: Dict,
        situation_id: str,
        base_price: int,
        tax_included_amount: int,
        tax_amount: int
    ) -> str:
        """正規化された家計簿アイテムをDBに登録（孫テーブル）"""
        data = {
            "transaction_id": transaction_id,
            "receipt_id": receipt_id,
            "official_name": normalized["product_name"],
            "category_id": normalized.get("category_id"),
            "situation_id": situation_id,
            "tax_rate": normalized["tax_rate"],
            "std_unit_price": base_price,  # 税抜本体価格
            "std_amount": tax_included_amount,  # 税込額
            "tax_amount": tax_amount,  # 消費税額
            "needs_review": normalized.get("tax_rate_source") != "master"
        }

        result = self.db.client.table("60_rd_standardized_items").insert(data).execute()
        return result.data[0]["id"]

    def _log_processing_success(
        self,
        file_name: str,
        drive_file_id: str,
        receipt_id: str,
        transaction_ids: List[str],
        model_name: str = None
    ) -> str:
        """処理成功をログに記録"""
        log_data = {
            "file_name": file_name,
            "drive_file_id": drive_file_id,
            "receipt_id": receipt_id,
            "status": "success",
            "transaction_ids": transaction_ids
        }
        if model_name:
            log_data["ocr_model"] = model_name

        result = self.db.client.table("99_lg_image_proc_log").insert(log_data).execute()
        return result.data[0]["id"]

    def _log_processing_error(
        self,
        file_name: str,
        drive_file_id: str,
        error_info: Dict,
        model_name: str = None,
        receipt_id: str = None
    ):
        """処理エラーをログに記録"""
        log_data = {
            "file_name": file_name,
            "drive_file_id": drive_file_id,
            "status": "failed",
            "error_message": error_info.get("error")
        }
        if model_name:
            log_data["ocr_model"] = model_name
        if receipt_id:
            log_data["receipt_id"] = receipt_id

        self.db.client.table("99_lg_image_proc_log").insert(log_data).execute()
