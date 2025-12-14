#!/bin/bash
# Cloud Runへのデプロイスクリプト（環境変数設定含む）

set -e  # エラーが発生したら終了

echo "================================"
echo "Cloud Runへのデプロイを開始します"
echo "================================"

# .envファイルから環境変数を読み込む
if [ ! -f .env ]; then
    echo "エラー: .envファイルが見つかりません"
    exit 1
fi

# .envファイルから必要な環境変数を抽出
echo "環境変数を読み込んでいます..."
source .env

# 必須環境変数のチェック
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
    echo "エラー: SUPABASE_URLまたはSUPABASE_KEYが設定されていません"
    exit 1
fi

echo "✓ 環境変数の読み込み完了"

# Cloud Runにデプロイ
echo ""
echo "Cloud Runにデプロイしています..."
gcloud run deploy mail-doc-search-system \
  --source . \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --set-env-vars "SUPABASE_URL=$SUPABASE_URL" \
  --set-env-vars "SUPABASE_KEY=$SUPABASE_KEY" \
  --set-env-vars "GOOGLE_AI_API_KEY=$GOOGLE_AI_API_KEY" \
  --set-env-vars "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" \
  --set-env-vars "OPENAI_API_KEY=$OPENAI_API_KEY" \
  --set-env-vars "LOG_LEVEL=${LOG_LEVEL:-INFO}" \
  --set-env-vars "RERANK_ENABLED=${RERANK_ENABLED:-true}"

echo ""
echo "================================"
echo "✓ デプロイが完了しました！"
echo "================================"
echo ""
echo "確認コマンド:"
echo "  curl https://mail-doc-search-system-983922127476.asia-northeast1.run.app/api/health"
echo "  curl https://mail-doc-search-system-983922127476.asia-northeast1.run.app/api/filters"
echo "  curl https://mail-doc-search-system-983922127476.asia-northeast1.run.app/api/debug/database"
echo ""
