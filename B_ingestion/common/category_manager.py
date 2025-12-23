"""
ネットスーパーカテゴリー実行スケジュール管理

カテゴリーごとに実行日とインターバルを指定し、
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
            except Exception as e:
                logger.error(f"設定ファイル読み込みエラー: {e}")
                self.config = {}
        else:
            logger.warning(f"設定ファイルが見つかりません: {self.config_path}")
            self.config = {}

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
        default_start_date: Optional[str] = None
    ):
        """
        店舗のカテゴリーを初期化

        Args:
            store_name: 店舗名（例: "rakuten_seiyu"）
            categories: カテゴリーリスト [{"name": "xxx", "url": "xxx"}, ...]
            default_interval_days: デフォルトのインターバル日数
            default_start_date: デフォルトの開始日（YYYY-MM-DD）、指定しない場合は今日
        """
        if default_start_date is None:
            default_start_date = datetime.now().strftime("%Y-%m-%d")

        if store_name not in self.config:
            self.config[store_name] = []

        existing_names = {cat["name"] for cat in self.config[store_name]}

        for category in categories:
            if category["name"] not in existing_names:
                self.config[store_name].append({
                    "name": category["name"],
                    "url": category.get("url", ""),
                    "enabled": True,
                    "start_date": default_start_date,
                    "interval_days": default_interval_days,
                    "last_run": None,
                    "notes": ""
                })

        self.save_config()
        logger.info(f"{store_name} のカテゴリーを初期化しました（{len(categories)}件）")

    def should_run_category(
        self,
        store_name: str,
        category_name: str,
        today: Optional[datetime] = None
    ) -> bool:
        """
        カテゴリーを今日実行すべきかどうかを判定

        ロジック:
        1. enabled が False なら False
        2. start_date が未来なら、今日 == start_date かチェック
        3. start_date が今日または過去の場合:
           - last_run が None なら、start_date から interval_days 経過しているかチェック
           - last_run がある場合、last_run から interval_days 経過しているかチェック

        Args:
            store_name: 店舗名
            category_name: カテゴリー名
            today: 今日の日付（指定しない場合は現在日時）

        Returns:
            実行すべきなら True
        """
        if today is None:
            today = datetime.now()

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

        # 日付を解析
        start_date = datetime.strptime(category["start_date"], "%Y-%m-%d")
        interval_days = category["interval_days"]
        last_run_str = category.get("last_run")

        # start_date が未来の場合
        if start_date.date() > today.date():
            # 今日が start_date なら実行
            should_run = today.date() == start_date.date()
            if should_run:
                logger.info(f"カテゴリー {category_name}: 初回実行日（start_date）です")
            return should_run

        # start_date が今日または過去の場合
        if last_run_str is None:
            # まだ一度も実行していない場合、start_date から interval_days 経過しているかチェック
            next_run_date = start_date + timedelta(days=interval_days)
            should_run = today.date() >= next_run_date.date()
            if should_run:
                logger.info(f"カテゴリー {category_name}: 初回実行（start_date + interval から {(today.date() - next_run_date.date()).days}日経過）")
            return should_run
        else:
            # 前回実行日から interval_days 経過しているかチェック
            last_run = datetime.strptime(last_run_str, "%Y-%m-%d")
            next_run_date = last_run + timedelta(days=interval_days)
            should_run = today.date() >= next_run_date.date()
            if should_run:
                logger.info(f"カテゴリー {category_name}: 実行可能（前回実行から {(today.date() - last_run.date()).days}日経過）")
            return should_run

    def mark_as_run(
        self,
        store_name: str,
        category_name: str,
        run_date: Optional[datetime] = None
    ):
        """
        カテゴリーを実行済みとしてマーク

        Args:
            store_name: 店舗名
            category_name: カテゴリー名
            run_date: 実行日（指定しない場合は今日）
        """
        if run_date is None:
            run_date = datetime.now()

        category = self._find_category(store_name, category_name)
        if category is not None:
            category["last_run"] = run_date.strftime("%Y-%m-%d")
            self.save_config()
            logger.info(f"カテゴリー {category_name} を実行済みとしてマークしました（{category['last_run']}）")
        else:
            logger.warning(f"カテゴリー {category_name} が見つかりません（店舗: {store_name}）")

    def get_next_run_date(
        self,
        store_name: str,
        category_name: str
    ) -> Optional[str]:
        """
        カテゴリーの次回実行予定日を取得

        Returns:
            次回実行予定日（YYYY-MM-DD形式）、または None
        """
        category = self._find_category(store_name, category_name)
        if category is None:
            return None

        start_date = datetime.strptime(category["start_date"], "%Y-%m-%d")
        interval_days = category["interval_days"]
        last_run_str = category.get("last_run")

        today = datetime.now()

        # start_date が未来の場合
        if start_date.date() > today.date():
            return start_date.strftime("%Y-%m-%d")

        # last_run がない場合
        if last_run_str is None:
            next_run = start_date + timedelta(days=interval_days)
            return next_run.strftime("%Y-%m-%d")

        # last_run がある場合
        last_run = datetime.strptime(last_run_str, "%Y-%m-%d")
        next_run = last_run + timedelta(days=interval_days)
        return next_run.strftime("%Y-%m-%d")

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
            updates: 更新する内容（enabled, start_date, interval_days など）
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
        default_start_date="2025-12-25"
    )

    # 実行判定テスト
    print("野菜を実行すべきか:", manager.should_run_category("rakuten_seiyu", "野菜"))
    print("次回実行予定日:", manager.get_next_run_date("rakuten_seiyu", "野菜"))
