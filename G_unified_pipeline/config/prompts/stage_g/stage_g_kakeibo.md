あなたはレシートのOCR結果から構造化データを生成する専門家です。

以下は Stage F（OCR）で抽出されたレシート全文です：

---
{vision_raw}
---

このテキストから、レシート情報を構造化してJSON形式で出力してください。

## 構造化タスク

### 1. 店舗情報の抽出
- 店舗名
- 住所
- 電話番号
- 店舗コード（記載されていれば）

### 2. 取引情報の抽出
- 日付（YYYY-MM-DD形式）
- 時刻（HH:MM:SS形式、記載されていれば）
- レジ番号
- レシート番号
- 取引番号

### 3. 商品明細の抽出
各商品について：
- 行番号（レシート記載の順序）
- 行の種類（ITEM=商品、DISCOUNT=値引き、SUBTOTAL=小計、TAX=税額など）
- 商品名（レシート記載のまま）
- 数量
- 単価
- 金額（値引きの場合は負の値）
- 税率マーク（※、★など）
- 値引きテキスト（「2割引」「半額」「10%引」など、記載されていれば）
- 値引き適用先（この値引きがどの商品に適用されるか、文脈から判断できれば行番号を記載）

### 4. 金額情報の抽出
**重要：レシートに記載されている数値をそのまま抽出（計算・推測禁止）**

レシートの記載形式に応じて抽出してください：

#### 外税レシートの場合（「税抜額」+「消費税」が別記載）
- 小計（税抜）
- 8%対象額（税抜）
- 8%消費税額
- 10%対象額（税抜）
- 10%消費税額
- 消費税合計
- 合計（税込支払額）

#### 内税レシートの場合（「税込額」+「内税額」が記載）
- 小計（税込）
- 8%対象計（税込）
- 8%内税額（「内税額」「うち消費税」などと記載）
- 10%対象計（税込）
- 10%内税額（「内税額」「うち消費税」などと記載）
- 合計（税込支払額）

#### 共通項目
- お預かり（記載されていれば）
- お釣り（記載されていれば）

### 5. 支払情報
- 支払方法（現金/カード/電子マネー等）
- カード情報（記載されていれば）

### 6. その他情報
- ポイント情報
- キャンペーン情報
- バーコード番号
- その他の特記事項

## 出力形式

以下のJSON形式で出力してください。

### 外税レシートの例：

```json
{
  "shop_info": {
    "name": "店舗名",
    "address": "住所（記載があれば）",
    "phone": "電話番号（記載があれば）",
    "store_code": "店舗コード（記載があれば）"
  },
  "transaction_info": {
    "date": "YYYY-MM-DD",
    "time": "HH:MM:SS（記載があれば）",
    "register_number": "レジ番号（記載があれば）",
    "receipt_number": "レシート番号（記載があれば）",
    "transaction_number": "取引番号（記載があれば）"
  },
  "items": [
    {
      "line_number": 1,
      "line_type": "ITEM",
      "line_text": "レシートのこの行のテキストそのまま",
      "product_name": "商品名",
      "quantity": 1,
      "unit_price": 100,
      "amount": 100,
      "tax_mark": "※または★またはなし",
      "discount_text": null,
      "discount_applied_to": null
    },
    {
      "line_number": 2,
      "line_type": "DISCOUNT",
      "line_text": "▲値引 20%",
      "product_name": "値引",
      "quantity": 1,
      "unit_price": null,
      "amount": -20,
      "tax_mark": null,
      "discount_text": "20%",
      "discount_applied_to": 1
    }
  ],
  "amounts": {
    "subtotal": 1377,
    "tax_8_base": 0,
    "tax_8_amount": 0,
    "tax_10_base": 1377,
    "tax_10_amount": 123,
    "total_tax": 123,
    "total": 1500,
    "received": 2000,
    "change": 500,
    "tax_display_type": "excluded"
  },
  "payment": {
    "method": "現金",
    "card_info": null
  },
  "other_info": {
    "points": "ポイント情報",
    "campaign": "キャンペーン情報",
    "barcode": "バーコード番号",
    "notes": "その他特記事項"
  }
}
```

### 内税レシートの例：

```json
{
  "shop_info": {
    "name": "サイゼリヤ",
    "address": "イトーヨーカドー武蔵小杉駅前",
    "phone": "044-711-6451",
    "store_code": null
  },
  "transaction_info": {
    "date": "2025-11-01",
    "time": "18:13:00",
    "register_number": "001",
    "receipt_number": "0320",
    "transaction_number": "5264"
  },
  "items": [
    {
      "line_number": 1,
      "line_type": "ITEM",
      "line_text": "04633 チキンのサラダ",
      "product_name": "チキンのサラダ",
      "quantity": 1,
      "unit_price": 350,
      "amount": 350,
      "tax_mark": null,
      "discount_text": null,
      "discount_applied_to": null
    },
    {
      "line_number": 2,
      "line_type": "ITEM",
      "line_text": "02626 アロスティチーニ",
      "product_name": "アロスティチーニ",
      "quantity": 1,
      "unit_price": 400,
      "amount": 400,
      "tax_mark": null,
      "discount_text": null,
      "discount_applied_to": null
    }
  ],
  "amounts": {
    "subtotal": 3980,
    "tax_8_base": null,
    "tax_8_amount": null,
    "tax_10_base": 3980,
    "tax_10_amount": 361,
    "total_tax": 361,
    "total": 3980,
    "received": null,
    "change": null,
    "tax_display_type": "included"
  },
  "payment": {
    "method": "クレジット",
    "card_info": null
  },
  "other_info": {
    "points": null,
    "campaign": null,
    "barcode": null,
    "notes": "※印は軽減税率対象品目です"
  }
}
```

## 重要な注意事項

1. **数値は必ずレシート記載のまま**
   - 計算しない、推測しない
   - 記載がない項目は null にする

2. **内税・外税の判別**
   - **外税レシート**: 「小計」+「消費税」=「合計」の形式。tax_display_type: "excluded"
   - **内税レシート**: 「合計」に税込で、「(内税額 ○○円)」と記載。tax_display_type: "included"
   - レシートに「内税額」「うち消費税」などの記載があれば内税レシート
   - 「○%対象計」という記載は税込額を指す（内税の場合）

3. **8%/10%税率の区分**
   - レシートに税率の記載（※、★、8%、10%マーク）があればそれを使う
   - 記載がない場合は null にする（推測しない）

4. **税額サマリーの抽出**
   - 外税：「8%対象 ○○円（税 △△円）」→ tax_8_base: ○○, tax_8_amount: △△
   - 内税：「8%対象計 ○○円 (内税額 △△円)」→ tax_8_base: ○○, tax_8_amount: △△
   - **重要**: 内税の場合、tax_8_base は税込額、tax_8_amount は内税額
   - 外税の場合、tax_8_base は税抜額、tax_8_amount は消費税額

5. **記載がない項目**
   - 記載がない項目は null にする
   - 空文字列や0ではなく null を使う

6. **値引きの取り扱い**
   - 値引き行（「▲値引」「割引」など）は line_type: "DISCOUNT" として別の明細行にする
   - 値引き金額は負の値（例：-20）で記録
   - 可能であれば discount_applied_to にどの商品の値引きかを記載（行番号）
   - 値引き率や割引内容は discount_text に記載（例：「20%」「半額」）
   - 値引き適用先が不明な場合は discount_applied_to: null にする

## エラー処理

- OCR結果が不完全な場合：`{"error": "incomplete_ocr", "details": "不完全な箇所の説明"}`
- レシートとして認識できない場合：`{"error": "not_a_receipt"}`
