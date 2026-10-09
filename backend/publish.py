"""Publica detalhes imutáveis primeiro, troca o índice por último."""
import copy
from pathlib import Path
from backend.http import atomic_json


def publish(store, payload, output):
    from backend.enrich import attach_histories, attach_expenses
    store.prepare(payload)
    attach_histories(store, payload)
    attach_expenses(store, payload)
    for m in payload['senado'] + payload['camara']:
        m['presencasHistoricas']=[h for h in store.attendance(m['pessoaId']) if h['casa']=='camara']
        m['comparecimentosSenado']=[h for h in store.attendance(m['pessoaId']) if h['casa']=='senado']
        m['licencasSenado']=store.senate_licenses(m['pessoaId'])
        subsidy=store.reference('subsidio')
        m.pop('subsidioReferencia',None)
        if subsidy:m['subsidioReferencia']=subsidy
        photo = store.photo(m['pessoaId'])
        m.pop('foto', None)
        if photo and (m.get('vinculos', {}).get(photo['casa']) == photo['idParlamentar'] or (photo['casa'] == 'senado' and m['ini'] == 2023 and m['fonte']['id'] == photo['idParlamentar'])):
            m['foto'] = photo
        m['resumosHistoricos'] = {
            'legislativos': [dict((k, h[k]) for k in ('casa', 'idParlamentar', 'periodoInicio', 'periodoFim', 'coletadoEm', 'criterio', 'fontes', 'total', 'aprov', 'neg')) | {
                'pendentes': sum(not p['situacao'] or p['situacao'] == 'Situação não informada' or (p['situacao'].upper() in {'TRANSFORMADO EM NORMA JURÍDICA', 'TRANSFORMADA EM NORMA JURÍDICA'} and not p['norma']) for p in h['projetos'])
            } for h in m['historicosLegislativos']],
            'despesas': [dict((k, h[k]) for k in ('casa', 'idParlamentar', 'periodoInicio', 'periodoFim', 'coletadoEm', 'criterio', 'fontes', 'totalCentavos', 'registros', 'cobertura')) for h in m['despesasHistoricas']],
            'licencasSenado': [{k:v for k,v in h.items() if k!='licencas'} for h in m['licencasSenado']],
            'comparecimentosSenado': [{k:v for k,v in h.items() if k!='sessoes'} for h in m['comparecimentosSenado']],
            'presencas': [{k:v for k,v in h.items() if k!='dias'} for h in m['presencasHistoricas']]
        }
    inventory=store.reference('senado-sessoes-agenda')
    payload.pop('coberturaSenado',None)
    if inventory:
        from backend.sources.senate_sessions import RECORTES
        ids={r['id'] for m in payload['senado']+payload['camara'] for h in m['comparecimentosSenado'] for r in h['sessoes']}
        covered=sum(any(c['id'] in ids and c['numero']==r['numero'] and c['tipo']==r['tipo'] and c['legislatura']==r['legislatura'] for c in RECORTES) for r in inventory['sessoes'])
        payload['coberturaSenado']=dict(periodoInicio=inventory['periodoInicio'],periodoFim=inventory['periodoFim'],sessoesIdentificadas=inventory['sessoesIdentificadas'],sessoesConferidas=covered,coletadoEm=max(s['coletadoEm'] for s in inventory['fontes']),fontes=[s['url'] for s in inventory['fontes']],criterio=inventory['criterio'])
    snapshot = store.stage(payload)
    summary = copy.deepcopy(payload)
    summary.update(schemaVersion=2, versao=snapshot)
    directory = Path(output).parent / 'data' / 'snapshots' / snapshot
    for m in summary['senado'] + summary['camara']:
        detail = dict(schemaVersion=2, versao=snapshot, pessoaId=m['pessoaId'], mandatoId=m['mandatoId'],
                      historico=m['historico'], indicadores=m.get('indicadores', {}), projetos=m.get('projetos', {'aprov': [], 'neg': []}), historicosLegislativos=m.get('historicosLegislativos', []), despesasHistoricas=m.get('despesasHistoricas', []),presencasHistoricas=m.get('presencasHistoricas',[]),licencasSenado=m.get('licencasSenado',[]),comparecimentosSenado=m.get('comparecimentosSenado',[]))
        filename = m['id'] + '.json'
        if Path(filename).name != filename:
            raise ValueError('Identificador inválido para arquivo de detalhe')
        atomic_json(directory / filename, detail, 0o644)
        m['detalhesUrl'] = f'data/snapshots/{snapshot}/{filename}'
        m.pop('projetos', None)
        m.pop('historicosLegislativos', None)
        m.pop('despesasHistoricas', None)
        m.pop('presencasHistoricas',None)
        m.pop('licencasSenado',None)
        m.pop('comparecimentosSenado',None)
    atomic_json(output, summary, 0o644)
    prune_snapshots(directory.parent, snapshot)
    # Se ocorrer falha depois da troca do índice, os arquivos publicados continuam consistentes.
    store.published(snapshot)
    return snapshot


def prune_snapshots(root, current, keep=2):
    """Mantém a versão atual e a anterior (clientes com índice antigo em cache)."""
    # ponytail: mtime decide "anterior"; usar store.snapshots se precisar de histórico maior
    import shutil
    others = sorted((d for d in Path(root).iterdir() if d.is_dir() and d.name != current), key=lambda d: d.stat().st_mtime, reverse=True)
    for d in others[keep - 1:]:
        shutil.rmtree(d)
