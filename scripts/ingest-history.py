#!/usr/bin/env python3
"""Histórico legislativo anterior com identidade confirmada e cobertura explícita."""
import argparse
import concurrent.futures
import copy
import datetime as dt
import fcntl
import json
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.http import HttpCache, atomic_json, read_url
from backend.store import Store
from backend.publish import publish
from backend.sources.identity import election_identities, normalize, match_camara, match_senado, ceap_identity_candidates
from backend.sources.history import START, END, CAMARA_FILES, history_record, parse_camara_projects, parse_camara_authors, senado_url, parse_senado_projects, law_reference
from backend.sources.composition import TSE, SENADO


from backend.enrich import attach_histories


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT / 'var/painel.sqlite3')
    parser.add_argument('--cache', type=Path, default=ROOT / 'var/cache')
    parser.add_argument('--output', type=Path, default=ROOT / 'public/data.json')
    parser.add_argument('--start', default=START)
    parser.add_argument('--end', default=END)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    dt.date.fromisoformat(args.start); dt.date.fromisoformat(args.end)
    if args.start > args.end or not 1 <= args.workers <= 4:
        parser.error('Período ou concorrência inválidos')
    collected = dt.datetime.now(dt.timezone.utc).isoformat()
    store = Store(args.db)
    lock = Path(str(args.db) + '.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    throttle = threading.Lock()
    next_request = [0.0]
    def fetch(url):
        with throttle:
            delay = max(0, next_request[0] - time.monotonic())
            if delay: time.sleep(delay)
            next_request[0] = time.monotonic() + .25
        return read_url(url)
    cache = HttpCache(args.cache, fetch=fetch, ttl=86400)
    errors = []
    try:
        payload = copy.deepcopy(store.latest(published_only=True))
        payload['atualizadoEm'] = collected
        all_members = payload['senado'] + payload['camara']
        artifact = store.db.execute("SELECT path FROM artifacts WHERE source='TSE' ORDER BY collected_at DESC LIMIT 1").fetchone()
        if not artifact: raise ValueError('Arquivo TSE privado ausente; execute a ingestão da composição primeiro')
        raw_tse = Path(artifact[0]).read_bytes()
        elected = election_identities(raw_tse)
        deputies_url = 'https://dadosabertos.camara.leg.br/arquivos/deputados/json/deputados.json'
        deputies = json.loads(cache.get(deputies_url))['dados']
        # Nomes apenas reduzem consultas; a confirmação da Câmara exige CPF validado e único.
        names = {normalize(e['nome']) for e in elected.values()}
        possible = [d for d in deputies if normalize(d['nomeCivil']) in names]
        ceap_artifact = store.db.execute("SELECT path FROM artifacts WHERE source='camara-despesas' ORDER BY collected_at DESC LIMIT 1").fetchone()
        if ceap_artifact:
            civil_ids = ceap_identity_candidates(Path(ceap_artifact[0]).read_bytes())
            extra_codes = {next(iter(codes)) for e in elected.values() if e['cpf'] for codes in [civil_ids.get(e['cpf'],set())] if len(codes)==1}
            by_code = {d['uri'].rsplit('/',1)[-1]:d for d in possible}
            for code in extra_codes: by_code.setdefault(code,dict(id=code,uri=f'https://dadosabertos.camara.leg.br/api/v2/deputados/{code}'))
            possible = list(by_code.values())
        def deputy(d):
            try: return json.loads(cache.get(d['uri']))['dados']
            except Exception as error: return {'error': str(error)}
        profiles = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for i, profile in enumerate(pool.map(deputy, possible), 1):
                profiles.append(profile)
                if i % 50 == 0: print(f'Identidades da Câmara: {i}/{len(possible)} perfis verificados.', flush=True)
        matched = {}
        for m in all_members:
            if m['ini'] != 2027: continue
            e = elected.get(m['fonte']['id'])
            profile = match_camara(e, profiles) if e else None
            if profile:
                code = str(profile['id'])
                store.link(m['pessoaId'], 'camara-parlamentar', code, 'Identificador civil oficial validado; valor mantido privado', [m['fonte']['url'], profile['uri']])
                matched[m['pessoaId']] = code
                m.setdefault('vinculos', {})['camara'] = code
                m['identidade'] = 'Vínculo oficial com a Câmara verificado'
        print(f'Câmara: {len(matched)} identidades confirmadas.', flush=True)
        # Arquivos por ano podem incluir registros relacionados de outros anos: filtrar data e deduplicar.
        projects, authors = {}, {}
        for year in range(int(args.start[:4]), int(args.end[:4]) + 1):
            projects_url = CAMARA_FILES.format(kind='proposicoes', year=year)
            authors_url = CAMARA_FILES.format(kind='proposicoesAutores', year=year)
            rows = parse_camara_projects(cache.get(projects_url), args.start, args.end)
            for key, row in rows.items(): projects[key] = row
            print(f'Projetos da Câmara: arquivo {year} processado.', flush=True)
        for year in range(int(args.start[:4]), int(args.end[:4]) + 1):
            mappings = parse_camara_authors(cache.get(CAMARA_FILES.format(kind='proposicoesAutores', year=year)), projects)
            for code, ids in mappings.items(): authors.setdefault(code, set()).update(ids)
        urls = [CAMARA_FILES.format(kind='proposicoes', year=year) for year in range(int(args.start[:4]), int(args.end[:4])+1)]
        selected_ids = set().union(*(authors.get(code,set()) for code in matched.values()))
        unresolved = [projects[key] for key in selected_ids if key in projects and projects[key]['situacao']=='Transformado em Norma Jurídica' and not projects[key]['norma']]
        def resolve(project):
            url = f'https://dadosabertos.camara.leg.br/api/v2/proposicoes/{project["id"]}'
            try:
                data = json.loads(cache.get(url))
                norma = law_reference(project,data)
                actual_status = data['dados']['statusProposicao']['descricaoSituacao']
                if actual_status != project['situacao']:
                    project.update(observacaoResultado=f'A API individual indica {actual_status}; há divergência com a situação do arquivo. Resultado não confirmado.',fonteVerificacao=url,resultadoVerificadoEm=collected)
                if not norma and data['dados']['statusProposicao']['descricaoSituacao']=='Transformado em Norma Jurídica':
                    url += '/tramitacoes'
                    rows = [r for page in cache.pages(url) for r in page]
                    norma = law_reference(project,data,rows)
                return project['id'],norma,url,None
            except Exception as error: return project['id'],None,url,str(error)
        confirmed_norms=0;norm_errors=[];pending_norms=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for project_id,norma,url,error in pool.map(resolve,unresolved):
                if error: norm_errors.append(dict(projetoId=project_id,erro=error))
                elif norma:
                    store.save_norm(project_id,norma,url,collected);confirmed_norms+=1
                else: pending_norms.append(dict(projetoId=project_id,numero=projects[project_id]['num'],fonteUrl=url,motivo='Sem referência unívoca em despacho ou evento formal de transformação'))
        print(f'Normas: {confirmed_norms}/{len(unresolved)} referências confirmadas.',flush=True)
        for person, code in matched.items():
            chosen = {key: projects[key] for key in authors.get(code, set()) if key in projects}
            store.save_history(person, history_record('camara', code, chosen, args.start, args.end, collected, urls))
        store.run('camara-historico', collected)
        # Perfis do Senado: nome completo, nascimento e UF de naturalidade, com unicidade.
        senate_artifact = store.db.execute("SELECT path FROM artifacts WHERE source='Senado' ORDER BY collected_at DESC LIMIT 1").fetchone()
        senate_catalog_url = 'https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/57.json'
        current = json.loads(cache.get(senate_catalog_url))['ListaParlamentarLegislatura']['Parlamentares']['Parlamentar']
        current = [row for row in current if normalize(row['IdentificacaoParlamentar'].get('NomeCompletoParlamentar')) in names]
        def senate_profile(row):
            code = row['IdentificacaoParlamentar']['CodigoParlamentar']
            try: return json.loads(cache.get(f'https://legis.senado.leg.br/dadosabertos/senador/{code}.json'))['DetalheParlamentar']['Parlamentar']
            except Exception: return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            senate_profiles = [p for p in pool.map(senate_profile, current) if p]
        elected_senators = {}
        for m in all_members:
            if m['ini'] != 2027: continue
            e = elected.get(m['fonte']['id'])
            profile = match_senado(e, senate_profiles) if e else None
            if profile:
                code = profile['IdentificacaoParlamentar']['CodigoParlamentar']
                store.link(m['pessoaId'], 'senado-parlamentar', code, 'Nome civil, nascimento e UF de naturalidade oficiais, correspondência única; valores pessoais privados', [m['fonte']['url'], f'https://legis.senado.leg.br/dadosabertos/senador/{code}.json'])
                elected_senators[m['pessoaId']] = code
                m.setdefault('vinculos', {})['senado'] = code
                m['identidade'] = 'Vínculo oficial com histórico parlamentar verificado'
        print(f'Senado: {len(elected_senators)} identidades eleitorais confirmadas.', flush=True)
        # Identidade própria do Senado já é conhecida para mandatos em continuidade.
        senator_map = {m['pessoaId']:m['fonte']['id'] for m in payload['senado'] if m['ini']==2023}
        senator_map.update(elected_senators)
        def senator_history(item):
            person, code = item
            try:
                rows = {}; sources = []
                for kind in ('PL', 'PLP'):
                    url = senado_url(code, kind, args.start, args.end); sources.append(url)
                    rows.update(parse_senado_projects(json.loads(cache.get(url)), args.start, args.end))
                return person, history_record('senado', code, rows, args.start, args.end, collected, sources), None
            except Exception as error: return person, None, str(error)
        # Threads fazem somente HTTP/parse; SQLite permanece em um único escritor.
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for person, history, error in pool.map(senator_history, senator_map.items()):
                if error: errors.append({'pessoaId':person,'fonte':'senado','erro':error})
                else: store.save_history(person, history)
        store.run('senado-historico', collected, ValueError(f'{len(errors)} consultas falharam') if errors else None)
        counts = attach_histories(store, payload)
        payload['observacoes'].append('Histórico legislativo anterior: PL/PLP apresentados no período indicado; situação observada na coleta. Vínculos não confirmados permanecem pendentes.')
        version = publish(store, payload, args.output)
        pending = [dict(id=m['id'],nome=m['nome'],casa=m['casa'],uf=m['uf'],motivo='Sem vínculo confirmado nos catálogos consultados; não comprova ausência de atuação anterior') for m in all_members if not m.get('historicosLegislativos')]
        report = dict(status='parcial' if errors or norm_errors or any('error' in p for p in profiles) else 'concluido', versao=version, coletadoEm=collected, periodoInicio=args.start, periodoFim=args.end, vinculosCamara=len(matched), vinculosSenado=len(elected_senators), historicos=counts, perfisCamaraFalharam=sum('error' in p for p in profiles), erros=errors, semHistorico=len(pending), normasConsultadas=len(unresolved),normasConfirmadas=confirmed_norms,errosNormas=norm_errors,normasPendentes=pending_norms,pendencias=pending)
        atomic_json(ROOT / 'docs/history-report.json', report, 0o644)
        print(json.dumps({k:v for k,v in report.items() if k!='pendencias'},ensure_ascii=False), flush=True)
    except Exception as error:
        store.run('historico', collected, error)
        parser.exit(1, f'Histórico não publicado; composição anterior preservada: {error}\n')
    finally:
        store.close(); lock.close()


if __name__ == '__main__': main()
