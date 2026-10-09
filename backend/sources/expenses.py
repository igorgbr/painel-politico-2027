"""Despesas por competência; valores em centavos, sem identidade por nome."""
import csv
import io
import json
import zipfile
from decimal import Decimal

CAMARA = 'https://www.camara.leg.br/cotas/Ano-{year}.csv.zip'
SENADO = 'https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/{year}'
START = '2026-01-01'
END = '2026-09-30'


def cents(value):
    n = Decimal(str(value))
    if not n.is_finite() or n * 100 != (n * 100).to_integral_value():
        raise ValueError('Valor monetário inválido')
    return int(n * 100)


def parse_expenses(raw, house, start, end):
    if house == 'camara':
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if n.endswith('.csv')]
            if len(names) != 1: raise ValueError('Arquivo CEAP incompatível')
            rows = csv.DictReader(io.StringIO(z.read(names[0]).decode('utf-8-sig')), delimiter=';')
            required = {'ideCadastro', 'numAno', 'numMes', 'vlrLiquido', 'vlrRestituicao', 'txtDescricao'}
            if not required.issubset(rows.fieldnames or []): raise ValueError('Campos CEAP ausentes')
            rows = list(rows)
    else:
        rows = json.loads(raw, parse_float=Decimal)
        if not isinstance(rows, list) or not rows: raise ValueError('Arquivo CEAPS incompatível')
    result = {}; ids = set()
    for row in rows:
        year = int(row['numAno' if house == 'camara' else 'ano'])
        month = int(row['numMes' if house == 'camara' else 'mes'])
        if not 1 <= month <= 12: raise ValueError('Competência inválida')
        period = f'{year:04}-{month:02}'
        if not start[:7] <= period <= end[:7]: continue
        code = str(row['ideCadastro' if house == 'camara' else 'codSenador'])
        if not code: continue  # Lideranças da Câmara não são pessoas.
        if not code.isdigit(): raise ValueError('Identificador parlamentar inválido')
        if house == 'senado':
            key = str(row['id'])
            if key in ids: raise ValueError('Registro CEAPS duplicado')
            ids.add(key)
        # ideDocumento NÃO identifica uma linha CEAP: parcelas/créditos devem permanecer.
        value = cents(row['vlrLiquido' if house == 'camara' else 'valorReembolsado'])
        refund = cents(row['vlrRestituicao'] or 0) if house == 'camara' else 0
        category = row['txtDescricao' if house == 'camara' else 'tipoDespesa']
        if category is None or category == '': category = 'Categoria não informada na fonte'
        if not isinstance(category, str) or not category.strip(): raise ValueError('Categoria inválida')
        item = result.setdefault(code, dict(totalCentavos=0, restituicoesCentavos=0, registros=0, meses={}, categorias={}))
        item['totalCentavos'] += value; item['restituicoesCentavos'] += refund; item['registros'] += 1
        item['meses'][period] = item['meses'].get(period, 0) + value
        item['categorias'][category] = item['categorias'].get(category, 0) + value
    if not result: raise ValueError('Nenhum registro no período solicitado')
    return result


def record(house, code, values, start, end, collected, sources):
    criterion = ('Soma de vlrLiquido por competência financeira, incluindo créditos negativos. Restituições informadas separadamente, sem subtração adicional.' if house == 'camara' else 'Soma de valorReembolsado por ano/mês da CEAPS, incluindo ajustes negativos.')
    months = []
    year, month = map(int, start[:7].split('-'))
    while f'{year:04}-{month:02}' <= end[:7]:
        period = f'{year:04}-{month:02}'
        months.append(dict(competencia=period, totalCentavos=values['meses'].get(period, 0)))
        month += 1
        if month == 13: year += 1; month = 1
    return dict(casa=house, idParlamentar=code, periodoInicio=start, periodoFim=end, coletadoEm=collected,
                cobertura='registros-disponiveis', criterio=criterion, fontes=sources,
                totalCentavos=values['totalCentavos'], restituicoesCentavos=values['restituicoesCentavos'] if house == 'camara' else None,
                registros=values['registros'], meses=months,
                categorias=[dict(nome=k, totalCentavos=v) for k,v in sorted(values['categorias'].items())])
