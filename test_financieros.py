"""Contratos de las nuevas series y migración del libro en copias temporales."""
import copy
import shutil
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from openpyxl import load_workbook
from actualizar_economicos import BOOK, SCHEMAS, apply_results, existing_rows
from fuentes_economicas import TZ
from fuentes_financieras import parse_forex, parse_cauciones, parse_riesgo

TODAY = date(2026,10,28)
NOW = datetime(2026,10,28,20,tzinfo=TZ)

class FinancialSources(unittest.TestCase):
    def test_forex_matches_photo_millions_not_peso_amount(self):
        payload = [{'fecha':'2026-10-26T00:00:00','cantidad':1132801649500,'volumen':764073000}]
        rows = parse_forex(payload,TODAY,date(2026,10,1))
        self.assertEqual(f'{rows[0][1]:.1f}','764.1')
        with self.assertRaises(ValueError): parse_forex(payload*2,TODAY,date(2026,10,1))
        payload[0]['volumen'] = -1
        with self.assertRaises(ValueError): parse_forex(payload,TODAY,date(2026,10,1))

    def test_caucion_photo_vwap_not_last_trade_and_friday(self):
        detail = dict(ticker='CAARS',tipoEmision='CAU',moneda='$',plazo='001',
                      fecha='2026-10-26T00:00:00',fechaLiquidacion='2026-10-27T00:00:00',
                      tasaPP=20.7117,ultimaTasa=25,minimo=17.5,maximo=25)
        payload = [{'fecha':'2026-10-26','details':[detail]}]
        row = parse_cauciones(payload,TODAY,date(2026,10,1))[0]
        self.assertEqual(f'{row[1]:.2%}','20.71%')
        self.assertEqual(f'{row[2]:.2%}','23.01%')
        self.assertEqual(row[3],1)
        friday = dict(detail,plazo='003',fecha='2026-10-23T00:00:00',
                      fechaLiquidacion='2026-10-26T00:00:00',tasaPP=20.5678)
        row = parse_cauciones([{'fecha':'2026-10-23','details':[friday]}],TODAY,date(2026,10,1))[0]
        self.assertEqual(f'{row[1]:.2%}','20.57%'); self.assertEqual(f'{row[2]:.2%}','22.83%')
        self.assertEqual(row[3],3)
        with self.assertRaises(ValueError): parse_cauciones([{'fecha':'2026-10-26','details':[detail,detail]}],TODAY,date(2026,10,1))
        wrong = dict(detail,ticker='CAUSD',moneda='D')
        with self.assertRaises(ValueError): parse_cauciones([{'fecha':'2026-10-26','details':[wrong]}],TODAY,date(2026,10,1))

    def test_riesgo_country_points_header_and_dates(self):
        data = [['Fecha','Puntos'],['28-10-2026','763,00'],['27-10-2026','753,00']]
        rows = parse_riesgo(data,TODAY)
        self.assertEqual(rows[-1][1],763)
        for bad in ([['Fecha','Dólar'],['28-10-2026','763,00']],data+[data[-1]],
                    [['Fecha','Puntos'],['29-10-2026','805,00']]):
            with self.assertRaises(ValueError): parse_riesgo(bad,TODAY)

class FinancialWorkbook(unittest.TestCase):
    def test_reactivates_errepar_preserves_history_removes_rofex_and_other_sheets(self):
        with tempfile.TemporaryDirectory() as folder:
            book=Path(folder)/'Datos Financieros.xlsx'; shutil.copy2(BOOK,book)
            apply_results(book,{'Cotizaciones':[[TODAY,1510,1560,'PUBLICADO']]},{},NOW)
            w=load_workbook(book)
            history=list(w['Histórico Errepar'].values)
            w.create_sheet('ROFEX')['A1']='historial anterior'
            w.create_sheet('Notas usuario')['A1']='conservar'
            w.save(book); w.close()
            before=book.read_bytes()
            results={'Errepar':[[TODAY,1500,1550,1520,1530,TODAY,'PUBLICADO EN ERREPAR']],
                     'FOREX':[[TODAY,764.073,'PUBLICADO']],
                     'Cauciones':[[TODAY,.207117,(1+.207117/365)**365-1,1,'VWAP']],
                     'Riesgo país':[[TODAY,763,'PUBLICADO']]}
            report=apply_results(book,results,{},NOW)
            self.assertEqual(Path(report['respaldo']).read_bytes(),before)
            w=load_workbook(book)
            self.assertNotIn('ROFEX',w.sheetnames); self.assertNotIn('Histórico Errepar',w.sheetnames)
            rows=existing_rows(w,'Errepar')
            self.assertEqual(len(rows),28)
            self.assertEqual(rows[0][1:5],list(history[6][1:5]))
            self.assertEqual(rows[-1][1:5],[1500,1550,1520,1530])
            self.assertEqual(w['Notas usuario']['A1'].value,'conservar')
            self.assertEqual(w['Cauciones']['B7'].number_format,'0.00%')
            self.assertEqual(w['FOREX']['B7'].number_format,'#,##0.0')
            self.assertEqual(w['Riesgo país']['B7'].value,763)
            self.assertEqual(w['Fuente'].max_row,5)
            w.close()
            apply_results(book,results,{},NOW)
            w=load_workbook(book)
            self.assertEqual(len(existing_rows(w,'Errepar')),28)
            self.assertEqual(len(existing_rows(w,'FOREX')),1); w.close()

    def test_rofex_never_collected_and_failed_new_source_is_marked(self):
        self.assertNotIn('ROFEX',SCHEMAS)
        with tempfile.TemporaryDirectory() as folder:
            book=Path(folder)/'copy.xlsx'; shutil.copy2(BOOK,book)
            apply_results(book,{'SOFR':[[date(2026,10,27),.0395,'PUBLICADO']]},{'FOREX':'HTTP 403'},NOW)
            w=load_workbook(book)
            self.assertEqual(w['FOREX'].max_row,6)
            self.assertIn('SIN CONSULTA CORRECTA',w['FOREX']['A3'].value); w.close()

if __name__ == '__main__': unittest.main()
