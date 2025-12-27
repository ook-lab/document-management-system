"""
日次自動分類エンジン
新規商品を3段階フォールバックで自動分類
"""

import asyncio
import json
from typing import Dict, List, Optional
from uuid import UUID

from A_common.database.client import DatabaseClient
from C_ai_common.llm_client.llm_client import LLMClient
import logging

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DailyAutoClassifier:
    """日次自動分類クラス"""

    def __init__(self):
        self.db = DatabaseClient(use_service_role=True)
        self.llm_client = LLMClient()

    async def tier1_lookup(self, product_name: str) -> Optional[str]:
        """
        Tier 1辞書lookup: raw_keyword → general_name

        Args:
            product_name: 商品名

        Returns:
            general_name（見つからない場合はNone）
        """
        result = self.db.client.table('MASTER_Product_generalize').select(
            'general_name'
        ).eq('raw_keyword', product_name).execute()

        if result.data:
            return result.data[0]["general_name"]
        return None

    async def tier2_lookup(
        self,
        general_name: str,
        source_type: str,
        workspace: str,
        doc_type: str,
        organization: Optional[str] = None
    ) -> Optional[UUID]:
        """
        Tier 2辞書lookup: general_name + context → category_id

        Args:
            general_name: 一般名詞
            source_type: ソースタイプ
            workspace: ワークスペース
            doc_type: ドキュメントタイプ
            organization: 組織名（オプション）

        Returns:
            category_id（見つからない場合はNone）
        """
        query = self.db.client.table('MASTER_Product_classify').select(
            'category_id'
        ).eq('general_name', general_name).eq(
            'source_type', source_type
        ).eq('workspace', workspace).eq('doc_type', doc_type)

        # organizationがNoneの場合は全組織共通のマッピングを使用
        if organization:
            result = query.eq('organization', organization).execute()
            if result.data:
                return result.data[0]["category_id"]

        # 組織固有が見つからない場合、全組織共通を試す
        result = query.is_('organization', 'null').execute()
        if result.data:
            return result.data[0]["category_id"]

        return None

    async def load_approved_examples(self, limit: int = 20) -> List[Dict]:
        """
        承認済みデータをFew-shot例として取得

        Args:
            limit: 取得件数

        Returns:
            承認済み商品リスト
        """
        result = self.db.client.table('Rawdata_NETSUPER_items').select(
            'product_name, general_name, category_id'
        ).eq('needs_approval', False).not_.is_(
            'general_name', 'null'
        ).limit(limit).execute()

        return result.data

    async def gemini_classify_with_fewshot(
        self,
        product: Dict,
        few_shot_examples: List[Dict]
    ) -> Dict:
        """
        Gemini Few-shot推論

        Args:
            product: 分類対象商品
            few_shot_examples: Few-shot例

        Returns:
            {"general_name": str, "category_id": UUID, "confidence": float}
        """
        # Few-shot例をテキスト化
        examples_text = []
        for i, ex in enumerate(few_shot_examples[:10], 1):  # 最大10例
            examples_text.append(
                f"{i}. 商品名: {ex['product_name']} → 一般名詞: {ex['general_name']}"
            )

        examples_str = "\n".join(examples_text)

        prompt = f"""あなたは商品分類の専門家です。以下の過去の分類実績を参考に、新しい商品の「一般名詞（general_name）」「小カテゴリ（small_category）」「キーワード（keywords）」を推定してください。

## 過去の分類実績（参考例）
{examples_str}

## 新規商品
商品名: {product['product_name']}
店舗: {product.get('organization', '不明')}

## 出力形式
以下のJSON形式で回答してください。

{{
  "general_name": "推定された一般名詞（例: 牛乳、食パン、トマト）",
  "small_category": "小カテゴリ（例: 乳製品、パン類、野菜）",
  "keywords": ["キーワード1", "キーワード2", "キーワード3"],
  "confidence": 0.85,
  "reasoning": "判断理由"
}}

**confidence**: 0.0〜1.0の信頼度
**keywords**: 検索に役立つ3-5個の単語
"""

        try:
            response = self.llm_client.call_model(
                tier="stageh_extraction",
                prompt=prompt,
                model_name="gemini-2.5-flash-lite",  # コスト効率重視
                response_format="json"
            )

            if response.get("success"):
                content = json.loads(response.get("content", "{}"))
                general_name = content.get("general_name")
                small_category = content.get("small_category")
                keywords = content.get("keywords", [])
                confidence = content.get("confidence", 0.5)

                # Tier 2でcategory_idを取得
                category_id = await self.tier2_lookup(
                    general_name,
                    source_type="online_shop",
                    workspace="shopping",
                    doc_type="online shop",
                    organization=product.get("organization")
                )

                # ログ記録
                self.db.client.table('99_lg_gemini_classification_log').insert({
                    "product_id": product["id"],
                    "operation_type": "daily_classification",
                    "model_name": "gemini-2.5-flash-lite",
                    "prompt": prompt[:500],
                    "response": response.get("content", "")[:500],
                    "confidence_score": confidence,
                    "error_message": None
                }).execute()

                return {
                    "general_name": general_name,
                    "small_category": small_category,
                    "keywords": keywords,
                    "category_id": category_id,
                    "confidence": confidence
                }

        except Exception as e:
            logger.error(f"Gemini classification error: {e}")
            return {"general_name": None, "small_category": None, "keywords": [], "category_id": None, "confidence": 0.0}

    async def classify_product(self, product: Dict) -> Dict:
        """
        商品を3段階フォールバックで分類

        Args:
            product: 商品データ

        Returns:
            分類結果
        """
        logger.info(f"Classifying: {product['product_name']}")

        # Step 1: Tier 1辞書lookup
        general_name = await self.tier1_lookup(product["product_name"])

        if general_name:
            # Step 2: Tier 2辞書lookup
            category_id = await self.tier2_lookup(
                general_name,
                source_type="online_supermarket",
                workspace="shopping",
                doc_type="online_grocery_item",
                organization=product.get("organization")
            )

            if category_id:
                logger.info(f"✓ Tier 2 hit: {general_name} → {category_id}")
                return {
                    "general_name": general_name,
                    "category_id": category_id,
                    "confidence": 1.0,
                    "source": "tier2"
                }

            logger.info(f"Tier 1 hit, but Tier 2 miss: {general_name}")

        # Step 3: Gemini few-shot推論
        logger.info("Falling back to Gemini few-shot inference")
        few_shot_examples = await self.load_approved_examples(limit=20)
        result = await self.gemini_classify_with_fewshot(product, few_shot_examples)
        result["source"] = "gemini_fewshot"
        return result

    async def process_unclassified_products(self):
        """未分類商品を一括処理"""
        # 未分類商品を取得
        result = self.db.client.table('Rawdata_NETSUPER_items').select(
            '*'
        ).eq('needs_approval', True).limit(1000).execute()

        products = result.data
        logger.info(f"Found {len(products)} unclassified products")

        classified_count = 0

        for product in products:
            classification = await self.classify_product(product)

            # Rawdata_NETSUPER_itemsを更新
            update_data = {
                "general_name": classification.get("general_name"),
                "small_category": classification.get("small_category"),
                "keywords": classification.get("keywords", []),
                "category_id": classification.get("category_id"),
                "classification_confidence": classification.get("confidence"),
                "needs_approval": True  # 常に手動承認必須（自動承認は無効）
            }

            self.db.client.table('Rawdata_NETSUPER_items').update(
                update_data
            ).eq('id', product["id"]).execute()

            classified_count += 1

            # レート制限対策
            if classification["source"] == "gemini_fewshot":
                await asyncio.sleep(0.5)

        logger.info(f"Classified {classified_count} products")
        return {"classified_count": classified_count}


# 実行スクリプト
async def main():
    """メイン実行"""
    classifier = DailyAutoClassifier()
    result = await classifier.process_unclassified_products()
    logger.info(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
