def history_uncertain(h):
    return any(not p['situacao'] or p['situacao']=='Situação não informada' or (p['situacao'].upper() in {'TRANSFORMADO EM NORMA JURÍDICA','TRANSFORMADA EM NORMA JURÍDICA'} and not p['norma']) for p in h['projetos'])


def attach_histories(store, payload):
    counts = {'camara': 0, 'senado': 0}
    for m in payload['senado'] + payload['camara']:
        histories = store.histories(m['pessoaId'])
        m['historicosLegislativos'] = histories
        # Os indicadores não se transferem de uma casa para outra nem de uma consulta incompleta.
        m['projetos'] = {'aprov': [], 'neg': []}
        if not histories:
            m['historico'] = 'Histórico anterior ainda sem vínculo confirmado ou consulta completa'
        if histories:
            m['historico'] = ' · '.join(f"Histórico {'Câmara' if h['casa']=='camara' else 'Senado'}: {h['total']} PL/PLP apresentados de {h['periodoInicio']} a {h['periodoFim']}; situação na coleta" for h in histories)
        for h in histories:
            counts[h['casa']] += 1
            if h['casa'] == m['casa']:
                m['aprov'] = None; m['neg'] = None
                for key in ('aprov', 'neg'): m.setdefault('indicadores', {}).pop(key, None)
                for key in ('aprov', 'neg'):
                    m['projetos'][key] = [p for p in h['projetos'] if p['classificacao'] == key]
                # Referências incompletas à norma ou situações vazias impedem métricas exatas.
                uncertain = history_uncertain(h)
                if not uncertain:
                    for key in ('aprov', 'neg'):
                        m[key] = h[key]
                        m.setdefault('indicadores', {})[key] = dict(periodoInicio=h['periodoInicio'], periodoFim=h['periodoFim'], casa=h['casa'], unidade='quantidade', cobertura='completa', fonteUrl=h['fontes'][0], coletadoEm=h['coletadoEm'], criterio=h['criterio'])
    return counts


def attach_expenses(store, payload):
    for m in payload['senado'] + payload['camara']:
        m['despesasHistoricas'] = store.expenses(m['pessoaId'])
        # Não converter registros disponíveis em indicador com cobertura completa.
        m['custo'] = None
        m.setdefault('indicadores', {}).pop('custo', None)

