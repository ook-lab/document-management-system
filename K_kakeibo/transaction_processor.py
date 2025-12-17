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

            # 各商品を処理
            transaction_ids = []

            for item in ocr_result["items"]:
                # 正規化処理
                normalized = self._normalize_item(item, ocr_result["shop_name"])

                # DB登録（モデル名とソースフォルダも記録）
                trans_id = self._insert_transaction(
                    transaction_date=trans_date.isoformat(),  # ISO形式の文字列に変換
                    shop_name=ocr_result["shop_name"],
                    product_name=normalized["product_name"],
                    quantity=item.get("quantity", 1),
                    unit_price=item["unit_price"],
                    total_amount=item["total_amount"],
                    category_id=normalized.get("category_id"),
                    situation_id=situation_id,
                    image_path=f"99_Archive/{trans_date.strftime('%Y-%m')}/{file_name}",
                    drive_file_id=drive_file_id,
                    ocr_model=model_name,
                    source_folder=source_folder
                )

                transaction_ids.append(trans_id)

            # 処理ログ記録
            self._log_processing_success(file_name, drive_file_id, transaction_ids, model_name)

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
        商品情報を正規化

        Priority:
        1. エイリアス変換
        2. 商品辞書マッチング
        3. そのまま使用

        Args:
            item: {"product_name": "...", ...}
            shop_name: 店舗名

        Returns:
            Dict: {"product_name": "正規化後", "category_id": "..."}
        """
        product_name = item["product_name"]

        # 1. エイリアス変換
        product_name = self.aliases.get(product_name.lower(), product_name)

        # 2. 商品辞書マッチング
        for entry in self.product_dict:
            if entry["raw_keyword"].lower() in product_name.lower():
                return {
                    "product_name": entry["official_name"],
                    "category_id": entry["category_id"]
                }

        # 3. マッチしなければそのまま（カテゴリ未定）
        return {
            "product_name": product_name,
            "category_id": None
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

    def _log_processing_success(self, file_name: str, drive_file_id: str, transaction_ids: List[str], model_name: str = None):
        """処理成功をログに記録"""
        log_data = {
            "file_name": file_name,
            "drive_file_id": drive_file_id,
            "status": "success",
            "transaction_ids": transaction_ids
        }
        if model_name:
            log_data["ocr_model"] = model_name

        self.db.table("money_image_processing_log").insert(log_data).execute()

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
