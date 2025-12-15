"""
ローカルPDFでVision処理をテスト
"""
from A_common.processors.pdf import PDFProcessor
from C_ai_common.llm_client.llm_client import LLMClient

# LLMClientとPDFProcessorを初期化
llm_client = LLMClient()
pdf_processor = PDFProcessor(llm_client=llm_client)

# PDF処理
pdf_path = "/Users/ookuboyoshinori/document_management_system/学年通信（29）.pdf"

print(f"📄 PDF処理開始: {pdf_path}")
print("=" * 80)

result = pdf_processor.extract_text(pdf_path)

if result["success"]:
    print("✅ 抽出成功")
    print(f"\nテキスト長: {len(result['content'])} 文字")
    print(f"\nメタデータ:")
    print(f"  - ページ数: {result['metadata'].get('num_pages')}")
    print(f"  - 抽出方法: {result['metadata'].get('extractor')}")
    print(f"  - Vision補完: {result['metadata'].get('vision_supplemented', False)}")
    print(f"  - Visionページ数: {result['metadata'].get('vision_pages', 0)}")
    print(f"  - pdfplumber表数: {result['metadata'].get('pdfplumber_tables', 0)}")

    # 最初の3000文字を表示
    print(f"\n=== 抽出テキスト（最初の3000文字） ===")
    print(result['content'][:3000])

    # Vision補完部分を探す
    if "Vision Supplement" in result['content']:
        print("\n=== Vision補完が検出されました！ ===")
        # Vision部分を抽出
        vision_start = result['content'].find("--- Vision Supplement ---")
        vision_end = result['content'].find("--- Page", vision_start + 1)
        if vision_end == -1:
            vision_end = len(result['content'])

        vision_content = result['content'][vision_start:vision_end]
        print(vision_content[:2000])
    else:
        print("\n⚠️  Vision補完は実行されませんでした")

else:
    print(f"❌ 抽出失敗: {result.get('error_message')}")
