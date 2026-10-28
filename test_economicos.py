"""Casos de integridad y migración en copias temporales; sin publicar datos de prueba."""
import copy
import json
import shutil
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from openpyxl import load_workbook
from fuentes_economicas import TZ, parse_sofr, parse_rofex, parse_yahoo, parse_byma, parse_byma_quote, parse_cronista, month_offset
from actualizar_economicos import apply_results, existing_rows, ROOT, BOOK

TODAY = date(2026,10,28)
NOW = datetime(2026,10,28,19,5,tzinfo=TZ)

class Sources(unittest.TestCase):
    def test_yahoo_current_quote_fills_only_missing_same_market_date(self):
        market_stamp = int(datetime(2026,10,28,4,0,tzinfo=TZ).timestamp())
        p = {'chart':{'error':None,'result':[{'meta':{'symbol':'000001.SS','instrumentType':'INDEX',
              'exchangeTimezoneName':'Asia/Shanghai','regularMarketTime':market_stamp,
              'regularMarketPrice':3681.469},'timestamp':[market_stamp],
              'indicators':{'quote':[{'close':[None]}]}}]}}
        rows = parse_yahoo(p,'000001.SS',TODAY)
        self.assertEqual(rows[0][0],TODAY); self.assertAlmostEqual(rows[0][1],3681.469)
        self.assertIn('HISTÓRICO DIARIO PENDIENTE',rows[0][-1])
        p['chart']['result'][0]['indicators']['quote'][0]['close']=[3682]
        self.assertEqual(parse_yahoo(p,'000001.SS',TODAY)[0][1],3682)
        p['chart']['result'][0]['indicators']['quote'][0]['close']=[None]
        p['chart']['result'][0]['meta']['regularMarketTime']-=86400
        with self.assertRaises(ValueError): parse_yahoo(p,'000001.SS',TODAY)

    def test_byma_current_close_is_not_trade_or_previous_close(self):
        row = {'symbol':'MMSCI','description':'MSCI MERVAL','date':'2026-10-28',
               'closingPrice':95438.89,'trade':96869.67,'previousClosingPrice':96681.01}
        self.assertEqual(parse_byma_quote({'data':[row]},TODAY)[0][1],95438.89)
        row['date']='2026-10-27'
        self.assertEqual(parse_byma_quote({'data':[row]},TODAY),[])
        row['symbol']='GMSCI'
        with self.assertRaises(ValueError): parse_byma_quote({'data':[row]},TODAY)

    def test_rofex_uses_settlement_zero_volume_and_thirteen_months(self):
        p = {'data':[dict(dateTime='2026-10-28T00:00:00Z',symbol='DLR102027',
                          product='DLR',settlement=1900,close=0,volume=0)]}
        rows = parse_rofex(p,TODAY)
        self.assertEqual(len(rows),13)
        self.assertEqual(rows[-1][:4],[TODAY,'DLR102027',date(2027,10,1),1900])
        self.assertIsNone(rows[0][3]); self.assertIn('SIN AJUSTE',rows[0][4])
        self.assertEqual(month_offset(date(2026,12,31),12),date(2027,12,1))
        p['data'][0]['settlement'] = 0
        with self.assertRaises(ValueError): parse_rofex(p,TODAY)

    def test_sofr_rate_effective_date_and_revisions(self):
        p = {'refRates':[dict(effectiveDate='2026-10-27',type='SOFR',percentRate=3.95,revisionIndicator='*')]}
        r = parse_sofr(p,TODAY)[0]
        self.assertEqual(r[0],date(2026,10,27)); self.assertAlmostEqual(r[1],0.0395)
        self.assertEqual(r[2],'REVISADO')
        p['refRates'] *= 2
        with self.assertRaises(ValueError): parse_sofr(p,TODAY)

    def test_yahoo_symbol_timezone_missing_and_stale(self):
        p = {'chart':{'error':None,'result':[{'meta':{'symbol':'^GSPC','instrumentType':'INDEX',
              'exchangeTimezoneName':'America/New_York'},'timestamp':[int(NOW.timestamp())],
              'indicators':{'quote':[{'close':[7700]}]}}]}}
        r = parse_yahoo(p,'^GSPC',TODAY)[0]
        self.assertEqual(r[1],7700); self.assertIn('PROVISIONAL',r[-1])
        with self.assertRaises(ValueError): parse_yahoo(p,'^BVSP',TODAY)
        p['chart']['result'][0]['indicators']['quote'][0]['close'] = [None]
        with self.assertRaises(ValueError): parse_yahoo(p,'^GSPC',TODAY)

    def test_byma_does_not_splice_bases_or_load_zeros_as_closes(self):
        days = [date(2026,10,16),date(2026,10,19),date(2026,10,27)]
        p = {'s':'ok','t':[int(datetime.combine(d,datetime.min.time(),TZ).timestamp()) for d in days],
             'c':[2800000,0,96681.01]}
        rows = parse_byma(p,TODAY)
        self.assertEqual(len(rows),2); self.assertIsNone(rows[0][1])
        self.assertEqual(rows[-1][1],96681.01)

    def test_cronista_exact_identity_and_spread(self):
        ms = int(NOW.timestamp()*1000)
        item = dict(Ric='ARS=BNAR',Nombre='Dólar BNA',Compra=1510,Venta=1560,
                    UltimaActualizacion=f'/Date({ms})/',historico=[])
        def html(x): return 'Fusion.contentCache='+json.dumps({'markets-general':{'query':{'data':[x]}}})+';'
        self.assertEqual(parse_cronista(html(item),TODAY)[0][1:3],[1510,1560])
        for field,value in [('Ric','ARSB'),('Compra',1600),('Venta',None)]:
            invalid = copy.deepcopy(item); invalid[field] = value
            with self.assertRaises(ValueError): parse_cronista(html(invalid),TODAY)

class Workbook(unittest.TestCase):
    def test_report_does_not_equate_successful_fetch_with_current_day_data(self):
        with tempfile.TemporaryDirectory() as folder:
            book = Path(folder)/BOOK.name; shutil.copy2(BOOK,book)
            yesterday=date(2026,10,27)
            result=apply_results(book,{'Merval':[[yesterday,96681.01,None,None,None,None,'PUBLICADO']],
                          'SOFR':[[yesterday,0.0395,'PUBLICADO']]},{},NOW)
            self.assertEqual(result['errores'],{})
            self.assertIn('Merval',result['pendientes_fecha_consulta'])
            self.assertNotIn('SOFR',result['pendientes_fecha_consulta'])
            self.assertEqual(result['cobertura']['Merval']['ultima_fecha_dato'],'2026-10-27')
            wb=load_workbook(book)
            self.assertIn('Merval: pendiente 2026-10-28',wb['Fuente']['B3'].value)
            wb.close()

    def test_calendar_effective_date_and_rofex_month_order(self):
        with tempfile.TemporaryDirectory() as folder:
            book = Path(folder)/BOOK.name; shutil.copy2(BOOK,book)
            friday = date(2026,10,23)
            payload = {'data':[dict(dateTime='2026-10-27T00:00:00Z',symbol=s,
                       product='DLR',settlement=1500) for s in ['DLR012027','DLR102026','DLR102027']]}
            apply_results(book,{'Cotizaciones':[[friday,1500,1550,'HISTÓRICO PUBLICADO']],
                               'ROFEX':parse_rofex(payload,TODAY)},{},NOW)
            wb = load_workbook(book)
            rows = existing_rows(wb,'Cotizaciones')
            self.assertEqual(len(rows),6)
            self.assertEqual(rows[2][3],friday)
            self.assertIn('SIN FILA',rows[2][4])
            months = [r[2] for r in existing_rows(wb,'ROFEX')]
            self.assertEqual(months,sorted(months))
            self.assertEqual(wb.active.title,'Cotizaciones')
            wb.close()

    def test_migration_partial_update_backup_and_repeat(self):
        with tempfile.TemporaryDirectory() as folder:
            book = Path(folder)/BOOK.name; shutil.copy2(BOOK,book)
            original = book.read_bytes()
            before = load_workbook(book); history = list(before['Cotizaciones'].values); before.close()
            result = {'Cotizaciones':[[TODAY,1510,1560,'OBSERVADO']],
                      'SOFR':[[date(2026,10,27),0.0395,'PUBLICADO']]}
            report = apply_results(book,result,{'Bovespa':'HTTP 403'},NOW)
            self.assertEqual(Path(report['respaldo']).read_bytes(),original)
            wb = load_workbook(book)
            self.assertEqual(list(wb['Histórico Errepar'].values),history)
            self.assertEqual(wb['Fuente'].max_row,5)
            self.assertEqual(wb['Cotizaciones']['B7'].value,1510)
            self.assertEqual(wb['SOFR']['B7'].number_format,'0.00%')
            self.assertEqual(len(existing_rows(wb,'SOFR')),1)
            wb.close()
            apply_results(book,{'SOFR':[[date(2026,10,27),0.0396,'REVISADO']]},{'Cotizaciones':'bloqueada'},NOW)
            wb = load_workbook(book)
            self.assertEqual(wb['Cotizaciones']['B7'].value,1510)
            self.assertEqual(wb['SOFR'].max_row,7)
            self.assertEqual(wb['SOFR']['B7'].value,0.0396)
            wb.close()
            stable = book.read_bytes()
            (book.parent/('~$'+book.name)).touch()
            with self.assertRaises(ValueError): apply_results(book,result,{},NOW)
            self.assertEqual(book.read_bytes(),stable)
            with self.assertRaises(ValueError): apply_results(book,{}, {'SOFR':'error'},NOW)
            self.assertEqual(book.read_bytes(),stable)

if __name__ == '__main__': unittest.main()
