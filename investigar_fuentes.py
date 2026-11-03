"""Comprobación pública acotada, sin escritura en Drive."""
import json, requests
from playwright.sync_api import sync_playwright

def note(x):
 s=json.dumps(x,ensure_ascii=True).replace('%','%25').replace('\n','%0A').replace('\r','%0D')
 print('::notice title=Investigación::'+s[:50000])
url='https://api.marketdata.mae.com.ar/api/mercado/titulo/historicocauciones'
r=requests.get(url,params={'oTitulo':json.dumps({'fechaDesde':'2026-10-20','fechaHasta':'2026-11-03'})},timeout=60)
if r.ok:
 note({'CAARS':[{'fecha':row['fecha'],'tasas':[{k:d.get(k) for k in ['ticker','plazo','tasaPP','ultimaTasa','fechaLiquidacion']} for d in row['details'] if d['ticker']=='CAARS']} for row in r.json()]})
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 page=browser.new_page()
 for url in ['https://www.ambito.com/contenidos/riesgo-pais.html',
             'https://mercados.ambito.com/riesgopais/historico-general/01-10-2026/03-11-2026']:
  try:
   response=page.goto(url,wait_until='domcontentloaded',timeout=60000)
   page.wait_for_timeout(4000)
   note({'url':url,'status':response.status,'text':page.locator('body').inner_text()[:10000]})
  except Exception as e: note({'url':url,'error':str(e)[:500]})
 browser.close()
