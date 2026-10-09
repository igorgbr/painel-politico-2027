#!/usr/bin/env python3
"""Fotos oficiais obtidas em perfis de identidades verificadas."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.http import HttpCache
from backend.store import Store
from backend.publish import publish


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=ROOT/'var/painel.sqlite3')
    parser.add_argument('--cache',type=Path,default=ROOT/'var/cache')
    parser.add_argument('--output',type=Path,default=ROOT/'public/data.json')
    parser.add_argument('--offline',action='store_true')
    args=parser.parse_args()
    lock=Path(str(args.db)+'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    store=Store(args.db);cache=HttpCache(args.cache,ttl=86400)
    count=0;errors=0
    try:
        payload=store.latest(published_only=True);store.prepare(payload)
        for m in payload['senado']+payload['camara']:
            for house in [m['casa'], 'camara' if m['casa']=='senado' else 'senado']:
                code=m.get('vinculos',{}).get(house)
                if house=='senado' and m['ini']==2023: code=m['fonte']['id']
                if not code: continue
                source=f'https://dadosabertos.camara.leg.br/api/v2/deputados/{code}' if house=='camara' else f'https://legis.senado.leg.br/dadosabertos/senador/{code}.json'
                path=args.cache/(hashlib.sha256(source.encode()).hexdigest()+'.bin')
                try:
                    raw=path.read_bytes() if args.offline else cache.get(source)
                    profile=json.loads(raw)
                    if house=='camara':
                        profile=profile['dados']
                        if str(profile['id'])!=code: raise ValueError('Perfil divergente')
                        url=profile['ultimoStatus'].get('urlFoto')
                    else:
                        profile=profile['DetalheParlamentar']['Parlamentar']['IdentificacaoParlamentar']
                        if str(profile['CodigoParlamentar'])!=code: raise ValueError('Perfil divergente')
                        url=profile.get('UrlFotoParlamentar')
                    if not url: continue
                    if url.startswith('http://'): url='https://'+url[7:]
                    parsed=urlparse(url)
                    if parsed.scheme!='https' or parsed.hostname!=('www.camara.leg.br' if house=='camara' else 'www.senado.leg.br'): raise ValueError('Foto fora da fonte oficial')
                    collected=dt.datetime.fromtimestamp(path.stat().st_mtime,dt.timezone.utc).isoformat()
                    photo=dict(url=url,fonteUrl=source,casa=house,idParlamentar=code,coletadoEm=collected)
                    previous=store.photo(m['pessoaId'])
                    if previous and previous['url']==url:
                        for key in ('arquivoLocal','imagemColetadaEm'):
                            if key in previous: photo[key]=previous[key]
                    store.save_photo(m['pessoaId'],photo)
                    count+=1;break
                except Exception as error:
                    errors+=1;print(f'Foto de {m["id"]}: {type(error).__name__}',flush=True)
        version=publish(store,payload,args.output)
        print(f'{count} fotos oficiais vinculadas; {errors} consultas pendentes. Snapshot {version}.')
    finally:
        store.close();lock.close()


if __name__=='__main__': main()
