"""
全ドキュメントのembeddingを再生成（シンプル版）
OpenAI APIを直接使用
"""
import os
from supabase import create_client
from openai import OpenAI
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

# クライアント初期化
supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def main():
    print("="*80)
    print("全ドキュメント embedding 再生成スクリプト（シンプル版）")
    print("="*80)

    # 全ドキュメントを取得
    print("\n[Step 1] ドキュメント取得中...")
    result = supabase.table('source_documents').select('id,file_name,attachment_text,summary').execute()
    documents = result.data if result.data else []

    total = len(documents)
    print(f"対象ドキュメント数: {total} 件")

    if total == 0:
        print("ドキュメントが見つかりません")
        return

    # 確認
    print(f"\n{total}件のドキュメントのembeddingを再生成します")
    print("続行しますか？ (y/N): ", end='')
    response = input().strip().lower()
    if response != 'y':
        print("キャンセルしました")
        return

    # 各ドキュメントのembeddingを生成
    print("\n[Step 2] Embedding生成中...")
    success_count = 0
    error_count = 0

    for idx, doc in enumerate(documents, 1):
        doc_id = doc['id']
        file_name = doc.get('file_name', 'unknown')
        attachment_text = doc.get('attachment_text', '')
        summary = doc.get('summary', '')

        # テキストを結合（最大8000文字に制限）
        text_to_embed = (attachment_text if attachment_text else summary)[:8000]
        if not text_to_embed:
            print(f"[{idx}/{total}] スキップ: {file_name} (テキストなし)")
            error_count += 1
            continue

        try:
            # OpenAI APIで embedding を生成
            response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text_to_embed,
                dimensions=1536
            )
            embedding = response.data[0].embedding

            # PostgreSQL vector形式に変換
            embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

            # データベースを更新
            supabase.table('source_documents').update({
                'embedding': embedding_str
            }).eq('id', doc_id).execute()

            print(f"[{idx}/{total}] OK: {file_name}")
            success_count += 1

        except Exception as e:
            print(f"[{idx}/{total}] ERROR: {file_name} - {e}")
            error_count += 1

    print("\n" + "="*80)
    print("完了")
    print("="*80)
    print(f"成功: {success_count} 件")
    print(f"失敗: {error_count} 件")
    print(f"合計: {total} 件")
    print("="*80)

    if success_count > 0:
        print("\n次のステップ:")
        print("1. EMERGENCY_RESTORE_GUIDE.md のStep 3を実行")
        print("2. ベクトル検索機能を使う検索関数をSupabaseで実行")
        print("3. アプリケーションで検索をテスト")

if __name__ == "__main__":
    main()
