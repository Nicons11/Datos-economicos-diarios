"""Descarga el libro vigente de Drive, actualiza y guarda sobre el mismo ID."""
import io
import json
import os
import subprocess
import sys
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from actualizar_oficial import BOOK

MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

def find_book(service, folder_id):
    if not folder_id or not all(c.isalnum() or c in '_-' for c in folder_id):
        raise ValueError('GOOGLE_DRIVE_FOLDER_ID debe ser el ID de la carpeta, no su URL')
    folder = service.files().get(fileId=folder_id, fields='mimeType,capabilities(canAddChildren)').execute()
    if folder['mimeType'] != 'application/vnd.google-apps.folder' or not folder.get('capabilities', {}).get('canAddChildren'):
        raise ValueError('La carpeta no existe o no permite escribir')
    result = service.files().list(
        q=f"'{folder_id}' in parents and trashed = false and name = '{BOOK.name}'",
        fields='files(id,mimeType,version),nextPageToken', pageSize=100).execute()
    files = result.get('files', [])
    if len(files) > 1 or result.get('nextPageToken'):
        raise ValueError('Hay varios archivos con ese nombre; conservar uno para evitar ambigüedad')
    if files and files[0]['mimeType'] != MIME:
        raise ValueError('Debe ser un archivo Excel .xlsx, no una hoja convertida a Google Sheets')
    return files[0] if files else None

def main():
    info = json.loads(os.environ['GOOGLE_DRIVE_CREDENTIALS_JSON'])
    if info.get('type') != 'authorized_user' or info.get('token_uri') != 'https://oauth2.googleapis.com/token':
        raise ValueError('Se requiere el JSON OAuth generado por autorizar_drive.py')
    credentials = Credentials.from_authorized_user_info(info)
    service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
    folder_id = os.environ['GOOGLE_DRIVE_FOLDER_ID']
    existing = find_book(service, folder_id)
    if existing:
        stream = io.BytesIO()
        download = MediaIoBaseDownload(stream, service.files().get_media(fileId=existing['id']))
        done = False
        while not done:
            _, done = download.next_chunk()
        BOOK.write_bytes(stream.getvalue())
    # Si falla la consulta o la validación, no se envía nada a Drive.
    subprocess.run([sys.executable, str(BOOK.parent / 'actualizar_oficial.py')], check=True)
    media = MediaFileUpload(str(BOOK), mimetype=MIME, resumable=True)
    if existing:
        current = service.files().get(fileId=existing['id'], fields='version').execute()
        if current['version'] != existing['version']:
            raise RuntimeError('El archivo cambió en Drive durante la consulta; se cancela para preservar los cambios')
        service.files().update(fileId=existing['id'], media_body=media).execute()
    else:
        service.files().create(body={'name': BOOK.name, 'parents': [folder_id]}, media_body=media).execute()
    print('Excel actualizado en Google Drive.')

if __name__ == '__main__':
    main()
