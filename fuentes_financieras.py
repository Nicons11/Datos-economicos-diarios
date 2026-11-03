"""Series públicas solicitadas: Errepar, riesgo país Ámbito y mercado MAE."""
import math
import unicodedata
from datetime import date, datetime
from fuentes_economicas import get, number, dated

ERREPAR = 'https://www.errepar.com/cotizacion-dolar'
RIESGO = 'https://www.ambito.com/contenidos/riesgo-pais.html'
RIESGO_API = 'https://mercados.ambito.com/riesgopais/historico-general'
FOREX = 'https://marketdata.mae.com.ar/forex/historico'
CAUCIONES = 'https://marketdata.mae.com.ar/cauciones/historico'
MAE_API = 'https://api.marketdata.mae.com.ar/api/mercado/titulo/'

def recent(rows, today):
    dates = [r[0] for r in rows if r[1] is not None]
    if not dates or (today - max(dates)).days > 7:
        raise ValueError('Fuente sin observaciones recientes')
    return sorted(rows, key=lambda r: r[0])

def mae_rows(payload, today, start):
    if not isinstance(payload, list) or not payload:
        raise ValueError('MAE sin histórico válido')
    seen = set()
    for row in payload:
        d = dated(row['fecha'], today)
        if d < start or d in seen:
            raise ValueError('Fecha MAE fuera de intervalo o duplicada')
        seen.add(d)
        yield d, row

def parse_forex(payload, today, start):
    rows = []
    for d, row in mae_rows(payload, today, start):
        # Campo VOLUMEN del total diario de la página, no MONTO en pesos.
        volume = number(row['volumen'], positive=False)
        if volume < 0: raise ValueError('Volumen FOREX negativo')
        rows.append([d, volume / 1_000_000,
                     'PROVISIONAL' if d == today else 'VOLUMEN PUBLICADO POR MAE'])
    return recent(rows, today)

def parse_cauciones(payload, today, start):
    rows = []
    for d, row in mae_rows(payload, today, start):
        candidates = [r for r in row['details'] if r.get('ticker') == 'CAARS'
                   and str(r.get('plazo')) in ('001','002','003','004') and r.get('moneda') == '$'
                   and r.get('tipoEmision') == 'CAU']
        shortest = min((int(r['plazo']) for r in candidates),default=None)
        matches = [r for r in candidates if int(r['plazo']) == shortest]
        if len(matches) > 1: raise ValueError('Más de una caución CAARS pesos a un día')
        if not matches:
            rows.append([d, None, None, None, 'SIN CAARS PESOS A PLAZO CORTO PUBLICADO'])
            continue
        item = matches[0]
        if dated(item['fecha'],today) != d: raise ValueError('Fecha de detalle CAARS distinta de la rueda')
        settlement = date.fromisoformat(item['fechaLiquidacion'][:10])
        if (settlement-d).days != shortest: raise ValueError('Plazo CAARS no coincide con su fecha de liquidación')
        tna = number(item['tasaPP'], positive=False) / 100
        low, high = number(item['minimo'],positive=False) / 100, number(item['maximo'],positive=False) / 100
        if not 0 <= low <= tna <= high < 10: raise ValueError('TNA VWAP CAARS fuera de rango')
        # Capitalización diaria de TNA simple, base 365. TEA calculada, no publicada por MAE.
        tea = math.expm1(365 * math.log1p(tna / 365))
        rows.append([d, tna, tea, shortest, 'TNA VWAP MAE; TEA EQUIVALENTE DIARIA BASE 365' + ('; PROVISIONAL' if d == today else '')])
    return recent(rows, today)

def mae(series, evidence, today, start):
    import json
    params = {'oTitulo': json.dumps({'fechaDesde':start.isoformat(), 'fechaHasta':today.isoformat()},separators=(',',':'))}
    payload = get(MAE_API + 'historico' + series, evidence, series + '.json', params).json()
    return (parse_forex if series == 'forex' else parse_cauciones)(payload, today, start)

def parse_riesgo(payload, today):
    if not isinstance(payload,list) or len(payload) < 2: raise ValueError('Ámbito sin histórico de riesgo país')
    def normalized(text):
        return ''.join(c for c in unicodedata.normalize('NFD',str(text).lower()) if unicodedata.category(c) != 'Mn')
    if normalized(payload[0][0]) != 'fecha' or normalized(payload[0][1]) not in ('puntos',):
        raise ValueError('Cambió la estructura de riesgo país Ámbito')
    rows = []; seen = set()
    for row in payload[1:]:
        if len(row) < 2: raise ValueError('Fila Ámbito incompleta')
        d = None
        for fmt in ('%d-%m-%Y','%d/%m/%Y','%Y-%m-%d'):
            try: d = datetime.strptime(row[0],fmt).date(); break
            except ValueError: pass
        if d is None or d > today or d in seen: raise ValueError('Fecha de riesgo país inválida, futura o duplicada')
        seen.add(d)
        raw = row[1]
        value = number(raw.replace('.','').replace(',','.') if isinstance(raw,str) else raw)
        if not value.is_integer(): raise ValueError('Riesgo país debe expresarse en puntos básicos enteros')
        rows.append([d,int(value),'OBSERVACIÓN ÁMBITO; PROVISIONAL' if d == today else 'PUBLICADO POR ÁMBITO'])
    return recent(rows,today)

def riesgo_pais(evidence, today, start):
    import json, os
    from playwright.sync_api import sync_playwright
    url = f'{RIESGO_API}/{start:%d-%m-%Y}/{today:%d-%m-%Y}'
    # Ámbito atiende esta consulta pública en navegación normal; no usar APIs privadas.
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True,executable_path=os.environ.get('BNA_CHROMIUM_EXECUTABLE') or None)
        try:
            page = browser.new_page(locale='es-AR')
            response = page.goto(url,wait_until='domcontentloaded',timeout=60000)
            if response is None or response.status != 200:
                raise ValueError('Ámbito rechazó la consulta pública; se conserva la serie previa')
            text = page.locator('body').inner_text()
            payload = json.loads(text)
            (evidence/'riesgo_pais.json').write_text(text)
            (evidence/'riesgo_pais.meta.json').write_text(json.dumps({'url':url,'captured_at':datetime.now().astimezone().isoformat()}))
            return parse_riesgo(payload,today)
        finally: browser.close()

def errepar(evidence, today, start):
    from actualizar_bna import fetch_live, validate_snapshot, TZ
    snap, _ = fetch_live(start,today,evidence / 'errepar')
    records, captured = validate_snapshot(snap)
    if captured.astimezone(TZ).date() != today: raise ValueError('Captura Errepar no es de hoy')
    return [[d,*map(float,rates),d,'PUBLICADO EN ERREPAR' + ('; PROVISIONAL' if d == today else '')]
            for d,rates in sorted(records.items())]
