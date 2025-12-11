"""
リランク（Reranking）

検索結果を再スコアリングして、最も関連性の高い結果のみを返します。
ベクトル検索で取得した上位50件を、より精密なモデルで再評価します。
"""
from typing import List, Dict, Any, Optional
from loguru import logger
import os


class Reranker:
    """検索結果を再スコアリングするリランカー"""

    def __init__(self, provider: str = "cohere", api_key: Optional[str] = None):
        """
        Args:
            provider: リランクプロバイダー ("cohere" or "huggingface")
            api_key: APIキー（Cohereの場合のみ必要）
        """
        self.provider = provider
        self.api_key = api_key or os.getenv("COHERE_API_KEY")

        if provider == "cohere" and not self.api_key:
            logger.warning("[Reranker] Cohere API key not found, falling back to huggingface")
            self.provider = "huggingface"

        self._initialize_model()

    def _initialize_model(self):
        """リランクモデルの初期化"""
        if self.provider == "cohere":
            try:
                import cohere
                self.client = cohere.Client(self.api_key)
                logger.info("[Reranker] Cohere Rerank initialized")
            except ImportError:
                logger.warning("[Reranker] cohere package not installed, falling back to huggingface")
                self.provider = "huggingface"
                self._initialize_huggingface()
        else:
            self._initialize_huggingface()

    def _initialize_huggingface(self):
        """Hugging Faceモデルの初期化"""
        try:
            from sentence_transformers import CrossEncoder
            # 日本語対応の軽量クロスエンコーダー
            self.model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            logger.info("[Reranker] Hugging Face CrossEncoder initialized")
        except ImportError:
            logger.error("[Reranker] sentence-transformers not installed")
            self.model = None

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        text_key: str = "chunk_text"
    ) -> List[Dict[str, Any]]:
        """
        検索結果を再スコアリング

        Args:
            query: ユーザーのクエリ
            documents: 検索結果のリスト（各要素は辞書）
            top_k: 返す結果の数
            text_key: テキストを取得するキー名

        Returns:
            再スコアリングされた上位top_k件の結果
        """
        if not documents:
            return []

        if len(documents) <= top_k:
            logger.info(f"[Reranker] 検索結果が{len(documents)}件のため、リランクをスキップ")
            return documents

        try:
            if self.provider == "cohere":
                return self._rerank_with_cohere(query, documents, top_k, text_key)
            else:
                return self._rerank_with_huggingface(query, documents, top_k, text_key)
        except Exception as e:
            logger.error(f"[Reranker] エラー: {e}", exc_info=True)
            # エラー時は元の順序でtop_kを返す
            return documents[:top_k]

    def _rerank_with_cohere(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int,
        text_key: str
    ) -> List[Dict[str, Any]]:
        """Cohere Rerankを使用した再スコアリング"""
        # ドキュメントのテキストを抽出（Noneを空文字列に変換）
        texts = []
        for doc in documents:
            text = doc.get(text_key) or ""
            # テキストが文字列でない場合は空文字列に変換
            if not isinstance(text, str):
                text = ""
            texts.append(text)

        # Cohere Rerank API呼び出し
        response = self.client.rerank(
            model="rerank-multilingual-v3.0",  # 日本語対応
            query=query,
            documents=texts,
            top_n=top_k
        )

        # スコア順にソート
        reranked = []
        for result in response.results:
            doc = documents[result.index].copy()
            doc["rerank_score"] = result.relevance_score
            reranked.append(doc)

        logger.info(f"[Reranker] Cohere Rerankで{len(documents)}件→{len(reranked)}件に絞り込み")
        return reranked

    def _rerank_with_huggingface(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int,
        text_key: str
    ) -> List[Dict[str, Any]]:
        """Hugging Face CrossEncoderを使用した再スコアリング"""
        if self.model is None:
            logger.warning("[Reranker] モデルが初期化されていません")
            return documents[:top_k]

        # クエリとドキュメントのペアを作成（Noneを空文字列に変換）
        pairs = []
        for doc in documents:
            text = doc.get(text_key) or ""
            # テキストが文字列でない場合は空文字列に変換
            if not isinstance(text, str):
                text = ""
            pairs.append([query, text])

        # スコアを計算
        scores = self.model.predict(pairs)

        # スコアでソート
        scored_docs = []
        for doc, score in zip(documents, scores):
            doc_copy = doc.copy()
            doc_copy["rerank_score"] = float(score)
            scored_docs.append(doc_copy)

        scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
        reranked = scored_docs[:top_k]

        logger.info(f"[Reranker] HuggingFace CrossEncoderで{len(documents)}件→{len(reranked)}件に絞り込み")
        return reranked


class RerankConfig:
    """リランク設定"""

    # リランク機能を使用するかどうか
    ENABLED = os.getenv("RERANK_ENABLED", "false").lower() == "true"

    # リランクプロバイダー ("cohere" or "huggingface")
    PROVIDER = os.getenv("RERANK_PROVIDER", "cohere")

    # 第一段階で取得する結果数（リランク前）
    INITIAL_RETRIEVAL_COUNT = int(os.getenv("RERANK_INITIAL_COUNT", "50"))

    # 第二段階で返す結果数（リランク後）
    FINAL_RESULT_COUNT = int(os.getenv("RERANK_FINAL_COUNT", "5"))

    @classmethod
    def should_rerank(cls, result_count: int) -> bool:
        """リランクを実行すべきかどうか判定"""
        return cls.ENABLED and result_count > cls.FINAL_RESULT_COUNT
