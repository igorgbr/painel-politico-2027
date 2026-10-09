import { COR, STATES, type Member, type LegislativeHistory } from './data';
import {validateSummaries,validateAttendance,validateSenateLicenses,validateSenateSessions,senateRecorte} from './history';

export interface Dataset {
  schemaVersion: 1 | 2;
  versao?: string;
  recorte: 'eleitos-2027';
  atualizadoEm: string;
  coberturaSenado?: import('./data').SenateCoverage;
  observacoes: string[];
  senado: Member[];
  camara: Member[];
}

// Falhas de schema/completude não podem se transformar silenciosamente em dados fictícios.
export function parseDataset(value: unknown): Dataset {
  const fail = (message: string): never => { throw new Error(`Dados oficiais inválidos: ${message}`); };
  if (!value || typeof value !== 'object') return fail('arquivo incompatível');
  const data = value as Record<string, unknown>;
  if ((data.schemaVersion !== 1 && data.schemaVersion !== 2) || data.recorte !== 'eleitos-2027') return fail('versão ou recorte incompatível');
  if (typeof data.atualizadoEm !== 'string' || !Number.isFinite(Date.parse(data.atualizadoEm))) return fail('data de coleta ausente');
  if (!Array.isArray(data.observacoes) || !data.observacoes.every(n => typeof n === 'string')) return fail('observações ausentes');
  if (data.schemaVersion === 2 && (typeof data.versao !== 'string' || !/^[a-f0-9]{24}$/.test(data.versao))) return fail('versão do snapshot inválida');
  const ids = new Set<string>();
  const read = (casa: 'senado' | 'camara'): Member[] => {
    const rows = data[casa];
    if (!Array.isArray(rows)) return fail(`lista de ${casa} ausente`);
    return rows.map((row: unknown) => {
      if (!row || typeof row !== 'object') return fail('parlamentar inválido');
      const m = row as Member;
      const state = STATES.find(s => s.uf === m.uf);
      if (typeof m.id !== 'string' || !m.id || ids.has(m.id)) return fail('identificador ausente ou duplicado');
      ids.add(m.id);
      if (m.casa !== casa || m.casaNome !== (casa === 'senado' ? 'Senado' : 'Câmara') || !state || m.reg !== state.reg) return fail('casa/estado/região incompatível');
      if (typeof m.nome !== 'string' || !m.nome.trim() || typeof m.partido !== 'string' || !m.partido.trim()) return fail('nome/partido ausente');
      if (!Number.isInteger(m.ini) || !Number.isInteger(m.fim) || !((m.ini === 2027 && m.fim === (casa === 'senado' ? 2035 : 2031)) || (casa === 'senado' && m.ini === 2023 && m.fim === 2031)) || m.mandato !== `${m.ini}–${m.fim}`) return fail('mandato incompatível');
      for (const key of ['aprov', 'neg', 'faltas', 'salario', 'custo'] as const) {
        if (m[key] === null) continue;
        const evidence = m.indicadores?.[key];
        if (data.schemaVersion !== 2 || typeof m[key] !== 'number' || !Number.isFinite(m[key]) || m[key]! < 0 || !evidence || evidence.casa !== casa || evidence.cobertura !== 'completa' || evidence.unidade !== (key === 'salario' || key === 'custo' ? 'BRL' : 'quantidade') || !evidence.criterio?.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(evidence.periodoInicio) || !/^\d{4}-\d{2}-\d{2}$/.test(evidence.periodoFim) || !Number.isFinite(Date.parse(evidence.periodoInicio)) || !Number.isFinite(Date.parse(evidence.periodoFim)) || evidence.periodoInicio > evidence.periodoFim || !Number.isFinite(Date.parse(evidence.coletadoEm))) return fail('indicador sem integração validada');
        let source: URL;
        try { source = new URL(evidence.fonteUrl); } catch { return fail('fonte do indicador inválida'); }
        if (source.protocol !== 'https:' || !(source.hostname.endsWith('.senado.leg.br') || source.hostname.endsWith('.camara.leg.br') || source.hostname === 'camara.leg.br')) return fail('fonte do indicador não oficial');
      }
      if (!m.fonte || typeof m.fonte.id !== 'string' || !m.fonte.id || typeof m.fonte.nome !== 'string' || !Number.isFinite(Date.parse(m.fonte.coletadoEm)) || !Number.isFinite(Date.parse(m.fonte.geradoEm))) return fail('fonte incompleta');
      let url: URL;
      try { url = new URL(m.fonte.url); } catch { return fail('URL de fonte inválida'); }
      if (url.protocol !== 'https:' || !(url.hostname.endsWith('.tse.jus.br') || url.hostname.endsWith('.senado.leg.br'))) return fail('fonte não oficial');
      if (typeof m.situacao !== 'string' || typeof m.participacao !== 'string' || typeof m.historico !== 'string') return fail('situação/histórico ausente');
      if (data.schemaVersion === 2 && (typeof m.pessoaId !== 'string' || !m.pessoaId.startsWith('p-') || m.mandatoId !== m.id || typeof m.identidade !== 'string' || m.detalhesUrl !== `data/snapshots/${data.versao}/${m.id}.json` || !/^[a-zA-Z0-9-]+$/.test(m.id))) return fail('identidade ou endereço dos detalhes incompatível');
      if (m.resumosHistoricos !== undefined) validateSummaries(m.resumosHistoricos,m);
      if(m.subsidioReferencia!==undefined){
        const r=m.subsidioReferencia;
        if(!r || r.tipo!=='referencia-bruta-mensal' || !Number.isSafeInteger(r.valorCentavos) || r.valorCentavos<=0 || !Number.isFinite(Date.parse(r.inicioVigencia)) || !Number.isFinite(Date.parse(r.verificadoEm)) || r.inicioVigencia>r.verificadoEm.slice(0,10) || !r.norma?.trim() || !Array.isArray(r.fontes) || r.fontes.length<2) return fail('referência de subsídio inválida');
        for(const source of r.fontes){const url=new URL(source);if(url.protocol!=='https:' || url.hostname!=='www2.camara.leg.br')return fail('fonte de subsídio inválida');}
      }
      if (m.foto !== undefined) {
        const f=m.foto;
        if (!f || !['camara','senado'].includes(f.casa) || !Number.isFinite(Date.parse(f.coletadoEm)) || (m.vinculos?.[f.casa] !== f.idParlamentar && !(f.casa==='senado' && m.ini===2023 && m.fonte.id===f.idParlamentar))) return fail('foto sem vínculo confirmado');
        if (f.arquivoLocal !== undefined && (!/^photos\/[a-f0-9]{64}\.(jpg|png)$/.test(f.arquivoLocal) || !f.imagemColetadaEm || !Number.isFinite(Date.parse(f.imagemColetadaEm)))) return fail('arquivo local da foto inválido');
        const photo=new URL(f.url), source=new URL(f.fonteUrl);
        if (photo.protocol!=='https:' || source.protocol!=='https:' || photo.hostname!==(f.casa==='camara'?'www.camara.leg.br':'www.senado.leg.br') || f.fonteUrl!==(f.casa==='camara'?`https://dadosabertos.camara.leg.br/api/v2/deputados/${f.idParlamentar}`:`https://legis.senado.leg.br/dadosabertos/senador/${f.idParlamentar}.json`)) return fail('fonte da foto inválida');
      }
      return { ...m, cor: COR[m.partido] ?? '#55585F' };
    });
  };
  const senado = read('senado'), camara = read('camara');
  for (const st of STATES) {
    if (senado.filter(m => m.uf === st.uf).length !== 3 || camara.filter(m => m.uf === st.uf).length !== st.deps) return fail(`composição incompleta em ${st.uf}`);
  }
  const coverage=data.coberturaSenado as import('./data').SenateCoverage|undefined;
  if(coverage!==undefined){
    const c=coverage;
    const expected=new Set([...senado,...camara].flatMap(m=>(m.resumosHistoricos?.comparecimentosSenado??[]).filter(h=>h.periodoInicio>=c?.periodoInicio && h.periodoFim<=c?.periodoFim).map(h=>senateRecorte(h)!.id)));
    if(!c || c.periodoInicio!=='2026-01-01' || !/^2026-\d{2}-\d{2}$/.test(c.periodoFim) || !Number.isFinite(Date.parse(c.periodoFim)) || c.periodoFim<c.periodoInicio || !Number.isFinite(Date.parse(c.coletadoEm)) || !c.criterio?.trim() || ![c.sessoesIdentificadas,c.sessoesConferidas].every(n=>Number.isSafeInteger(n)&&n>=0) || c.sessoesConferidas>c.sessoesIdentificadas || c.sessoesConferidas!==expected.size || !Array.isArray(c.fontes) || c.fontes.length!==Number(c.periodoFim.slice(5,7)) || c.fontes.some((url,i)=>url!==`https://legis.senado.leg.br/dadosabertos/plenario/agenda/mes/2026${String(i+1).padStart(2,'0')}01.json?v=2`))return fail('cobertura do Senado sem fontes, período ou contagens válidas');
  }
  return { schemaVersion: data.schemaVersion as 1 | 2, versao: data.versao as string | undefined, recorte: 'eleitos-2027', atualizadoEm: data.atualizadoEm, observacoes: data.observacoes as string[], coberturaSenado:coverage, senado, camara };
}

export function partyCounts(members: Member[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const m of members) counts.set(m.partido, (counts.get(m.partido) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'pt-BR'));
}

export interface MemberDetails {
  schemaVersion: 2; versao: string; pessoaId: string; mandatoId: string; historico: string;
  projetos: { aprov: import('./data').Law[]; neg: import('./data').Law[] };
  historicosLegislativos?: LegislativeHistory[];
  despesasHistoricas?: import('./data').ExpenseHistory[];
  licencasSenado?: import('./data').SenateLicenseHistory[];
  comparecimentosSenado?: import('./data').SenateSessionHistory[];
  presencasHistoricas?: import('./data').AttendanceHistory[];
}

export function parseMemberDetails(value: unknown, member: Member, version: string): MemberDetails {
  if (!value || typeof value !== 'object') throw new Error('Detalhes inválidos');
  const d = value as MemberDetails;
  if (d.schemaVersion !== 2 || d.versao !== version || d.pessoaId !== member.pessoaId || d.mandatoId !== member.mandatoId || typeof d.historico !== 'string' || !d.projetos || !Array.isArray(d.projetos.aprov) || !Array.isArray(d.projetos.neg)) throw new Error('Detalhes de outro parlamentar ou versão');
  for (const law of [...d.projetos.aprov, ...d.projetos.neg]) {
    if (typeof law.num !== 'string' || typeof law.titulo !== 'string' || typeof law.url !== 'string') throw new Error('Projeto inválido');
    const url = new URL(law.url);
    if (url.protocol !== 'https:' || !(url.hostname.endsWith('.camara.leg.br') || url.hostname === 'camara.leg.br' || url.hostname.endsWith('.senado.leg.br'))) throw new Error('Fonte de projeto não oficial');
  }
  if (d.historicosLegislativos !== undefined) {
    if (!Array.isArray(d.historicosLegislativos)) throw new Error('Histórico inválido');
    for (const h of d.historicosLegislativos) {
      if (!['senado','camara'].includes(h.casa) || h.cobertura !== 'completa' || typeof h.idParlamentar !== 'string' || !h.idParlamentar || typeof h.criterio !== 'string' || !h.criterio || !Number.isFinite(Date.parse(h.periodoInicio)) || !Number.isFinite(Date.parse(h.periodoFim)) || h.periodoInicio > h.periodoFim || !Number.isFinite(Date.parse(h.coletadoEm)) || !Array.isArray(h.fontes) || !h.fontes.length || !Array.isArray(h.projetos) || h.total !== h.projetos.length) throw new Error('Cobertura do histórico inválida');
      if (member.vinculos?.[h.casa] !== h.idParlamentar && !(h.casa === 'senado' && member.ini === 2023 && member.fonte?.id === h.idParlamentar)) throw new Error('Histórico sem vínculo confirmado');
      for (const source of h.fontes) {
        const url = new URL(source);
        if (url.protocol !== 'https:' || !(url.hostname.endsWith('.camara.leg.br') || url.hostname.endsWith('.senado.leg.br'))) throw new Error('Fonte de histórico inválida');
      }
      const ids = new Set<string>();
      for (const p of h.projetos) {
        if (typeof p.id !== 'string' || !p.id || ids.has(p.id) || typeof p.num !== 'string' || typeof p.titulo !== 'string' || typeof p.situacao !== 'string' || !['aprov','neg','outros'].includes(p.classificacao) || !Number.isFinite(Date.parse(p.dataApresentacao)) || p.dataApresentacao < h.periodoInicio || p.dataApresentacao > h.periodoFim || (p.classificacao === 'aprov' && !p.norma)) throw new Error('Projeto do histórico inválido');
        ids.add(p.id);
        if (p.observacaoResultado !== undefined && (typeof p.observacaoResultado !== 'string' || !p.resultadoVerificadoEm || !Number.isFinite(Date.parse(p.resultadoVerificadoEm)) || p.fonteVerificacao !== `https://dadosabertos.camara.leg.br/api/v2/proposicoes/${p.id}`)) throw new Error('Verificação de resultado inválida');
        if (p.fonteNorma !== undefined) {
          if (h.casa !== 'camara' || p.classificacao !== 'aprov' || !p.norma || !p.normaVerificadaEm || !Number.isFinite(Date.parse(p.normaVerificadaEm)) || ![`https://dadosabertos.camara.leg.br/api/v2/proposicoes/${p.id}`,`https://dadosabertos.camara.leg.br/api/v2/proposicoes/${p.id}/tramitacoes`].includes(p.fonteNorma)) throw new Error('Confirmação de norma inválida');
        }
        const url = new URL(p.url);
        if (url.protocol !== 'https:' || !(url.hostname.endsWith('.camara.leg.br') || url.hostname.endsWith('.senado.leg.br'))) throw new Error('Fonte de projeto inválida');
      }
      if (h.aprov !== h.projetos.filter(p => p.classificacao === 'aprov').length || h.neg !== h.projetos.filter(p => p.classificacao === 'neg').length) throw new Error('Contagem do histórico inconsistente');
    }
  }
  if (d.despesasHistoricas !== undefined) {
    if (!Array.isArray(d.despesasHistoricas)) throw new Error('Despesas inválidas');
    for (const h of d.despesasHistoricas) {
      if (!['camara','senado'].includes(h.casa) || h.cobertura !== 'registros-disponiveis' || !Number.isSafeInteger(h.totalCentavos) || !Number.isSafeInteger(h.registros) || h.registros <= 0 || !h.criterio?.trim() || !Number.isFinite(Date.parse(h.coletadoEm)) || !Number.isFinite(Date.parse(h.periodoInicio)) || !Number.isFinite(Date.parse(h.periodoFim)) || h.periodoInicio > h.periodoFim || !Array.isArray(h.fontes) || !h.fontes.length || !Array.isArray(h.meses) || !h.meses.length || !Array.isArray(h.categorias) || !h.categorias.length || (h.restituicoesCentavos !== null && (!Number.isSafeInteger(h.restituicoesCentavos) || h.restituicoesCentavos < 0))) throw new Error('Cobertura das despesas inválida');
      if (member.vinculos?.[h.casa] !== h.idParlamentar && !(h.casa === 'senado' && member.ini === 2023 && member.fonte?.id === h.idParlamentar)) throw new Error('Despesas sem vínculo confirmado');
      for (const source of h.fontes) {
        const url = new URL(source);
        if (url.protocol !== 'https:' || !(h.casa === 'camara' ? url.hostname === 'www.camara.leg.br' : url.hostname === 'adm.senado.gov.br')) throw new Error('Fonte de despesas inválida');
      }
      const seen = new Set<string>();
      for (const month of h.meses) {
        if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month.competencia) || month.competencia < h.periodoInicio.slice(0,7) || month.competencia > h.periodoFim.slice(0,7) || seen.has(month.competencia) || !Number.isSafeInteger(month.totalCentavos)) throw new Error('Competência inválida');
        seen.add(month.competencia);
      }
      for (const category of h.categorias) if (!category.nome?.trim() || !Number.isSafeInteger(category.totalCentavos)) throw new Error('Categoria inválida');
      if (h.meses.reduce((sum,m) => sum + m.totalCentavos,0) !== h.totalCentavos || h.categorias.reduce((sum,c) => sum + c.totalCentavos,0) !== h.totalCentavos) throw new Error('Totais de despesas inconsistentes');
    }
  }
  if(d.licencasSenado!==undefined){
    if(!Array.isArray(d.licencasSenado))throw new Error('Detalhes de licenças inválidos');
    for(const h of d.licencasSenado){
      validateSenateLicenses(h,member);
      if(!Array.isArray(h.licencas) || h.licencas.length!==h.registros)throw new Error('Contagem de licenças inválida');
      const ids=new Set<string>();
      const validDate=(v:string|null)=>v===null || (typeof v==='string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && Number.isFinite(Date.parse(v)));
      for(const r of h.licencas){
        const beginning=r.inicio ?? r.inicioPrevisto;const finish=r.inicio?r.fim:r.fimPrevisto;
        if(!/^\d+$/.test(r.id) || ids.has(r.id) || !r.tipo?.trim() || !r.descricao?.trim() || ![r.inicio,r.fim,r.inicioPrevisto,r.fimPrevisto].every(validDate) || (!r.inicio && !r.inicioPrevisto) || (r.fim && (!r.inicio || r.fim<r.inicio)) || (r.fimPrevisto && (!r.inicioPrevisto || r.fimPrevisto<r.inicioPrevisto)) || beginning! > h.periodoFim || (finish && finish < h.periodoInicio))throw new Error('Registro de licença inválido');
        ids.add(r.id);
      }
    }
  }
  if((d.comparecimentosSenado?.length??0)!==(member.resumosHistoricos?.comparecimentosSenado?.length??0))throw new Error('Recortes Senado incompletos');
  if(d.comparecimentosSenado!==undefined){
    if(!Array.isArray(d.comparecimentosSenado))throw new Error('Detalhes do recorte Senado inválidos');
    const periods=new Set<string>();
    for(const h of d.comparecimentosSenado){
      validateSenateSessions(h,member);
      if(periods.has(h.periodoInicio) || !Array.isArray(h.sessoes) || h.sessoes.length!==1)throw new Error('Sessão duplicada ou contagem inválida');periods.add(h.periodoInicio);
      const r=h.sessoes[0];const cut=senateRecorte(h)!;
      if(r.id!==cut.id || r.numero!==cut.numero || typeof r.comparecimentoRegistrado!=='boolean' || Number(r.comparecimentoRegistrado)!==h.comparecimentosRegistrados || !Array.isArray(r.exercicios) || !Array.isArray(r.votacoes) || r.votacoes.length!==cut.votacoes.length)throw new Error('Evidência de sessão inválida');
      if(r.comparecimentoRegistrado ? (!r.registroDiario?.nomeDiario?.trim() || !STATES.some(s=>s.uf===r.registroDiario?.uf) || !cut.paginas.includes(r.registroDiario.pagina) || (r.registroDiario.votoRegistrado!==undefined && typeof r.registroDiario.votoRegistrado!=='boolean')) : r.registroDiario!==null)throw new Error('Registro DSF inválido');
      if(!cut.votacoes.length && r.registroDiario?.votoRegistrado)throw new Error('Voto no Diário de sessão sem nominal');
      for(const e of r.exercicios)if(!/^\d{4}-\d{2}-\d{2}$/.test(e.inicio) || !/^\d{4}-\d{2}-\d{2}$/.test(e.fim) || !Number.isFinite(Date.parse(e.inicio)) || !Number.isFinite(Date.parse(e.fim)) || e.inicio>e.fim)throw new Error('Exercício inválido');
      const ids=new Set<string>();
      for(const v of r.votacoes){
        const spec=cut.votacoes.find(s=>s.id===v.id);
        const secretRegisters:Record<string,string>={'Votou':'Votou','AP':'Atividade parlamentar','P-NRV':'Presente – Não registrou voto','Presidente (art. 51 RISF)':'Presidiu votação'};
        if(!spec || ids.has(v.id) || v.data!==spec.data || v.materia!==spec.materia || v.secreta!==spec.secreta || !v.descricao?.trim() || (v.registro!==null && typeof v.registro!=='string') || !Array.isArray(v.licencasEfetivas) || new Set(v.licencasEfetivas).size!==v.licencasEfetivas.length || (v.secreta && (v.registro===null?v.descricao!=='Sem registro individual':secretRegisters[v.registro]!==v.descricao)))throw new Error('Votação inválida ou voto secreto exposto');
        ids.add(v.id);
        for(const id of v.licencasEfetivas)if(!d.licencasSenado?.some(h=>h.licencas.some(l=>l.id===id && l.inicio && l.fim && l.inicio<=v.data && l.fim>=v.data)))throw new Error('Licença sem período efetivo confirmado');
        const active=r.exercicios.some(e=>e.inicio<=v.data && e.fim>=v.data);
        const expected=!active?'fora-exercicio':['Votou','Sim','Não','Abstenção','Presidente (art. 51 RISF)'].includes(v.registro!)?'participou':v.registro==='AP' || v.licencasEfetivas.length?'justificativa-registrada':'pendente';
        if(v.classificacao!==expected)throw new Error('Classificação da votação sem evidência');
      }
      const states=r.votacoes.map(v=>v.classificacao);
      const outside=states.length?states.every(s=>s==='fora-exercicio'):!r.exercicios.some(e=>e.inicio<=h.periodoFim && e.fim>=h.periodoInicio);
      const status=outside?'fora-exercicio':r.comparecimentoRegistrado && !states.length?'comparecimento-conferido':r.comparecimentoRegistrado && states.includes('participou') && states.every(s=>['participou','fora-exercicio'].includes(s))?'participacao-conferida':states.includes('justificativa-registrada') && states.every(s=>['participou','justificativa-registrada','fora-exercicio'].includes(s))?'justificativa-registrada':'pendente';
      if(r.classificacao!==status || (r.comparecimentoRegistrado && status==='fora-exercicio') || (h.comparecimentosConferidos??0)!==Number(status==='comparecimento-conferido') || h.participacoesConferidas!==Number(status==='participacao-conferida') || h.justificativasRegistradas!==Number(status==='justificativa-registrada') || h.pendentes!==Number(status==='pendente') || h.foraExercicio!==Number(status==='fora-exercicio'))throw new Error('Contagem do recorte sem evidência');
      const summary=member.resumosHistoricos?.comparecimentosSenado?.find(s=>s.periodoInicio===h.periodoInicio);
      if(!summary || ['comparecimentosRegistrados','comparecimentosConferidos','participacoesConferidas','justificativasRegistradas','pendentes','foraExercicio'].some(k=>summary[k as keyof typeof summary]!==h[k as keyof typeof h]))throw new Error('Detalhe diverge do resumo Senado');
    }
  }
  if(d.presencasHistoricas!==undefined){
    if(!Array.isArray(d.presencasHistoricas))throw new Error('Detalhes de presença inválidos');
    for(const h of d.presencasHistoricas){
      validateAttendance(h,member);
      if(!Array.isArray(h.dias) || h.dias.length!==h.totalDias)throw new Error('Contagem de dias inválida');
      const dates=new Set<string>();
      for(const day of h.dias){if(!/^\d{4}-\d{2}-\d{2}$/.test(day.data) || !Number.isFinite(Date.parse(day.data)) || day.data<h.periodoInicio || day.data>h.periodoFim || dates.has(day.data) || !day.situacao?.trim() || !['presenca','justificada','naoJustificada','outros'].includes(day.classificacao))throw new Error('Dia de presença inválido');dates.add(day.data);}
      for(const status of ['presenca','justificada','naoJustificada','outros'] as const)if(h.dias.filter(day=>day.classificacao===status).length!==h[status])throw new Error('Classificação dos dias inconsistente');
    }
  }
  return d;
}
