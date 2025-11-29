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

        # ワークスペースフィルタを無効化（常に全件検索）
        # if workspace:
        #     rpc_params["filter_workspace"] = workspace

        response = self.client.rpc("match_documents", rpc_params).execute()
        return response.data if response.data else []

    def get_documents_for_review(
        self,
        max_confidence: float = 0.9,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        レビュー対象のドキュメントを取得（全ステータス）

        Args:
            max_confidence: 信頼度の上限（デフォルト: 0.9）
            limit: 取得する最大件数

        Returns:
            ドキュメントのリスト（更新日時降順）
        """
        try:
            response = (
                self.client.table('documents')
                .select('*')
                .lt('confidence', max_confidence)
                .order('updated_at', desc=True)
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

        注意: この関数は修正履歴を記録しません。
        修正履歴を記録する場合は record_correction() を使用してください。

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

    def record_correction(
        self,
        doc_id: str,
        new_metadata: Dict[str, Any],
        new_doc_type: Optional[str] = None,
        corrector_email: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        ドキュメントのメタデータを更新し、修正履歴を記録

        Phase 2: トランザクション管理・ロールバック機能

        Args:
            doc_id: ドキュメントID
            new_metadata: 新しいメタデータ
            new_doc_type: 新しい文書タイプ（オプション）
            corrector_email: 修正者のメールアドレス（オプション）
            notes: 修正に関するメモ（オプション）

        Returns:
            成功したかどうか
        """
        try:
            # Step 1: 現在のドキュメントを取得
            current_doc = self.get_document_by_id(doc_id)
            if not current_doc:
                print(f"Error: Document not found: {doc_id}")
                return False

            old_metadata = current_doc.get('metadata', {})
            old_doc_type = current_doc.get('doc_type')

            # Step 2: correction_history に修正履歴を記録
            correction_data = {
                'document_id': doc_id,
                'old_metadata': old_metadata,
                'new_metadata': new_metadata,
                'corrector_email': corrector_email,
                'correction_type': 'manual',
                'notes': notes
            }

            correction_response = (
                self.client.table('correction_history')
                .insert(correction_data)
                .execute()
            )

            if not correction_response.data:
                print("Error: Failed to insert correction history")
                return False

            correction_id = correction_response.data[0]['id']
            print(f"✅ 修正履歴を記録: correction_id={correction_id}")

            # Step 3: documents テーブルを更新
            update_data = {
                'metadata': new_metadata,
                'latest_correction_id': correction_id
            }
            if new_doc_type and new_doc_type != old_doc_type:
                update_data['doc_type'] = new_doc_type

            document_response = (
                self.client.table('documents')
                .update(update_data)
                .eq('id', doc_id)
                .execute()
            )

            if not document_response.data:
                print("Error: Failed to update document")
                return False

            print(f"✅ ドキュメント更新成功: doc_id={doc_id}")
            return True

        except Exception as e:
            print(f"Error recording correction: {e}")
            import traceback
            traceback.print_exc()
            return False

    def rollback_document(self, doc_id: str) -> bool:
        """
        ドキュメントのメタデータを最新の修正前の状態にロールバック

        Phase 2: トランザクション管理・ロールバック機能

        Args:
            doc_id: ドキュメントID

        Returns:
            成功したかどうか
        """
        try:
            # Step 1: 現在のドキュメントを取得
            current_doc = self.get_document_by_id(doc_id)
            if not current_doc:
                print(f"Error: Document not found: {doc_id}")
                return False

            latest_correction_id = current_doc.get('latest_correction_id')
            if not latest_correction_id:
                print(f"Error: No correction history found for document: {doc_id}")
                return False

            # Step 2: 最新の修正履歴を取得
            correction_response = (
                self.client.table('correction_history')
                .select('*')
                .eq('id', latest_correction_id)
                .execute()
            )

            if not correction_response.data:
                print(f"Error: Correction history not found: {latest_correction_id}")
                return False

            correction = correction_response.data[0]
            old_metadata = correction['old_metadata']

            # Step 3: documentsテーブルを修正前の状態に戻す
            update_data = {
                'metadata': old_metadata,
                'latest_correction_id': None  # ロールバック後は修正履歴をクリア
            }

            document_response = (
                self.client.table('documents')
                .update(update_data)
                .eq('id', doc_id)
                .execute()
            )

            if not document_response.data:
                print("Error: Failed to rollback document")
                return False

            print(f"✅ ロールバック成功: doc_id={doc_id}, correction_id={latest_correction_id}")
            return True

        except Exception as e:
            print(f"Error rolling back document: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_correction_history(
        self,
        doc_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        ドキュメントの修正履歴を取得

        Phase 2: トランザクション管理・ロールバック機能

        Args:
            doc_id: ドキュメントID
            limit: 取得する最大件数

        Returns:
            修正履歴のリスト（新しい順）
        """
        try:
            response = (
                self.client.table('correction_history')
                .select('*')
                .eq('document_id', doc_id)
                .order('corrected_at', desc=True)
                .limit(limit)
                .execute()
            )
            return response.data if response.data else []
        except Exception as e:
            print(f"Error getting correction history: {e}")
            return []

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

    def check_duplicate_hash(self, content_hash: str) -> bool:
        """
        content_hashが既にデータベースに存在するかチェック

        Args:
            content_hash: SHA256ハッシュ値

        Returns:
            True: 重複あり（既に存在する）
            False: 重複なし（新規）
        """
        try:
            # content_hashが一致するドキュメントを検索
            response = (
                self.client.table('documents')
                .select('id, file_name, content_hash')
                .eq('content_hash', content_hash)
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                # 重複が見つかった
                existing_doc = response.data[0]
                print(f"⚠️  重複検知: content_hash={content_hash[:16]}... は既に存在します")
                print(f"   既存ファイル: {existing_doc.get('file_name', 'Unknown')}")
                return True

            # 重複なし
            return False

        except Exception as e:
            print(f"Error checking duplicate hash: {e}")
            # エラー時は安全側に倒して重複なしとして扱う
            return False