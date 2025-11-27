"""
LLMクライアント（v3.0: マルチプロバイダ対応）
Gemini / Claude / OpenAI を統一インターフェースで利用
"""

import os
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import json
import mimetypes

import google.generativeai as genai
from anthropic import Anthropic, RateLimitError
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError

from config.model_tiers import AIProvider, ModelTier, get_model_config

class LLMClient:
    """統合LLMクライアント"""
    
    def __init__(self):
        """環境変数からAPIキーを取得し、各プロバイダーを初期化"""

        self.gemini_api_key = os.getenv("GOOGLE_AI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        # Gemini設定 (最新SDK対応)
        if self.gemini_api_key:
            # 旧方式の設定も維持（GenerativeModel用）
            genai.configure(api_key=self.gemini_api_key)
            # 最新のClientインスタンスを作成（ファイル操作用）
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_api_key)
            except AttributeError:
                # genai.Clientが存在しない場合はNone
                self.gemini_client = None
        else:
            self.gemini_client = None

        # Claude設定
        if self.anthropic_api_key:
            self.anthropic_client = Anthropic(api_key=self.anthropic_api_key)
        else:
            self.anthropic_client = None

        # OpenAI設定
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        else:
            self.openai_client = None
    
    def call_model(
        self,
        tier: str,
        prompt: str,
        file_path: Optional[Path] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        指定されたタスクに最適なモデルを呼び出し
        
        Args:
            tier: モデル階層("stage1_classification", "stage2_extraction", "ui_response")
            prompt: プロンプト
            file_path: ファイルパス (GeminiのStage 1分類用)
            **kwargs: 追加パラメータ
        
        Returns:
            モデルレスポンス
        """
        config = get_model_config(tier)
        provider = config["provider"]
        model_name = config["model"]
        
        if provider == AIProvider.GEMINI:
            if not self.gemini_api_key:
                return {"success": False, "error": "Gemini API key is missing", "model": model_name}
            return self._call_gemini(model_name, prompt, file_path, config, **kwargs)
        
        elif provider == AIProvider.CLAUDE:
            if not self.anthropic_client:
                return {"success": False, "error": "Claude API key is missing", "model": model_name}
            try:
                return self._call_claude(model_name, prompt, config, **kwargs)
            except RetryError as e:
                # リトライが全て失敗した場合
                original_error = e.last_attempt.exception()
                return {"success": False, "error": str(original_error), "model": model_name, "provider": "claude"}
        
        elif provider == AIProvider.OPENAI:
            if not self.openai_client:
                return {"success": False, "error": "OpenAI API key is missing", "model": model_name}
            return self._call_openai(model_name, prompt, config, **kwargs)
        
        else:
            raise ValueError(f"未対応のプロバイダー: {provider}")

    def _call_gemini(
        self,
        model_name: str,
        prompt: str,
        file_path: Optional[Path],
        config: Dict,
        **kwargs
    ) -> Dict[str, Any]:
        """Gemini API呼び出し（最新SDK対応）"""
        uploaded_file = None
        try:
            model = genai.GenerativeModel(model_name)

            content_parts = [prompt]

            if file_path and file_path.exists():
                # MIMEタイプを自動判定
                mime_type, _ = mimetypes.guess_type(str(file_path))
                if not mime_type:
                    mime_type = "application/pdf"  # デフォルト

                # ファイルをアップロード（最新API使用）
                if self.gemini_client:
                    # 最新のClient APIを使用
                    uploaded_file = self.gemini_client.files.upload(
                        path=str(file_path),
                        config={
                            "mime_type": mime_type
                        }
                    )
                else:
                    # フォールバック: 旧APIを試行
                    try:
                        uploaded_file = genai.upload_file(path=str(file_path), mime_type=mime_type)
                    except AttributeError as e:
                        return {
                            "success": False,
                            "error": f"Gemini file upload API not available: {str(e)}",
                            "model": model_name,
                            "provider": "gemini"
                        }

                content_parts.append(uploaded_file)

            response = model.generate_content(
                content_parts,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=config.get("max_tokens", 2000),
                    temperature=config.get("temperature", 0.1)
                )
            )

            # レスポンスの検証
            if not response.candidates:
                self._cleanup_uploaded_file(uploaded_file)
                return {"success": False, "error": "Gemini returned no candidates", "model": model_name, "provider": "gemini"}

            candidate = response.candidates[0]

            # finish_reason をチェック
            if candidate.finish_reason != 1:  # 1 = STOP (正常終了)
                self._cleanup_uploaded_file(uploaded_file)
                return {
                    "success": False,
                    "error": f"Gemini finish_reason: {candidate.finish_reason}",
                    "model": model_name,
                    "provider": "gemini"
                }

            # テキストを取得
            text_content = candidate.content.parts[0].text if candidate.content.parts else ""

            # ファイルを削除
            self._cleanup_uploaded_file(uploaded_file)

            return {
                "success": True,
                "content": text_content,
                "model": model_name,
                "provider": "gemini"
            }

        except Exception as e:
            self._cleanup_uploaded_file(uploaded_file)
            return {"success": False, "error": str(e), "model": model_name, "provider": "gemini"}

    def _cleanup_uploaded_file(self, uploaded_file) -> None:
        """
        アップロードされたファイルを削除（最新SDK対応）

        Args:
            uploaded_file: アップロードされたファイルオブジェクト
        """
        if not uploaded_file:
            return

        try:
            if self.gemini_client:
                # 最新のClient APIを使用
                self.gemini_client.files.delete(name=uploaded_file.name)
            else:
                # フォールバック: 旧APIを試行
                try:
                    genai.delete_file(name=uploaded_file.name)
                except AttributeError:
                    # どちらのAPIも利用できない場合は警告のみ
                    pass
        except Exception:
            # 削除に失敗しても処理は継続
            pass

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60)
    )
    def _call_claude(
        self,
        model_name: str,
        prompt: str,
        config: Dict,
        **kwargs
    ) -> Dict[str, Any]:
        """Claude API呼び出し"""
        try:
            response = self.anthropic_client.messages.create(
                model=model_name,
                max_tokens=config.get("max_tokens", 4096),
                temperature=config.get("temperature", 0.0),
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            return {
                "success": True,
                "content": response.content[0].text,
                "model": model_name,
                "provider": "claude"
            }

        except RateLimitError:
            # RateLimitErrorは再スローしてtenacityにリトライさせる
            raise
        except Exception as e:
            return {"success": False, "error": str(e), "model": model_name, "provider": "claude"}

    def _call_openai(
        self,
        model_name: str,
        prompt: str,
        config: Dict,
        **kwargs
    ) -> Dict[str, Any]:
        """OpenAI API呼び出し"""
        try:
            max_tokens = config.get("max_tokens", 2048)
            
            response = self.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=config.get("temperature", 0.7)
            )
            
            return {
                "success": True,
                "content": response.choices[0].message.content,
                "model": model_name,
                "provider": "openai"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e), "model": model_name, "provider": "openai"}

    def generate_embedding(self, text: str) -> List[float]:
        """
        Embedding生成

        Args:
            text: Embeddingを生成するテキスト

        Returns:
            1536次元のembeddingベクトル
        """
        config = get_model_config("embeddings")

        if not self.openai_client:
            raise ConnectionError("OpenAI client not initialized for embedding generation.")

        # text-embedding-3-smallモデルで1536次元を明示的に指定
        response = self.openai_client.embeddings.create(
            model=config["model"],
            input=text,
            dimensions=config.get("dimensions", 1536)  # デフォルト1536次元
        )

        return response.data[0].embedding