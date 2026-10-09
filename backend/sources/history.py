"""PL/PLP apresentados no período; resultados oficiais observados na coleta."""
import csv
import io
import re
from urllib.parse import urlencode

START = '2023-02-01'
END = '2026-10-05'
CAMARA_FILES = 'https://dadosabertos.camara.leg.br/arquivos/{kind}/csv/{kind}-{year}.csv'
SENADO_PROCESS = 'https://legis.senado.leg.br/dadosabertos/processo.json'


def csv_rows(raw):
    return csv.DictReader(io.TextIOWrapper(io.BytesIO(raw), encoding='utf-8-sig', newline=''), delimiter=';')


def parse_camara_projects(raw, start, end):
    result = {}
    for row in csv_rows(raw):
        if row['siglaTipo'] not in {'PL', 'PLP'} or not start <= row['dataApresentacao'][:10] <= end:
            continue
        status = row['ultimoStatus_descricaoSituacao']
        urn = row.get('urnFinal', '')
        classification = 'outros'
        # Status final + referência à norma publicada: aprovação parcial não satisfaz.
        if status == 'Transformado em Norma Jurídica' and re.search(r'urn:lex:br:federal:lei(?:\.complementar)?:', urn):
            classification = 'aprov'
        # Só rejeição expressa; arquivamento não é sinônimo de rejeição.
        elif status in {'Rejeitada', 'Rejeitado'}:
            classification = 'neg'
        result[row['id']] = dict(id=row['id'], num=f"{row['siglaTipo']} {row['numero']}/{row['ano']}", titulo=row['ementa'], url=f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={row['id']}", situacao=status or 'Situação não informada', dataApresentacao=row['dataApresentacao'][:10], classificacao=classification, norma=urn or None)
    return result


def parse_camara_authors(raw, projects):
    result = {}
    for row in csv_rows(raw):
        project = row['idProposicao']
        if project not in projects:
            continue
        match = re.fullmatch(r'https://dadosabertos\.camara\.leg\.br/api/v2/deputados/(\d+)', row['uriAutor'])
        if match:
            result.setdefault(match[1], set()).add(project)
    return result


def senado_url(code, kind, start, end):
    return SENADO_PROCESS + '?' + urlencode(dict(codigoParlamentarAutor=code, sigla=kind, dataInicioApresentacao=start, dataFimApresentacao=end))


def parse_senado_projects(rows, start, end):
    if not isinstance(rows, list):
        raise ValueError('Schema de processos do Senado incompatível')
    result = {}
    for row in rows:
        if not start <= row['dataApresentacao'][:10] <= end or not re.match(r'^PLP? \d+/\d{4}$', row['identificacao']):
            continue
        norma = row.get('normaGerada')
        status = row.get('situacaoAtual', '')
        classification = 'outros'
        if norma and re.search(r'\bLEI(?:\s+COMPLEMENTAR)?\b', norma, re.I):
            classification = 'aprov'
        elif status.upper() in {'REJEITADA', 'REJEITADO', 'REJEITADA EM DECISÃO TERMINATIVA'}:
            classification = 'neg'
        code = str(row['id'])
        url = f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{row['codigoMateria']}" if row.get('codigoMateria') else f'https://legis.senado.leg.br/dadosabertos/processo.json?idProcesso={code}'
        result[code] = dict(id=code, num=row['identificacao'], titulo=row['ementa'], url=url, situacao=status or 'Situação não informada', dataApresentacao=row['dataApresentacao'][:10], classificacao=classification, norma=norma)
    return result


def history_record(house, code, projects, start, end, collected, urls):
    rows = sorted(projects.values(), key=lambda p: (p['dataApresentacao'], p['id']), reverse=True)
    return dict(casa=house, idParlamentar=str(code), periodoInicio=start, periodoFim=end, coletadoEm=collected,
                cobertura='completa', criterio='PL e PLP de autoria/coautoria apresentados no período; situação observada na coleta. Conversão exige referência oficial à lei; rejeição exige situação expressa.',
                fontes=urls, total=len(rows), projetos=rows,
                aprov=sum(p['classificacao'] == 'aprov' for p in rows), neg=sum(p['classificacao'] == 'neg' for p in rows))


def law_reference(project, payload, tramitations=None):
    """Somente despacho explícito de transformação, com ID/tipo/número/ano coincidentes."""
    row = payload['dados']
    if str(row['id']) != project['id'] or f"{row['siglaTipo']} {row['numero']}/{row['ano']}" != project['num']:
        raise ValueError('Referência de outro projeto')
    status = row['statusProposicao']
    if status.get('descricaoSituacao') != 'Transformado em Norma Jurídica': return None
    urn = row.get('urnFinal')
    if urn and re.fullmatch(r'urn:lex:br:federal:lei(?:\.complementar)?:[^\s]+',urn): return urn
    def dispatch_reference(text):
        match = re.search(r'^\s*Transformad[oa]\s+(?:na|em)\s+Lei\s+(Ordinária|Complementar)\s*(?:n[º°.]?\s*)?(\d[\d.]*)/(\d{4})\b',text or '',re.I)
        if not match: return None
        kind, number, year = match.groups()
        return f"Lei {'Complementar' if kind.casefold() == 'complementar' else 'Ordinária'} {number}/{year}"
    reference = dispatch_reference(status.get('despacho'))
    if reference: return reference
    references = {dispatch_reference(r.get('despacho')) for r in tramitations or [] if str(r.get('codTipoTramitacao'))=='251'} - {None}
    return next(iter(references)) if len(references)==1 else None
