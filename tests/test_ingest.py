import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('ingest', Path(__file__).resolve().parents[1] / 'scripts/ingest.py')
ingest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingest)
COLLECTED = '2026-10-06T01:00:00+00:00'


def candidates_zip(rows):
    stream = io.StringIO(newline='')
    fields = ['ANO_ELEICAO', 'NR_TURNO', 'DS_CARGO', 'SQ_CANDIDATO', 'SG_UF', 'NM_URNA_CANDIDATO', 'SG_PARTIDO', 'DS_SIT_TOT_TURNO', 'DT_GERACAO', 'HH_GERACAO', 'CD_TIPO_ELEICAO']
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter=';')
    writer.writeheader()
    for row in rows:
        writer.writerow(dict(ANO_ELEICAO='2026', NR_TURNO='1', DS_CARGO='DEPUTADO FEDERAL', SQ_CANDIDATO='100', SG_UF='SC', NM_URNA_CANDIDATO='Exemplo', SG_PARTIDO='PL', DS_SIT_TOT_TURNO='ELEITO POR QP', DT_GERACAO='05/10/2026', HH_GERACAO='10:14:11', CD_TIPO_ELEICAO='2', **{}) | row)
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as archive:
        archive.writestr('consulta_cand_2026_BRASIL.csv', stream.getvalue().encode('latin1'))
    return raw.getvalue()


class IngestTests(unittest.TestCase):
    def test_only_elected_main_offices(self):
        data = candidates_zip([{}, {'SQ_CANDIDATO': '101', 'DS_CARGO': 'SENADOR', 'DS_SIT_TOT_TURNO': 'ELEITO'}, {'SQ_CANDIDATO': '102', 'DS_SIT_TOT_TURNO': 'SUPLENTE'}, {'SQ_CANDIDATO': '103', 'DS_CARGO': '1º SUPLENTE', 'DS_SIT_TOT_TURNO': 'ELEITO'}, {'SQ_CANDIDATO': '104', 'DS_SIT_TOT_TURNO': '#NULO'}])
        result = ingest.tse_members(data, COLLECTED)
        self.assertEqual([m['fonte']['id'] for m in result], ['100', '101'])
        self.assertEqual([m['fim'] for m in result], [2031, 2035])
        self.assertTrue(all(m['aprov'] is None and m['custo'] is None for m in result))
        self.assertTrue(all('CPF' not in json.dumps(m) for m in result))

    def test_wrong_election_rejected(self):
        for field, value in [('ANO_ELEICAO', '2022'), ('NR_TURNO', '2'), ('CD_TIPO_ELEICAO', '1')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                ingest.tse_members(candidates_zip([{field: value}]), COLLECTED)

    def test_substitute_and_mandate_continuity(self):
        def row(end):
            return {'IdentificacaoParlamentar': {'CodigoParlamentar': '123', 'NomeParlamentar': 'Suplente em exercício', 'UfParlamentar': 'SC', 'SiglaPartidoParlamentar': 'PL', 'UrlPaginaParlamentar': 'http://www25.senado.leg.br/web/senadores/123'}, 'Mandato': {'CodigoMandato': '42', 'PrimeiraLegislaturaDoMandato': {'DataInicio': '2023-02-01' if end == '2031' else '2019-02-01'}, 'SegundaLegislaturaDoMandato': {'DataFim': end + '-01-31'}, 'DescricaoParticipacao': '1º Suplente', 'Titular': {'NomeParlamentar': 'Titular'}}}
        data = {'ListaParlamentarEmExercicio': {'Metadados': {'Versao': '05/10/2026 22:00:00'}, 'Parlamentares': {'Parlamentar': [row('2031'), row('2027')]}}}
        result = ingest.continuing_members(json.dumps(data), COLLECTED)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['titular'], 'Titular')
        self.assertEqual(result[0]['participacao'], '1º Suplente')
        self.assertIsNone(result[0]['partidoEleicao'])

    def test_complete_snapshot_and_no_private_documents(self):
        data = json.loads((ingest.ROOT / 'public/data.json').read_text())
        ingest.validate(data['senado'] + data['camara'])
        self.assertEqual(len(data['senado']), 81)
        self.assertEqual(len(data['camara']), 513)
        for m in data['senado'] + data['camara']:
            for key in ['faltas', 'salario', 'custo']:
                self.assertIsNone(m[key])
            for key in ['aprov', 'neg']:
                if m[key] is not None: self.assertEqual(m['indicadores'][key]['cobertura'], 'completa')
            self.assertFalse(set(m) & {'cpf', 'NR_CPF_CANDIDATO', 'email', 'dataNascimento'})
        self.assertEqual(sum(m['ini'] == 2023 for m in data['senado']), 27)

    def test_duplicate_and_incomplete_rejected(self):
        data = json.loads((ingest.ROOT / 'public/data.json').read_text())
        members = data['senado'] + data['camara']
        for invalid in [members[:-1], members + [members[0]]]:
            with self.assertRaises(ValueError):
                ingest.validate(invalid)

    def test_failure_preserves_last_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, report, raw, senate = [Path(tmp) / name for name in ['data.json', 'report.json', 'tse.zip', 'senado.json']]
            output.write_text('último conjunto válido')
            raw.write_bytes(candidates_zip([{}]))
            senate.write_text('{}')
            with patch('sys.argv', ['ingest', '--tse-zip', str(raw), '--senado-json', str(senate), '--output', str(output), '--report', str(report), '--db', str(Path(tmp) / 'test.sqlite3'), '--cache', str(Path(tmp) / 'cache')]):
                with self.assertRaises(SystemExit):
                    ingest.main()
            self.assertEqual(output.read_text(), 'último conjunto válido')
            self.assertEqual(json.loads(report.read_text())['status'], 'erro')


if __name__ == '__main__':
    unittest.main()
