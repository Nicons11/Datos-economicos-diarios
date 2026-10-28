"""Lectura y validación de fuentes públicas. No modifica libros ni opera mercados."""
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
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
YAHOO = {'Bovespa': '^BVSP', 'SP500': '^GSPC', 'SSEC': '000001.SS'}
BYMA = 'https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/chart/index-historical-series/history'
BYMA_QUOTE = 'https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/index-price'

def index_url(name):
    from urllib.parse import quote
    return BYMA if name == 'Merval' else 'https://query1.finance.yahoo.com/v8/finance/chart/' + quote(YAHOO[name], safe='')

def parse_yahoo(payload, symbol, today):
    chart = payload['chart']
    if chart.get('error') or len(chart.get('result') or []) != 1: raise ValueError('Yahoo sin una serie única')
    item = chart['result'][0]; meta = item['meta']
    if meta.get('symbol') != symbol or meta.get('instrumentType') != 'INDEX':
        raise ValueError('Yahoo devolvió otro instrumento')
    zone = ZoneInfo(meta['exchangeTimezoneName']); quote = item['indicators']['quote'][0]
    timestamps = item['timestamp']
    if len(quote['close']) != len(timestamps): raise ValueError('Serie Yahoo incompleta')
    result = {}; valid = []
    for i,t in enumerate(timestamps):
        d = datetime.fromtimestamp(t,timezone.utc).astimezone(zone).date()
        if d > today or d in result: raise ValueError('Fecha Yahoo futura o duplicada')
        close = quote['close'][i]
        if close is None:
            if d < today: result[d] = [d,None,None,None,None,None,'SIN DATO PUBLICADO']
            continue
        close = number(close); valid.append(d)
        status = 'PROVISIONAL; VERIFICAR EN PRÓXIMA RUEDA' if d == today else 'CIERRE PUBLICADO'
        result[d] = [d,close,None,None,None,None,status]
    # Yahoo puede publicar la cotización fechada del día antes de completar
    # su vela histórica. Usar solo esa fecha real, sin trasladar la del día anterior.
    stamp = meta.get('regularMarketTime')
    if isinstance(stamp,(int,float)) and not isinstance(stamp,bool):
        quoted = datetime.fromtimestamp(stamp,timezone.utc).astimezone(zone).date()
        if quoted == today and (quoted not in result or result[quoted][1] is None) and meta.get('regularMarketPrice') is not None:
            value = number(meta['regularMarketPrice'])
            result[quoted] = [quoted,value,None,None,None,None,'COTIZACIÓN YAHOO; HISTÓRICO DIARIO PENDIENTE']
            valid.append(quoted)
    if not valid or (today-max(valid)).days > 7: raise ValueError('Yahoo sin cierres recientes')
    return [result[d] for d in sorted(result)]

def parse_byma_quote(payload, today):
    matches = [r for r in payload.get('data',[]) if r.get('symbol') == 'MMSCI'
               and r.get('description','').strip().upper() == 'MSCI MERVAL']
    if len(matches) != 1: raise ValueError('BYMA no identificó una cotización única de MSCI Merval')
    row = matches[0]; d = dated(row['date'],today)
    if d != today or row.get('closingPrice') in (None,0): return []
    return [[d,number(row['closingPrice']),None,None,None,None,'CIERRE INFORMADO POR BYMA (COTIZACIÓN)']]

def parse_byma(payload, today):
    if payload.get('s') != 'ok': raise ValueError('BYMA sin serie histórica')
    if len(payload['t']) != len(payload['c']): raise ValueError('Serie BYMA incompleta')
    result = {}; valid = []
    # Cambio de administrador/base anunciado por BYMA para el 19/10/2026.
    # No empalmar el antiguo S&P con MSCI, aunque el endpoint reutilice el código M.
    for t,c in zip(payload['t'],payload['c']):
        d = datetime.fromtimestamp(t,timezone.utc).astimezone(TZ).date()
        if d < date(2026,10,19): continue
        if d > today or d in result: raise ValueError('Fecha BYMA futura o duplicada')
        if c is None or c == 0:
            result[d] = [d,None,None,None,None,None,'SIN DATO PUBLICADO POR BYMA']
        else:
            close = number(c); valid.append(d)
            result[d] = [d,close,None,None,None,None,
                         'PROVISIONAL' if d == today else 'CIERRE PUBLICADO POR BYMA']
    if not valid or (today-max(valid)).days > 7: raise ValueError('BYMA sin cierres recientes de MSCI Merval')
    return [result[d] for d in sorted(result)]

def index_data(name, evidence, today, start):
    if name == 'Merval':
        rows = parse_byma(get(BYMA,evidence,'Merval.json',{
            'symbol':'M','resolution':'D',
            'from':int(datetime.combine(start,datetime.min.time(),TZ).timestamp()),
            'to':int(datetime.combine(today+timedelta(days=1),datetime.min.time(),TZ).timestamp())}).json(),today)
        if not any(r[0] == today and r[1] is not None for r in rows):
            current = parse_byma_quote(get(BYMA_QUOTE,evidence,'Merval_cotizacion.json',body={}).json(),today)
            merged = {r[0]:r for r in rows}
            merged.update({r[0]:r for r in current})
            rows = [merged[d] for d in sorted(merged)]
        return rows
    return parse_yahoo(get(index_url(name),evidence,name+'.json',{
        'period1':int(datetime.combine(start,datetime.min.time(),timezone.utc).timestamp()),
        'period2':int(datetime.combine(today+timedelta(days=1),datetime.min.time(),timezone.utc).timestamp()),
        'interval':'1d'}).json(),YAHOO[name],today)

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

def get(url, evidence, name, params=None, body=None):
    request = requests.get if body is None else requests.post
    extra = {} if body is None else {'json':body}
    response = request(url, params=params, timeout=(15, 90), **extra,
                            headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9'})
    response.raise_for_status()
    (evidence / name).write_bytes(response.content)
    (evidence / (name + '.meta.json')).write_text(json.dumps({
        'url': response.url, 'method':'GET' if body is None else 'POST',
        'captured_at': datetime.now(TZ).isoformat()}, ensure_ascii=False))
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
