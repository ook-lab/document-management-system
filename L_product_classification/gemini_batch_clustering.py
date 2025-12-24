"""
Gemini Flashを使った商品バッチクラスタリング
5,000件の既存商品を効率的にグループ化
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List

from A_common.database.client import DatabaseClient
from C_ai_common.llm_client.llm_client import LLMClient
import logging

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GeminiBatchClustering:
    """商品バッチクラスタリングクラス"""

    def __init__(self, batch_size: int = 30):
        """
        初期化

        Args:
            batch_size: 1回のGemini呼び出しで処理する商品数（デフォルト: 30）
        """
        self.db = DatabaseClient(use_service_role=True)
        self.llm_client = LLMClient()
        self.batch_size = batch_size

    def _build_clustering_prompt(self, products: List[Dict]) -> str:
        """
        クラスタリング用プロンプト生成

        Args:
            products: 商品リスト

        Returns:
            Gemini用プロンプト
        """
        # 商品リストをテキスト化
        product_list = []
        for idx, product in enumerate(products, start=1):
            product_name = product.get("product_name", "")
            org = product.get("organization", "")
            product_list.append(f"{idx}. {product_name} (店舗: {org})")

        product_text = "\n".join(product_list)

        prompt = f"""あなたは商品データ整理の専門家です。以下の{len(products)}件のネットスーパー商品を分析し、
類似商品をグループ化して「一般名詞（general_name）」と「カテゴリー」を提案してください。

## 重要なルール
1. 表記ゆれを吸収: 「牛乳」「ぎゅうにゅう」「牛にゅう」などは同じグループ
2. メーカー名・容量は無視: 「明治おいしい牛乳1L」と「メグミルク500ml」は「牛乳」でグループ化
3. 同じ商品の異なるサイズは1つのグループに統合
4. カテゴリは「食材」固定（ネットスーパーの商品なので）

## 商品リスト
{product_text}

## 出力形式
以下の形式で**JSON形式のみ**で回答してください。説明文は不要です。

{{
  "clusters": [
    {{
      "general_name": "牛乳",
      "category_name": "食材",
      "product_indices": [1, 2, 3],
      "confidence": 0.95,
      "reasoning": "全て牛乳製品のため統合"
    }},
    {{
      "general_name": "豚肉",
      "category_name": "食材",
      "product_indices": [4, 5],
      "confidence": 0.98,
      "reasoning": "豚肉関連商品"
    }}
  ]
}}

**product_indices**: 1-indexed（上記の商品番号と対応）
**confidence**: 0.0〜1.0の信頼度
"""
        return prompt

    async def fetch_unclassified_products(self, limit: int = 5000) -> List[Dict]:
        """
        未分類商品を取得

        Args:
            limit: 取得件数

        Returns:
            商品リスト
        """
        logger.info(f"Fetching up to {limit} unclassified products...")

        result = self.db.client.table('Rawdata_NETSUPER_items').select(
            'id, product_name, product_name_normalized, organization, jan_code'
        ).is_('general_name', 'null').limit(limit).execute()

        logger.info(f"Found {len(result.data)} unclassified products")
        return result.data

    async def cluster_batch(self, products: List[Dict], batch_id: str) -> List[Dict]:
        """
        1バッチの商品をGeminiでクラスタリング

        Args:
            products: 商品リスト（最大batch_size件）
            batch_id: バッチID

        Returns:
            クラスタ結果リスト
        """
        logger.info(f"Clustering batch of {len(products)} products...")

        # プロンプト生成
        prompt = self._build_clustering_prompt(products)

        # Gemini呼び出し
        try:
            response = self.llm_client.call_model(
                tier="stageh_extraction",
                prompt=prompt,
                model_name="gemini-2.5-flash",
                response_format="json",
                max_output_tokens=8192  # クラスタリング結果用に大きめに設定
            )

            if not response.get("success"):
                logger.error(f"Gemini call failed: {response.get('error')}")
                return []

            # JSON解析
            content = response.get("content", "{}")
            clusters_data = json.loads(content)

            # クラスタをデータベース形式に変換
            cluster_records = []
            for cluster in clusters_data.get("clusters", []):
                # product_indicesからproduct_idsとnamesを取得
                indices = cluster.get("product_indices", [])
                product_ids = [products[i - 1]["id"] for i in indices if 0 < i <= len(products)]
                product_names = [products[i - 1]["product_name"] for i in indices if 0 < i <= len(products)]

                cluster_record = {
                    "batch_id": batch_id,
                    "general_name": cluster.get("general_name"),
                    "category_name": cluster.get("category_name", "食材"),
                    "product_ids": product_ids,
                    "product_names": product_names,
                    "confidence_avg": cluster.get("confidence", 0.5),
                    "approval_status": "pending"
                }
                cluster_records.append(cluster_record)

            # ログに記録
            for product in products:
                self.db.client.table('99_lg_gemini_classification_log').insert({
                    "product_id": product["id"],
                    "operation_type": "batch_clustering",
                    "model_name": "gemini-2.5-flash",
                    "prompt": prompt[:500],  # 省略版
                    "response": content[:500],
                    "confidence_score": None,
                    "error_message": None
                }).execute()

            logger.info(f"Generated {len(cluster_records)} clusters")
            return cluster_records

        except Exception as e:
            logger.error(f"Clustering error: {e}")
            return []

    async def process_all_products(self):
        """
        全ての未分類商品をバッチ処理
        """
        # 未分類商品を取得
        products = await self.fetch_unclassified_products(limit=5000)

        if not products:
            logger.info("No unclassified products found")
            return

        # バッチIDを生成
        batch_id = str(uuid.uuid4())
        logger.info(f"Starting batch clustering with ID: {batch_id}")

        # バッチに分割
        total_batches = (len(products) + self.batch_size - 1) // self.batch_size
        all_clusters = []

        for i in range(0, len(products), self.batch_size):
            batch_num = i // self.batch_size + 1
            batch_products = products[i:i + self.batch_size]

            logger.info(f"Processing batch {batch_num}/{total_batches}")

            clusters = await self.cluster_batch(batch_products, batch_id)
            all_clusters.extend(clusters)

            # レート制限対策（1秒待機）
            await asyncio.sleep(1)

        # 99_tmp_gemini_clusteringに一括保存
        if all_clusters:
            logger.info(f"Saving {len(all_clusters)} clusters to database...")
            self.db.client.table('99_tmp_gemini_clustering').insert(
                all_clusters
            ).execute()

        logger.info(f"Batch clustering complete. Total clusters: {len(all_clusters)}")
        return {
            "batch_id": batch_id,
            "total_products": len(products),
            "total_clusters": len(all_clusters),
            "clusters": all_clusters
        }


# 実行スクリプト
async def main():
    """メイン実行"""
    clustering = GeminiBatchClustering(batch_size=30)  # 小さめのバッチサイズ
    result = await clustering.process_all_products()
    logger.info(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
