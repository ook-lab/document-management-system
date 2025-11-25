"""
Embedding Client
"""
from typing import List, Optional
import google.generativeai as genai
from config.settings import settings


class EmbeddingClient:
    """
    Google Generative AI (text-embedding-004) を使用したEmbedding生成クライアント
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GOOGLE_AI_API_KEY
        if not self.api_key:
            raise ValueError("Google AI API Key が設定されていません")
        
        genai.configure(api_key=self.api_key)
        self.model_name = "models/text-embedding-004"
    
    def generate_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        if not text or not text.strip():
            raise ValueError("空のテキストはembedding化できません")
        
        result = genai.embed_content(
            model=self.model_name,
            content=text,
            task_type=task_type
        )
        
        return result['embedding']
    
    def generate_embeddings_batch(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        if not texts:
            return []

        embeddings = []
        for text in texts:
            if text and text.strip():
                embedding = self.generate_embedding(text, task_type)
                embeddings.append(embedding)
            else:
                # Google text-embedding-004は768次元
                embeddings.append([0.0] * 768)

        return embeddings
    
    def generate_query_embedding(self, query: str) -> List[float]:
        return self.generate_embedding(query, task_type="RETRIEVAL_QUERY")
