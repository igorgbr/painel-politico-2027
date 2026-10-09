"""Correspondência privada com evidência; nome é só filtro de busca, nunca prova."""
import csv
import io
import re
import unicodedata
import zipfile


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value or '') if not unicodedata.combining(c)).casefold().strip()


def cpf(value):
    value = re.sub(r'\D', '', value or '')
    if len(value) != 11 or len(set(value)) == 1:
        return None
    for size in (9, 10):
        check = (sum(int(value[i]) * (size + 1 - i) for i in range(size)) * 10) % 11 % 10
        if check != int(value[size]):
            return None
    return value


def election_identities(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        name = next(n for n in archive.namelist() if 'BRASIL' in n and n.endswith('.csv'))
        with io.TextIOWrapper(archive.open(name), encoding='latin1') as stream:
            return {r['SQ_CANDIDATO']: {'nome': r['NM_CANDIDATO'], 'cpf': cpf(r['NR_CPF_CANDIDATO']), 'nascimento': r['DT_NASCIMENTO'], 'ufNascimento': r['SG_UF_NASCIMENTO']} for r in csv.DictReader(stream, delimiter=';') if r['DS_CARGO'] in {'DEPUTADO FEDERAL', 'SENADOR'} and r['DS_SIT_TOT_TURNO'] in {'ELEITO', 'ELEITO POR QP', 'ELEITO POR MÉDIA'}}


def match_camara(election, profiles):
    matches = [d for d in profiles if election['cpf'] and cpf(d.get('cpf')) == election['cpf']]
    return matches[0] if len(matches) == 1 else None


def ceap_identity_candidates(raw):
    """CPF privado seleciona perfis; cada vínculo ainda exige confirmação no perfil."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = [n for n in archive.namelist() if n.endswith('.csv')]
        if len(names) != 1: raise ValueError('Arquivo CEAP incompatível')
        with io.TextIOWrapper(archive.open(names[0]), encoding='utf-8-sig') as stream:
            result = {}
            for row in csv.DictReader(stream, delimiter=';'):
                identifier = cpf(row['cpf']); code = row['ideCadastro']
                if identifier and code.isdigit(): result.setdefault(identifier,set()).add(code)
            return result


def match_senado(election, profiles):
    matches = []
    for p in profiles:
        identity = p['IdentificacaoParlamentar']
        basics = p['DadosBasicosParlamentar']
        # São necessárias três características e uma única correspondência.
        if normalize(identity.get('NomeCompletoParlamentar')) == normalize(election['nome']) and basics.get('DataNascimento', '') == '-'.join(reversed(election['nascimento'].split('/'))) and basics.get('UfNaturalidade') == election['ufNascimento'] and election['ufNascimento'] not in {'#NULO', 'ZZ', ''}:
            matches.append(p)
    return matches[0] if len(matches) == 1 else None
