"""
設定ファイル
環境変数から各種APIキー・設定を読み込み
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .envファイル読み込み
load_dotenv()

# ========================================
# Google Drive 設定
# ========================================
GOOGLE_DRIVE_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")

# 2つのInboxフォルダ（難易度別）
INBOX_EASY_FOLDER_ID = os.getenv("KAKEIBO_INBOX_EASY_FOLDER_ID")  # 00_Inbox_Easy (読みやすいレシート)
INBOX_HARD_FOLDER_ID = os.getenv("KAKEIBO_INBOX_HARD_FOLDER_ID")  # 00_Inbox_Hard (読みづらいレシート)

ARCHIVE_FOLDER_ID = os.getenv("KAKEIBO_ARCHIVE_FOLDER_ID")  # 99_Archive のフォルダID
ERROR_FOLDER_ID = os.getenv("KAKEIBO_ERROR_FOLDER_ID")  # errors フォルダID

# ========================================
# Gemini API 設定
# ========================================
GEMINI_API_KEY = os.getenv("GOOGLE_AI_API_KEY")  # 既存の.envに合わせる

# 2つのモデルを使い分け
GEMINI_MODEL_EASY = "gemini-2.5-flash-lite"  # 読みやすいレシート用（低コスト・高速）
GEMINI_MODEL_HARD = "gemini-2.5-flash"       # 読みづらいレシート用（高精度）

GEMINI_TEMPERATURE = 0.1  # 低めに設定（精度重視）

# フォルダとモデルのマッピング
FOLDER_MODEL_MAP = {
    "INBOX_EASY": {
        "folder_id": INBOX_EASY_FOLDER_ID,
        "model": GEMINI_MODEL_EASY,
        "description": "読みやすいレシート（きれい、シンプル）"
    },
    "INBOX_HARD": {
        "folder_id": INBOX_HARD_FOLDER_ID,
        "model": GEMINI_MODEL_HARD,
        "description": "読みづらいレシート（かすれ、複雑、手書き）"
    }
}

# ========================================
# Supabase 設定
# ========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
# service_role キー推奨（anonキーでも動作するが権限制限あり）
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

# ========================================
# 処理設定
# ========================================
TEMP_DIR = Path("K_kakeibo/temp")  # 一時ダウンロードフォルダ
TEMP_DIR.mkdir(parents=True, exist_ok=True)

MAX_RETRY = 3  # Gemini API リトライ回数
POLL_INTERVAL = 300  # 監視間隔（秒） = 5分

# ========================================
# Gemini プロンプトテンプレート
# ========================================
GEMINI_PROMPT = """
このレシート画像を解析し、JSON形式で返してください。

【重要な指示】
1. 店名・商品名は正式名称に変換してください（略語・カタカナを正しい日本語に）
2. **各商品の価格は必ず税込価格で返してください**
   - 外税レシート（小計+消費税=合計）の場合：
     * レシート記載の「合計」金額を「total」に設定
     * 各商品の税抜価格に消費税を加算して税込価格を計算
     * 例：小計1377円+消費税123円=合計1500円 → total: 1500
   - 内税レシート（既に税込）の場合：そのまま
3. 割引がある場合は、割引後の価格を商品価格に反映してください
4. **各商品の税率（8% or 10%）を推測してください**
   - 食品（生鮮食品、加工食品、飲料など）: 8%
   - それ以外（日用品、雑貨、酒類など）: 10%
5. **レシートに記載されている税額サマリー情報も取得してください**
   - 8%対象額、8%税額
   - 10%対象額、10%税額
6. 複数のレシートが1枚の画像に写っている場合は、"error": "multiple_receipts" を返してください
7. レシートとして認識できない画像の場合は、"error": "not_a_receipt" を返してください

【出力JSON形式】
{
  "shop_name": "店舗名",
  "transaction_date": "YYYY-MM-DD",
  "items": [
    {
      "product_name": "商品名",
      "quantity": 1,
      "unit_price": 100,
      "total_amount": 100,
      "tax_rate": 10
    }
  ],
  "total": 1000,
  "payment_method": "現金 or カード",
  "tax_summary": {
    "tax_8_subtotal": 500,
    "tax_8_amount": 40,
    "tax_10_subtotal": 300,
    "tax_10_amount": 30,
    "total_amount": 870
  }
}

**注意**: tax_summaryはレシートに明記されている場合のみ記載してください。記載がない場合は省略可能です。

エラーの場合:
{
  "error": "multiple_receipts" または "not_a_receipt",
  "message": "エラーの詳細"
}
"""

# ========================================
# バリデーション
# ========================================
def validate_config():
    """必須設定のチェック"""
    required_vars = {
        "KAKEIBO_INBOX_EASY_FOLDER_ID": INBOX_EASY_FOLDER_ID,
        "KAKEIBO_INBOX_HARD_FOLDER_ID": INBOX_HARD_FOLDER_ID,
        "GOOGLE_AI_API_KEY": GEMINI_API_KEY,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
    }

    missing = [k for k, v in required_vars.items() if not v]

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Please set them in .env file."
        )

if __name__ == "__main__":
    validate_config()
    print("Configuration is valid!")
