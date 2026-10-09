"""Recorte conferido: sessão encerrada, DSF, votos e exercício oficial.

Classifica evidências de participação, nunca faltas regimentais. Há sessões com e sem votação nominal; continuações contam uma vez.
"""
import datetime as dt
import json
import re
from pathlib import Path
import unicodedata

RECORTES=json.loads((Path(__file__).resolve().parents[2]/'src/senate-recortes.json').read_text())
if len({r['periodoInicio'] for r in RECORTES})!=len(RECORTES) or len({r['id'] for r in RECORTES})!=len(RECORTES):raise ValueError('Recortes configurados duplicados; não sobrescrever sessões do mesmo dia')
DEFAULT=next(r for r in RECORTES if r['numero']==120)
START=DEFAULT['periodoInicio']; END=DEFAULT['periodoFim']
TYPES='https://legis.senado.leg.br/dadosabertos/plenario/lista/tiposComparecimento.json'
MANDATES='https://legis.senado.leg.br/dadosabertos/senador/{code}/mandatos.json?v=5'
SECRET_REGISTERS={'Votou':'Votou','AP':'Atividade parlamentar','P-NRV':'Presente – Não registrou voto','Presidente (art. 51 RISF)':'Presidiu votação'}
PARTICIPATED={'Votou','Sim','Não','Abstenção','Presidente (art. 51 RISF)'}
CRITERION='Recortes de sessões deliberativas encerradas, conferidos separadamente. Continuações contam uma vez. DSF confrontado com todas as votações nominais do recorte, exercício e licenças efetivas. Sem nominal, confirma somente comparecimento registrado. Não mede assiduidade anual; códigos de justificativa não classificam faltas. Casos sem evidência suficiente permanecem pendentes.'


def diary_url(cut):return f"https://legis.senado.leg.br/diarios/ver/{cut['diario']}"

def pdf_url(cut):return f"https://legis.senado.leg.br/diarios/BuscaPaginasDiario?codDiario={cut['diario']}&download=true&paginaInicial={cut['paginas'][0]}&paginaFinal={cut['paginas'][-1]}"

DIARY=diary_url(DEFAULT);PDF=pdf_url(DEFAULT);VOTES=DEFAULT['votosUrl']


def canonical(name):
    name=unicodedata.normalize('NFD',name).encode('ascii','ignore').decode().lower()
    name=name.replace('astr.','astronauta').replace('prof.','professora')
    return ' '.join(w for w in re.findall('[a-z]+',name) if w not in {'de','do','da','dos','das'})


def parse_evidence(text,raw,types_raw,cut=DEFAULT,page_offset=0):
    kind={'DOR':'Ordinária','DEX':'Extraordinária'}.get(cut['tipo'])
    if not kind:raise ValueError('Tipo de sessão deliberativa não conferido')
    all_votes=json.loads(raw)
    expected={v['id']:v for c in RECORTES if c['votosUrl']==cut['votosUrl'] for v in c['votacoes']}
    if not isinstance(all_votes,list) or len(all_votes)!=len(expected):raise ValueError('Consulta de votos incompleta')
    roster={};ids=set();votes=[]
    for vote in all_votes:
        identity=str(vote['codigoSessaoVotacao']);spec=expected.get(identity)
        parent=next((c for c in RECORTES if any(v['id']==identity for v in c['votacoes'])),None)
        if identity in ids or not spec or not parent or vote['numeroSessao']!=parent['numero'] or vote['codigoSessaoLegislativa']!=parent['sessaoLegislativa'] or vote['casaSessao']!='SF' or vote['siglaTipoSessao']!=parent['tipo']:raise ValueError('Sessão ou votação divergente')
        ids.add(identity)
        if (vote['dataSessao'],vote['identificacao'],vote['votacaoSecreta'])!=(spec['data'],spec['materia'],'S' if spec['secreta'] else 'N'):raise ValueError('Votação fora do recorte conferido')
        individuals=vote['votos'];seen=set()
        if not isinstance(individuals,list) or len(individuals)!=81:raise ValueError('Lista de votos incompleta')
        for r in individuals:
            code=str(r['codigoParlamentar'])
            if code in seen or not code.isdigit():raise ValueError('Voto duplicado')
            seen.add(code);key=(canonical(r['nomeParlamentar']),r['siglaUFParlamentar'])
            if code in roster and roster[code]!=key:raise ValueError('Identidade varia entre votações')
            roster[code]=key
            if spec['secreta'] and r['siglaVotoParlamentar'] not in SECRET_REGISTERS:raise ValueError('Voto secreto individual não pode ser publicado')
        if sum(r['siglaVotoParlamentar'] in PARTICIPATED for r in individuals)!=spec['participacoes']:raise ValueError('Participações não reconciliadas com resultado oficial')
        if spec['secreta']:
            if (vote['totalVotosSim'],vote['totalVotosNao'],vote['totalVotosAbstencao'])!=(spec['sim'],spec['nao'],spec['abstencao']):raise ValueError('Total da votação secreta divergente')
        elif any(sum(r['siglaVotoParlamentar']==label for r in individuals)!=spec[field] for field,label in [('sim','Sim'),('nao','Não'),('abstencao','Abstenção')]):raise ValueError('Resultado aberto divergente do Diário')
        if parent['id']==cut['id']:votes.append(vote)
    if len(votes)!=len(cut['votacoes']) or len(roster)!=cut['identidades'] or len(set(roster.values()))!=len(roster):raise ValueError('Identidades ou votações ambíguas')
    legend=json.loads(types_raw)['ListaTiposComparecimento']['TiposComparecimento']['TipoComparecimento']
    meanings={r['Sigla']:r['Descricao'] for r in legend}
    if meanings.get('AP')!='Atividade parlamentar':raise ValueError('Legenda AP divergente')
    by_name={value:code for code,value in roster.items()};present={};pages=[];footers=[]
    for i,page in enumerate(text.split('\f'),1+page_offset):
        if 'REGISTRO DE COMPARECIMENTO' not in page or 'Presenças no período:' not in page:continue
        if i not in cut['paginas'] or f"{cut['numero']}ª Sessão Deliberativa {kind}" not in page or f"{cut['legislatura']}ª Legislatura" not in page or '4ª Sessão Legislativa Ordinária' not in page or cut['intervalo'] not in page:raise ValueError('Registro de comparecimento divergente')
        if bool(cut['votacoes'])!=('REGISTRO DE COMPARECIMENTO E VOTO' in page):raise ValueError('Registro de votação divergente')
        if not re.search(rf'\b{i}\b','\n'.join(page.splitlines()[:9])):raise ValueError('Página física do Diário divergente')
        pages.append(i)
        for line in page.splitlines():
            match=re.match(r'^\s*([\wÀ-ÿ]+)\s+([A-Z]{2})\s+(.+?)\s{2,}(X)(?:\s+(X))?\s*$',line)
            if not match:continue
            position=cut['paginas'].index(i)
            if match.start(4)!=cut['colunasPresenca'][position] or (match[5] and match.start(5)!=cut['colunasVoto'][position]):raise ValueError('Marcação X fora da coluna conferida')
            uf,name=match[2],match[3].strip();code=by_name.get((canonical(name),uf))
            if not code or code in present:raise ValueError('Comparecimento sem identidade única')
            if not cut['votacoes'] and match[5]:raise ValueError('Voto em sessão sem nominal')
            present[code]=dict(nomeDiario=name,uf=uf,pagina=i,votoRegistrado=bool(match[5]))
        footers.extend(int(n) for n in re.findall(r'Compareceram\s+(\d+)\s+senadores',page))
    if pages!=cut['paginas'] or footers!=[cut['comparecimentos']] or len(present)!=cut['comparecimentos']:raise ValueError('Contagem DSF não reconciliada')
    return votes,present,meanings


def exercises(raw,code):
    p=json.loads(raw)['MandatoParlamentar']['Parlamentar']
    if str(p['Codigo'])!=str(code):raise ValueError('Exercício de outra identidade')
    mandates=p.get('Mandatos',{}).get('Mandato',[])
    if isinstance(mandates,dict):mandates=[mandates]
    ranges=[]
    for mandate in mandates:
        limit=mandate['SegundaLegislaturaDoMandato']['DataFim']
        records=mandate.get('Exercicios',{}).get('Exercicio',[])
        if isinstance(records,dict):records=[records]
        for r in records:
            start=r['DataInicio'];end=r.get('DataFim') or limit
            for date in (start,end):dt.date.fromisoformat(date)
            if start>end or end>limit:raise ValueError('Exercício inválido')
            ranges.append(dict(inicio=start,fim=end))
    return ranges


def reconcile(code,votes,present,meanings,ranges,licenses,collected,cut=DEFAULT):
    code=str(code);details=[]
    for vote in sorted(votes,key=lambda v:v['dataSessao']):
        day=vote['dataSessao'];active=any(r['inicio']<=day<=r['fim'] for r in ranges)
        records=[r for r in vote['votos'] if str(r['codigoParlamentar'])==code]
        if len(records)>1:raise ValueError('Voto duplicado')
        row=records[0] if records else None
        sigla=row['siglaVotoParlamentar'] if row else None
        if vote['votacaoSecreta']=='S' and sigla is not None and sigla not in SECRET_REGISTERS:raise ValueError('Registro secreto fora do recorte conferido')
        effective=[r['id'] for h in licenses for r in h['licencas'] if r['inicio'] and r['fim'] and r['inicio']<=day<=r['fim']]
        status='fora-exercicio' if not active else 'participou' if sigla in PARTICIPATED else 'justificativa-registrada' if sigla=='AP' or effective else 'pendente'
        details.append(dict(id=str(vote['codigoSessaoVotacao']),data=day,materia=vote['identificacao'],secreta=vote['votacaoSecreta']=='S',registro=sigla,descricao=(SECRET_REGISTERS[sigla] if vote['votacaoSecreta']=='S' else (row.get('descricaoVotoParlamentar') or meanings.get(sigla) or sigla)) if row else 'Sem registro individual',classificacao=status,licencasEfetivas=effective))
    statuses=[r['classificacao'] for r in details]
    registered=code in present
    active_session=any(r['inicio']<=cut['periodoFim'] and r['fim']>=cut['periodoInicio'] for r in ranges)
    outside=not active_session if not details else all(s=='fora-exercicio' for s in statuses)
    if registered and outside:raise ValueError('DSF conflita com exercício')
    status='fora-exercicio' if outside else 'comparecimento-conferido' if registered and not details else 'participacao-conferida' if registered and 'participou' in statuses and all(s in {'participou','fora-exercicio'} for s in statuses) else 'justificativa-registrada' if 'justificativa-registrada' in statuses and all(s in {'participou','justificativa-registrada','fora-exercicio'} for s in statuses) else 'pendente'
    session=dict(id=cut['id'],numero=cut['numero'],comparecimentoRegistrado=registered,registroDiario=present.get(code),classificacao=status,votacoes=details,exercicios=ranges)

    return dict(casa='senado',idParlamentar=code,periodoInicio=cut['periodoInicio'],periodoFim=cut['periodoFim'],coletadoEm=collected,criterio=CRITERION,fontes=[diary_url(cut),cut['votosUrl'],TYPES,MANDATES.format(code=code)]+[h['fontes'][0] for h in licenses],unidade='sessoes',cobertura='recorte-conferido',totalSessoes=1,comparecimentosRegistrados=int(registered),comparecimentosConferidos=int(status=='comparecimento-conferido'),participacoesConferidas=int(status=='participacao-conferida'),justificativasRegistradas=int(status=='justificativa-registrada'),pendentes=int(status=='pendente'),foraExercicio=int(status=='fora-exercicio'),naoJustificada=None,sessoes=[session])
