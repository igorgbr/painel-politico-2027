#!/usr/bin/env python3
"""Subsídio de referência e presença histórica em Plenário da Câmara."""
import argparse
import concurrent.futures
import datetime as dt
import fcntl
import hashlib
import json
from urllib.error import HTTPError, URLError
from pathlib import Path
import sys
import threading
import time
import urllib.request
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.store import Store
from backend.http import HttpCache,atomic_json
from backend.publish import publish
from backend.sources.attendance import URL,parse_attendance,AttendanceUnavailable
from backend.sources.subsidy import GUIDE,NORM,reference


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=ROOT/'var/painel.sqlite3')
    parser.add_argument('--cache',type=Path,default=ROOT/'var/cache')
    parser.add_argument('--output',type=Path,default=ROOT/'public/data.json')
    parser.add_argument('--year',type=int,default=2026)
    parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--diagnose-only',action='store_true',help='Grava diagnóstico sem alterar históricos ou publicar snapshot')
    parser.add_argument('--timeout',type=int,default=15)
    args=parser.parse_args()
    if not 1<=args.timeout<=60:parser.error('Timeout deve ser entre 1 e 60 segundos')
    today=dt.datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    if not 2023<=args.year<=today.year:parser.error('Ano fora do período disponível')
    end=min(today,dt.date(args.year,12,31)).isoformat();collected=dt.datetime.now(dt.timezone.utc).isoformat()
    lock=Path(str(args.db)+'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    store=Store(args.db);mutex=threading.Lock();next_request=[0.0]
    def fetch(url):
        with mutex:
            delay=max(0,next_request[0]-time.monotonic())
            if delay:time.sleep(delay)
            next_request[0]=time.monotonic()+.25
        request=urllib.request.Request(url,headers={'User-Agent':'PainelPolitico/0.3'})
        with urllib.request.urlopen(request,timeout=args.timeout) as response:return response.read()
    cache=HttpCache(args.cache,fetch=fetch,ttl=86400);errors=[];count=0;network_down=False
    def cache_path(url):
        return args.cache/(hashlib.sha256(url.encode()).hexdigest()+'.bin')
    def get(url):
        if args.offline:
            return cache_path(url).read_bytes()
        return cache.get(url,refresh=args.refresh)
    try:
        payload=store.latest(True)
        subsidy=None
        if not args.diagnose_only:
            guide=get(GUIDE);norm=get(NORM)
            verified=min(dt.datetime.fromtimestamp(cache_path(url).stat().st_mtime,dt.timezone.utc) for url in (GUIDE,NORM)).isoformat()
            subsidy=reference(guide,norm,verified)
            for url,raw in [(GUIDE,guide),(NORM,norm)]:store.artifact('subsidio',url,raw,verified,args.db.parent/'raw')
        matched=[m for m in payload['senado']+payload['camara'] if m.get('vinculos',{}).get('camara')]
        def consult(m):
            code=m['vinculos']['camara'];url=URL.format(code=code,year=args.year)
            try:
                cached=cache_path(url)
                if network_down:
                    if not cached.exists():return m,None,dict(erro='Consulta adiada: fonte sem conexão',tipo='adiada'),False
                    raw=cached.read_bytes()
                else:raw=get(url)
                observed=dt.datetime.fromtimestamp(cached.stat().st_mtime,dt.timezone.utc)
                period_end=min(end,observed.astimezone(ZoneInfo('America/Sao_Paulo')).date().isoformat())
                value=parse_attendance(raw,code,args.year,period_end,observed.isoformat())
                return m,value,None,False
            except FileNotFoundError:return m,None,dict(erro='Relatório não disponível no cache local',tipo='sem-cache'),False
            except Exception as error:
                unavailable=isinstance(error,(TimeoutError,ConnectionError,URLError)) and not isinstance(error,HTTPError)
                diagnostic=dict(erro=str(error),tipo='sem-registros' if isinstance(error,AttendanceUnavailable) else 'conexao' if unavailable else 'http' if isinstance(error,HTTPError) else 'validacao')
                if hasattr(error,'diagnostic'):diagnostic['diagnostico']=error.diagnostic
                return m,None,diagnostic,unavailable
        # Lotes limitados: não enfileirar centenas de chamadas durante uma queda da fonte.
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for offset in range(0,len(matched),4):
                results=list(pool.map(consult,matched[offset:offset+4]))
                if not args.offline and all(unavailable for _,_,_,unavailable in results):
                    network_down=True
                    print('Fonte sem conexão: próximas consultas usarão apenas cache.',flush=True)
                for m,value,error,_ in results:
                    if error:errors.append(dict(id=m['id'],fonte='camara',**error))
                    else:
                        if not args.diagnose_only:store.save_attendance(m['pessoaId'],value)
                        count+=1
                if offset%48==0:print(f'Presença: {min(offset+4,len(matched))}/{len(matched)} consultas concluídas.',flush=True)
        if args.diagnose_only:
            from collections import Counter
            report=dict(tentativaEm=collected,snapshotPublicado=json.loads(args.output.read_text())['versao'],consultados=len(matched),validados=count,fonteSemConexao=network_down,offline=args.offline,errosPorTipo=dict(Counter(e['tipo'] for e in errors)),erros=errors)
            atomic_json(ROOT/'docs/attendance-attempt.json',report,0o644)
            print({k:v for k,v in report.items() if k!='erros'},flush=True)
            return
        if not count:raise ValueError('Nenhuma consulta de presença validada; publicação anterior mantida')
        store.save_reference('subsidio',subsidy);store.run('camara-presenca',collected,ValueError(f'{len(errors)} consultas falharam') if errors else None)
        payload['atualizadoEm']=collected
        note='Subsídio bruto de referência vigente na coleta não comprova pagamento individual ou valor futuro. Presença Câmara por dia em Plenário, com justificativas separadas; Senado aguarda reconciliação de licenças e ausências.'
        if note not in payload['observacoes']:payload['observacoes'].append(note)
        version=publish(store,payload,args.output)
        report=dict(status='parcial' if errors else 'concluido',versao=version,coletadoEm=collected,periodoInicio=f'{args.year}-01-01',periodoFim=end,consultados=len(matched),presencasCamara=count,erros=errors,subsidio=subsidy,senado=dict(status='pendente',motivo='Reconciliar presenças com licenças e justificativas; não inferir faltas de votos ausentes.',fonteUrl='https://www12.senado.leg.br/assessoria-de-imprensa/guia-para-jornalistas/tutorial-de-verificacao-da-assiduidade-dos-senadores'))
        atomic_json(ROOT/'docs/attendance-report.json',report,0o644)
        print({k:v for k,v in report.items() if k not in ['erros','subsidio']},flush=True)
    except Exception as error:
        if not args.diagnose_only:store.run('presenca-subsidio',collected,error)
        parser.exit(1,f'Integração não publicada: {error}\n')
    finally:store.close();lock.close()


if __name__=='__main__':main()
