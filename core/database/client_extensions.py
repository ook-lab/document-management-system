"""
DatabaseClient拡張メソッド
リアクティブ編集システム用の追加メソッド

これらのメソッドは core/database/client.py に手動でマージしてください
"""
from typing import Dict, Any, List, Optional


# 以下のメソッドを DatabaseClient クラスに追加:

def get_all_documents_for_review(self, filter_status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    レビュー対象ドキュメント一覧を取得
    """
    try:
        query = self.client.table('documents').select(
            'id, file_name, doc_type, workspace, reviewed, review_status, created_at, updated_at, full_text, extracted_tables'
        ).order('created_at', desc=False).limit(limit)

        if filter_status:
            query = query.eq('review_status', filter_status)

        response = query.execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting documents for review: {e}")
        return []


def update_document_sync(self, document_id: str, updates: Dict[str, Any]) -> bool:
    """
    ドキュメントを同期的に更新
    """
    try:
        response = self.client.table('documents').update(updates).eq('id', document_id).execute()
        return True
    except Exception as e:
        print(f"Error updating document: {e}")
        return False


def delete_document_chunks_sync(self, document_id: str) -> bool:
    """
    ドキュメントの全チャンクを同期的に削除
    """
    try:
        self.client.table('document_chunks').delete().eq('document_id', document_id).execute()
        return True
    except Exception as e:
        print(f"Error deleting document chunks: {e}")
        return False


def delete_hypothetical_questions_sync(self, document_id: str) -> bool:
    """
    ドキュメントの全質問を同期的に削除
    """
    try:
        self.client.table('hypothetical_questions').delete().eq('document_id', document_id).execute()
        return True
    except Exception as e:
        print(f"Error deleting hypothetical questions: {e}")
        return False


async def get_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
    """
    ドキュメントの全チャンクを取得
    """
    try:
        response = self.client.table('document_chunks').select('*').eq('document_id', document_id).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting document chunks: {e}")
        return []


async def insert_hypothetical_question(
    self,
    document_id: str,
    chunk_id: Optional[str],
    question_text: str,
    question_embedding: List[float],
    confidence_score: float = 1.0
) -> bool:
    """
    仮想質問を1件挿入
    """
    try:
        # embeddingをPostgreSQLのvector型形式に変換
        embedding_str = '[' + ','.join(str(x) for x in question_embedding) + ']'

        data = {
            'document_id': document_id,
            'chunk_id': chunk_id,
            'question_text': question_text,
            'question_embedding': embedding_str,
            'confidence_score': confidence_score
        }

        self.client.table('hypothetical_questions').insert(data).execute()
        return True
    except Exception as e:
        print(f"Error inserting hypothetical question: {e}")
        return False
