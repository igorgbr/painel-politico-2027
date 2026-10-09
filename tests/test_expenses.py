import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from backend.sources.expenses import parse_expenses, record, cents
from backend.store import Store


def archive(rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=['ideCadastro','numAno','numMes','vlrLiquido','vlrRestituicao','txtDescricao','ideDocumento'], delimiter=';')
    writer.writeheader(); writer.writerows(rows)
    result = io.BytesIO()
    with zipfile.ZipFile(result,'w') as z: z.writestr('Ano-2026.csv',stream.getvalue())
    return result.getvalue()


class ExpenseTests(unittest.TestCase):
    def test_competence_credits_and_repeated_document(self):
        base = dict(ideCadastro='42',numAno='2026',numMes='2',vlrLiquido='100.10',vlrRestituicao='',txtDescricao='Transporte',ideDocumento='7')
        rows = [base,base | dict(vlrLiquido='-20.05'),base | dict(vlrLiquido='0',vlrRestituicao='10'),base | dict(ideCadastro=''),base | dict(numMes='10')]
        values = parse_expenses(archive(rows),'camara','2026-01-01','2026-09-30')['42']
        self.assertEqual(values['totalCentavos'],8005)
        self.assertEqual(values['restituicoesCentavos'],1000)
        self.assertEqual(values['registros'],3)
        expense = record('camara','42',values,'2026-01-01','2026-09-30','2026-10-06T12:00:00Z',['https://www.camara.leg.br/cotas/Ano-2026.csv.zip'])
        self.assertEqual(len(expense['meses']),9)
        self.assertEqual(sum(m['totalCentavos'] for m in expense['meses']),8005)
        self.assertNotIn('cpf',json.dumps(expense))

    def test_senate_duplicate_and_missing_category(self):
        row = dict(id=1,codSenador=42,ano=2026,mes=2,tipoDespesa=None,valorReembolsado=1.23)
        result = parse_expenses(json.dumps([row]).encode(),'senado','2026-01-01','2026-09-30')
        self.assertEqual(result['42']['totalCentavos'],123)
        with self.assertRaises(ValueError): parse_expenses(json.dumps([row,row]).encode(),'senado','2026-01-01','2026-09-30')
        for value in ['NaN','Infinity','0.001']:
            with self.assertRaises(ValueError): cents(value)

    def test_migration_persistence_and_enrichment(self):
        from backend.enrich import attach_expenses
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'test.sqlite3'
            store = Store(path)
            store.db.execute("INSERT INTO people VALUES('p-test','Teste')");store.db.commit()
            expense = dict(casa='camara',periodoInicio='2026-01-01',periodoFim='2026-09-30',coletadoEm='2026-10-06T12:00:00Z')
            store.save_expenses('p-test',expense)
            payload = dict(senado=[dict(pessoaId='p-test',casa='senado',custo=123)],camara=[])
            attach_expenses(store,payload)
            self.assertIsNone(payload['senado'][0]['custo'])
            self.assertEqual(payload['senado'][0]['despesasHistoricas'],[expense])
            store.close(); store = Store(path)
            self.assertEqual(store.expenses('p-test'),[expense]); store.close()
