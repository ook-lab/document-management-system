"""
LLMClient の _call_claude メソッドのリトライロジックをテスト
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from anthropic import RateLimitError, APIError
from tenacity import RetryError
from C_ai_common.llm_client.llm_client import LLMClient
from A_common.config.model_tiers import AIProvider


class TestLLMClientRetry:
    """LLMClient のリトライ機能のテスト"""

    @pytest.fixture
    def llm_client(self):
        """LLMClientインスタンスを作成（モック化されたAnthropicクライアント付き）"""
        with patch.dict('os.environ', {
            'ANTHROPIC_API_KEY': 'test-api-key',
            'GOOGLE_AI_API_KEY': 'test-google-key',
            'OPENAI_API_KEY': 'test-openai-key'
        }):
            client = LLMClient()
            # Anthropicクライアントをモック化
            client.anthropic_client = MagicMock()
            return client

    def test_rate_limit_error_retries_5_times_then_fails(self, llm_client):
        """
        テストケース 1: RateLimitError が発生し、5回のリトライ後に失敗
        """
        # RateLimitErrorをモック（常に失敗）
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}}
        )
        llm_client.anthropic_client.messages.create.side_effect = rate_limit_error

        # モデル設定をモック
        config = {"max_tokens": 4096, "temperature": 0.0}

        # _call_claude を呼び出し（RetryErrorが発生することを期待）
        with pytest.raises(RetryError) as exc_info:
            llm_client._call_claude(
                model_name="claude-sonnet-4-5-20250929",
                prompt="Test prompt",
                config=config
            )

        # リトライが5回実行されたことを確認（初回 + 4回のリトライ = 合計5回）
        assert llm_client.anthropic_client.messages.create.call_count == 5

        # RetryErrorから元のエラーを取得できることを確認
        retry_error = exc_info.value
        original_error = retry_error.last_attempt.exception()
        assert isinstance(original_error, RateLimitError)
        assert "Rate limit exceeded" in str(original_error)

    def test_rate_limit_error_recovers_on_second_retry(self, llm_client):
        """
        テストケース 2: RateLimitError が発生し、2回目のリトライで成功
        """
        # 最初の呼び出しでRateLimitError、2回目で成功するようにモック
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}}
        )

        # 成功時のレスポンスをモック
        success_response = Mock()
        success_response.content = [Mock(text="Success response")]

        # 最初の呼び出しで失敗、2回目で成功
        llm_client.anthropic_client.messages.create.side_effect = [
            rate_limit_error,  # 1回目: 失敗
            success_response   # 2回目: 成功
        ]

        config = {"max_tokens": 4096, "temperature": 0.0}

        # _call_claude を呼び出し
        result = llm_client._call_claude(
            model_name="claude-sonnet-4-5-20250929",
            prompt="Test prompt",
            config=config
        )

        # 2回呼び出されたことを確認（初回失敗 + 1回目のリトライで成功）
        assert llm_client.anthropic_client.messages.create.call_count == 2

        # 成功レスポンスが返されることを確認
        assert result["success"] is True
        assert result["content"] == "Success response"
        assert result["model"] == "claude-sonnet-4-5-20250929"
        assert result["provider"] == "claude"

    def test_non_rate_limit_error_fails_immediately(self, llm_client):
        """
        テストケース 3: RateLimitError 以外のエラーはリトライせず即座に失敗
        """
        # APIError（401認証エラーなど）をモック
        api_error = APIError(
            message="Invalid API key",
            request=Mock(),
            body={"error": {"message": "Invalid API key"}}
        )
        llm_client.anthropic_client.messages.create.side_effect = api_error

        config = {"max_tokens": 4096, "temperature": 0.0}

        # _call_claude を呼び出し
        result = llm_client._call_claude(
            model_name="claude-sonnet-4-5-20250929",
            prompt="Test prompt",
            config=config
        )

        # 1回だけ呼び出されたことを確認（リトライなし）
        assert llm_client.anthropic_client.messages.create.call_count == 1

        # エラーレスポンスが返されることを確認
        assert result["success"] is False
        assert "Invalid API key" in result["error"]
        assert result["model"] == "claude-sonnet-4-5-20250929"
        assert result["provider"] == "claude"

    def test_call_model_handles_retry_error_gracefully(self, llm_client):
        """
        テストケース 4: call_model メソッド経由で RetryError が適切に処理される
        """
        # RateLimitErrorをモック（常に失敗）
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}}
        )
        llm_client.anthropic_client.messages.create.side_effect = rate_limit_error

        # call_model を使用して呼び出し
        with patch('core.ai.llm_client.get_model_config') as mock_config:
            mock_config.return_value = {
                "provider": AIProvider.CLAUDE,
                "model": "claude-sonnet-4-5-20250929",
                "max_tokens": 4096,
                "temperature": 0.0
            }

            result = llm_client.call_model(
                tier="stage2_extraction",
                prompt="Test prompt"
            )

        # リトライが5回実行されたことを確認
        assert llm_client.anthropic_client.messages.create.call_count == 5

        # エラーレスポンスが返されることを確認（RetryErrorではなく、適切なエラー辞書）
        assert result["success"] is False
        assert "Rate limit exceeded" in result["error"]
        assert result["model"] == "claude-sonnet-4-5-20250929"
        assert result["provider"] == "claude"
