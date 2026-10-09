import collections
import csv
import datetime as dt
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
STATES = json.loads((ROOT / 'src/states.json').read_text())
BY_UF = {s['uf']: s for s in STATES}
TSE = 'https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2026.zip'
SENADO = 'https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json'
CATALOG = 'https://dadosabertos.tse.jus.br/dataset/candidatos-2026'
ELECTED = {'ELEITO', 'ELEITO POR QP', 'ELEITO POR MÉDIA'}
PARTIES = {'PCDOB': 'PCdoB', 'UNIÃO': 'União', 'UNIAO': 'União', 'REPUBLICANOS': 'Republicanos', 'NOVO': 'Novo', 'PODE': 'Podemos', 'PODEMOS': 'Podemos', 'REDE': 'Rede', 'AVANTE': 'Avante', 'SOLIDARIEDADE': 'Solidariedade', 'CIDADANIA': 'Cidadania', 'S/PARTIDO': 'Sem partido'}


def party(value):
    return PARTIES.get(value.upper(), value)


def member(casa, nome, uf, partido, ini, fim, identifier, fonte):
    if uf not in BY_UF:
        raise ValueError(f'UF inválida: {uf}')
    if not nome.strip() or not partido.strip():
        raise ValueError('Nome/partido vazio')
    return dict(id=identifier, casa=casa, casaNome='Senado' if casa == 'senado' else 'Câmara', nome=nome,
                uf=uf, reg=BY_UF[uf]['reg'], partido=party(partido), ini=ini, fim=fim, mandato=f'{ini}–{fim}',
                aprov=None, neg=None, faltas=None, salario=None, custo=None, fonte=fonte,
                historico='Histórico anterior ainda não integrado')


def tse_members(raw, collected):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = [n for n in archive.namelist() if n.endswith('.csv') and 'BRASIL' in n.upper()]
        if len(files) != 1:
            raise ValueError('CSV nacional único ausente no ZIP do TSE')
        with io.TextIOWrapper(archive.open(files[0]), encoding='latin1', newline='') as stream:
            reader = csv.DictReader(stream, delimiter=';')
            required = {'ANO_ELEICAO', 'NR_TURNO', 'DS_CARGO', 'SQ_CANDIDATO', 'SG_UF', 'NM_URNA_CANDIDATO', 'SG_PARTIDO', 'DS_SIT_TOT_TURNO', 'DT_GERACAO', 'HH_GERACAO', 'CD_TIPO_ELEICAO'}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError('Schema TSE incompatível')
            result = []
            for row in reader:
                if row['DS_CARGO'] not in {'DEPUTADO FEDERAL', 'SENADOR'} or row['DS_SIT_TOT_TURNO'] not in ELECTED:
                    continue
                if row['ANO_ELEICAO'] != '2026' or row['NR_TURNO'] != '1' or row['CD_TIPO_ELEICAO'] != '2':
                    raise ValueError('Eleição/período inesperado no arquivo TSE')
                casa = 'senado' if row['DS_CARGO'] == 'SENADOR' else 'camara'
                generated = dt.datetime.strptime(row['DT_GERACAO'] + ' ' + row['HH_GERACAO'], '%d/%m/%Y %H:%M:%S').replace(tzinfo=dt.timezone(dt.timedelta(hours=-3))).isoformat()
                source = dict(nome='TSE — candidaturas e situação de totalização 2026', url=CATALOG,
                              coletadoEm=collected, geradoEm=generated, id=row['SQ_CANDIDATO'])
                m = member(casa, row['NM_URNA_CANDIDATO'], row['SG_UF'], row['SG_PARTIDO'], 2027,
                           2035 if casa == 'senado' else 2031, f"tse-2026-{row['SQ_CANDIDATO']}", source)
                m.update(situacao='Eleito em 2026 — ' + row['DS_SIT_TOT_TURNO'].lower(), partidoEleicao=m['partido'], partidoAtual=None, participacao='Titular eleito', titular=None)
                result.append(m)
            return result


def continuing_members(raw, collected):
    data = json.loads(raw)['ListaParlamentarEmExercicio']
    generated = dt.datetime.strptime(data['Metadados']['Versao'], '%d/%m/%Y %H:%M:%S').replace(tzinfo=dt.timezone(dt.timedelta(hours=-3))).isoformat()
    result = []
    for row in data['Parlamentares']['Parlamentar']:
        mandate = row['Mandato']
        ini = int(mandate['PrimeiraLegislaturaDoMandato']['DataInicio'][:4])
        fim = int(mandate['SegundaLegislaturaDoMandato']['DataFim'][:4])
        if fim <= 2027:
            continue
        if (ini, fim) != (2023, 2031):
            raise ValueError('Mandato em continuidade inesperado')
        identity = row['IdentificacaoParlamentar']
        source = dict(nome='Senado — parlamentar em exercício na coleta', url=identity['UrlPaginaParlamentar'].replace('http:', 'https:'),
                      coletadoEm=collected, geradoEm=generated, id=identity['CodigoParlamentar'])
        m = member('senado', identity['NomeParlamentar'], identity['UfParlamentar'], identity['SiglaPartidoParlamentar'], ini, fim,
                   'senado-mandato-' + mandate['CodigoMandato'], source)
        m.update(situacao='Mandato até 2031 — ocupante na data da coleta', partidoEleicao=None, partidoAtual=m['partido'],
                 participacao=mandate['DescricaoParticipacao'], titular=mandate.get('Titular', {}).get('NomeParlamentar'))
        result.append(m)
    return result


def validate(members):
    ids = [m['id'] for m in members]
    if len(ids) != len(set(ids)):
        raise ValueError('Identificadores duplicados')
    for state in STATES:
        for casa, expected in [('senado', 3), ('camara', state['deps'])]:
            found = sum(m['uf'] == state['uf'] and m['casa'] == casa for m in members)
            if found != expected:
                raise ValueError(f"{casa}/{state['uf']}: {found} registros; esperado {expected}. Último conjunto preservado.")
    counts = collections.Counter(m['casa'] for m in members)
    if counts != {'senado': 81, 'camara': 513}:
        raise ValueError('Composição incompleta')


