"""Relatório oficial de presença por dia, sem inferir falta a partir de votação."""
import datetime as dt
from html.parser import HTMLParser
import re
from backend.sources.identity import normalize

URL = 'https://www.camara.leg.br/deputados/{code}/presenca-plenario/{year}'


class AttendanceUnavailable(ValueError):
    pass


class AttendanceMismatch(ValueError):
    def __init__(self, expected, observed, statuses):
        super().__init__('Contagem diária não confere com o resumo oficial')
        self.diagnostic = dict(resumoOficial=expected, contagemDiaria=observed, situacoes=statuses)


class Rows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[];self.cells=None;self.cell=None;self.classes='';self.links=[];self.text=[]

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='a': self.links.append(attrs.get('href',''))
        if tag=='tr':self.cells=[];self.classes=attrs.get('class','').split()
        if tag=='td' and self.cells is not None:self.cell=''

    def handle_data(self,data):
        self.text.append(data)
        if self.cell is not None:self.cell+=data

    def handle_endtag(self,tag):
        if tag=='td' and self.cell is not None:self.cells.append(' '.join(self.cell.split()));self.cell=None
        if tag=='tr' and self.cells is not None:self.rows.append((self.classes,self.cells));self.cells=None;self.cell=None


def parse_attendance(raw,code,year,end,collected):
    parser=Rows();parser.feed(raw.decode('utf-8'));text=' '.join(' '.join(parser.text).split())
    if f'Presença em Plenário - {year}' not in text or not any(url.startswith(f'https://www.camara.leg.br/deputados/{code}?') for url in parser.links):raise ValueError('Relatório de outra identidade/ano')
    if f'Não há dados disponíveis para o ano de {year}.' in text:
        raise AttendanceUnavailable(f'Fonte oficial informa ausência de dados para {year}')
    statuses={'presenca':'presenca','ausencia justificada':'justificada','ausencia nao justificada':'naoJustificada',
              'missao autorizada':'justificada','decisao da mesa':'justificada','licenca para tratamento de saude':'justificada',
              'licenca-gestante (maternidade)':'justificada','licenca paternidade':'justificada','ausencia':'naoJustificada'}
    days={};totals={}
    for classes,cells in parser.rows:
        if len(cells)!=3:continue
        if cells[0].startswith('Total de dias '):
            if not cells[1].isdigit():raise ValueError('Total de dias inválido')
            totals[cells[0]]=int(cells[1])
        if 'info-data' not in classes:continue
        match=re.match(r'^(\d{2}/\d{2}/\d{4})\b',cells[0])
        if not match:continue
        date=dt.datetime.strptime(match[1],'%d/%m/%Y').date().isoformat()
        if date[:4]!=str(year) or date>end or date in days:raise ValueError('Data duplicada ou fora do período')
        status=cells[2].strip()
        if not status:raise ValueError('Dia sem classificação')
        classification=statuses.get(normalize(status),'outros')
        # Alguns relatórios acrescentam notas/justificativas ao rótulo visível.
        for label,value in statuses.items():
            if re.match(re.escape(label)+r'\b',normalize(status)):classification=value;break
        days[date]=dict(data=date,situacao=status,classificacao=classification)
    counts={key:sum(d['classificacao']==key for d in days.values()) for key in ['presenca','justificada','naoJustificada','outros']}
    labels={'totalDias':'Total de dias com sessões deliberativas realizadas no período','presenca':'Total de dias com presença nas sessões deliberativas','justificada':'Total de dias com ausências justificadas em sessões deliberativas','naoJustificada':'Total de dias com ausências não justificadas em sessões deliberativas'}
    expected={key:totals.get(label) for key,label in labels.items()}
    observed=dict(totalDias=len(days),**counts)
    if any(expected[key]!=observed[key] for key in labels):
        from collections import Counter
        raise AttendanceMismatch(expected,observed,dict(Counter(d['situacao'] for d in days.values())))
    return dict(casa='camara',idParlamentar=str(code),periodoInicio=f'{year}-01-01',periodoFim=end,coletadoEm=collected,cobertura='registros-disponiveis',unidade='dias',criterio='Dias classificados no relatório oficial de presença em Plenário, no período de exercício. Ausências justificadas e não justificadas separadas; sujeitas a atualização.',fontes=[URL.format(code=code,year=year)],totalDias=len(days),**counts,dias=list(days.values()))
