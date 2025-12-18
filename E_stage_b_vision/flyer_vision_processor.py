"""
Stage B: Gemini Vision - チラシ画像処理（2段階）

Step 1: OCR + レイアウト解析
Step 2: 商品情報の構造化抽出
"""
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger
import json

from C_ai_common.llm_client.llm_client import LLMClient


# Step 1: OCR + レイアウト解析プロンプト
STEP1_OCR_PROMPT = """
あなたはスーパーマーケットのチラシを分析する専門家です。

この画像はスーパーマーケットのチラシです。以下の情報を抽出してください：

## 抽出する情報

### 1. チラシ全体のテキスト
- 画像内のすべてのテキストをOCRで抽出
- レイアウトと位置関係を保持
- 商品名、価格、説明文すべて含む

### 2. レイアウト構造
- セクション（野菜、肉、日用品など）
- 各セクションの商品配置
- 見出し、キャッチコピー

### 3. チラシ基本情報
- 有効期間（〜月〜日）
- 特売情報（タイムセール、日替わりなど）
- 店舗情報

## 出力形式

JSON形式で以下の構造で出力してください：

```json
{
  "full_text": "チラシ全体のテキスト（改行や空白を保持）",
  "sections": [
    {
      "section_name": "セクション名（例: 野菜・果物、精肉、鮮魚など）",
      "position": "上部、中央、下部など",
      "items_text": "このセクションのすべてのテキスト"
    }
  ],
  "flyer_info": {
    "valid_period": "有効期間のテキスト",
    "special_offers": ["タイムセール情報", "特売情報など"],
    "catchphrases": ["キャッチコピー"]
  }
}
```

**重要:**
- すべてのテキストを漏れなく抽出してください
- 価格情報は正確に抽出してください
- レイアウト構造を保持してください
"""


# Step 2: 商品情報の構造化抽出プロンプト
STEP2_PRODUCT_EXTRACTION_PROMPT = """
あなたはスーパーマーケットのチラシから商品情報を抽出する専門家です。

以下はStep 1で抽出したチラシのテキストとレイアウト情報です：

---
{ocr_result}
---

このテキストから商品情報を構造化して抽出してください。

## 抽出する商品情報

各商品について以下の情報を抽出：
- **product_name**: 商品名（必須）
- **price**: 価格（数値、単位なし。例: 298）
- **original_price**: 元の価格（割引前、ある場合のみ）
- **discount_rate**: 割引率（%、ある場合のみ）
- **price_unit**: 価格の単位（"円", "円/100g", "円/個" など）
- **price_text**: 価格の元のテキスト（"298円", "特価", "398円→298円" など）
- **category**: カテゴリ（野菜、果物、肉、魚、日用品、飲料、冷凍食品、菓子、調味料、その他）
- **subcategory**: サブカテゴリ（ある場合のみ）
- **brand**: ブランド名（ある場合のみ）
- **quantity**: 数量・容量（"100g", "1パック", "500ml" など）
- **origin**: 産地（"国産", "青森県産" など、ある場合のみ）
- **is_special_offer**: 特売品かどうか（true/false）
- **offer_type**: 特売タイプ（"タイムセール", "日替わり", "週末限定" など）
- **extracted_text**: この商品に関する元のテキスト
- **confidence**: 抽出の信頼度（0.0〜1.0）

## 出力形式

```json
{
  "products": [
    {
      "product_name": "国産キャベツ",
      "price": 98,
      "price_unit": "円",
      "price_text": "98円",
      "category": "野菜",
      "quantity": "1玉",
      "origin": "国産",
      "is_special_offer": true,
      "offer_type": "日替わり",
      "extracted_text": "国産キャベツ 1玉 98円 日替わり特価",
      "confidence": 0.95
    }
  ],
  "total_products": 1,
  "extraction_notes": "抽出時の注意点や不明点があればここに記載"
}
```

## 重要な注意事項

1. **すべての商品を漏れなく抽出**してください
2. **価格は数値のみ**抽出（"298円" → 298）
3. **カテゴリは指定された選択肢から選択**
4. **商品名は正確に**抽出（ブランド名を含む）
5. **特売・セール品は is_special_offer を true** に設定
6. **情報が不明な場合は null** を設定
7. **同じ商品が複数箇所に記載されている場合は1つにまとめる**

それでは、商品情報を抽出してください。
"""


class FlyerVisionProcessor:
    """チラシ画像のVision処理（2段階）"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Args:
            llm_client: LLMクライアント（Noneの場合は新規作成）
        """
        self.llm_client = llm_client or LLMClient()

    async def process_flyer_image(
        self,
        image_path: Path,
        flyer_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        チラシ画像を2段階で処理

        Args:
            image_path: 画像ファイルパス
            flyer_metadata: チラシメタデータ（店舗名、期間など）

        Returns:
            {
                'step1_result': {...},  # OCR結果
                'step2_result': {...},  # 商品情報
                'success': bool,
                'error': str
            }
        """
        result = {
            'step1_result': None,
            'step2_result': None,
            'success': False,
            'error': None
        }

        try:
            # ============================================
            # Step 1: OCR + レイアウト解析
            # ============================================
            logger.info("[Stage B - Step 1] OCR + レイアウト解析開始...")

            step1_result = await self._step1_ocr_and_layout(image_path)

            if not step1_result or not step1_result.get('full_text'):
                error_msg = "Step 1でテキストを抽出できませんでした"
                logger.error(error_msg)
                result['error'] = error_msg
                return result

            result['step1_result'] = step1_result
            logger.info(f"[Step 1完了] テキスト長: {len(step1_result.get('full_text', ''))}文字")

            # ============================================
            # Step 2: 商品情報の構造化抽出
            # ============================================
            logger.info("[Stage B - Step 2] 商品情報抽出開始...")

            step2_result = await self._step2_extract_products(step1_result)

            if not step2_result:
                error_msg = "Step 2で商品情報を抽出できませんでした"
                logger.error(error_msg)
                result['error'] = error_msg
                return result

            result['step2_result'] = step2_result
            logger.info(f"[Step 2完了] 商品数: {step2_result.get('total_products', 0)}件")

            result['success'] = True

        except Exception as e:
            error_msg = f"Vision処理エラー: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result['error'] = error_msg

        return result

    async def _step1_ocr_and_layout(self, image_path: Path) -> Optional[Dict[str, Any]]:
        """
        Step 1: OCR + レイアウト解析

        Args:
            image_path: 画像ファイルパス

        Returns:
            OCR結果、またはNone
        """
        try:
            # Gemini Vision でOCR + レイアウト解析
            response = await self.llm_client.generate_with_vision(
                prompt=STEP1_OCR_PROMPT,
                image_path=str(image_path),
                model="gemini-2.0-flash-exp",
                response_format="json"
            )

            # JSONパース
            try:
                ocr_result = json.loads(response)
                return ocr_result
            except json.JSONDecodeError as e:
                logger.error(f"Step 1 JSONパースエラー: {e}")
                logger.debug(f"レスポンス: {response[:500]}")
                return None

        except Exception as e:
            logger.error(f"Step 1エラー: {e}", exc_info=True)
            return None

    async def _step2_extract_products(
        self,
        step1_result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Step 2: 商品情報の構造化抽出

        Args:
            step1_result: Step 1のOCR結果

        Returns:
            商品情報、またはNone
        """
        try:
            # Step 1の結果をJSON文字列に変換
            ocr_json = json.dumps(step1_result, ensure_ascii=False, indent=2)

            # プロンプト生成
            prompt = STEP2_PRODUCT_EXTRACTION_PROMPT.format(
                ocr_result=ocr_json
            )

            # Gemini でテキスト処理（Visionではない）
            response = self.llm_client.call_model(
                tier="stage1_classification",  # Gemini 2.5 Flash
                prompt=prompt,
                model_name="gemini-2.0-flash-exp",
                response_format="json_object"
            )

            if not response.get('success'):
                logger.error(f"Step 2 LLM呼び出しエラー: {response.get('error')}")
                return None

            # JSONパース
            try:
                content = response.get('content', response.get('response', ''))
                products_result = json.loads(content)
                return products_result
            except json.JSONDecodeError as e:
                logger.error(f"Step 2 JSONパースエラー: {e}")
                logger.debug(f"レスポンス: {content[:500]}")
                return None

        except Exception as e:
            logger.error(f"Step 2エラー: {e}", exc_info=True)
            return None
