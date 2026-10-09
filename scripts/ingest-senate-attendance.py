#!/usr/bin/env python3
"""Integra licenças oficiais do Senado, primeira evidência da apuração de assiduidade."""
import argparse
import concurrent.futures
import datetime as dt
import fcntl
import hashlib
from pathlib import Path
import sys
import urllib.request
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.http import HttpCache,atomic_json
from backend.publish import publish
from backend.store import Store
from backend.sources.senate_attendance import LICENSE_URL,GUIDE,parse_licenses


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true');parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--year',type=int,default=2026)
    args=parser.parse_args()
    today=dt.datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    if not 2023<=args.year<=today.year:parser.error('Ano fora do período disponível')
    start=f'{args.year}-01-01';end=min(today,dt.date(args.year,12,31)).isoformat()
    lock=(ROOT/'var/painel.sqlite3.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    store=Store(ROOT/'var/painel.sqlite3')
    def fetch(url):
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'PainelPolitico/0.4'}),timeout=15) as r:return r.read()
    cache=HttpCache(ROOT/'var/cache',fetch=fetch,ttl=86400)
    errors=[];valid=0;records=0
    try:
        payload=store.latest(True)
        matched=[]
        for m in payload['senado']+payload['camara']:
            code=m.get('vinculos',{}).get('senado') or (m['fonte']['id'] if m['casa']=='senado' and m['ini']==2023 else None)
            if code:matched.append((m,code))
        def consult(item):
            m,code=item;url=LICENSE_URL.format(code=code,start=start.replace('-',''),end=end.replace('-',''))
            path=cache.directory/(hashlib.sha256(url.encode()).hexdigest()+'.bin')
            try:
                raw=path.read_bytes() if args.offline else cache.get(url,refresh=args.refresh)
                collected=dt.datetime.fromtimestamp(path.stat().st_mtime,dt.timezone.utc).isoformat()
                return m,parse_licenses(raw,code,start,end,collected),None
            except Exception as error:return m,None,dict(id=m['id'],fonteUrl=url,erro=str(error))
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for i,(m,value,error) in enumerate(pool.map(consult,matched),1):
                if error:errors.append(error)
                else:store.save_senate_licenses(m['pessoaId'],value);valid+=1;records+=value['registros']
                if i%10==0:print(f'Senado: {i}/{len(matched)} consultas concluídas.',flush=True)
        if not valid:raise ValueError('Nenhuma consulta validada; publicação preservada')
        collected=dt.datetime.now(dt.timezone.utc).isoformat();payload['atualizadoEm']=collected
        note='Senado: licenças e missões oficiais disponíveis por período; apuração de presença e faltas ainda depende de reconciliar comparecimento, votos e justificativas dos Diários.'
        if note not in payload['observacoes']:payload['observacoes'].append(note)
        version=publish(store,payload,ROOT/'public/data.json')
        report=dict(status='parcial',versao=version,coletadoEm=collected,periodoInicio=start,periodoFim=end,consultados=len(matched),licencasConsultadas=valid,registros=records,erros=errors,assiduidade=dict(status='pendente',motivo='Licença não comprova dias de sessão ou assiduidade; reconciliar Diários, votos, exercício e justificativas antes de classificar ausências.',fonteUrl=GUIDE))
        atomic_json(ROOT/'docs/senate-attendance-report.json',report,0o644)
        print({k:v for k,v in report.items() if k not in ['erros','assiduidade']},flush=True)
    finally:store.close();lock.close()


if __name__=='__main__':main()
