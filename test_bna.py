"""Pruebas sintéticas de reglas; sus precios no son cotizaciones reales."""
import unittest
import argparse
import tempfile
from pathlib import Path
from datetime import date
from decimal import Decimal
from actualizar_bna import resolve, validate_snapshot, parse_date, parse_number, HEADERS, URL
from actualizar_bna import run, ROOT

class Rules(unittest.TestCase):
    def setUp(self):
        self.records = {date(2026, 10, 22): tuple(map(Decimal, ['10','20','11','21'])),
                        date(2026, 10, 26): tuple(map(Decimal, ['12','22','13','23']))}

    def test_exact_previous_order_duplicates_and_ignore_extra(self):
        inputs = [(2,date(2026,10,26)), (3,date(2026,10,24)), (4,date(2026,10,24))]
        r = resolve(inputs, self.records, date(2026,10,27))
        self.assertEqual(len(r),3)
        self.assertEqual([x[2] for x in r], [date(2026,10,26),date(2026,10,22),date(2026,10,22)])
        self.assertEqual(r[1][3],2)
        self.assertEqual([x[-1] for x in r],[2,3,4])

    def test_unavailable_invalid_blank_future_and_today(self):
        r=resolve([(2,'01/10/2026'),(3,'31/02/2026'),(4,None),(5,'28/10/2026'),(6,'26/10/2026')],self.records,date(2026,10,26))
        for x in r[:4]:
            self.assertIsNone(x[2])
            self.assertIsNone(x[4])
        self.assertIn('PROVISIONAL',r[4][8])
        old=resolve([(2,'26/10/2026')],self.records,date(2026,10,27),date(2026,10,26))
        self.assertIn('PROVISIONAL',old[0][8])

    def test_parse(self):
        self.assertEqual(parse_number('1.234,5678'),Decimal('1234.5678'))
        for x in [45000,'02-03-26','13/13/2026']:
            with self.assertRaises(ValueError): parse_date(x)
        for x in ['0,0000','-1,0000','1.23','s/d']:
            with self.assertRaises(ValueError): parse_number(x)

    def test_source_validation(self):
        s=dict(url=URL, source=True, headers=HEADERS, captured_at='2026-10-27T20:00:00Z',queried_from='2026-10-01',queried_to='2026-10-27', rows=[['26/10/2026','10,0000','20,0000','11,0000','21,0000']])
        self.assertEqual(len(validate_snapshot(s)[0]),1)
        for field,value in [('rows',[]),('source',False),('headers',['Otra'])]:
            with self.assertRaises(ValueError): validate_snapshot(dict(s,**{field:value}))
        with self.assertRaises(ValueError): validate_snapshot(dict(s,rows=s['rows']*2))
        with self.assertRaises(ValueError): validate_snapshot(dict(s,rows=[['26/10/2026','30,0000','20,0000','11,0000','21,0000']]))

    def test_workbook_end_to_end_with_real_saved_source(self):
        from openpyxl import load_workbook
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            inputfile=Path(folder)/'entrada.xlsx'
            outputfile=Path(folder)/'salida.xlsx'
            wb=load_workbook(ROOT/'BNA_independiente.xlsx')
            ws=wb['Fechas']
            for r,v in enumerate(['26/10/2026',None,'24/10/2026','24/10/2026','31/02/2026','30/09/2026'],2):
                ws.cell(r,1,v)
            ws['D2']='Billete Venta'
            wb.save(inputfile)
            run(argparse.Namespace(archivo=str(inputfile),salida=str(outputfile),snapshot='evidencia/fuente_verificada.json'))
            out=load_workbook(outputfile)['Resultados']
            self.assertEqual(out['B7'].value,1560)
            self.assertEqual(out['B9'].value,1550)
            self.assertEqual(out['B10'].value,1550)
            self.assertEqual(out['J10'].value,5)
            self.assertIsNone(out['B8'].value)
            self.assertIsNone(out['B11'].value)
            self.assertIsNone(out['B12'].value)
            self.assertIn('SIN ANTECEDENTE',out['I12'].value)
            with self.assertRaises(ValueError):
                run(argparse.Namespace(archivo=str(inputfile),salida=str(outputfile),snapshot='evidencia/fuente_verificada.json'))

if __name__=='__main__': unittest.main()
