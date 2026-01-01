#!/bin/bash
# 定期バッチ処理スクリプト
# 20件ずつドキュメントを処理

# 作業ディレクトリに移動
cd /Users/ookuboyoshinori/document_management_system

# 処理実行（エラーも出力に含める）
python3 process_queued_documents_v3.py --limit=20 2>&1

# 終了ステータスを返す
exit $?
