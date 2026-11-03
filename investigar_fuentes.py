"""Diagnóstico manual de respuestas públicas; no modifica libros ni usa secretos."""
import json
import re
from urllib.parse import urljoin
import requests

def notice(data):
    message = json.dumps(data, ensure_ascii=True).replace('%','%25').replace('\n','%0A').replace('\r','%0D')
    print('::notice title=Fuente pública::' + message[:55000])

for url in ['https://marketdata.mae.com.ar/forex/historico',
            'https://marketdata.mae.com.ar/cauciones/historico',
            'https://www.ambito.com/contenidos/riesgo-pais.html',
            'https://mercados.ambito.com/riesgopais/historico-general/2026-10-01/2026-11-03']:
    try:
        r = requests.get(url, timeout=60)
        notice({'url':url,'status':r.status_code,'sample':r.text[:1500],
                'scripts':re.findall(r'<script[^>]+src=["\']([^"\']+)',r.text)})
        if r.ok and 'marketdata.mae' in url:
            for src in re.findall(r'<script[^>]+src=["\']([^"\']+)',r.text):
                js = requests.get(urljoin(r.url,src),timeout=60)
                hits = re.findall(r'.{0,120}(?:CAARS|caars|forex|cauciones|apiUrl|baseURL|historico).{0,180}',js.text)
                notice({'js':js.url,'hits':hits[:100]})
    except Exception as exc:
        notice({'url':url,'error':str(exc)[:500]})

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    for url in ['https://marketdata.mae.com.ar/forex/historico','https://marketdata.mae.com.ar/cauciones/historico']:
        responses=[]
        def capture(r):
            if r.request.resource_type in ('xhr','fetch'):
                try: responses.append({'url':r.url,'status':r.status,'body':r.text()[:6000]})
                except Exception: pass
        page.on('response',capture)
        try:
            page.goto(url,wait_until='networkidle',timeout=90000)
            notice({'browser':url,'text':page.locator('body').inner_text()[:14000],'responses':responses[:25]})
        except Exception as exc: notice({'browser':url,'error':str(exc)[:500]})
        page.remove_listener('response',capture)
    browser.close()
