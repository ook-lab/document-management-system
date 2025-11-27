"""
Database Client
Supabaseデータベースへの接続と操作を管理
"""
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
from config.settings import settings


class DatabaseClient:
    """Supabaseデータベースクライアント"""
    
    def __init__(self):
        """Supabaseクライアントの初期化"""
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL と SUPABASE_KEY が設定されていません")
        
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
    
    def get_document_by_source_id(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        source_id で文書を検索
        
        Args:
            source_id: Google Drive のファイルID
        
        Returns:
            既存の文書レコード、存在しない場合は None
        """
        try:
            response = self.client.table('documents').select('*').eq('source_id', source_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            print(f"Error getting document by source_id: {e}")
            return None
    
    async def insert_document(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        文書をデータベースに挿入

        Args:
            table: テーブル名
            data: 挿入するデータ

        Returns:
            挿入されたレコード
        """
        # embeddingをPostgreSQLのvector型形式に変換
        if 'embedding' in data and data['embedding'] is not None:
            embedding_list = data['embedding']
            if isinstance(embedding_list, list):
                # ベクトル形式の文字列に変換: [0.1,0.2,0.3]
                data = data.copy()  # 元のdataを変更しないようにコピー
                data['embedding'] = '[' + ','.join(str(x) for x in embedding_list) + ']'

        response = self.client.table(table).insert(data).execute()
        return response.data[0] if response.data else {}
    
    async def search_documents(
        self,
        query: str,
        embedding: List[float],
        limit: int = 50,
        workspace: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        ベクトル検索で文書を検索

        Args:
            query: 検索クエリ
            embedding: クエリのembeddingベクトル
            limit: 取得する最大件数（デフォルト: 50）
            workspace: ワークスペースフィルタ (オプション)

        Returns:
            検索結果のリスト
        """
        # RPC関数を使用してベクトル検索
        rpc_params = {
            "query_embedding": embedding,
            "match_threshold": 0.0,  # 類似度の下限を0.0に設定（すべての結果を返す）
            "match_count": limit
        }
        
        if workspace:
            rpc_params["filter_workspace"] = workspace
        
        response = self.client.rpc("match_documents", rpc_params).execute()
        return response.data if response.data else []

    def get_documents_for_review(
        self,
        status: str = 'completed',
        max_confidence: float = 0.9,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        レビュー対象のドキュメントを取得

        Args:
            status: 処理ステータス（デフォルト: 'completed'）
            max_confidence: 信頼度の上限（デフォルト: 0.9）
            limit: 取得する最大件数

        Returns:
            ドキュメントのリスト
        """
        try:
            response = (
                self.client.table('documents')
                .select('*')
                .eq('processing_status', status)
                .lt('confidence', max_confidence)
                .order('created_at', desc=True)
                .limit(limit)
                .execute()
            )
            return response.data if response.data else []
        except Exception as e:
            print(f"Error getting documents for review: {e}")
            return []

    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        IDでドキュメントを取得

        Args:
            doc_id: ドキュメントID

        Returns:
            ドキュメント、存在しない場合は None
        """
        try:
            response = self.client.table('documents').select('*').eq('id', doc_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            print(f"Error getting document by id: {e}")
            return None

    def update_document_metadata(
        self,
        doc_id: str,
        new_metadata: Dict[str, Any],
        new_doc_type: Optional[str] = None
    ) -> bool:
        """
        ドキュメントのメタデータと文書タイプを更新

        Args:
            doc_id: ドキュメントID
            new_metadata: 新しいメタデータ
            new_doc_type: 新しい文書タイプ（オプション）

        Returns:
            成功したかどうか
        """
        try:
            update_data = {'metadata': new_metadata}
            if new_doc_type:
                update_data['doc_type'] = new_doc_type

            response = (
                self.client.table('documents')
                .update(update_data)
                .eq('id', doc_id)
                .execute()
            )
            return bool(response.data)
        except Exception as e:
            print(f"Error updating document metadata: {e}")
            return False

    def get_processed_file_ids(self) -> List[str]:
        """
        既に処理済みのファイルIDリストを取得

        Returns:
            処理済みファイルのsource_id（Google Drive file ID）のリスト
        """
        try:
            # source_idが存在するすべてのドキュメントを取得
            response = (
                self.client.table('documents')
                .select('source_id')
                .not_.is_('source_id', 'null')
                .execute()
            )

            # source_idのリストを抽出
            if response.data:
                file_ids = [doc['source_id'] for doc in response.data if doc.get('source_id')]
                print(f"Supabaseから {len(file_ids)} 件の処理済みファイルIDを取得しました")
                return file_ids
            return []

        except Exception as e:
            print(f"Error getting processed file IDs: {e}")
            return []