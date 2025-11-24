"""
2段階パイプラインのエラーハンドリング機能をテスト
"""

import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
import shutil

# テスト対象のインポート
from pipelines.two_stage_ingestion import TwoStageIngestionPipeline


class TestDBErrorHandling:
    """Step 1: DB保存エラーハンドリングのテスト"""

    @pytest.fixture
    def pipeline(self):
        """パイプラインインスタンスを作成（モック化）"""
        with patch('pipelines.two_stage_ingestion.GoogleDriveConnector'), \
             patch('pipelines.two_stage_ingestion.DatabaseClient'), \
             patch('pipelines.two_stage_ingestion.LLMClient'), \
             patch('pipelines.two_stage_ingestion.get_classification_yaml_string', return_value="mock yaml"):
            pipeline = TwoStageIngestionPipeline(temp_dir="./temp_test")
            yield pipeline
            # クリーンアップ
            if Path("./temp_test").exists():
                shutil.rmtree("./temp_test")
            if Path("logs/db_errors").exists():
                shutil.rmtree("logs/db_errors")

    @pytest.mark.asyncio
    async def test_db_save_failure_creates_fallback_file(self, pipeline):
        """
        テストケース 1: DB保存が失敗した際、ローカルにJSONファイルが生成される
        """
        # モックの設定
        file_meta = {
            'id': 'test_file_123',
            'name': 'test_document.pdf',
            'mimeType': 'application/pdf'
        }

        # DB保存時に例外を発生させる
        pipeline.db.insert_document = AsyncMock(side_effect=Exception("DB connection failed"))

        # get_document_by_source_id はNoneを返す（新規ファイル）
        pipeline.db.get_document_by_source_id = Mock(return_value=None)

        # ダウンロードをモック
        pipeline.drive.download_file = Mock(return_value="./temp_test/test_document.pdf")

        # Stage 1をモック
        pipeline.stage1_classifier.classify = AsyncMock(return_value={
            'doc_type': 'other',
            'workspace': 'personal',
            'summary': 'Test summary',
            'relevant_date': None,
            'confidence': 0.5
        })

        # テキスト抽出をモック（失敗させる）
        pipeline._extract_text = Mock(return_value={
            'success': False,
            'error_message': 'Extraction failed'
        })

        # 一時ファイルを作成
        Path("./temp_test").mkdir(parents=True, exist_ok=True)
        Path("./temp_test/test_document.pdf").touch()

        # process_file を実行
        result = await pipeline.process_file(file_meta, workspace='personal')

        # 結果の検証
        assert result is None  # エラー時はNoneを返す

        # fallbackファイルが作成されたことを確認
        fallback_dir = Path('logs/db_errors')
        assert fallback_dir.exists(), "fallback directory should be created"

        # JSONファイルが存在することを確認
        fallback_files = list(fallback_dir.glob('db_error_*.json'))
        assert len(fallback_files) > 0, "At least one fallback file should be created"

        # JSONファイルの内容を検証
        with open(fallback_files[0], 'r', encoding='utf-8') as f:
            fallback_data = json.load(f)

        assert 'error_data' in fallback_data
        assert 'db_error' in fallback_data
        assert 'db_error_traceback' in fallback_data
        assert 'timestamp' in fallback_data

        assert fallback_data['error_data']['source_id'] == 'test_file_123'
        assert fallback_data['error_data']['file_name'] == 'test_document.pdf'
        assert fallback_data['error_data']['processing_status'] == 'failed'
        assert 'DB connection failed' in fallback_data['db_error']


class TestStage2ErrorRecording:
    """Step 2: Stage 2エラー記録のテスト"""

    @pytest.fixture
    def pipeline(self):
        """パイプラインインスタンスを作成（モック化）"""
        with patch('pipelines.two_stage_ingestion.GoogleDriveConnector'), \
             patch('pipelines.two_stage_ingestion.DatabaseClient'), \
             patch('pipelines.two_stage_ingestion.LLMClient'), \
             patch('pipelines.two_stage_ingestion.get_classification_yaml_string', return_value="mock yaml"):
            pipeline = TwoStageIngestionPipeline(temp_dir="./temp_test")
            yield pipeline
            # クリーンアップ
            if Path("./temp_test").exists():
                shutil.rmtree("./temp_test")

    @pytest.mark.asyncio
    async def test_stage2_error_recorded_in_metadata(self, pipeline):
        """
        テストケース 2: Stage 2がエラーになった際、metadataにエラー情報が記録される
        """
        # モックの設定
        file_meta = {
            'id': 'test_file_456',
            'name': 'test_document.pdf',
            'mimeType': 'application/pdf'
        }

        # DB保存は成功させる
        captured_document_data = {}

        async def capture_insert(table, data):
            captured_document_data.update(data)
            return {'id': 1, **data}

        pipeline.db.insert_document = AsyncMock(side_effect=capture_insert)
        pipeline.db.get_document_by_source_id = Mock(return_value=None)

        # ダウンロードをモック
        pipeline.drive.download_file = Mock(return_value="./temp_test/test_document.pdf")

        # Stage 1をモック（信頼度を低くしてStage 2を実行させる）
        pipeline.stage1_classifier.classify = AsyncMock(return_value={
            'doc_type': 'other',
            'workspace': 'personal',
            'summary': 'Test summary',
            'relevant_date': None,
            'confidence': 0.5  # 低信頼度
        })

        # テキスト抽出は成功させる
        pipeline._extract_text = Mock(return_value={
            'success': True,
            'content': 'This is a test document with enough text to trigger Stage 2 processing.',
            'metadata': {}
        })

        # Stage 2をモック（エラーを発生させる）
        pipeline.stage2_extractor.extract_metadata = Mock(
            side_effect=Exception("Stage 2 processing failed")
        )

        # Embedding生成をモック
        pipeline.llm_client.generate_embedding = Mock(return_value=[0.1] * 1536)

        # 一時ファイルを作成
        Path("./temp_test").mkdir(parents=True, exist_ok=True)
        Path("./temp_test/test_document.pdf").touch()

        # process_file を実行
        result = await pipeline.process_file(file_meta, workspace='personal')

        # 結果の検証
        assert result is not None, "Should return a result even with Stage 2 error"

        # processing_stage が 'stage2_failed' であることを確認
        assert captured_document_data['processing_stage'] == 'stage2_failed'

        # metadata にエラー情報が含まれていることを確認
        metadata = captured_document_data['metadata']
        assert 'stage2_attempted' in metadata
        assert metadata['stage2_attempted'] is True
        assert 'stage2_error' in metadata
        assert 'Stage 2 processing failed' in metadata['stage2_error']
        assert 'stage2_error_type' in metadata
        assert metadata['stage2_error_type'] == 'Exception'
        assert 'stage2_error_timestamp' in metadata


class TestExitCodeLogic:
    """Step 3: 終了コードロジックのテスト"""

    def test_exit_code_all_success(self):
        """
        テストケース 3a: 全ファイル成功時、終了コード0が返される
        """
        stats = {
            'total_files': 10,
            'processed_success': 10,
            'processed_failed': 0
        }

        # 終了コードロジックをシミュレート
        exit_code = self._calculate_exit_code(stats)
        assert exit_code == 0

    def test_exit_code_high_failure_rate(self):
        """
        テストケース 3b: 失敗率50%以上で終了コード1が返される
        """
        stats = {
            'total_files': 10,
            'processed_success': 4,
            'processed_failed': 6
        }

        exit_code = self._calculate_exit_code(stats)
        assert exit_code == 1

    def test_exit_code_partial_failure(self):
        """
        テストケース 3c: 一部失敗（失敗率50%未満）で終了コード2が返される
        """
        stats = {
            'total_files': 10,
            'processed_success': 8,
            'processed_failed': 2
        }

        exit_code = self._calculate_exit_code(stats)
        assert exit_code == 2

    def test_exit_code_no_files(self):
        """
        テストケース 3d: 処理対象ファイル0件で終了コード3が返される
        """
        stats = {
            'total_files': 0,
            'processed_success': 0,
            'processed_failed': 0
        }

        exit_code = self._calculate_exit_code(stats)
        assert exit_code == 3

    def _calculate_exit_code(self, stats):
        """scripts/daily_sync.py のロジックを模倣"""
        if stats['total_files'] == 0:
            return 3

        failure_rate = stats['processed_failed'] / stats['total_files']

        if failure_rate >= 0.5:
            return 1
        elif stats['processed_failed'] > 0:
            return 2
        else:
            return 0
