"""Pruebas aisladas: nunca consultan Drive ni publican cotizaciones sintéticas."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from openpyxl import load_workbook
from actualizar_bna import ROOT, HEADERS, URL, TZ
from actualizar_oficial import BOOK, apply_snapshot
import actualizar_drive as drive

class Cloud(unittest.TestCase):
    def test_excel_append_backup_stale_and_locked(self):
        now = datetime(2026, 10, 28, 19, 5, tzinfo=TZ)
        snap = dict(url=URL, source=True, headers=HEADERS,
                    captured_at=now.isoformat(), queried_from='2026-10-28',
                    queried_to='2026-10-28',
                    rows=[['28/10/2026','1600,0000','1650,0000','1610,0000','1660,0000']])
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            book = Path(folder) / BOOK.name
            evidence = Path(folder) / 'sintetica.json'
            shutil.copy2(BOOK, book)
            original = book.read_bytes()
            evidence.write_text(json.dumps(snap))
            result = apply_snapshot(book, snap, evidence, now=now)
            self.assertTrue(result['dato_hoy'])
            self.assertEqual(Path(result['respaldo']).read_bytes(), original)
            wb = load_workbook(book, read_only=True, data_only=True)
            self.assertEqual(wb['Cotizaciones']['B34'].value, 1600)
            self.assertEqual(wb['Cotizaciones']['B7'].value, 1495)
            wb.close()
            updated = book.read_bytes()
            with self.assertRaises(ValueError):
                apply_snapshot(book, snap, evidence, now=now + timedelta(days=1))
            self.assertEqual(book.read_bytes(), updated)
            (book.parent / ('~$' + book.name)).touch()
            with self.assertRaises(ValueError):
                apply_snapshot(book, snap, evidence, now=now)
            self.assertEqual(book.read_bytes(), updated)

    def test_failed_update_never_uploads(self):
        service = MagicMock()
        credentials = {'type': 'authorized_user', 'token_uri': 'https://oauth2.googleapis.com/token'}
        with patch.dict(os.environ, GOOGLE_DRIVE_CREDENTIALS_JSON=json.dumps(credentials), GOOGLE_DRIVE_FOLDER_ID='abc'), \
             patch.object(drive.Credentials, 'from_authorized_user_info'), \
             patch.object(drive, 'build', return_value=service), \
             patch.object(drive, 'find_book', return_value=None), \
             patch.object(drive.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'actualizador')):
            with self.assertRaises(subprocess.CalledProcessError):
                drive.main()
        service.files.assert_not_called()

    def test_reject_ambiguous_or_converted_books(self):
        service = MagicMock()
        service.files().get().execute.return_value = {
            'mimeType': 'application/vnd.google-apps.folder', 'capabilities': {'canAddChildren': True}}
        for files in ([{'id': 'a'}, {'id': 'b'}], [{'id': 'a', 'mimeType': 'application/vnd.google-apps.spreadsheet'}]):
            service.files().list().execute.return_value = {'files': files}
            with self.assertRaises(ValueError):
                drive.find_book(service, 'carpeta_123')

    def test_existing_book_updates_same_id_after_success(self):
        service = MagicMock()
        service.files().get().execute.return_value = {'version': '3'}
        download = MagicMock()
        download.next_chunk.return_value = (None, True)
        credentials = {'type': 'authorized_user', 'token_uri': 'https://oauth2.googleapis.com/token'}
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, GOOGLE_DRIVE_CREDENTIALS_JSON=json.dumps(credentials), GOOGLE_DRIVE_FOLDER_ID='abc'), \
             patch.object(drive.Credentials, 'from_authorized_user_info'), \
             patch.object(drive, 'build', return_value=service), \
             patch.object(drive, 'BOOK', Path(folder) / BOOK.name), \
             patch.object(drive, 'find_book', return_value={'id': 'same-id', 'version': '3'}), \
             patch.object(drive, 'MediaIoBaseDownload', return_value=download), \
             patch.object(drive, 'MediaFileUpload'), \
             patch.object(drive.subprocess, 'run') as run:
            drive.main()
            run.assert_called_once()
            service.files().update.assert_called_once()
            self.assertEqual(service.files().update.call_args.kwargs['fileId'], 'same-id')
            service.files().create.assert_not_called()

if __name__ == '__main__':
    unittest.main()
