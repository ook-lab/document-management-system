"""利用可能なモデルを確認"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .envファイルを読み込み
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

print("=" * 50)
print("利用可能なモデルを確認")
print("=" * 50)

# Claude
print("\n--- Claude (Anthropic) ---")
try:
    from anthropic import Anthropic
    client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    
    # 実際にリクエストを送って確認
    # Claude 4.5 Sonnetの可能性があるモデル名を試す
    test_models = [
        "claude-sonnet-4-5-20250929",  # Claude 4.5の可能性
        "claude-4-sonnet-20250514",
        "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-latest",
        "claude-3-5-sonnet-20241022",
        "claude-3-sonnet-20240229"
    ]
    
    for model in test_models:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            print(f"✅ 利用可能: {model}")
            break  # 最初に成功したモデルで終了
        except Exception as e:
            if "404" in str(e) or "not_found" in str(e):
                print(f"❌ 利用不可: {model}")
            else:
                print(f"⚠️ エラー ({model}): {e}")
                
except Exception as e:
    print(f"❌ Claude接続エラー: {e}")

# OpenAI
print("\n--- OpenAI (GPT) ---")
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # GPT-5.1の可能性があるモデル名を試す
    test_models = [
        "gpt-5.1",
        "gpt-4o",  # 最新の高性能モデル
        "gpt-4-turbo",
        "gpt-4-turbo-preview",
        "gpt-4"
    ]
    
    for model in test_models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            print(f"✅ 利用可能: {model}")
            break  # 最初に成功したモデルで終了
        except Exception as e:
            if "404" in str(e) or "does not exist" in str(e):
                print(f"❌ 利用不可: {model}")
            else:
                print(f"⚠️ エラー ({model}): {e}")
                
except Exception as e:
    print(f"❌ OpenAI接続エラー: {e}")

print("\n" + "=" * 50)
