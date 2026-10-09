"""SQLite privado: identidade separada de candidatura, mandato e exercício."""
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS migrations(version INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS senate_licenses(person_id TEXT NOT NULL REFERENCES people(id),period_start TEXT NOT NULL,period_end TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(person_id,period_start));
CREATE TABLE IF NOT EXISTS reference_values(name TEXT PRIMARY KEY,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attendance(person_id TEXT NOT NULL REFERENCES people(id),house TEXT NOT NULL,period_start TEXT NOT NULL,period_end TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(person_id,house,period_start));
CREATE TABLE IF NOT EXISTS photos(person_id TEXT PRIMARY KEY REFERENCES people(id), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS norms(project_id TEXT PRIMARY KEY, norma TEXT NOT NULL, source_url TEXT NOT NULL, collected_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS people(id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS identities(source TEXT NOT NULL, external_id TEXT NOT NULL,
 person_id TEXT NOT NULL REFERENCES people(id), PRIMARY KEY(source,external_id));
CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY, collected_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('staged','published')), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY, person_id TEXT NOT NULL REFERENCES people(id),
 election_year INTEGER NOT NULL, house TEXT NOT NULL, uf TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS mandates(id TEXT PRIMARY KEY, house TEXT NOT NULL, uf TEXT NOT NULL,
 start_year INTEGER NOT NULL, end_year INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS exercises(snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
 mandate_id TEXT NOT NULL REFERENCES mandates(id), person_id TEXT NOT NULL REFERENCES people(id),
 participation TEXT NOT NULL, observed_at TEXT NOT NULL, PRIMARY KEY(snapshot_id,mandate_id));
CREATE TABLE IF NOT EXISTS indicators(person_id TEXT NOT NULL REFERENCES people(id),
 house TEXT NOT NULL, metric TEXT NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
 value REAL, unit TEXT NOT NULL, coverage TEXT NOT NULL, source_url TEXT NOT NULL,
 collected_at TEXT NOT NULL, PRIMARY KEY(person_id,house,metric,period_start,period_end,source_url));
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, source TEXT NOT NULL, started_at TEXT NOT NULL,
 status TEXT NOT NULL, error TEXT);
CREATE TABLE IF NOT EXISTS identity_evidence(source TEXT NOT NULL, external_id TEXT NOT NULL,
 person_id TEXT NOT NULL REFERENCES people(id), method TEXT NOT NULL, evidence TEXT NOT NULL,
 PRIMARY KEY(source,external_id));
CREATE TABLE IF NOT EXISTS histories(person_id TEXT NOT NULL REFERENCES people(id), house TEXT NOT NULL,
 period_start TEXT NOT NULL, period_end TEXT NOT NULL, collected_at TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(person_id,house,period_start,period_end));
CREATE TABLE IF NOT EXISTS expenses(person_id TEXT NOT NULL REFERENCES people(id), house TEXT NOT NULL,
 period_start TEXT NOT NULL, period_end TEXT NOT NULL, collected_at TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(person_id,house,period_start,period_end));
CREATE TABLE IF NOT EXISTS artifacts(sha256 TEXT PRIMARY KEY, source TEXT NOT NULL, url TEXT NOT NULL,
 collected_at TEXT NOT NULL, path TEXT NOT NULL);
'''


class Store:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30)
        path.chmod(0o600)
        self.db.execute('PRAGMA foreign_keys=ON')
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1, 2, 3, 4, 5, 6, 7):
            raise ValueError('Versão do banco não suportada')
        self.db.executescript(SCHEMA)
        self.db.execute('INSERT OR IGNORE INTO migrations VALUES (7)')
        self.db.execute('PRAGMA user_version=7')
        self.db.commit()

    def close(self):
        self.db.close()

    def save_reference(self,name,value):
        with self.db:self.db.execute('INSERT INTO reference_values VALUES(?,?) ON CONFLICT(name) DO UPDATE SET payload=excluded.payload',(name,json.dumps(value,ensure_ascii=False)))

    def reference(self,name):
        row=self.db.execute('SELECT payload FROM reference_values WHERE name=?',(name,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_senate_licenses(self,person,value):
        with self.db:self.db.execute('INSERT INTO senate_licenses VALUES(?,?,?,?) ON CONFLICT(person_id,period_start) DO UPDATE SET period_end=excluded.period_end,payload=excluded.payload',(person,value['periodoInicio'],value['periodoFim'],json.dumps(value,ensure_ascii=False)))

    def senate_licenses(self,person):
        return [json.loads(row[0]) for row in self.db.execute('SELECT payload FROM senate_licenses WHERE person_id=? ORDER BY period_start',(person,))]

    def save_attendance(self,person,value):
        with self.db:self.db.execute('INSERT INTO attendance VALUES(?,?,?,?,?) ON CONFLICT(person_id,house,period_start) DO UPDATE SET period_end=excluded.period_end,payload=excluded.payload',(person,value['casa'],value['periodoInicio'],value['periodoFim'],json.dumps(value,ensure_ascii=False)))

    def attendance(self,person):
        return [json.loads(row[0]) for row in self.db.execute('SELECT payload FROM attendance WHERE person_id=? ORDER BY house,period_start',(person,))]

    def save_photo(self, person, photo):
        with self.db:
            self.db.execute('INSERT INTO photos VALUES(?,?) ON CONFLICT(person_id) DO UPDATE SET payload=excluded.payload', (person, json.dumps(photo, ensure_ascii=False)))

    def photo(self, person):
        row = self.db.execute('SELECT payload FROM photos WHERE person_id=?', (person,)).fetchone()
        return json.loads(row[0]) if row else None

    def run(self, source, collected, error=None):
        with self.db:
            self.db.execute('INSERT INTO runs(source,started_at,status,error) VALUES(?,?,?,?)',
                            (source, collected, 'error' if error else 'success', str(error) if error else None))

    def artifact(self, source, url, raw, collected, directory):
        from backend.http import atomic_bytes
        digest = hashlib.sha256(raw).hexdigest()
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)
        path = directory / digest
        if not path.exists():
            atomic_bytes(path, raw)
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?)', (digest, source, url, collected, str(path)))
        return digest

    def prepare(self, payload):
        # Sem vínculo por nome. Identidades eleitorais são provisórias até haver evidência de correspondência.
        with self.db:
            for m in payload['senado'] + payload['camara']:
                source = 'tse-candidatura-2026' if m['ini'] == 2027 else 'senado-parlamentar'
                external = m['fonte']['id']
                identity = self.db.execute('SELECT person_id FROM identities WHERE source=? AND external_id=?', (source, external)).fetchone()
                person = identity[0] if identity else 'p-' + str(uuid.uuid5(uuid.NAMESPACE_URL, source + ':' + external))
                self.db.execute('INSERT INTO people VALUES(?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name', (person, m['nome']))
                self.db.execute('INSERT OR IGNORE INTO identities VALUES(?,?,?)', (source, external, person))
                mandate = m['id']
                linked = {('camara' if src == 'camara-parlamentar' else 'senado'): eid for src, eid in self.db.execute('SELECT source,external_id FROM identity_evidence WHERE person_id=?', (person,))}
                if linked: m['vinculos'] = linked
                else: m.pop('vinculos', None)
                m.update(pessoaId=person, mandatoId=mandate, identidade='Vínculo oficial com histórico parlamentar verificado' if linked else 'Identidade na fonte; vínculo entre fontes ainda não verificado')
                if m['ini'] == 2027:
                    self.db.execute('INSERT OR IGNORE INTO candidates VALUES(?,?,?,?,?)', (m['id'], person, 2026, m['casa'], m['uf']))
                self.db.execute('INSERT OR IGNORE INTO mandates VALUES(?,?,?,?,?)', (mandate, m['casa'], m['uf'], m['ini'], m['fim']))

    def stage(self, payload):
        self.prepare(payload)
        with self.db:
            serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            snapshot = hashlib.sha256(serialized.encode()).hexdigest()[:24]
            self.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?,?,?)', (snapshot, payload['atualizadoEm'], 'staged', serialized))
            for m in payload['senado'] + payload['camara']:
                self.db.execute('INSERT OR IGNORE INTO exercises VALUES(?,?,?,?,?)',
                                (snapshot, m['mandatoId'], m['pessoaId'], m['participacao'], payload['atualizadoEm']))
        return snapshot

    def published(self, snapshot):
        with self.db:
            self.db.execute("UPDATE snapshots SET status='published' WHERE id=?", (snapshot,))

    def latest(self, published_only=False):
        where = " WHERE status='published'" if published_only else ''
        row = self.db.execute('SELECT payload FROM snapshots' + where + ' ORDER BY collected_at DESC LIMIT 1').fetchone()
        if not row:
            raise ValueError('Banco ainda sem composição validada')
        return json.loads(row[0])

    def link(self, person, source, external, method, urls):
        with self.db:
            found = self.db.execute('SELECT person_id FROM identities WHERE source=? AND external_id=?', (source, str(external))).fetchone()
            if found and found[0] != person:
                raise ValueError('Identidade já vinculada a outra pessoa; revisão necessária')
            self.db.execute('INSERT OR IGNORE INTO identities VALUES(?,?,?)', (source, str(external), person))
            self.db.execute('INSERT INTO identity_evidence VALUES(?,?,?,?,?) ON CONFLICT(source,external_id) DO UPDATE SET method=excluded.method,evidence=excluded.evidence', (source, str(external), person, method, json.dumps(urls)))

    def save_history(self, person, history):
        self.resolve_history(history)
        with self.db:
            self.db.execute('INSERT INTO histories VALUES(?,?,?,?,?,?) ON CONFLICT(person_id,house,period_start,period_end) DO UPDATE SET collected_at=excluded.collected_at,payload=excluded.payload',
                            (person, history['casa'], history['periodoInicio'], history['periodoFim'], history['coletadoEm'], json.dumps(history, ensure_ascii=False)))
            from backend.enrich import history_uncertain
            incomplete = history_uncertain(history)
            for metric in ('aprov', 'neg'):
                self.db.execute('INSERT INTO indicators VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(person_id,house,metric,period_start,period_end,source_url) DO UPDATE SET value=excluded.value,coverage=excluded.coverage,collected_at=excluded.collected_at',
                                (person, history['casa'], metric, history['periodoInicio'], history['periodoFim'], None if incomplete else history[metric], 'quantidade', 'parcial' if incomplete else 'completa', history['fontes'][0], history['coletadoEm']))

    def histories(self, person):
        histories = [json.loads(row[0]) for row in self.db.execute('SELECT payload FROM histories WHERE person_id=? ORDER BY house,period_start', (person,))]
        for history in histories: self.resolve_history(history)
        return histories

    def save_norm(self, project, norma, source, collected):
        with self.db:
            self.db.execute('INSERT INTO norms VALUES(?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET norma=excluded.norma,source_url=excluded.source_url,collected_at=excluded.collected_at', (project,norma,source,collected))

    def resolve_history(self, history):
        if history['casa'] != 'camara': return
        for project in history['projetos']:
            if project['situacao'] == 'Transformado em Norma Jurídica' and not project['norma']:
                row = self.db.execute('SELECT norma,source_url,collected_at FROM norms WHERE project_id=?', (project['id'],)).fetchone()
                if row: project.update(norma=row[0],fonteNorma=row[1],normaVerificadaEm=row[2],classificacao='aprov')
        history['aprov'] = sum(p['classificacao']=='aprov' for p in history['projetos'])

    def save_expenses(self, person, expense):
        with self.db:
            self.db.execute('INSERT INTO expenses VALUES(?,?,?,?,?,?) ON CONFLICT(person_id,house,period_start,period_end) DO UPDATE SET collected_at=excluded.collected_at,payload=excluded.payload',
                            (person, expense['casa'], expense['periodoInicio'], expense['periodoFim'], expense['coletadoEm'], json.dumps(expense, ensure_ascii=False)))

    def expenses(self, person):
        return [json.loads(row[0]) for row in self.db.execute('SELECT payload FROM expenses WHERE person_id=? ORDER BY house,period_start', (person,))]
