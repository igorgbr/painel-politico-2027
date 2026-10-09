#!/usr/bin/env python3
"""Ingestão modular, armazenamento SQLite e publicação estática versionada."""
import argparse
import fcntl
import os
import datetime as dt
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.sources.composition import TSE, SENADO, tse_members, continuing_members, validate
from backend.http import HttpCache, atomic_json
from backend.store import Store
from backend.publish import publish

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT / 'var/painel.sqlite3')
    parser.add_argument('--cache', type=Path, default=ROOT / 'var/cache')
    parser.add_argument('--refresh', action='store_true', help='Ignorar TTL do cache')
    parser.add_argument('--export-only', action='store_true', help='Republicar último snapshot do banco, sem rede')
    parser.add_argument('--tse-zip', type=Path)
    parser.add_argument('--senado-json', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'public/data.json')
    parser.add_argument('--report', type=Path, default=ROOT / 'docs/ingest-report.json')
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(str(args.db) + '.lock')
    with lock_path.open('a') as lock:
        os.chmod(lock_path, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, 'Uma ingestão já está em andamento para este banco.\n')
        collected = dt.datetime.now(dt.timezone.utc).isoformat()
        previous_index = args.output.read_bytes() if args.output.exists() else None
        store = Store(args.db)
        cache = HttpCache(args.cache)
        try:
            if args.export_only:
                snapshot = publish(store, store.latest(), args.output)
                print(f'Snapshot {snapshot} exportado do SQLite.')
                return
            def load_source(name, url, local, parse):
                try:
                    raw = local.read_bytes() if local else cache.get(url, refresh=args.refresh)
                    try:
                        records = parse(raw, collected)
                    except Exception:
                        if not local: cache.invalidate(url)
                        raise
                    digest = store.artifact(name, url, raw, collected, args.cache.parent / 'raw')
                    store.run(name, collected)
                    return raw, records, digest
                except Exception as error:
                    store.run(name, collected, error)
                    raise
            tse, elected, tse_hash = load_source('TSE', TSE, args.tse_zip, tse_members)
            senado, continuing, senado_hash = load_source('Senado', SENADO, args.senado_json, continuing_members)
            validate(elected + continuing)
            members = sorted(elected + continuing, key=lambda m: (m['casa'], m['uf'], m['nome']))
            # Composição exige as duas fontes; respostas completas já ficam em cache para retomada.
            notes = ['Indicadores e histórico anterior ainda não integrados.', 'Mandatos do Senado em continuidade mostram o ocupante em exercício na coleta; a composição poderá mudar até 2027.', 'Partido dos eleitos: eleição de 2026. Partido dos mandatos em continuidade: cadastro do Senado na coleta.']
            substitutions = [dict(uf=m['uf'], nome=m['nome'], participacao=m['participacao'], titular=m['titular']) for m in continuing if m['participacao'] != 'Titular']
            report = dict(status='validado', atualizadoEm=collected, total=len(members), eleitos2026=len(elected), continuidade=len(continuing), suplentesEmExercicio=substitutions, observacoes=notes)
            payload = dict(schemaVersion=1, recorte='eleitos-2027', atualizadoEm=collected, observacoes=notes,
                           fontes=[dict(nome='TSE', url=TSE, sha256=tse_hash), dict(nome='Senado', url=SENADO, sha256=senado_hash)],
                           senado=[m for m in members if m['casa'] == 'senado'], camara=[m for m in members if m['casa'] == 'camara'])
            snapshot = publish(store, payload, args.output)
            store.run('composicao', collected)
            report['snapshot'] = snapshot
            atomic_json(args.report, report, 0o644)
            print(f'Importados {len(members)} registros oficiais: 81 Senado e 513 Câmara. {len(substitutions)} suplentes em exercício identificados.')
        except Exception as error:
            store.run('composicao', collected, error)
            atomic_json(args.report, dict(status='erro', atualizadoEm=collected, erro=str(error), ultimoConjuntoPreservado=(args.output.read_bytes() if args.output.exists() else None) == previous_index))
            parser.exit(1, f'Ingestão falhou: {error}\n')
        finally:
            store.close()


if __name__ == '__main__':
    main()
