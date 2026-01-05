"""
リセット結果を検証する
"""
from A_common.database.client import DatabaseClient

def verify_reset():
    db = DatabaseClient(use_service_role=True)

    # pending状態のドキュメントを取得
    result = db.client.table('Rawdata_FILE_AND_MAIL')\
        .select('id, file_name, title, processing_status, workspace, stage_e1_text, stage_f_text_ocr, stage_h_normalized, stage_i_structured, stage_j_chunks_json')\
        .eq('processing_status', 'pending')\
        .execute()

    print(f"pending状態のドキュメント: {len(result.data)}件\n")

    # ワークスペース別集計
    workspace_counts = {}
    for doc in result.data:
        ws = doc.get('workspace', '(不明)')
        workspace_counts[ws] = workspace_counts.get(ws, 0) + 1

    print("ワークスペース別:")
    for ws, count in workspace_counts.items():
        print(f"  - {ws}: {count}件")

    # ステージフィールドが全てNullかチェック
    print("\n最初の5件のステージフィールドチェック:")
    for i, doc in enumerate(result.data[:5]):
        title = doc.get('title', doc.get('file_name', '(名前なし)'))
        ws = doc.get('workspace', '不明')

        # ステージフィールドが全てNullかチェック
        stage_fields = {
            'stage_e1_text': doc.get('stage_e1_text'),
            'stage_f_text_ocr': doc.get('stage_f_text_ocr'),
            'stage_h_normalized': doc.get('stage_h_normalized'),
            'stage_i_structured': doc.get('stage_i_structured'),
            'stage_j_chunks_json': doc.get('stage_j_chunks_json'),
        }

        all_null = all(v is None for v in stage_fields.values())
        status = "OK (全てNull)" if all_null else "NG (一部データ残存)"

        print(f"\n{i+1}. [{ws}] {title}")
        print(f"   ステータス: {status}")
        if not all_null:
            for field, value in stage_fields.items():
                if value is not None:
                    value_preview = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                    print(f"   - {field}: {value_preview}")

if __name__ == '__main__':
    verify_reset()
