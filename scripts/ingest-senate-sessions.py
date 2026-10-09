#!/usr/bin/env python3
"""Publica recortes conferidos de sessões encerradas do Senado."""
import argparse
import concurrent.futures
import datetime as dt
import fcntl
import hashlib
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.http import HttpCache,atomic_json
from backend.publish import publish
from backend.store import Store
from backend.sources.senate_sessions import RECORTES,TYPES,MANDATES,CRITERION,parse_evidence,exercises,reconcile,pdf_url,diary_url


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--offline',action='store_true');parser.add_argument('--refresh',action='store_true');parser.add_argument('--session',type=int,choices=[c['numero'] for c in RECORTES],help='Reprocessa somente uma sessão conferida');args=parser.parse_args()
    lock=(ROOT/'var/painel.sqlite3.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    store=Store(ROOT/'var/painel.sqlite3')
    def fetch(url):
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'PainelPolitico/0.5','Accept':'application/pdf' if '/diarios/' in url else 'application/json'}),timeout=25) as r:return r.read()
    cache=HttpCache(ROOT/'var/cache',fetch=fetch,ttl=86400)
    def read(url):
        path=cache.directory/(hashlib.sha256(url.encode()).hexdigest()+'.bin')
        raw=path.read_bytes() if args.offline else cache.get(url,refresh=args.refresh)
        collected=dt.datetime.fromtimestamp(path.stat().st_mtime,dt.timezone.utc).isoformat()
        return url,raw,collected
    try:
        payload=store.latest(True);matched=[]
        for m in payload['senado']+payload['camara']:
            code=m.get('vinculos',{}).get('senado') or (m['fonte']['id'] if m['casa']=='senado' and m['ini']==2023 else None)
            if code:matched.append((m,str(code)))
        cuts=[c for c in RECORTES if args.session is None or c['numero']==args.session]
        urls=list(dict.fromkeys([TYPES]+[url for c in cuts for url in [pdf_url(c),c['votosUrl']]]+[MANDATES.format(code=c) for _,c in matched]))
        raw={};collected={};errors=[]
        def consult(url):
            try:return read(url),None
            except Exception as e:return None,dict(fonte=url,erro=str(e))
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for i,(result,error) in enumerate(pool.map(consult,urls),1):
                if error:errors.append(error)
                else:
                    url,data,time=result;raw[url]=data;collected[url]=time
                    store.artifact('senado-recortes-conferidos',url,data,time,ROOT/'var/artifacts')
                if i%10==0:print(f'Recorte Senado: {i}/{len(urls)} fontes consultadas.',flush=True)
        validated=[];recuts=[]
        for cut in cuts:
            pdf,votes_url=pdf_url(cut),cut['votosUrl']
            result=dict(id=cut['id'],numero=cut['numero'],periodoInicio=cut['periodoInicio'],periodoFim=cut['periodoFim'],fonte=diary_url(cut),paginas=cut['paginas'],comparecimentosDSF=cut['comparecimentos'],votacoes=len(cut['votacoes']),validados=0)
            recuts.append(result)
            try:
                if any(url not in raw for url in [pdf,votes_url,TYPES]):raise ValueError('Fontes do recorte incompletas')
                pdf_path=cache.directory/(hashlib.sha256(pdf.encode()).hexdigest()+'.bin')
                text=subprocess.run(['pdftotext','-layout',str(pdf_path),'-'],check=True,capture_output=True).stdout.decode()
                if len([p for p in text.split('\f') if p.strip()])!=len(cut['paginas']):raise ValueError('Intervalo de páginas do Diário divergente')
                votes,present,meanings=parse_evidence(text,raw[votes_url],raw[TYPES],cut,cut['paginas'][0]-1)
            except Exception as e:
                errors.append(dict(sessao=cut['numero'],erro=str(e)));continue
            for m,code in matched:
                url=MANDATES.format(code=code)
                if url not in raw:continue
                try:
                    ranges=exercises(raw[url],code)
                    licenses=[h for h in store.senate_licenses(m['pessoaId']) if h['periodoInicio']<=cut['periodoInicio'] and h['periodoFim']>=cut['periodoFim']]
                    if not licenses:raise ValueError('Licenças não consultadas para o recorte')
                    observed=max([collected[pdf],collected[votes_url],collected[TYPES],collected[url]]+[h['coletadoEm'] for h in licenses])
                    validated.append((m,reconcile(code,votes,present,meanings,ranges,licenses,observed,cut)));result['validados']+=1
                except Exception as e:errors.append(dict(id=m['id'],sessao=cut['numero'],erro=str(e)))
        if not validated:raise ValueError('Nenhuma identidade validada; publicação preservada')
        for m,h in validated:store.save_attendance(m['pessoaId'],h)
        published=[h for m,_ in matched for h in store.attendance(m['pessoaId']) if h['casa']=='senado']
        payload['observacoes']=[note.replace('apuração de presença e faltas ainda depende de reconciliar comparecimento, votos e justificativas dos Diários','assiduidade anual e faltas ainda em apuração') for note in payload['observacoes']]
        payload['atualizadoEm']=dt.datetime.now(dt.timezone.utc).isoformat()
        payload['observacoes']=[n for n in payload['observacoes'] if not n.startswith('Senado: primeiro recorte conferido') and not n.startswith('Senado: recortes conferidos')]
        session_numbers=sorted({r['numero'] for h in published for r in h['sessoes']})
        note=f"Senado: recortes conferidos das sessões {', '.join(map(str,session_numbers))}, separados por período. Sessão sem nominal confirma apenas comparecimento. Continuações contam uma vez; faltas e assiduidade anual permanecem sem classificação."
        if note not in payload['observacoes']:payload['observacoes'].append(note)
        version=publish(store,payload,ROOT/'public/data.json')
        totals={key:sum(h.get(key,0) for h in published) for key in ['comparecimentosRegistrados','comparecimentosConferidos','participacoesConferidas','justificativasRegistradas','pendentes','foraExercicio']}
        report=dict(status='recortes-parciais',versao=version,sessoesDistintas=len({r['id'] for h in published for r in h['sessoes']}),recortes=recuts,vinculosConsultados=len(matched),conferenciasPublicadas=len(published),conferenciasValidadasNestaExecucao=len(validated),totais=totals,erros=errors,criterio=CRITERION,faltasNaoJustificadas=None,
            aguardandoConferencia=[dict(numero=114,fonte='https://legis.senado.leg.br/diarios/ver/126479',motivo='Registro de comparecimento ainda sem extração e reconciliação verificáveis; não publicado.')],
            justificativas=dict(status='pendente',auditoria='docs/senate-justifications-audit.json',motivo='Documentos posteriores consultados não permitem resolver as três pendências da sessão 120. Requerimento de justificativa não prova deferimento.'))
        atomic_json(ROOT/'docs/senate-sessions-report.json',report,0o644);print(report,flush=True)
    finally:store.close();lock.close()

if __name__=='__main__':main()
