"""Licenças oficiais: evidência para apuração, sem inferir assiduidade."""
import datetime as dt
import json

LICENSE_URL='https://legis.senado.leg.br/dadosabertos/senador/{code}/licencas.json?dataInicio={start}&dataFim={end}&v=6'
GUIDE='https://www12.senado.leg.br/assessoria-de-imprensa/guia-para-jornalistas/tutorial-de-verificacao-da-assiduidade-dos-senadores'


def parse_licenses(raw, code, start, end, collected):
    for value in (start,end):dt.date.fromisoformat(value)
    if start>end:raise ValueError('Período inválido')
    root=json.loads(raw)['LicencaParlamentar']
    person=root['Parlamentar']
    if str(person['Codigo'])!=str(code):raise ValueError('Licenças de outra identidade')
    container=person.get('Licencas')
    if container is not None and not isinstance(container,dict):raise ValueError('Formato das licenças inválido')
    records=container.get('Licenca',[]) if isinstance(container,dict) else []
    if isinstance(records,dict):records=[records]
    if not isinstance(records,list):raise ValueError('Lista de licenças inválida')
    result=[];seen=set()
    def date(value):
        if value is None or value=='':return None
        if not isinstance(value,str) or dt.date.fromisoformat(value).isoformat()!=value:raise ValueError('Data de licença inválida')
        return value
    for record in records:
        identity=str(record['Codigo'])
        if not identity.isdigit() or identity in seen:raise ValueError('Licença duplicada ou sem código')
        seen.add(identity)
        kind=record['SiglaTipoAfastamento'];description=record['DescricaoTipoAfastamento']
        if not isinstance(kind,str) or not kind.strip() or not isinstance(description,str) or not description.strip():raise ValueError('Licença sem descrição')
        actual_start=date(record.get('DataInicio'));actual_end=date(record.get('DataFim'))
        planned_start=date(record.get('DataInicioPrevista'));planned_end=date(record.get('DataFimPrevista'))
        if not actual_start and not planned_start:raise ValueError('Licença sem início')
        if actual_end and (not actual_start or actual_end<actual_start):raise ValueError('Período efetivo inválido')
        if planned_end and (not planned_start or planned_end<planned_start):raise ValueError('Período previsto inválido')
        beginning=actual_start or planned_start
        finish=actual_end if actual_start else planned_end
        if beginning>end or (finish and finish<start):continue
        result.append(dict(id=identity,tipo=kind,descricao=description,inicio=actual_start,fim=actual_end,inicioPrevisto=planned_start,fimPrevisto=planned_end))
    result.sort(key=lambda r:(r['inicio'] or r['inicioPrevisto'],r['id']))
    url=LICENSE_URL.format(code=code,start=start.replace('-',''),end=end.replace('-',''))
    return dict(casa='senado',idParlamentar=str(code),periodoInicio=start,periodoFim=end,coletadoEm=collected,cobertura='registros-disponiveis',criterio='Licenças oficiais com interseção no período consultado. Datas efetivas e previstas separadas. Não mede presença, faltas ou dias de sessão.',fontes=[url],registros=len(result),licencas=result)
