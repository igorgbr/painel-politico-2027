import senateRecortes from './senate-recortes.json';
import type {Member, HistoricalBase, HistoricalSummary, AttendanceSummary} from './data';

export function validateAttendance(h: AttendanceSummary,m: Member) {
  if (!h || h.casa !== 'camara' || m.vinculos?.camara !== h.idParlamentar || h.unidade !== 'dias' || h.cobertura !== 'registros-disponiveis' || ![h.totalDias,h.presenca,h.justificada,h.naoJustificada,h.outros].every(n => Number.isSafeInteger(n) && n>=0) || h.totalDias !== h.presenca+h.justificada+h.naoJustificada+h.outros || !Number.isFinite(Date.parse(h.periodoInicio)) || !Number.isFinite(Date.parse(h.periodoFim)) || h.periodoInicio>h.periodoFim || h.periodoInicio.slice(0,4)!==h.periodoFim.slice(0,4) || !Number.isFinite(Date.parse(h.coletadoEm)) || !h.criterio?.trim() || !Array.isArray(h.fontes) || h.fontes.length!==1 || h.fontes[0]!==`https://www.camara.leg.br/deputados/${h.idParlamentar}/presenca-plenario/${h.periodoInicio.slice(0,4)}`) throw new Error('Presença sem identidade, período ou classificação válidos');
}

export function validateSenateLicenses(h:import('./data').SenateLicenseSummary,m:Member){
  const validDate=(v:string)=>/^\d{4}-\d{2}-\d{2}$/.test(v) && Number.isFinite(Date.parse(v));
  if(!h || h.casa!=='senado' || (m.vinculos?.senado!==h.idParlamentar && !(m.casa==='senado' && m.ini===2023 && m.fonte?.id===h.idParlamentar)) || h.cobertura!=='registros-disponiveis' || !Number.isSafeInteger(h.registros) || h.registros<0 || !validDate(h.periodoInicio) || !validDate(h.periodoFim) || h.periodoInicio>h.periodoFim || !Number.isFinite(Date.parse(h.coletadoEm)) || !h.criterio?.trim() || !Array.isArray(h.fontes) || h.fontes.length!==1 || h.fontes[0]!==`https://legis.senado.leg.br/dadosabertos/senador/${h.idParlamentar}/licencas.json?dataInicio=${h.periodoInicio.replace(/-/g,'')}&dataFim=${h.periodoFim.replace(/-/g,'')}&v=6`)throw new Error('Licenças sem identidade ou fonte confirmada');
}

export const senateRecorte=(h:import('./data').SenateSessionSummary)=>senateRecortes.find(r=>r.periodoInicio===h.periodoInicio && r.periodoFim===h.periodoFim && h.fontes?.[0]===`https://legis.senado.leg.br/diarios/ver/${r.diario}`);

export function validateSenateSessions(h:import('./data').SenateSessionSummary,m:Member){
  const cut=h && senateRecorte(h);
  const counts=[h?.totalSessoes,h?.comparecimentosRegistrados,h?.comparecimentosConferidos===undefined?0:h?.comparecimentosConferidos,h?.participacoesConferidas,h?.justificativasRegistradas,h?.pendentes,h?.foraExercicio];
  const official=[
    `https://legis.senado.leg.br/diarios/ver/${cut?.diario}`, cut?.votosUrl,
    'https://legis.senado.leg.br/dadosabertos/plenario/lista/tiposComparecimento.json',
    `https://legis.senado.leg.br/dadosabertos/senador/${h?.idParlamentar}/mandatos.json?v=5`
  ];
  if(!h || !cut || h.casa!=='senado' || (m.vinculos?.senado!==h.idParlamentar && !(m.casa==='senado' && m.ini===2023 && m.fonte?.id===h.idParlamentar)) || h.unidade!=='sessoes' || h.cobertura!=='recorte-conferido' || !Number.isFinite(Date.parse(h.coletadoEm)) || !h.criterio?.trim() || !counts.every(n=>Number.isSafeInteger(n)&&n>=0) || h.totalSessoes!==1 || h.comparecimentosRegistrados>h.totalSessoes || h.participacoesConferidas+(h.comparecimentosConferidos??0)>h.comparecimentosRegistrados || h.participacoesConferidas+(h.comparecimentosConferidos??0)+h.justificativasRegistradas+h.pendentes+h.foraExercicio!==h.totalSessoes || h.naoJustificada!==null || !Array.isArray(h.fontes) || h.fontes.length!==5 || official.some((url,i)=>h.fontes[i]!==url) || !m.resumosHistoricos?.licencasSenado?.some(l=>l.idParlamentar===h.idParlamentar && l.periodoInicio<=h.periodoInicio && l.periodoFim>=h.periodoFim && l.fontes[0]===h.fontes[4]))throw new Error('Recorte Senado sem identidade, fontes ou contagens válidas');
  if((!cut.votacoes.length && ((h.comparecimentosConferidos??0)!==h.comparecimentosRegistrados || h.participacoesConferidas)) || (cut.votacoes.length && h.comparecimentosConferidos))throw new Error('Comparecimento sem nominal confundido com participação');
}

export const senateSessionLabel=(status:import('./data').SenateSessionStatus)=>({'comparecimento-conferido':'Comparecimento conferido (sem votação nominal)','participacao-conferida':'Participação conferida','justificativa-registrada':'Justificativa registrada','pendente':'Participação ainda pendente','fora-exercicio':'Fora do exercício neste recorte'}[status]);

export const moneyCents = (n: number) => (n / 100).toLocaleString('pt-BR', {style:'currency',currency:'BRL'});
export const attendanceHistory = (m: Member) => m.resumosHistoricos?.presencas?.filter(h=>h.casa===m.casa).sort((a,b)=>b.periodoFim.localeCompare(a.periodoFim))[0];
export const resultHistory = (m: Member) => m.resumosHistoricos?.legislativos.filter(h => h.casa === m.casa).sort((a,b) => b.periodoFim.localeCompare(a.periodoFim))[0];
export const missingMetric = (m: Member, key: 'aprov'|'neg'|'custo'|'faltas'|'salario') => {
  if (key === 'salario') return 'Pagamento individual ainda não integrado';
  if (key === 'faltas' && m.resumosHistoricos?.comparecimentosSenado?.length) return 'Consulte o recorte do Senado';
  if (key === 'faltas') return m.resumosHistoricos?.presencas?.length ? 'Consulte a presença histórica' : 'Presença ainda sem consulta confirmada';
  if (key === 'custo') return m.ini === 2027 ? 'Ainda não iniciado' : 'Consulte as despesas históricas';
  const histories = m.resumosHistoricos?.legislativos;
  if (histories?.some(h => h.casa === m.casa)) return 'Resultado ainda não confirmado';
  if (histories?.length) return 'Histórico em outra Casa';
  return 'Histórico ainda não vinculado';
};

export function validateSummaries(s: HistoricalSummary, m: Member) {
  if (!s || !Array.isArray(s.legislativos) || !Array.isArray(s.despesas)) throw new Error('Resumos históricos inválidos');
  for (const kind of ['legislativos','despesas'] as const) {
    const seen = new Set<string>();
    for (const h of s[kind]) {
      const key = JSON.stringify([h.casa,h.periodoInicio,h.periodoFim]);
      if (seen.has(key) || !['camara','senado'].includes(h.casa) || !h.criterio?.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(h.periodoInicio) || !/^\d{4}-\d{2}-\d{2}$/.test(h.periodoFim) || !Number.isFinite(Date.parse(h.periodoInicio)) || !Number.isFinite(Date.parse(h.periodoFim)) || h.periodoInicio > h.periodoFim || !Number.isFinite(Date.parse(h.coletadoEm)) || !Array.isArray(h.fontes) || !h.fontes.length) throw new Error('Período do resumo inválido');
      seen.add(key);
      if (m.vinculos?.[h.casa] !== h.idParlamentar && !(h.casa === 'senado' && m.ini === 2023 && m.fonte?.id === h.idParlamentar)) throw new Error('Resumo sem vínculo confirmado');
      for (const source of h.fontes) {
        const url = new URL(source);
        const allowed = h.casa === 'camara' ? url.hostname.endsWith('.camara.leg.br') : url.hostname.endsWith('.senado.leg.br') || (kind === 'despesas' && url.hostname === 'adm.senado.gov.br');
        if (url.protocol !== 'https:' || !allowed) throw new Error('Fonte de resumo inválida');
      }
    }
  }
  for (const h of s.legislativos) if (![h.total,h.aprov,h.neg,h.pendentes].every(n => Number.isSafeInteger(n) && n >= 0) || h.aprov + h.neg + h.pendentes > h.total) throw new Error('Contagem de resumo inválida');
  for (const h of s.despesas) if (!Number.isSafeInteger(h.totalCentavos) || !Number.isSafeInteger(h.registros) || h.registros <= 0 || h.cobertura !== 'registros-disponiveis') throw new Error('Despesas do resumo inválidas');
  if(s.comparecimentosSenado!==undefined){
    if(!Array.isArray(s.comparecimentosSenado))throw new Error('Recortes Senado inválidos');
    const periods=new Set<string>();
    for(const h of s.comparecimentosSenado){validateSenateSessions(h,m);if(periods.has(h.periodoInicio))throw new Error('Recorte Senado duplicado');periods.add(h.periodoInicio);}
  }
  if(s.licencasSenado!==undefined){
    if(!Array.isArray(s.licencasSenado))throw new Error('Licenças inválidas');
    const periods=new Set<string>();
    for(const h of s.licencasSenado){validateSenateLicenses(h,m);if(periods.has(h.periodoInicio))throw new Error('Licenças duplicadas');periods.add(h.periodoInicio);}
  }
  if (s.presencas!==undefined) {
    if (!Array.isArray(s.presencas)) throw new Error('Presenças inválidas');
    const periods=new Set<string>();
    for(const h of s.presencas){validateAttendance(h,m);if(periods.has(h.periodoInicio))throw new Error('Presença duplicada');periods.add(h.periodoInicio);}
  }
}

export function aggregateHistory(rows: Member[], group: 'partido'|'uf'|'reg'|'casaNome') {
  type Bucket = HistoricalBase & {key: string; grupo: string; participantes: number; universo: number; total: number; aprov: number; neg: number; pendentes: number; totalCentavos: number};
  const totals = new Map<string,number>();
  for (const m of rows) totals.set(m[group], (totals.get(m[group]) ?? 0) + 1);
  const build = (kind: 'legislativos'|'despesas') => {
    const buckets = new Map<string,Bucket>();
    for (const m of rows) for (const h of m.resumosHistoricos?.[kind] ?? []) {
      const key = JSON.stringify([m[group],h.casa,h.periodoInicio,h.periodoFim,h.criterio]);
      const b = buckets.get(key) ?? {...h,key,grupo:m[group],participantes:0,universo:totals.get(m[group])!,total:0,aprov:0,neg:0,pendentes:0,totalCentavos:0};
      b.participantes++;
      if ('totalCentavos' in h) b.totalCentavos += h.totalCentavos;
      else { b.total += h.total; b.aprov += h.aprov; b.neg += h.neg; b.pendentes += h.pendentes; }
      if (h.coletadoEm > b.coletadoEm) b.coletadoEm = h.coletadoEm;
      buckets.set(key,b);
    }
    return [...buckets.values()].sort((a,b) => b.universo-a.universo || a.grupo.localeCompare(b.grupo,'pt-BR') || a.casa.localeCompare(b.casa));
  };
  const attendance=new Map<string,AttendanceSummary & {key:string;grupo:string;participantes:number;universo:number}>();
  for(const m of rows)for(const h of m.resumosHistoricos?.presencas??[]){
    const key=JSON.stringify([m[group],h.casa,h.periodoInicio,h.periodoFim,h.criterio]);
    const b=attendance.get(key)??{...h,key,grupo:m[group],participantes:0,universo:totals.get(m[group])!,presenca:0,justificada:0,naoJustificada:0,outros:0,totalDias:0};
    b.participantes++;for(const field of ['presenca','justificada','naoJustificada','outros','totalDias'] as const)b[field]+=h[field];attendance.set(key,b);
  }
  return {legislativos:build('legislativos'),despesas:build('despesas'),presencas:[...attendance.values()],grupos:[...totals.entries()]};
}
