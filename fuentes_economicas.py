"""Lectura y validación de fuentes públicas. No modifica libros ni opera mercados."""
import json
import math
import os
import re
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from zoneinfo import ZoneInfo
import requests

TZ = ZoneInfo('America/Argentina/Buenos_Aires')
CRONISTA = 'https://www.cronista.com/MercadosOnline/dolar.html/'
SOFR = 'https://markets.newyorkfed.org/api/rates/secured/sofr/search.json'
ROFEX = 'https://apicem.matbarofex.com.ar/api/v2/closing-prices'
INDICES = {
    'Bovespa': ('bovespa', 'Bovespa'),
    'SP500': ('us-spx-500', 'S&P 500'),
    'Merval': ('msci-merval', 'MSCI Merval'),
    'SSEC': ('shanghai-composite', 'Shanghai Composite'),
}

def number(value, positive=True):
    if isinstance(value, bool) or value is None:
        raise ValueError('Valor numérico ausente o inválido')
    n = float(str(value).replace(',', '').replace('%', '').strip())
    if not math.isfinite(n) or (positive and n <= 0):
        raise ValueError(f'Valor numérico inválido: {value!r}')
    return n

def dated(value, today):
    d = date.fromisoformat(value[:10])
    if d > today:
        raise ValueError('Fecha de observación futura')
    return d

def get(url, evidence, name, params=None):
    response = requests.get(url, params=params, timeout=(15, 90),
                            headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9'})
    response.raise_for_status()
    (evidence / name).write_bytes(response.content)
    (evidence / (name + '.meta.json')).write_text(json.dumps({
        'url': response.url, 'captured_at': datetime.now(TZ).isoformat()}, ensure_ascii=False))
    return response

def parse_cronista(html, today):
    marker = 'Fusion.contentCache='
    if marker not in html:
        raise ValueError('El Cronista cambió su estructura de datos')
    cache = json.JSONDecoder().raw_decode(html.split(marker, 1)[1])[0]
    candidates = [item for entry in cache.get('markets-general', {}).values()
                  for item in entry.get('data', [])
                  if item.get('Ric') == 'ARS=BNAR' and item.get('Nombre') == 'Dólar BNA']
    if len(candidates) != 1:
        raise ValueError('No se identificó una única serie Dólar BNA')
    item = candidates[0]
    def stamp(value):
        m = re.fullmatch(r'/Date\((\d+)\)/', value)
        if not m:
            raise ValueError('Fecha de El Cronista inválida')
        return datetime.fromtimestamp(int(m[1]) / 1000, timezone.utc).astimezone(TZ)
    result = {}
    for row in item.get('historico', []):
        d = stamp(row['Fecha']).date()
        if d > today or d in result:
            raise ValueError('Fecha futura o duplicada en El Cronista')
        buy, sell = number(row['Compra']), number(row['Venta'])
        if buy > sell:
            raise ValueError('Compra BNA mayor que venta')
        result[d] = [d, buy, sell, 'HISTÓRICO PUBLICADO']
    updated = stamp(item['UltimaActualizacion'])
    if updated.date() > today or (today - updated.date()).days > 7:
        raise ValueError('Cotización BNA futura o desactualizada')
    buy, sell = number(item['Compra']), number(item['Venta'])
    if buy > sell:
        raise ValueError('Compra BNA mayor que venta')
    # El panel en vivo no certifica cierre ni una nueva rueda en fines de semana.
    if updated.weekday() < 5 and updated.date() not in result:
        d = updated.date()
        result[d] = [d, buy, sell, 'OBSERVADO EN PANEL; CIERRE NO VERIFICADO']
    if not result:
        raise ValueError('El Cronista sin historial BNA')
    return [result[d] for d in sorted(result)]

def cronista(evidence, today):
    return parse_cronista(get(CRONISTA, evidence, 'cronista.html').text, today)

class Tables(HTMLParser):
    def __init__(self):
        super().__init__(); self.tables = []; self.table = None; self.row = None; self.cell = None
    def handle_starttag(self, tag, attrs):
        if tag == 'table': self.table = []
        elif tag == 'tr' and self.table is not None: self.row = []
        elif tag in ('td', 'th') and self.row is not None: self.cell = []
    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip()); self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table.append(self.row); self.row = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table); self.table = None

def parse_index(html, today, expected):
    if expected not in html:
        raise ValueError('Investing devolvió otro instrumento o un bloqueo')
    parser = Tables(); parser.feed(html)
    matches = [t for t in parser.tables if t and t[0][:5] == ['Date', 'Price', 'Open', 'High', 'Low']]
    if len(matches) != 1:
        raise ValueError('No se encontró una tabla histórica diaria única de Investing')
    result = {}; headers = matches[0][0]
    for row in matches[0][1:]:
        if len(row) != len(headers):
            raise ValueError('Fila incompleta en Investing')
        d = datetime.strptime(row[0], '%b %d, %Y').date()
        if d > today or d in result:
            raise ValueError('Fecha futura o duplicada en Investing')
        close, opening, high, low = [number(v) for v in row[1:5]]
        if not low <= close <= high or not low <= opening <= high:
            raise ValueError('Cierre o apertura fuera del mínimo/máximo')
        change = number(row[headers.index('Change %')], positive=False) / 100
        status = 'PROVISIONAL; VERIFICAR EN PRÓXIMA RUEDA' if d == today else 'HISTÓRICO PUBLICADO'
        result[d] = [d, close, opening, high, low, change, status]
    if not result or (today - max(result)).days > 7:
        raise ValueError('Histórico Investing vacío o sin actualización reciente')
    return [result[d] for d in sorted(result)]

def investing(name, evidence, today):
    slug, label = INDICES[name]
    url = f'https://www.investing.com/indices/{slug}-historical-data'
    try:
        html = get(url, evidence, name + '.html').text
        return parse_index(html, today, label)
    except (requests.RequestException, ValueError):
        # Navegación normal: no se resuelven desafíos ni se eluden bloqueos.
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            kwargs = {'headless': True}
            if os.environ.get('BNA_CHROMIUM_EXECUTABLE'):
                kwargs['executable_path'] = os.environ['BNA_CHROMIUM_EXECUTABLE']
            browser = p.chromium.launch(**kwargs)
            try:
                page = browser.new_page(locale='en-US', timezone_id='America/Argentina/Buenos_Aires')
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                page.get_by_role('heading', name=label + ' Historical Data', exact=True).wait_for(timeout=30000)
                page.locator('table').filter(has_text='Change %').first.wait_for(timeout=30000)
                html = page.content()
                (evidence / (name + '.html')).write_text(html)
                page.screenshot(path=str(evidence / (name + '.png')), full_page=True)
                (evidence / (name + '.html.meta.json')).write_text(json.dumps({
                    'url': page.url, 'captured_at': datetime.now(TZ).isoformat()}))
                return parse_index(html, today, label)
            finally:
                browser.close()

def parse_sofr(payload, today):
    result = {}
    for row in payload['refRates']:
        if row.get('type') != 'SOFR': raise ValueError('Serie recibida distinta de SOFR overnight')
        d = dated(row['effectiveDate'], today)
        rate = number(row['percentRate'], positive=False)
        if not -10 < rate < 100 or d in result: raise ValueError('SOFR inválida o fecha duplicada')
        result[d] = [d, rate / 100, 'REVISADO' if row.get('revisionIndicator') else 'PUBLICADO']
    if not result or (today - max(result)).days > 7: raise ValueError('SOFR vacía o desactualizada')
    return [result[d] for d in sorted(result)]

def sofr(evidence, today, start):
    return parse_sofr(get(SOFR, evidence, 'sofr.json', {
        'startDate': start.isoformat(), 'endDate': today.isoformat()}).json(), today)

def month_offset(d, offset):
    n = d.year * 12 + d.month - 1 + offset
    return date(n // 12, n % 12 + 1, 1)

def parse_rofex(payload, today):
    result = {}
    for row in payload['data']:
        m = re.fullmatch(r'DLR(\d{2})(\d{4})', row['symbol'])
        if row.get('product') != 'DLR' or not m or row.get('optionType') or row.get('underlying'):
            raise ValueError('A3 devolvió contratos distintos de futuros DLR simples')
        d = dated(row['dateTime'], today)
        month = date(int(m[2]), int(m[1]), 1)
        if not month_offset(d, 0) <= month <= month_offset(d, 12): continue
        key = (d, month)
        if key in result: raise ValueError('Ajuste A3 duplicado')
        settlement = row.get('settlement')
        value = None if settlement is None else number(settlement)
        result[key] = [d, row['symbol'], month, value,
                       'AJUSTE PUBLICADO' if value is not None else 'SIN AJUSTE PUBLICADO']
    if not result or (today - max(k[0] for k in result)).days > 7:
        raise ValueError('A3 sin ajustes recientes')
    for d in sorted({k[0] for k in result}):
        for i in range(13):
            month = month_offset(d, i)
            result.setdefault((d, month), [d, f'DLR{month:%m%Y}', month, None, 'SIN AJUSTE PUBLICADO'])
    return [result[k] for k in sorted(result)]

def rofex(evidence, today, start):
    all_rows = []; page = 1
    while True:
        payload = get(ROFEX, evidence, f'rofex_{page}.json', {
            'from': start.isoformat(), 'to': (today + timedelta(days=1)).isoformat(),
            'product': 'DLR', 'type': 'FUT', 'excludeEmptyVol': 'false',
            'page': page, 'pageSize': 1000, 'market': 'ROFX'}).json()
        rows = payload['data']; all_rows.extend(rows)
        if len(all_rows) >= payload['totalEntries']: break
        if not rows or page >= 100: raise ValueError('Paginación A3 incompleta')
        page += 1
    return parse_rofex({'data': all_rows}, today)
