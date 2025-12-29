"""
日次自動分類エンジン
新規商品を3段階フォールバックで自動分類
"""

import asyncio
import json
from typing import Dict, List, Optional
from uuid import UUID
from collections import defaultdict

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
        self._existing_categories_cache = None

    async def get_existing_categories(self) -> Dict:
        """
        既存のカテゴリ体系を取得（キャッシュ付き）

        Returns:
            {
                'large': set(['食料品', ...]),
                'medium_by_large': {'食料品': set(['調味料', '茶類', ...])},
                'small_by_medium': {'食料品>調味料': set(['味噌', 'ソース', ...])}
            }
        """
        # キャッシュがあれば再利用
        if self._existing_categories_cache:
            return self._existing_categories_cache

        result = self.db.client.table('MASTER_Categories_product').select(
            'large_category, medium_category, small_category'
        ).execute()

        categories = {
            'large': set(),
            'medium_by_large': defaultdict(set),
            'small_by_medium': defaultdict(set)
        }

        for cat in result.data:
            large = cat.get('large_category')
            medium = cat.get('medium_category')
            small = cat.get('small_category')

            if large:
                categories['large'].add(large)
            if medium and large:
                categories['medium_by_large'][large].add(medium)
            if small and medium and large:
                key = f"{large}>{medium}"
                categories['small_by_medium'][key].add(small)

        # キャッシュ
        self._existing_categories_cache = categories
        return categories

    async def get_or_create_category(self, large: str, medium: str, small: str) -> Optional[UUID]:
        """
        カテゴリを取得、なければ作成

        Args:
            large: 大分類名
            medium: 中分類名
            small: 小分類名

        Returns:
            category_id (UUID)
        """
        if not large or not medium or not small:
            return None

        full_name = f"{large}>{medium}>{small}"

        # 既存検索
        result = self.db.client.table('MASTER_Categories_product').select('id').eq('name', full_name).execute()
        if result.data:
            return result.data[0]['id']

        # 新規作成
        try:
            new_cat = {
                'name': full_name,
                'large_category': large,
                'medium_category': medium,
                'small_category': small,
                'parent_id': None
            }
            result = self.db.client.table('MASTER_Categories_product').insert(new_cat).execute()
            logger.info(f"  ✓ 新規カテゴリ作成: {full_name}")

            # キャッシュをクリア
            self._existing_categories_cache = None

            return result.data[0]['id']
        except Exception as e:
            logger.error(f"カテゴリ作成エラー: {full_name} - {e}")
            # 既に存在する可能性があるので再検索
            result = self.db.client.table('MASTER_Categories_product').select('id').eq('name', full_name).execute()
            if result.data:
                return result.data[0]['id']
            return None

    async def tier1_lookup(self, product_name: str) -> Optional[str]:
        """
        Tier 1辞書lookup: raw_keyword → general_name

        Args:
            product_name: 商品名

        Returns:
            general_name（見つからない場合はNone）
        """
        # まず正規化されていない商品名で検索
        result = self.db.client.table('MASTER_Product_generalize').select(
            'general_name'
        ).eq('raw_keyword', product_name).execute()

        if result.data:
            return result.data[0]["general_name"]

        # 見つからない場合は正規化された商品名（小文字化）で検索
        result = self.db.client.table('MASTER_Product_generalize').select(
            'general_name'
        ).eq('raw_keyword', product_name.lower()).execute()

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
            {"general_name": str, "large_category": str, "medium_category": str, "small_category": str, "category_id": UUID, "confidence": float}
        """
        # 既存カテゴリを取得
        existing_cats = await self.get_existing_categories()

        # Few-shot例をテキスト化
        examples_text = []
        for i, ex in enumerate(few_shot_examples[:10], 1):  # 最大10例
            examples_text.append(
                f"{i}. 商品名: {ex['product_name']} → 一般名詞: {ex['general_name']}"
            )

        examples_str = "\n".join(examples_text) if examples_text else "（参考例なし）"

        # 既存カテゴリをテキスト化
        large_list = sorted(list(existing_cats['large']))
        medium_samples = []
        small_samples = []

        for large in large_list[:3]:  # 代表的な大分類のみ表示
            mediums = sorted(list(existing_cats['medium_by_large'].get(large, [])))[:5]
            medium_samples.append(f"  {large}: {', '.join(mediums)}...")

            for medium in mediums[:2]:  # 代表的な中分類のみ
                key = f"{large}>{medium}"
                smalls = sorted(list(existing_cats['small_by_medium'].get(key, [])))[:5]
                if smalls:
                    small_samples.append(f"    {large}>{medium}: {', '.join(smalls)}...")

        existing_cats_text = f"""
大分類: {', '.join(large_list)}

中分類の例:
{chr(10).join(medium_samples)}

小分類の例:
{chr(10).join(small_samples[:10])}
"""

        prompt = f"""あなたは商品分類の専門家です。以下の商品を大分類・中分類・小分類に分類してください。

## 既存のカテゴリ体系
{existing_cats_text}

## 重要な指示
1. **既存カテゴリを優先**: 上記の既存カテゴリに適合する場合は、既存カテゴリ名をそのまま使用してください
2. **新規カテゴリは慎重に**: 既存カテゴリに適合しない場合のみ、新しいカテゴリ名を提案してください
3. **無理な押し込み禁止**: 明らかに異なるジャンルの商品を、既存カテゴリに無理やり押し込めないでください
   - 例：トイレットペーパーを「食料品」に分類しない → 新しく「日用品」を作る

## 過去の分類実績（参考例）
{examples_str}

## 分類対象商品
商品名: {product['product_name']}
店舗: {product.get('organization', '不明')}

## 出力形式
以下のJSON形式で回答してください。

{{
  "large_category": "大分類名（例: 食料品）",
  "medium_category": "中分類名（例: 調味料）",
  "small_category": "小分類名（例: 味噌）",
  "general_name": "一般名詞（例: 味噌）",
  "keywords": ["キーワード1", "キーワード2", "キーワード3"],
  "confidence": 0.85,
  "reasoning": "既存の「食料品>調味料」に該当するため"
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
                large_category = content.get("large_category")
                medium_category = content.get("medium_category")
                small_category = content.get("small_category")
                general_name = content.get("general_name")
                keywords = content.get("keywords", [])
                confidence = content.get("confidence", 0.5)
                reasoning = content.get("reasoning", "")

                # 大中小分類からcategory_idを取得/作成
                category_id = await self.get_or_create_category(
                    large_category,
                    medium_category,
                    small_category
                )

                logger.info(f"  → 分類: {large_category}>{medium_category}>{small_category}")
                logger.info(f"  → 一般名詞: {general_name}")
                if reasoning:
                    logger.info(f"  → 理由: {reasoning}")

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
                    "large_category": large_category,
                    "medium_category": medium_category,
                    "small_category": small_category,
                    "general_name": general_name,
                    "keywords": keywords,
                    "category_id": category_id,
                    "confidence": confidence
                }

        except Exception as e:
            logger.error(f"Gemini classification error: {e}")
            return {
                "large_category": None,
                "medium_category": None,
                "small_category": None,
                "general_name": None,
                "keywords": [],
                "category_id": None,
                "confidence": 0.0
            }

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

                # category_idから大中小分類を取得
                cat_result = self.db.client.table('MASTER_Categories_product').select(
                    'large_category, medium_category, small_category'
                ).eq('id', category_id).execute()

                if cat_result.data:
                    cat_data = cat_result.data[0]
                    large_category = cat_data.get('large_category')
                    medium_category = cat_data.get('medium_category')
                    small_category = cat_data.get('small_category')
                else:
                    large_category = None
                    medium_category = None
                    small_category = None

                # キーワードのみGemini生成（コスト削減）
                gemini_result = await self.gemini_classify_with_fewshot(product, [])

                return {
                    "large_category": large_category,
                    "medium_category": medium_category,
                    "small_category": small_category,
                    "general_name": general_name,
                    "keywords": gemini_result.get("keywords", []),
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
        # 未分類商品を取得（general_name が NULL の商品のみ）
        result = self.db.client.table('Rawdata_NETSUPER_items').select(
            '*'
        ).is_('general_name', 'null').limit(1000).execute()

        products = result.data
        logger.info(f"Found {len(products)} unclassified products")

        classified_count = 0

        for product in products:
            classification = await self.classify_product(product)

            # Rawdata_NETSUPER_itemsを更新
            # 注：Rawdata_NETSUPER_itemsにはsmall_categoryカラムのみ存在
            # large_category, medium_categoryはcategory_idから参照可能
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
