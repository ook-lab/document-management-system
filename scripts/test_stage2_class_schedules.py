#!/usr/bin/env python3
"""
Stage 2 class_schedules抽出テスト

既存の「学年通信 (28).pdf」のfull_textを使用して、
Stage 2の詳細抽出（特にclass_schedules）をテストします。
"""
import sys
import os
import json

# プロジェクトルートをPythonパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from supabase import create_client
from config.settings import settings
from core.ai.stage2_extractor import Stage2Extractor
from core.ai.llm_client import LLMClient


def test_class_schedules_extraction(doc_id: str):
    """
    指定されたドキュメントIDのfull_textを使用してStage 2抽出をテスト

    Args:
        doc_id: ドキュメントID (例: 70551c94-8bfa-4488-a4ca-ef23575ccb84)
    """

    # Supabaseクライアント初期化
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        print("❌ エラー: SUPABASE_URL と SUPABASE_KEY が設定されていません")
        sys.exit(1)

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    print(f"🔍 ドキュメントID: {doc_id}")
    print("=" * 80)

    try:
        # ドキュメント取得
        response = client.table('documents').select(
            'id, file_name, doc_type, full_text, metadata'
        ).eq('id', doc_id).execute()

        if not response.data or len(response.data) == 0:
            print(f"❌ ドキュメントが見つかりません: {doc_id}")
            sys.exit(1)

        doc = response.data[0]
        file_name = doc.get('file_name')
        doc_type = doc.get('doc_type')
        full_text = doc.get('full_text', '')
        old_metadata = doc.get('metadata', {})

        print(f"📄 ファイル名: {file_name}")
        print(f"📋 ドキュメントタイプ: {doc_type}")
        print(f"📝 テキスト長: {len(full_text)} 文字")
        print("\n" + "=" * 80)

        if not full_text:
            print("❌ full_textが空です")
            sys.exit(1)

        # Stage 2抽出実行
        print("\n🤖 Stage 2 詳細抽出を実行中...\n")

        llm_client = LLMClient()
        stage2_extractor = Stage2Extractor(llm_client=llm_client)

        # Stage 1結果をモック（既存のdoc_typeとconfidenceを使用）
        stage1_result = {
            'doc_type': doc_type,
            'confidence': 0.64,  # 既存の信頼度
            'summary': '洗足学園小学校5年生向けの学年通信'
        }

        stage2_result = stage2_extractor.extract_metadata(
            full_text=full_text,
            file_name=file_name,
            stage1_result=stage1_result,
            workspace='family'
        )

        print("=" * 80)
        print("✅ Stage 2 抽出完了")
        print("=" * 80)

        # 結果を表示
        print(f"\n📊 抽出結果:")
        print(f"  doc_type: {stage2_result.get('doc_type')}")
        print(f"  summary: {stage2_result.get('summary')}")
        print(f"  document_date: {stage2_result.get('document_date')}")
        print(f"  extraction_confidence: {stage2_result.get('extraction_confidence')}")
        print(f"  tags: {stage2_result.get('tags')}")

        # metadataを詳細表示
        metadata = stage2_result.get('metadata', {})
        print(f"\n📋 メタデータ ({len(metadata)} フィールド):")
        print(json.dumps(metadata, ensure_ascii=False, indent=2))

        # weekly_scheduleの有無を確認
        print("\n" + "=" * 80)
        if 'weekly_schedule' in metadata:
            print("✅ weekly_schedule フィールドが存在します")
            weekly_schedule = metadata['weekly_schedule']
            print(f"   週間スケジュール件数: {len(weekly_schedule)}")

            # class_schedulesの確認
            has_class_schedules = False
            for day_idx, day_info in enumerate(weekly_schedule):
                if 'class_schedules' in day_info:
                    has_class_schedules = True
                    print(f"\n   📅 {day_info.get('date')} ({day_info.get('day')}):")
                    print(f"      ✅ class_schedules が抽出されました！")
                    class_schedules = day_info['class_schedules']
                    for class_info in class_schedules:
                        class_name = class_info.get('class', '不明')
                        subjects = class_info.get('subjects', [])
                        print(f"      - {class_name}: {len(subjects)} 科目")
                        for subject in subjects[:3]:  # 最初の3科目を表示
                            print(f"          {subject}")
                        if len(subjects) > 3:
                            print(f"          ... 他 {len(subjects) - 3} 科目")

            if has_class_schedules:
                print("\n🎉 class_schedules の抽出に成功しました！")
            else:
                print("\n⚠️  class_schedules フィールドが見つかりませんでした")
                print("   （このドキュメントにクラス別時間割が含まれていない可能性があります）")
        else:
            print("⚠️  weekly_schedule フィールドが見つかりませんでした")

        print("=" * 80)

        # 旧メタデータとの比較
        print("\n📊 旧メタデータとの比較:")
        old_weekly = old_metadata.get('weekly_schedule', [])
        new_weekly = metadata.get('weekly_schedule', [])
        print(f"  旧: {len(old_weekly)} 日分")
        print(f"  新: {len(new_weekly)} 日分")

        if old_weekly and new_weekly:
            # 最初の日を比較
            if len(old_weekly) > 0 and len(new_weekly) > 0:
                print("\n  1日目の比較:")
                print(f"    旧キー: {list(old_weekly[0].keys())}")
                print(f"    新キー: {list(new_weekly[0].keys())}")

                if 'class_schedules' in new_weekly[0] and 'class_schedules' not in old_weekly[0]:
                    print("    ✅ 新しいフィールド 'class_schedules' が追加されました！")

        print("\n" + "=" * 80)

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """メインエントリーポイント"""
    if len(sys.argv) < 2:
        print("使用方法: python scripts/test_stage2_class_schedules.py <ドキュメントID>")
        print("例: python scripts/test_stage2_class_schedules.py 70551c94-8bfa-4488-a4ca-ef23575ccb84")
        sys.exit(1)

    doc_id = sys.argv[1]
    test_class_schedules_extraction(doc_id)


if __name__ == "__main__":
    main()
