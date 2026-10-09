#!/usr/bin/env python3
"""Armazena fotos já vinculadas, preservando cópias anteriores em falhas de rede."""
import argparse
import concurrent.futures
import datetime as dt
import fcntl
from pathlib import Path
import sys
import urllib.request
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.photos import save_image
from backend.publish import publish
from backend.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    lock = (ROOT / 'var/painel.sqlite3.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    store = Store(ROOT / 'var/painel.sqlite3')
    try:
        payload = store.latest(published_only=True)
        groups = {}
        for member in payload['senado'] + payload['camara']:
            photo = store.photo(member['pessoaId'])
            if photo:
                groups.setdefault(photo['casa'], []).append((member['pessoaId'], photo))
        completed = failed = 0
        def fetch(item):
            person, photo = item
            local = photo.get('arquivoLocal')
            if not args.refresh and local and (ROOT / 'public' / local).is_file():
                return person, photo, None
            try:
                request = urllib.request.Request(photo['url'], headers={'User-Agent': 'PainelPolitico/0.3'})
                with urllib.request.urlopen(request, timeout=8) as response:
                    if urlparse(response.geturl()).hostname not in {'www.camara.leg.br', 'www.senado.leg.br', 'legis.senado.leg.br'}:
                        raise ValueError('Redirecionamento fora da fonte oficial')
                    raw = response.read(5_000_001)
                    if len(raw) > 5_000_000:
                        raise ValueError('Imagem excede limite')
                result = dict(photo, arquivoLocal=save_image(raw, ROOT / 'public'), imagemColetadaEm=dt.datetime.now(dt.timezone.utc).isoformat())
                return person, result, None
            except Exception as error:
                return person, photo, str(error)
        # Interrompe uma Casa sem respostas para evitar centenas de requisições em uma indisponibilidade.
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for house, items in groups.items():
                for offset in range(0, len(items), 8):
                    results = list(pool.map(fetch, items[offset:offset+8]))
                    for person, photo, error in results:
                        if error:
                            failed += 1
                        else:
                            store.save_photo(person, photo)
                            completed += 1
                    print(f'{house}: {completed} fotos locais; {failed} falhas', flush=True)
                    if all(error for _, _, error in results):
                        print(f'{house}: fonte indisponível; próximas fotos preservadas para nova tentativa.', flush=True)
                        break
        version = publish(store, payload, ROOT / 'public/data.json')
        print(f'Snapshot {version}; {completed} fotos locais disponíveis.', flush=True)
    finally:
        store.close()
        lock.close()


if __name__ == '__main__':
    main()
