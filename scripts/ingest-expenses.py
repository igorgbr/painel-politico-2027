#!/usr/bin/env python3
"""Publica despesas históricas de identidades já verificadas."""
import argparse
import calendar
import copy
import datetime as dt
import fcntl
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.http import HttpCache, atomic_json
from backend.store import Store
from backend.publish import publish
from backend.sources.expenses import CAMARA, SENADO, START, END, parse_expenses, record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT / 'var/painel.sqlite3')
    parser.add_argument('--cache', type=Path, default=ROOT / 'var/cache')
    parser.add_argument('--output', type=Path, default=ROOT / 'public/data.json')
    parser.add_argument('--start', default=START)
    parser.add_argument('--end', default=END)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    start, end = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    if start > end or start.day != 1 or end.day != calendar.monthrange(end.year, end.month)[1] or end >= dt.date.today():
        parser.error('Use competências completas anteriores ao mês atual')
    args.db.parent.mkdir(parents=True, exist_ok=True)
    lock = Path(str(args.db) + '.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    store = Store(args.db)
    collected = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        payload = copy.deepcopy(store.latest(published_only=True))
        store.prepare(payload)
        cache = HttpCache(args.cache)
        collected_rows = {}; counts = {}
        # Validar todas as fontes antes de persistir ou trocar o índice público.
        for house, template in [('camara', CAMARA), ('senado', SENADO)]:
            values = {}; sources = []
            for year in range(start.year, end.year + 1):
                url = template.format(year=year); sources.append(url)
                raw = cache.get(url, refresh=args.refresh)
                try: parsed = parse_expenses(raw, house, args.start, args.end)
                except Exception:
                    cache.invalidate(url); raise
                store.artifact(house + '-despesas', url, raw, collected, args.db.parent / 'raw')
                for code, item in parsed.items():
                    if code not in values: values[code] = item
                    else:
                        target = values[code]
                        for key in ['totalCentavos','restituicoesCentavos','registros']: target[key] += item[key]
                        for key in ['meses','categorias']:
                            for k,v in item[key].items(): target[key][k] = target[key].get(k,0) + v
            records = []
            for m in payload['senado'] + payload['camara']:
                code = m.get('vinculos', {}).get(house)
                if not code and house == 'senado' and m['casa'] == house and m['ini'] == 2023: code = m['fonte']['id']
                # Ausência de linha não prova gasto zero nem vínculo de identidade.
                if code in values: records.append((m['pessoaId'], record(house, code, values[code], args.start, args.end, collected, sources)))
            collected_rows[house] = records; counts[house] = len(records)
            print(f'{house}: {len(records)} históricos de despesas vinculados.', flush=True)
        for house, records in collected_rows.items():
            for person, expense in records: store.save_expenses(person, expense)
            store.run(house + '-despesas', collected)
        payload['atualizadoEm'] = collected
        note = 'Despesas históricas: registros disponíveis por competência, separados por Casa; sujeitos a atualizações. Ausência de vínculo ou registro não significa gasto zero.'
        if note not in payload['observacoes']: payload['observacoes'].append(note)
        version = publish(store, payload, args.output)
        report = dict(status='concluido', versao=version, coletadoEm=collected, periodoInicio=args.start, periodoFim=args.end, cobertura='registros-disponiveis', historicos=counts)
        atomic_json(ROOT / 'docs/expenses-report.json', report, 0o644)
        print(report)
    except Exception as error:
        store.run('despesas', collected, error)
        parser.exit(1, f'Despesas não publicadas; índice anterior preservado: {error}\n')
    finally:
        store.close(); lock.close()


if __name__ == '__main__': main()
