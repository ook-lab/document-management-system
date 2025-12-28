#!/usr/bin/env python3
"""
失敗ドキュメントを分析・修正・再処理するプログラム

使い方:
    # 失敗を分析（実行しない）
    python3 retry_failed_documents.py --dry-run

    # 自動修正可能な失敗のみ再処理
    python3 retry_failed_documents.py --auto

    # 全ての失敗を再処理
    python3 retry_failed_documents.py --all
"""
import argparse
import json
from typing import List, Dict, Any
from A_common.database.client import DatabaseClient


class FailureAnalyzer:
    """失敗原因を分析して修正可能か判定"""

    # 自動修正可能なエラーパターン
    AUTO_RETRYABLE_PATTERNS = [
        "extract_text",  # extract_text() メソッド追加で修正済み
        "Stage E",       # Stage E の改善で修正可能
        "Stage H失敗: JSON抽出",  # プロンプト改善で修正可能
        "テキスト抽出エラー",  # OfficeProcessor修正で解決
    ]

    # 手動確認が必要なエラーパターン
    MANUAL_CHECK_PATTERNS = [
        "テキストが空",  # データ自体に問題
        "File not found",  # ファイルが存在しない
        "ダウンロード失敗",  # ネットワーク等の問題
    ]

    # データ不正で再処理不要なパターン
    SKIP_PATTERNS = [
        "動画ファイル",  # 意図的にスキップ
    ]

    @classmethod
    def categorize_error(cls, error_msg: str) -> str:
        """
        エラーをカテゴリ分類

        Returns:
            'auto_retry': 自動再処理推奨
            'manual_check': 手動確認必要
            'skip': 再処理不要
            'unknown': 不明（デフォルトは再処理推奨）
        """
        if not error_msg:
            return 'unknown'

        error_msg_lower = error_msg.lower()

        # スキップパターン
        for pattern in cls.SKIP_PATTERNS:
            if pattern.lower() in error_msg_lower:
                return 'skip'

        # 手動確認パターン
        for pattern in cls.MANUAL_CHECK_PATTERNS:
            if pattern.lower() in error_msg_lower:
                return 'manual_check'

        # 自動再処理パターン
        for pattern in cls.AUTO_RETRYABLE_PATTERNS:
            if pattern.lower() in error_msg_lower:
                return 'auto_retry'

        # 不明なエラーはデフォルトで再処理推奨
        return 'unknown'


def get_failed_documents(db: DatabaseClient) -> List[Dict[str, Any]]:
    """失敗したドキュメントを取得"""
    result = db.client.table('Rawdata_FILE_AND_MAIL').select(
        'id', 'file_name', 'workspace', 'doc_type', 'metadata', 'updated_at'
    ).eq('processing_status', 'failed').order('updated_at', desc=True).execute()

    return result.data


def extract_error_message(doc: Dict[str, Any]) -> str:
    """メタデータからエラーメッセージを抽出"""
    metadata = doc.get('metadata', {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            return "エラーメッセージなし"

    if isinstance(metadata, dict):
        return metadata.get('last_error', 'エラーメッセージなし')

    return "メタデータ不正"


def analyze_failures(db: DatabaseClient) -> Dict[str, List[Dict[str, Any]]]:
    """失敗をカテゴリ別に分析"""
    failed_docs = get_failed_documents(db)

    categorized = {
        'auto_retry': [],
        'manual_check': [],
        'skip': [],
        'unknown': []
    }

    for doc in failed_docs:
        error_msg = extract_error_message(doc)
        category = FailureAnalyzer.categorize_error(error_msg)

        categorized[category].append({
            'id': doc['id'],
            'file_name': doc.get('file_name', 'unknown'),
            'workspace': doc.get('workspace', 'unknown'),
            'doc_type': doc.get('doc_type', 'unknown'),
            'error': error_msg,
            'updated_at': doc.get('updated_at')
        })

    return categorized


def print_analysis(categorized: Dict[str, List[Dict[str, Any]]]):
    """分析結果を表示"""
    print('=' * 100)
    print('失敗ドキュメント分析結果')
    print('=' * 100)

    total = sum(len(docs) for docs in categorized.values())
    print(f'\n総失敗数: {total}件\n')

    # 自動再処理推奨
    auto_retry = categorized['auto_retry']
    if auto_retry:
        print(f'🔄 自動再処理推奨: {len(auto_retry)}件')
        print('   （コード修正により解決済みの可能性が高い）')
        for doc in auto_retry:
            print(f'   - {doc["file_name"]}')
            print(f'     エラー: {doc["error"]}')
        print()

    # 手動確認必要
    manual_check = categorized['manual_check']
    if manual_check:
        print(f'⚠️  手動確認必要: {len(manual_check)}件')
        print('   （データ不正やネットワークエラーの可能性）')
        for doc in manual_check:
            print(f'   - {doc["file_name"]}')
            print(f'     エラー: {doc["error"]}')
        print()

    # スキップ推奨
    skip = categorized['skip']
    if skip:
        print(f'⏭️  スキップ推奨: {len(skip)}件')
        print('   （意図的なスキップまたは再処理不要）')
        for doc in skip:
            print(f'   - {doc["file_name"]}')
            print(f'     エラー: {doc["error"]}')
        print()

    # 不明なエラー
    unknown = categorized['unknown']
    if unknown:
        print(f'❓ 不明なエラー: {len(unknown)}件')
        print('   （再処理を試す価値あり）')
        for doc in unknown:
            print(f'   - {doc["file_name"]}')
            print(f'     エラー: {doc["error"]}')
        print()

    print('=' * 100)


def reset_to_pending(db: DatabaseClient, doc_ids: List[str], category: str):
    """指定したドキュメントをpendingに戻す"""
    if not doc_ids:
        print(f'\n{category}: 対象ドキュメントなし')
        return

    print(f'\n{category}: {len(doc_ids)}件をpendingに変更中...')

    for doc_id in doc_ids:
        try:
            db.client.table('Rawdata_FILE_AND_MAIL').update({
                'processing_status': 'pending'
            }).eq('id', doc_id).execute()
        except Exception as e:
            print(f'ERROR: {doc_id} の更新に失敗: {e}')

    print(f'✅ {len(doc_ids)}件をpendingに変更しました')


def main():
    parser = argparse.ArgumentParser(description='失敗ドキュメントを分析・再処理')
    parser.add_argument('--dry-run', action='store_true',
                       help='分析のみ実行（再処理しない）')
    parser.add_argument('--auto', action='store_true',
                       help='自動再処理推奨のみpendingに戻す')
    parser.add_argument('--all', action='store_true',
                       help='全ての失敗（スキップ推奨以外）をpendingに戻す')

    args = parser.parse_args()

    db = DatabaseClient()

    # 失敗を分析
    categorized = analyze_failures(db)
    print_analysis(categorized)

    # Dry run（分析のみ）
    if args.dry_run:
        print('\n--dry-run モード: 再処理は実行しません')
        print('\n💡 再処理を実行するには:')
        print('   python3 retry_failed_documents.py --auto     # 自動修正可能な失敗のみ')
        print('   python3 retry_failed_documents.py --all      # 全ての失敗（スキップ以外）')
        return

    # 自動再処理モード
    if args.auto:
        auto_retry_ids = [doc['id'] for doc in categorized['auto_retry']]
        unknown_ids = [doc['id'] for doc in categorized['unknown']]

        reset_to_pending(db, auto_retry_ids, '自動再処理推奨')
        reset_to_pending(db, unknown_ids, '不明なエラー')

        if categorized['manual_check']:
            print(f'\n⚠️  手動確認必要: {len(categorized["manual_check"])}件は再処理されませんでした')
            print('   これらを再処理するには: python3 retry_failed_documents.py --all')

        return

    # 全て再処理モード
    if args.all:
        all_retry_ids = []
        for category in ['auto_retry', 'manual_check', 'unknown']:
            all_retry_ids.extend([doc['id'] for doc in categorized[category]])

        reset_to_pending(db, all_retry_ids, '全ての失敗（スキップ以外）')

        if categorized['skip']:
            print(f'\n⏭️  スキップ推奨: {len(categorized["skip"])}件は再処理されませんでした')

        return

    # オプション未指定の場合
    print('\n❗ モードを指定してください:')
    print('   --dry-run : 分析のみ')
    print('   --auto    : 自動修正可能な失敗のみ再処理')
    print('   --all     : 全ての失敗を再処理（スキップ推奨以外）')


if __name__ == '__main__':
    main()
