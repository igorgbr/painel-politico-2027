import copy
import json
import tempfile
import unittest
from pathlib import Path
from backend.sources.senate_attendance import parse_licenses
from backend.store import Store


def fixture(records=None):
    person={'Codigo':'6009','Nome':'Perfil oficial'}
    if records is not None:person['Licencas']={'Licenca':records}
    return {'LicencaParlamentar':{'Parlamentar':person}}


RECORD={'Codigo':'123','DataInicio':'2026-06-09','DataFim':'2026-06-11','DataInicioPrevista':'2026-06-09','DataFimPrevista':'2026-06-12','SiglaTipoAfastamento':'LICENCA_ATIVIDADE_PARLAMENTAR','DescricaoTipoAfastamento':'Missão política ou cultural de interesse parlamentar'}


def parse(data):
    return parse_licenses(json.dumps(data).encode(),'6009','2026-01-01','2026-10-08','2026-10-09T01:00:00Z')


class SenateAttendanceTests(unittest.TestCase):
    def test_license_dates_are_preserved_without_attendance_inference(self):
        h=parse(fixture(RECORD))
        self.assertEqual(h['registros'],1)
        self.assertEqual(h['licencas'][0]['fim'],'2026-06-11')
        self.assertEqual(h['licencas'][0]['fimPrevisto'],'2026-06-12')
        for field in ['presenca','faltas','naoJustificada','totalDias']:self.assertNotIn(field,h)

    def test_no_records_is_a_valid_query_not_zero_absences(self):
        h=parse(fixture())
        self.assertEqual(h['registros'],0)
        self.assertEqual(h['licencas'],[])
        self.assertNotIn('faltas',h)

    def test_mismatched_identity_duplicate_and_invalid_dates_are_rejected(self):
        wrong=fixture(RECORD);wrong['LicencaParlamentar']['Parlamentar']['Codigo']='42'
        for data in [wrong,fixture([RECORD,RECORD]),fixture(dict(RECORD,DataFim='2026-06-08')),fixture(dict(RECORD,DataInicio='2026-02-30')),fixture(dict(RECORD,DataInicio='20260609')),fixture(dict(RECORD,DescricaoTipoAfastamento=''))]:
            with self.assertRaises((ValueError,KeyError)):parse(data)

    def test_open_licenses_and_future_plans_do_not_use_planned_end_as_effective(self):
        open_license=dict(RECORD,DataFim='',DataFimPrevista='2026-12-31')
        h=parse(fixture(open_license));self.assertIsNone(h['licencas'][0]['fim'])
        planned=dict(RECORD,DataInicio='',DataFim='',DataInicioPrevista='2026-06-09')
        self.assertIsNone(parse(fixture(planned))['licencas'][0]['inicio'])
        future=dict(planned,DataInicioPrevista='2026-11-01',DataFimPrevista='2026-11-03')
        self.assertEqual(parse(fixture(future))['registros'],0)
        old=dict(RECORD,DataInicio='2025-06-09',DataFim='2025-06-11',DataInicioPrevista='2025-06-09',DataFimPrevista='2025-06-11')
        self.assertEqual(parse(fixture(old))['registros'],0)

    def test_persistence_separate_from_attendance_and_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'db.sqlite3')
            store.db.execute("INSERT INTO people VALUES('p','Teste')");store.db.commit()
            h=parse(fixture(RECORD));store.save_senate_licenses('p',h)
            self.assertEqual(store.senate_licenses('p'),[h])
            self.assertEqual(store.attendance('p'),[])
            self.assertEqual(store.db.execute('SELECT count(*) FROM indicators').fetchone()[0],0)
            self.assertEqual(store.db.execute('PRAGMA user_version').fetchone()[0],7)
            store.close()
