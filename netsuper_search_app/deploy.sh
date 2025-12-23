#!/bin/bash

# ネットスーパー横断検索アプリをCloud Runにデプロイ

set -e

# プロジェクトルートの.envファイルを読み込む
if [ -f "../.env" ]; then
    export $(grep -v '^#' ../.env | grep -v '^$' | xargs)
else
    echo "エラー: ../.env ファイルが見つかりません"
    exit 1
fi

PROJECT_ID="consummate-yew-479020-u2"
SERVICE_NAME="netsuper-search"
REGION="asia-northeast1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "=================================="
echo "ネットスーパー検索アプリデプロイ"
echo "=================================="

# Cloud Buildでビルド＆デプロイ（ローカルにDockerは不要）
echo ""
echo "Cloud Buildでビルド＆デプロイ中..."
gcloud run deploy ${SERVICE_NAME} \
  --source . \
  --platform managed \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 10 \
  --set-env-vars "SUPABASE_URL=${SUPABASE_URL},SUPABASE_KEY=${SUPABASE_KEY}"

echo ""
echo "=================================="
echo "✅ デプロイ完了！"
echo "=================================="
echo ""
echo "アプリURL:"
gcloud run services describe ${SERVICE_NAME} \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --format 'value(status.url)'
