"""
Analyze classroom document IDs to understand the relationship
"""
from core.database.client import DatabaseClient
import json

def analyze():
    db = DatabaseClient()

    result = db.client.table('documents').select('*').eq(
        'workspace', 'ikuya_classroom'
    ).execute()

    print("\n" + "="*80)
    print("Google Classroom Document ID Analysis")
    print("="*80)

    for doc in result.data:
        print(f"\n--- {doc['file_name']} ---")
        print(f"source_type: {doc.get('source_type')}")
        print(f"source_id: {doc.get('source_id')}")
        print(f"drive_file_id: {doc.get('drive_file_id')}")

        metadata = doc.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}

        print(f"\nMetadata:")
        for key, value in metadata.items():
            print(f"  {key}: {value}")

        print(f"\nAnalysis:")
        source_id = doc.get('source_id', '')
        if source_id and source_id.isdigit():
            print(f"  source_id ({source_id}) appears to be a Classroom Post ID (numeric)")
        else:
            print(f"  source_id ({source_id}) might be a Drive file ID")

        original_file_id = metadata.get('original_file_id', '')
        if original_file_id:
            if original_file_id.startswith('1'):
                print(f"  original_file_id ({original_file_id}) looks like a valid Drive file ID")
            else:
                print(f"  original_file_id ({original_file_id}) format is unusual")

        print("-" * 80)

    print("\n" + "="*80)
    print("Conclusion:")
    print("="*80)
    print("""
If original_file_id is valid but returns 404:
1. The file is in a Google Classroom Course Drive folder
2. Service account needs access to the Classroom course drive folder
3. Or the file ID might be from a different Google account

Solutions:
A. Share the Classroom Course Drive folder with service account
B. Use Google Classroom API to download files instead of Drive API
C. Grant domain-wide delegation to service account
""")

if __name__ == "__main__":
    analyze()
