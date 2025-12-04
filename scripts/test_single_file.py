import asyncio
from pipelines.two_stage_ingestion import TwoStageIngestionPipeline
from core.connectors.google_drive import GoogleDriveConnector

async def test():
    gd = GoogleDriveConnector()
    pipe = TwoStageIngestionPipeline()
    file = {
        'id': '1s74eXyRdI_-5wP1cdzPDEi5hHqPRIXip',
        'name': '価格表(小）2025.5.1以降 (1).pdf',
        'mimeType': 'application/pdf'
    }
    result = await pipe.process_file(file, gd)
    print('Processing complete')

asyncio.run(test())
