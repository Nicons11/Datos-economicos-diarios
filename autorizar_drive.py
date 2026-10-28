"""Autorización única en tu computadora. No se ejecuta diariamente."""
import argparse
import json
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('cliente', help='JSON OAuth de aplicación de escritorio descargado de Google')
    p.add_argument('salida', help='Archivo privado de salida, fuera del repositorio')
    args = p.parse_args()
    output = Path(args.salida).expanduser().resolve()
    root = Path(__file__).resolve().parent
    if output.is_relative_to(root):
        p.error('Guardá el token fuera del repositorio')
    flow = InstalledAppFlow.from_client_secrets_file(
        args.cliente, scopes=['https://www.googleapis.com/auth/drive'])
    credentials = flow.run_local_server(port=0, access_type='offline', prompt='consent')
    if not credentials.refresh_token:
        raise RuntimeError('Google no devolvió autorización para futuras ejecuciones')
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
        data = json.loads(credentials.to_json())
        data['type'] = 'authorized_user'
        json.dump(data, f)
    print('Autorización guardada en el archivo privado indicado. No la subas al repositorio.')
