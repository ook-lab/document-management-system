#!/usr/bin/env python
"""
Embeddingテストスクリプト
次元数が1536であることを確認
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.ai.llm_client import LLMClient
from config.model_tiers import ModelTier


def test_embedding_dimensions():
    """Embeddingの次元数テスト"""
    print("=" * 60)
    print("Embeddingテスト開始")
    print("=" * 60)

    # 設定確認
    embedding_config = ModelTier.EMBEDDING
    print(f"\n【設定情報】")
    print(f"  モデル: {embedding_config['model']}")
    print(f"  期待次元数: {embedding_config['dimensions']}")
    print(f"  プロバイダー: {embedding_config['provider'].value}")

    # クライアント初期化
    print(f"\n【LLMクライアント初期化】")
    try:
        client = LLMClient()
        print("  ✓ 初期化成功")
    except Exception as e:
        print(f"  ✗ 初期化失敗: {e}")
        return False

    # Embedding生成テスト
    print(f"\n【Embedding生成テスト】")
    test_texts = [
        "これはテストです",
        "プロジェクトの納期は2024年3月31日です",
        "What is the meaning of life?"
    ]

    all_passed = True
    for idx, text in enumerate(test_texts, 1):
        try:
            print(f"\n  テスト{idx}: '{text}'")
            embedding = client.generate_embedding(text)

            # 次元数チェック
            actual_dim = len(embedding)
            expected_dim = embedding_config['dimensions']

            if actual_dim == expected_dim:
                print(f"    ✓ 次元数: {actual_dim} (期待値: {expected_dim})")
                print(f"    ✓ 最初の3要素: {embedding[:3]}")
                print(f"    ✓ 最後の3要素: {embedding[-3:]}")
            else:
                print(f"    ✗ 次元数エラー: {actual_dim} (期待値: {expected_dim})")
                all_passed = False

        except Exception as e:
            print(f"    ✗ エラー: {e}")
            all_passed = False

    # 結果サマリー
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ すべてのテストが成功しました")
        print("✓ Embeddingは1536次元で正しく生成されています")
    else:
        print("✗ 一部のテストが失敗しました")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = test_embedding_dimensions()
    sys.exit(0 if success else 1)
