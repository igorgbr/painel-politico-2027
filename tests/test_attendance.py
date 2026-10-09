import tempfile
import importlib.util
import hashlib
import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError
import unittest
from pathlib import Path
from backend.sources.attendance import parse_attendance, AttendanceMismatch, AttendanceUnavailable
from backend.sources.subsidy import reference
from backend.store import Store


def page(days):
    html='<h2>Presença em Plenário - 2026</h2><a href="https://www.camara.leg.br/deputados/42?ano=2026">Perfil</a><table>'
    for date,status in days:
        html+=f'<tr class="info-data"><td>{date}</td><td></td><td>{status}</td></tr><tr class="info-data__child"><td>Sessão</td><td>Presença</td><td></td></tr>'
    totals={'Total de dias com sessões deliberativas realizadas no período':len(days),'Total de dias com presença nas sessões deliberativas':sum(s=='Presença' for _,s in days),'Total de dias com ausências justificadas em sessões deliberativas':sum(s=='Ausência justificada' for _,s in days),'Total de dias com ausências não justificadas em sessões deliberativas':sum(s=='Ausência não justificada' for _,s in days)}
    for label,n in totals.items():html+=f'<tr><td>{label}</td><td>{n}</td><td>0%</td></tr>'
    return (html+'</table>').encode()


class AttendanceTests(unittest.TestCase):
    def test_day_scope_justifications_and_other_status(self):
        rows=[('01/02/2026','Presença'),('02/02/2026','Ausência justificada'),('03/02/2026','Ausência não justificada'),('04/02/2026','Licença')]
        h=parse_attendance(page(rows),'42',2026,'2026-10-06','2026-10-06T23:00:00Z')
        self.assertEqual([h[k] for k in ['totalDias','presenca','justificada','naoJustificada','outros']],[4,1,1,1,1])
        self.assertEqual(h['unidade'],'dias')
        for rows in [[('01/02/2026','Presença')]*2,[('01/02/2027','Presença')],[('01/02/2026','')]]:
            with self.assertRaises(ValueError):parse_attendance(page(rows),'42',2026,'2026-10-06','2026-10-06T23:00:00Z')
        with self.assertRaises(ValueError):parse_attendance(page([]),'43',2026,'2026-10-06','2026-10-06T23:00:00Z')
        with self.assertRaises(ValueError):parse_attendance(page([]).replace(b'<td>0</td>',b'<td>1</td>',1),'42',2026,'2026-10-06','2026-10-06T23:00:00Z')


    def test_mismatch_reports_expected_counts_and_original_statuses(self):
        raw=page([('01/02/2026','Presença')]).replace(b'<td>1</td>',b'<td>2</td>',1)
        with self.assertRaises(AttendanceMismatch) as caught:
            parse_attendance(raw,'42',2026,'2026-10-06','2026-10-06T23:00:00Z')
        diagnostic=caught.exception.diagnostic
        self.assertEqual(diagnostic['resumoOficial']['totalDias'],2)
        self.assertEqual(diagnostic['contagemDiaria']['totalDias'],1)
        self.assertEqual(diagnostic['situacoes'],{'Presença':1})

    def test_status_notes_reconcile_without_turning_license_into_absence(self):
        raw=page([('01/02/2026','Presença'),('02/02/2026','Ausência justificada'),('03/02/2026','Ausência não justificada'),('04/02/2026','Licença')])
        raw=raw.replace('Ausência justificada</td>'.encode(),'Ausência justificada — missão oficial</td>'.encode()).replace('Ausência não justificada</td>'.encode(),'Ausência não justificada (em revisão)</td>'.encode())
        h=parse_attendance(raw,'42',2026,'2026-10-06','2026-10-06T23:00:00Z')
        self.assertEqual([h[k] for k in ['presenca','justificada','naoJustificada','outros']],[1,1,1,1])
        self.assertIn('missão oficial',h['dias'][1]['situacao'])


    def test_outage_stops_new_requests_and_diagnosis_never_publishes(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('attendance_collector',root/'scripts/ingest-attendance.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            temp=Path(directory);cache=temp/'cache';cache.mkdir()
            index=temp/'data.json';index.write_text(json.dumps({'versao':'unchanged'}))
            members=[dict(id=str(i),pessoaId=str(i),vinculos={'camara':str(i)}) for i in range(1,8)]
            for i in (5,6):
                url=module.URL.format(code=i,year=2026)
                (cache/(hashlib.sha256(url.encode()).hexdigest()+'.bin')).write_bytes(page([('01/02/2026','Presença')]).replace(b'deputados/42?',f'deputados/{i}?'.encode()))
            store=MagicMock();store.latest.return_value={'senado':[],'camara':members}
            argv=['collector','--diagnose-only','--db',str(temp/'db.sqlite3'),'--cache',str(cache),'--output',str(index)]
            with patch.object(module,'ROOT',temp),patch.object(module,'Store',return_value=store),patch.object(module,'publish') as publish,patch.object(module.urllib.request,'urlopen',side_effect=URLError('offline')) as request,patch('sys.argv',argv):
                module.main()
            self.assertEqual(request.call_count,4)
            store.save_attendance.assert_not_called();store.save_reference.assert_not_called();store.run.assert_not_called();publish.assert_not_called()
            report=json.loads((temp/'docs/attendance-attempt.json').read_text())
            self.assertEqual(report['validados'],2)
            self.assertTrue(report['fonteSemConexao'])
            self.assertEqual(report['errosPorTipo'],{'conexao':4,'adiada':1})
            self.assertEqual(json.loads(index.read_text())['versao'],'unchanged')


    def test_official_justification_labels_match_summary(self):
        labels=['Missão Autorizada','Licença para Tratamento de Saúde','Licença-Gestante (Maternidade)','Licença Paternidade','Decisão da Mesa']
        for label in labels:
            raw=page([('01/02/2026','Ausência justificada')]).replace('Ausência justificada</td>'.encode(),(label+'</td>').encode())
            h=parse_attendance(raw,'42',2026,'2026-10-08','2026-10-09T01:00:00Z')
            self.assertEqual(h['justificada'],1)
            self.assertEqual(h['naoJustificada'],0)
            self.assertEqual(h['dias'][0]['situacao'],label)
        raw=page([('01/02/2026','Ausência não justificada')]).replace('Ausência não justificada</td>'.encode(),'Ausência</td>'.encode())
        h=parse_attendance(raw,'42',2026,'2026-10-08','2026-10-09T01:00:00Z')
        self.assertEqual(h['naoJustificada'],1)
        # O rótulo sozinho não é suficiente: deve conferir com o resumo oficial.
        raw=page([('01/02/2026','Ausência justificada')]).replace('Ausência justificada</td>'.encode(),'Ausência</td>'.encode())
        with self.assertRaises(AttendanceMismatch):
            parse_attendance(raw,'42',2026,'2026-10-08','2026-10-09T01:00:00Z')

    def test_official_no_data_is_unavailable_instead_of_zero(self):
        raw=page([])+b'<p>N'+ 'ão há dados disponíveis para o ano de 2026.'.encode()+b'</p>'
        with self.assertRaises(AttendanceUnavailable):
            parse_attendance(raw,'42',2026,'2026-10-08','2026-10-09T01:00:00Z')

    def test_reference_requires_current_guide_and_matching_norm(self):
        guide='Decreto Legislativo 172/2022, remuneração bruta mensal em R$ 46.366,19 a partir de 1º de fevereiro de 2025. O valor é o mesmo para deputados federais e senadores'.encode()
        norm='membros do Congresso Nacional IV - R$ 46.366,19'.encode()
        value=reference(guide,norm,'2026-10-06T23:00:00Z')
        self.assertEqual(value['valorCentavos'],4636619)
        self.assertEqual(value['tipo'],'referencia-bruta-mensal')
        with self.assertRaises(ValueError):reference(guide,norm.replace(b'46.366,19',b'44.008,52'),'2026-10-06T23:00:00Z')

    def test_persistence_does_not_fill_individual_pay_or_transfer_absences(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'data.sqlite3')
            store.db.execute("INSERT INTO people VALUES('p-test','Teste')");store.db.commit()
            h=parse_attendance(page([('01/02/2026','Ausência não justificada')]),'42',2026,'2026-10-06','2026-10-06T23:00:00Z')
            store.save_attendance('p-test',h)
            self.assertEqual(store.attendance('p-test')[0]['naoJustificada'],1)
            store.save_reference('subsidio',{'valorCentavos':4636619})
            self.assertEqual(store.reference('subsidio')['valorCentavos'],4636619)
            self.assertEqual(store.db.execute('SELECT count(*) FROM indicators').fetchone()[0],0)
            store.close()
