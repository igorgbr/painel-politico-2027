"""Subsídio normativo bruto de referência, sem folha individual nem previsão de 2027."""
import re
from backend.sources.attendance import Rows
from backend.sources.expenses import cents

GUIDE='https://www2.camara.leg.br/comunicacao/assessoria-de-imprensa/guia-para-jornalistas/salario-de-deputados'
NORM='https://www2.camara.leg.br/legin/fed/decleg/2022/decretolegislativo-172-21-dezembro-2022-793529-publicacaooriginal-166604-pl.html'


def reference(guide,norm,collected):
    def plain(raw):
        parser=Rows();parser.feed(raw.decode('utf-8'));return ' '.join(' '.join(parser.text).split())
    text=plain(guide);law=plain(norm)
    match=re.search(r'remuneração bruta mensal.*?R\$\s*([\d.,]+)\s+a partir de 1º de fevereiro de (\d{4})',text)
    if not match or 'o mesmo para deputados federais e senadores' not in text or '172/2022' not in text:raise ValueError('Subsídio de referência não confirmado')
    amount,year=match.groups()
    if not re.search(r'IV\s*-\s*R\$\s*'+re.escape(amount),law) or 'membros do Congresso Nacional' not in law or year!='2025':raise ValueError('Norma e guia divergentes; revisar nova vigência')
    return dict(valorCentavos=cents(amount.replace('.','').replace(',','.')),inicioVigencia=f'{year}-02-01',verificadoEm=collected,fontes=[GUIDE,NORM],norma='Decreto Legislativo 172/2022',tipo='referencia-bruta-mensal')
