"""
ネットスーパーカテゴリー実行スケジュール管理

カテゴリーごとに次回実行日時とインターバルを指定し、
実行すべきかどうかを判定する機能を提供します。
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from loguru import logger


class CategoryManager:
    """カテゴリーの実行スケジュールを管理"""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: 設定ファイルのパス（指定しない場合はデフォルト）
        """
        if config_path is None:
            # デフォルトパス: B_ingestion/common/category_config.json
            self.config_path = Path(__file__).parent / "category_config.json"
        else:
            self.config_path = Path(config_path)

        self.config: Dict[str, List[Dict[str, Any]]] = {}
        self.load_config()

    def load_config(self):
        """設定ファイルを読み込む"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"設定ファイルを読み込みました: {self.config_path}")
                # 旧フォーマットから新フォーマットへ自動変換
                self._migrate_old_format()
            except Exception as e:
                logger.error(f"設定ファイル読み込みエラー: {e}")
                self.config = {}
        else:
            logger.warning(f"設定ファイルが見つかりません: {self.config_path}")
            self.config = {}

    def _migrate_old_format(self):
        """旧フォーマット（start_date）から新フォーマット（next_run_datetime）へ変換"""
        migrated = False
        for store_name, categories in self.config.items():
            for category in categories:
                # start_dateがあり、next_run_datetimeがない場合
                if "start_date" in category and "next_run_datetime" not in category:
                    # start_date（日付のみ）を next_run_datetime（日時）に変換
                    # 午前1時を設定
                    start_date = category["start_date"]
                    category["next_run_datetime"] = f"{start_date} 01:00"
                    del category["start_date"]
                    migrated = True
                    logger.info(f"カテゴリー {category['name']} を新フォーマットに変換しました")

                # last_runをlast_run_datetimeに変換
                if "last_run" in category and "last_run_datetime" not in category:
                    last_run = category["last_run"]
                    if last_run:
                        category["last_run_datetime"] = f"{last_run} 01:00"
                    else:
                        category["last_run_datetime"] = None
                    del category["last_run"]
                    migrated = True

        if migrated:
            self.save_config()
            logger.info("設定ファイルを新フォーマットに変換しました")

    def save_config(self):
        """設定ファイルに保存"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info(f"設定ファイルを保存しました: {self.config_path}")
        except Exception as e:
            logger.error(f"設定ファイル保存エラー: {e}")

    def initialize_store_categories(
        self,
        store_name: str,
        categories: List[Dict[str, str]],
        default_interval_days: int = 7,
        default_next_run: Optional[str] = None
    ):
        """
        店舗のカテゴリーを初期化

        Args:
            store_name: 店舗名（例: "rakuten_seiyu"）
            categories: カテゴリーリスト [{"name": "xxx", "url": "xxx"}, ...]
            default_interval_days: デフォルトのインターバル日数
            default_next_run: デフォルトの次回実行日時（YYYY-MM-DD HH:MM）、指定しない場合は明日午前1時
        """
        if default_next_run is None:
            # デフォルト: 明日の午前1時
            tomorrow = datetime.now() + timedelta(days=1)
            default_next_run = tomorrow.strftime("%Y-%m-%d") + " 01:00"

        if store_name not in self.config:
            self.config[store_name] = []

        existing_names = {cat["name"] for cat in self.config[store_name]}

        for category in categories:
            if category["name"] not in existing_names:
                self.config[store_name].append({
                    "name": category["name"],
                    "url": category.get("url", ""),
                    "enabled": True,
                    "next_run_datetime": default_next_run,
                    "interval_days": default_interval_days,
                    "last_run_datetime": None,
                    "notes": ""
                })

        self.save_config()
        logger.info(f"{store_name} のカテゴリーを初期化しました（{len(categories)}件）")

    def should_run_category(
        self,
        store_name: str,
        category_name: str,
        now: Optional[datetime] = None
    ) -> bool:
        """
        カテゴリーを今実行すべきかどうかを判定

        ロジック: 現在時刻 >= next_run_datetime なら True

        Args:
            store_name: 店舗名
            category_name: カテゴリー名
            now: 現在時刻（指定しない場合は現在時刻）

        Returns:
            実行すべきなら True
        """
        if now is None:
            now = datetime.now()

        if store_name not in self.config:
            logger.warning(f"店舗 {store_name} が設定ファイルに存在しません")
            return False

        category = self._find_category(store_name, category_name)
        if category is None:
            logger.warning(f"カテゴリー {category_name} が見つかりません（店舗: {store_name}）")
            return False

        # 無効化されている場合はスキップ
        if not category.get("enabled", True):
            logger.info(f"カテゴリー {category_name} は無効化されています")
            return False

        # 次回実行日時を取得
        next_run_str = category.get("next_run_datetime")
        if not next_run_str:
            logger.warning(f"カテゴリー {category_name} の次回実行日時が設定されていません")
            return False

        # 日時をパース
        try:
            next_run = datetime.strptime(next_run_str, "%Y-%m-%d %H:%M")
        except ValueError as e:
            logger.error(f"次回実行日時のパースエラー: {next_run_str}, {e}")
            return False

        # 判定
        should_run = now >= next_run
        if should_run:
            logger.info(f"カテゴリー {category_name}: 実行可能（次回実行日時: {next_run_str}）")

        return should_run

    def mark_as_run(
        self,
        store_name: str,
        category_name: str,
        run_datetime: Optional[datetime] = None
    ):
        """
        カテゴリーを実行済みとしてマークし、次回実行日時を更新

        次回実行日時 = (実行日 + interval_days + 1日) の 午前1時

        Args:
            store_name: 店舗名
            category_name: カテゴリー名
            run_datetime: 実行日時（指定しない場合は現在時刻）
        """
        if run_datetime is None:
            run_datetime = datetime.now()

        category = self._find_category(store_name, category_name)
        if category is not None:
            # 最終実行日時を記録
            category["last_run_datetime"] = run_datetime.strftime("%Y-%m-%d %H:%M")

            # 次回実行日時を計算: (実行日 + interval_days + 1) の 01:00
            interval_days = category.get("interval_days", 7)
            next_run_date = run_datetime.date() + timedelta(days=interval_days + 1)
            next_run_datetime = datetime.combine(next_run_date, datetime.min.time().replace(hour=1))
            category["next_run_datetime"] = next_run_datetime.strftime("%Y-%m-%d %H:%M")

            self.save_config()
            logger.info(f"カテゴリー {category_name} を実行済みとしてマークしました")
            logger.info(f"  最終実行: {category['last_run_datetime']}")
            logger.info(f"  次回実行: {category['next_run_datetime']}")
        else:
            logger.warning(f"カテゴリー {category_name} が見つかりません（店舗: {store_name}）")

    def get_next_run_datetime(
        self,
        store_name: str,
        category_name: str
    ) -> Optional[str]:
        """
        カテゴリーの次回実行予定日時を取得

        Returns:
            次回実行予定日時（YYYY-MM-DD HH:MM形式）、または None
        """
        category = self._find_category(store_name, category_name)
        if category is None:
            return None

        return category.get("next_run_datetime")

    def _find_category(
        self,
        store_name: str,
        category_name: str
    ) -> Optional[Dict[str, Any]]:
        """カテゴリーを検索"""
        if store_name not in self.config:
            return None

        for category in self.config[store_name]:
            if category["name"] == category_name:
                return category

        return None

    def get_all_categories(self, store_name: str) -> List[Dict[str, Any]]:
        """店舗のすべてのカテゴリーを取得"""
        return self.config.get(store_name, [])

    def update_category(
        self,
        store_name: str,
        category_name: str,
        updates: Dict[str, Any]
    ):
        """
        カテゴリー情報を更新

        Args:
            store_name: 店舗名
            category_name: カテゴリー名
            updates: 更新する内容（enabled, next_run_datetime, interval_days など）
        """
        category = self._find_category(store_name, category_name)
        if category is not None:
            category.update(updates)
            self.save_config()
            logger.info(f"カテゴリー {category_name} を更新しました")
        else:
            logger.warning(f"カテゴリー {category_name} が見つかりません（店舗: {store_name}）")


if __name__ == "__main__":
    # テスト実行
    manager = CategoryManager()

    # サンプルデータで初期化
    sample_categories = [
        {"name": "野菜", "url": "https://example.com/vegetables"},
        {"name": "果物", "url": "https://example.com/fruits"},
        {"name": "肉類", "url": "https://example.com/meat"},
    ]

    manager.initialize_store_categories(
        "rakuten_seiyu",
        sample_categories,
        default_interval_days=7,
        default_next_run="2025-12-25 01:00"
    )

    # 実行判定テスト
    print("野菜を実行すべきか:", manager.should_run_category("rakuten_seiyu", "野菜"))
    print("次回実行予定日時:", manager.get_next_run_datetime("rakuten_seiyu", "野菜"))
