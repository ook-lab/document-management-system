#!/bin/bash

# 日次商品自動分類スクリプト
# 毎日3:00 AMに実行（ネットスーパースクレイピング後）

# エラー時は即座に終了
set -e

# プロジェクトディレクトリに移動
cd /Users/ookuboyoshinori/document_management_system

# 仮想環境をアクティベート
source venv/bin/activate

# Python実行
echo "$(date): Starting daily classification..."
python L_product_classification/daily_auto_classifier.py

echo "$(date): Daily classification completed"
