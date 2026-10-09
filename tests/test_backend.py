import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.http import HttpCache
from backend.publish import publish
from backend.store import Store

ROOT = Path(__file__).resolve().parents[1]


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'store.sqlite3')
        self.payload = json.loads((ROOT / 'public/data.json').read_text())
        self.payload.pop('versao', None)
        self.payload['schemaVersion'] = 1
        for m in self.payload['senado'] + self.payload['camara']:
            for key in ['pessoaId', 'mandatoId', 'identidade', 'detalhesUrl']:
                m.pop(key, None)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_repeated_import_stable_identity_and_separate_entities(self):
        first = self.store.stage(copy.deepcopy(self.payload))
        second = self.store.stage(copy.deepcopy(self.payload))
        self.assertEqual(first, second)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM people').fetchone()[0], 594)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM candidates').fetchone()[0], 567)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM mandates').fetchone()[0], 594)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM exercises').fetchone()[0], 594)

    def test_same_name_does_not_merge_people(self):
        self.payload['senado'][0]['nome'] = self.payload['camara'][0]['nome']
        self.store.stage(self.payload)
        self.assertNotEqual(self.payload['senado'][0]['pessoaId'], self.payload['camara'][0]['pessoaId'])

    def test_snapshot_history_preserves_old_exercises(self):
        old = self.store.stage(copy.deepcopy(self.payload))
        replacement = copy.deepcopy(self.payload)
        replacement['atualizadoEm'] = '2026-10-07T00:00:00+00:00'
        replacement['senado'][0]['fonte']['id'] = 'replacement-identity'
        replacement['senado'][0]['nome'] = 'Novo ocupante'
        new = self.store.stage(replacement)
        self.assertNotEqual(old, new)
        ids = self.store.db.execute('SELECT DISTINCT person_id FROM exercises WHERE mandate_id=?', (replacement['senado'][0]['id'],)).fetchall()
        self.assertEqual(len(ids), 2)

    def test_publication_versioned_details_and_index_last(self):
        output = self.root / 'public/data.json'
        version = publish(self.store, self.payload, output)
        index = json.loads(output.read_text())
        self.assertEqual(index['versao'], version)
        for m in index['senado'] + index['camara']:
            detail = json.loads((output.parent / m['detalhesUrl']).read_text())
            self.assertEqual(detail['pessoaId'], m['pessoaId'])
            self.assertEqual(detail['versao'], version)
            self.assertNotIn('projetos', m)
        original = output.read_bytes()
        failed = copy.deepcopy(self.payload)
        failed['atualizadoEm'] = '2026-10-08T00:00:00+00:00'
        with patch('backend.publish.atomic_json', side_effect=OSError('disco indisponível')):
            with self.assertRaises(OSError):
                publish(self.store, failed, output)
        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM snapshots WHERE status='published'").fetchone()[0], 1)

    def test_senate_session_evidence_survives_republication_separate_from_daily_counts(self):
        self.store.prepare(self.payload)
        m=self.payload['senado'][0]
        senate={'casa':'senado','periodoInicio':'2026-09-01','periodoFim':'2026-09-03','totalSessoes':1,'sessoes':[{'id':'120'}]}
        camara={'casa':'camara','periodoInicio':'2026-09-01','periodoFim':'2026-09-03','totalDias':3,'dias':[{'data':'2026-09-01'}]}
        self.store.save_attendance(m['pessoaId'],senate)
        self.store.save_attendance(m['pessoaId'],camara)
        output=self.root/'public/data.json'
        for _ in range(2):
            publish(self.store,self.payload,output)
            index=json.loads(output.read_text())['senado'][0]
            detail=json.loads((output.parent/index['detalhesUrl']).read_text())
            self.assertEqual(detail['comparecimentosSenado'],[senate])
            self.assertEqual(detail['presencasHistoricas'],[camara])
            self.assertEqual(index['resumosHistoricos']['comparecimentosSenado'][0]['totalSessoes'],1)
            self.assertNotIn('sessoes',index['resumosHistoricos']['comparecimentosSenado'][0])
            self.assertNotIn('comparecimentosSenado',index)

    def test_cache_resumes_completed_pages_after_failure(self):
        calls = []
        first = 'https://dadosabertos.camara.leg.br/api/v2/test?page=1'
        second = first.replace('1', '2')
        def fetch(url):
            calls.append(url)
            if url == second and calls.count(second) == 1:
                raise OSError('falha transitória')
            return json.dumps({'dados': [url], 'links': [{'rel': 'next', 'href': second}] if url == first else []}).encode()
        cache = HttpCache(self.root / 'cache', fetch=fetch)
        with self.assertRaises(OSError):
            list(cache.pages(first))
        self.assertEqual(list(cache.pages(first)), [[first], [second]])
        self.assertEqual(calls.count(first), 1)
        self.assertEqual(calls.count(second), 2)

    def test_reject_cycle_external_origin_and_invalid_cache(self):
        url = 'https://dadosabertos.camara.leg.br/api/v2/test'
        for target in [url, 'https://example.com/data']:
            cache = HttpCache(self.root / target.split('//')[-1].replace('/', '_'), fetch=lambda _: json.dumps({'dados': [], 'links': [{'rel': 'next', 'href': target}]}).encode())
            with self.assertRaises(ValueError):
                list(cache.pages(url))
        cache = HttpCache(self.root / 'bad-cache', fetch=lambda _: b'{invalid')
        with self.assertRaises(ValueError):
            list(cache.pages(url))
        self.assertFalse(list(cache.directory.glob('*.bin')))

    def test_composition_refresh_preserves_verified_history(self):
        from backend.sources.history import history_record
        original = copy.deepcopy(self.payload)
        self.store.stage(original)
        member = original['camara'][0]
        self.store.link(member['pessoaId'], 'camara-parlamentar', '123', 'evidência de teste', ['https://dadosabertos.camara.leg.br/api/v2/deputados/123'])
        h = history_record('camara','123',{},'2023-02-01','2026-10-05','2026-10-05T23:00:00-03:00',['https://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes-2023.csv'])
        self.store.save_history(member['pessoaId'],h)
        fresh=copy.deepcopy(self.payload)
        output=self.root/'published/data.json'
        publish(self.store,fresh,output)
        result=json.loads(output.read_text())['camara'][0]
        self.assertEqual(result['vinculos']['camara'],'123')
        self.assertEqual(result['aprov'],0)
        detail=json.loads((output.parent/result['detalhesUrl']).read_text())
        self.assertEqual(len(detail['historicosLegislativos']),1)
        self.assertEqual(self.store.db.execute('SELECT coverage FROM indicators LIMIT 1').fetchone()[0],'completa')

    def test_writer_lock_rejects_second_ingestion(self):
        import fcntl
        import importlib.util
        spec = importlib.util.spec_from_file_location('locked_ingest', ROOT / 'scripts/ingest.py')
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        db = self.root / 'locked.sqlite3'
        with Path(str(db) + '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch('sys.argv', ['ingest', '--db', str(db), '--export-only']):
                with self.assertRaises(SystemExit):
                    cli.main()
        self.assertFalse(db.exists())

    def test_failed_source_does_not_remove_other_data(self):
        self.store.run('camara-projetos', '2026-10-06T00:00:00+00:00', ValueError('falha'))
        self.store.stage(self.payload)
        self.assertEqual(self.store.db.execute('SELECT source,status FROM runs').fetchone(), ('camara-projetos', 'error'))
        self.assertEqual(len(self.store.latest()['camara']), 513)


if __name__ == '__main__':
    unittest.main()


class PruneSnapshotsTest(__import__('unittest').TestCase):
    def test_keeps_current_and_previous(self):
        import os, tempfile, time
        from pathlib import Path
        from backend.publish import prune_snapshots
        with tempfile.TemporaryDirectory() as tmp:
            for i, name in enumerate(['a', 'b', 'c', 'd']):
                (Path(tmp) / name).mkdir(); os.utime(Path(tmp) / name, (i, i))
            prune_snapshots(tmp, 'a')
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ['a', 'd'])
