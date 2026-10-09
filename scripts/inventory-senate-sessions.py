#!/usr/bin/env python3
"""Inventário da agenda de 2026, separado da conferência dos Diários."""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.http import HttpCache,atomic_json
from backend.sources.senate_sessions import RECORTES


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--offline',action='store_true');parser.add_argument('--refresh',action='store_true');parser.add_argument('--publish',action='store_true',help='Publica o indicador de cobertura após validar todos os meses');args=parser.parse_args()
    today=dt.datetime.now(ZoneInfo('America/Sao_Paulo')).date();end=min(today,dt.date(2026,12,31))
    urls=[f'https://legis.senado.leg.br/dadosabertos/plenario/agenda/mes/2026{month:02d}01.json?v=2' for month in range(1,end.month+1)]
    def fetch(url):
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'PainelPolitico/0.6','Accept':'application/json'}),timeout=25) as r:return r.read()
    cache=HttpCache(ROOT/'var/cache',fetch=fetch,ttl=86400);errors=[];sources=[];sessions={}
    def consult(url):
        try:
            path=cache.directory/(hashlib.sha256(url.encode()).hexdigest()+'.bin');raw=path.read_bytes() if args.offline else cache.get(url,refresh=args.refresh)
            root=json.loads(raw)['AgendaPlenario'];records=root.get('Sessoes',{}).get('Sessao',[])
            if isinstance(records,dict):records=[records]
            if not isinstance(records,list):raise ValueError('Agenda inválida')
            month=re.search(r'/mes/(2026\d{2})01',url)[1]
            for row in records:
                day=row['Data'];dt.date.fromisoformat(day)
                if day.replace('-','')[:6]!=month:raise ValueError('Agenda de outro mês')
            return dict(url=url,sha256=hashlib.sha256(raw).hexdigest(),coletadoEm=dt.datetime.fromtimestamp(path.stat().st_mtime,dt.timezone.utc).isoformat()),records,None
        except Exception as e:return None,[],dict(fonte=url,erro=str(e))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for source,records,error in pool.map(consult,urls):
            if error:errors.append(error);continue
            sources.append(source)
            for s in records:
                kind=s.get('TipoSessao','').strip()
                if s.get('Casa')!='SF' or kind not in ['SESSÃO DELIBERATIVA ORDINÁRIA','SESSÃO DELIBERATIVA EXTRAORDINÁRIA'] or s.get('SituacaoSessao')!='Encerrada' or s.get('Realizada',{}).get('Status')!='Sim' or s['Data']>end.isoformat():continue
                match=re.match(r'^(\d+)ª\s+SESSÃO',s.get('NumeroSessao','').strip())
                if not match:errors.append(dict(fonte=source['url'],erro='Sessão encerrada sem número válido'));continue
                numero=int(match[1]);tipo='DOR' if kind.endswith('ORDINÁRIA') and not kind.endswith('EXTRAORDINÁRIA') else 'DEX'
                key=f"{s['Legislatura']}-{s['SessaoLegislativa']}-{numero}-{tipo}"
                r=sessions.setdefault(key,dict(idAgenda=key,numero=numero,tipo=tipo,legislatura=int(s['Legislatura']),sessaoLegislativaOrdinal=int(s['SessaoLegislativa']),datas=[],encontros=[],fontes=[]))
                if s['Data'] not in r['datas']:r['datas'].append(s['Data'])
                if s['CodigoSessao'] not in r['encontros']:r['encontros'].append(s['CodigoSessao'])
                if source['url'] not in r['fontes']:r['fontes'].append(source['url'])
    snapshot=json.loads((ROOT/'public/data.json').read_text());published={(h['periodoInicio'],h['periodoFim'],h['fontes'][0]) for m in snapshot['senado']+snapshot['camara'] for h in m['resumosHistoricos'].get('comparecimentosSenado',[])}
    rows=sorted(sessions.values(),key=lambda r:(min(r['datas']),r['numero']))
    for r in rows:
        r['datas'].sort();r['conferenciaDisponivel']=any((c['periodoInicio'],c['periodoFim'],f"https://legis.senado.leg.br/diarios/ver/{c['diario']}") in published and c['numero']==r['numero'] and c['tipo']==r['tipo'] and c['legislatura']==r['legislatura'] for c in RECORTES)
    report=dict(status='inventario-da-agenda' if not errors else 'inventario-parcial',periodoInicio='2026-01-01',periodoFim=end.isoformat(),mesesConsultados=len(urls),mesesValidados=len(sources),sessoesIdentificadas=len(rows),sessoesComRecorteConferido=sum(r['conferenciaDisponivel'] for r in rows),criterio='Inventário de sessões deliberativas realizadas e encerradas segundo a agenda. Número, legislatura, sessão legislativa e tipo deduplicam continuações. Agenda não comprova comparecimento, votos nem ausência; exige DSF e evidências individuais. Conferência disponível indica apenas o recorte de identidades vinculadas no projeto.',fontes=sources,erros=errors,sessoes=rows)
    if args.publish:
        if errors or len(sources)!=len(urls):raise ValueError('Inventário incompleto; cobertura publicada preservada')
        import fcntl
        from backend.store import Store
        from backend.publish import publish
        lock=(ROOT/'var/painel.sqlite3.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        store=Store(ROOT/'var/painel.sqlite3')
        try:
            store.save_reference('senado-sessoes-agenda',report)
            payload=store.latest(True);payload['atualizadoEm']=dt.datetime.now(dt.timezone.utc).isoformat()
            report['versao']=publish(store,payload,ROOT/'public/data.json')
        finally:store.close();lock.close()
    atomic_json(ROOT/'docs/senate-sessions-inventory.json',report,0o644)
    print({k:v for k,v in report.items() if k not in ['fontes','sessoes']},flush=True)

if __name__=='__main__':main()
