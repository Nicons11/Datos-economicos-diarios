"""Actualiza el Excel mediante el puente de Apps Script autorizado por el usuario."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import time
import requests
from actualizar_oficial import BOOK

def exchange(url, key, action, **values):
    if not re.fullmatch(r'https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec', url):
        raise ValueError('APPS_SCRIPT_URL debe ser la URL /exec de la implementación de Google')
    if len(key) < 32:
        raise ValueError('Falta APPS_SCRIPT_KEY o su longitud es inválida')
    payload = json.dumps(dict(action=action, timestamp=int(time.time()), nonce=secrets.token_hex(16), **values),
                         separators=(',', ':'), ensure_ascii=True)
    signature = hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    response = requests.post(url, json={'payload': payload, 'signature': signature}, timeout=180)
    response.raise_for_status()
    try:
        result = response.json()
    except ValueError:
        raise RuntimeError('Apps Script no devolvió JSON. Revisar implementación y acceso a Cualquier usuario.') from None
    if result.get('ok') is not True:
        raise RuntimeError('Apps Script: ' + str(result.get('error', 'respuesta inválida')))
    return result

def main():
    url, key = os.environ['APPS_SCRIPT_URL'].strip(), os.environ['APPS_SCRIPT_KEY'].strip()
    previous = exchange(url, key, 'read')
    if previous.get('content') is not None:
        BOOK.write_bytes(base64.b64decode(previous['content'], validate=True))
    subprocess.run([sys.executable, str(BOOK.parent / 'actualizar_economicos.py')], check=True)
    result = exchange(url, key, 'write', version=previous.get('version'),
                      content=base64.b64encode(BOOK.read_bytes()).decode('ascii'))
    if not result.get('fileId'):
        raise RuntimeError('Google no confirmó el ID del archivo guardado')
    print('Excel actualizado en la carpeta de Google Drive.')
    from actualizar_economicos import check_result
    check_result()

if __name__ == '__main__':
    main()

