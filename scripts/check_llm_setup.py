"""
初期動作確認スクリプト (LLMクライアント)
- 各AIプロバイダーへの接続とレスポンスを確認する
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ai.llm_client import LLMClient

# .envファイルを読み込み
load_dotenv()

def check_ai_connection():
    """全AIプロバイダーへの接続をチェック"""
    print("=" * 50)
    print("🚀 LLMクライアント接続テスト開始")
    print("=" * 50)

    try:
        # LLMClientを初期化（環境変数からキーを読み込む）
        client = LLMClient()
    except Exception as e:
        print(f"❌ LLMClient初期化エラー: {e}")
        return

    # --- 1. Gemini (Stage 1) テスト ---
    print("\n--- 1. Gemini (Stage 1 Classifier) ---")
    try:
        # NOTE: ファイルなしでの簡単なプロンプトで接続確認
        prompt = "この文書のdoc_typeを'timetable'または'other'のどちらかに分類し、JSON形式で回答してください: \"明日の数学のテスト範囲\""
        
        response = client.call_model(
            tier="stage1_classification", 
            prompt=prompt
        )
        
        if response.get("success"):
            print(f"✅ Gemini接続成功 (モデル: {response['model']})")
            print(f"   レスポンス抜粋: {response['content'][:50]}...")
        else:
            print(f"❌ Gemini接続失敗: {response['error']}")
    except Exception as e:
        print(f"❌ Geminiテスト中に例外発生: {e}")

    # --- 2. Claude (Stage 2) テスト ---
    print("\n--- 2. Claude (Stage 2 Extractor) ---")
    try:
        prompt = "以下の内容から日付と場所をJSONで抽出してください: 会議は2025年1月10日に東京本社で行われます。"
        
        response = client.call_model(
            tier="stage2_extraction", 
            prompt=prompt
        )
        
        if response.get("success"):
            print(f"✅ Claude接続成功 (モデル: {response['model']})")
            print(f"   レスポンス抜粋: {response['content'][:50]}...")
        else:
            print(f"❌ Claude接続失敗: {response['error']}")
    except Exception as e:
        print(f"❌ Claudeテスト中に例外発生: {e}")
        
    # --- 3. OpenAI (UI/Embedding) テスト ---
    print("\n--- 3. OpenAI (UI Responder/Embedding) ---")
    
    # 3a. UI Responderテスト
    try:
        prompt = "以下の情報を親切な日本語で要約してください: 山田太郎は明日、理科のテストを午後1時に受けます。"
        
        response = client.call_model(
            tier="ui_response", 
            prompt=prompt
        )
        
        if response.get("success"):
            print(f"✅ GPT (UI) 接続成功 (モデル: {response['model']})")
            print(f"   レスポンス抜粋: {response['content'][:50]}...")
        else:
            print(f"❌ GPT (UI) 接続失敗: {response['error']}")
    except Exception as e:
        print(f"❌ GPT (UI) テスト中に例外発生: {e}")

    # 3b. Embeddingテスト
    try:
        embedding = client.generate_embedding("テスト用の文書を埋め込み化します。")
        if embedding and len(embedding) == 1536: # text-embedding-3-smallの次元数
            print(f"✅ Embedding生成成功 (次元数: {len(embedding)})")
        else:
            print(f"❌ Embedding生成失敗 (次元数: {len(embedding)})")
    except Exception as e:
        print(f"❌ Embeddingテスト中に例外発生: {e}")
        
    print("\n=" * 50)
    print("テスト完了。❌ がある場合は.envとSecretsを確認してください。")
    print("=" * 50)

if __name__ == "__main__":
    check_ai_connection()