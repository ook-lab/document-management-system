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