from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

class DocsService:
    def _get_services(self, token: str):
        creds = Credentials(token=token)
        return build('docs', 'v1', credentials=creds), build('drive', 'v3', credentials=creds)

    def create_document(self, token: str, title: str, content: str) -> tuple[str, str]:
        docs_service, drive_service = self._get_services(token)
        
        document = docs_service.documents().create(body={'title': title}).execute()
        doc_id = document.get('documentId')
        
        requests = [{'insertText': {'location': {'index': 1}, 'text': content}}]
        docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
        
        drive_service.permissions().create(
            fileId=doc_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        return doc_id, f"https://docs.google.com/document/d/{doc_id}/edit"