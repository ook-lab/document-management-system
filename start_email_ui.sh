#!/bin/bash

# メール受信トレイUI起動スクリプト

echo "📬 メール受信トレイUIを起動します..."
echo ""
echo "ブラウザで http://localhost:8501 を開いてください"
echo ""
echo "終了するには Ctrl+C を押してください"
echo ""

# 仮想環境をアクティベート
source venv/bin/activate

# Streamlitを起動
streamlit run ui/email_inbox.py
