import stateData from './states.json';
// Dados FICTÍCIOS para o protótipo. Troque `buildData()` por um fetch de `public/data.json`
// gerado pelo script de ingestão (APIs do Senado/Câmara) mantendo o tipo `Member`.

export type Casa = 'senado' | 'camara';
export interface HistoricalBase {
  casa: Casa; idParlamentar: string; periodoInicio: string; periodoFim: string;
  coletadoEm: string; criterio: string; fontes: string[];
}
export interface HistoricalSummary {
  legislativos: (HistoricalBase & {total: number; aprov: number; neg: number; pendentes: number})[];
  despesas: (HistoricalBase & {totalCentavos: number; registros: number; cobertura: 'registros-disponiveis'})[];
  presencas?: AttendanceSummary[];
  licencasSenado?: SenateLicenseSummary[];
  comparecimentosSenado?: SenateSessionSummary[];
}
export interface SenateCoverage {periodoInicio:string;periodoFim:string;sessoesIdentificadas:number;sessoesConferidas:number;coletadoEm:string;fontes:string[];criterio:string}
export interface SenateLicenseSummary extends HistoricalBase {casa:'senado';cobertura:'registros-disponiveis';registros:number}
export interface SenateLicenseHistory extends SenateLicenseSummary {licencas:{id:string;tipo:string;descricao:string;inicio:string|null;fim:string|null;inicioPrevisto:string|null;fimPrevisto:string|null}[]}
export type SenateSessionStatus = 'comparecimento-conferido'|'participacao-conferida'|'justificativa-registrada'|'pendente'|'fora-exercicio';
export interface SenateSessionSummary extends HistoricalBase {
  casa:'senado'; unidade:'sessoes'; cobertura:'recorte-conferido'; totalSessoes:number;
  comparecimentosRegistrados:number; comparecimentosConferidos?:number; participacoesConferidas:number; justificativasRegistradas:number;
  pendentes:number; foraExercicio:number; naoJustificada:null;
}
export interface SenateSessionHistory extends SenateSessionSummary {sessoes:{
  id:string; numero:number; comparecimentoRegistrado:boolean;
  registroDiario:{nomeDiario:string;uf:string;pagina:number;votoRegistrado?:boolean}|null;
  classificacao:SenateSessionStatus; exercicios:{inicio:string;fim:string}[];
  votacoes:{id:string;data:string;materia:string;secreta:boolean;registro:string|null;descricao:string;classificacao:'participou'|'justificativa-registrada'|'pendente'|'fora-exercicio';licencasEfetivas:string[]}[];
}[]}
export interface AttendanceSummary extends HistoricalBase {
  casa: 'camara'; unidade: 'dias'; cobertura: 'registros-disponiveis'; totalDias: number;
  presenca: number; justificada: number; naoJustificada: number; outros: number;
}
export interface AttendanceHistory extends AttendanceSummary {dias: {data:string;situacao:string;classificacao:'presenca'|'justificada'|'naoJustificada'|'outros'}[]}
export interface SubsidyReference {valorCentavos:number;inicioVigencia:string;verificadoEm:string;fontes:string[];norma:string;tipo:'referencia-bruta-mensal'}
export interface ExpenseHistory {
  casa: Casa; idParlamentar: string; periodoInicio: string; periodoFim: string; coletadoEm: string;
  cobertura: 'registros-disponiveis'; criterio: string; fontes: string[];
  totalCentavos: number; restituicoesCentavos: number | null; registros: number;
  meses: {competencia: string; totalCentavos: number}[];
  categorias: {nome: string; totalCentavos: number}[];
}
export interface IndicatorEvidence {
  periodoInicio: string; periodoFim: string; casa: Casa; unidade: 'quantidade' | 'BRL';
  cobertura: 'completa'; fonteUrl: string; coletadoEm: string; criterio: string;
}
export interface LegislativeProject extends Law {
  id: string; situacao: string; dataApresentacao: string; classificacao: 'aprov' | 'neg' | 'outros'; norma: string | null;
  fonteNorma?: string; normaVerificadaEm?: string;
  observacaoResultado?: string; fonteVerificacao?: string; resultadoVerificadoEm?: string;
}
export interface LegislativeHistory {
  casa: Casa; idParlamentar: string; periodoInicio: string; periodoFim: string; coletadoEm: string;
  cobertura: 'completa'; criterio: string; fontes: string[]; total: number; aprov: number; neg: number;
  projetos: LegislativeProject[];
}
export interface Member {
  id: string; casa: Casa; casaNome: string; nome: string; uf: string; reg: string;
  partido: string; cor: string; ini: number; fim: number; mandato: string;
  aprov: number | null; neg: number | null; faltas: number | null; salario: number | null; custo: number | null;
  fonte?: { nome: string; url: string; coletadoEm: string; geradoEm: string; id: string };
  situacao?: string; partidoEleicao?: string | null; partidoAtual?: string | null;
  participacao?: string; titular?: string | null; historico?: string;
  vinculos?: Partial<Record<Casa,string>>;
  pessoaId?: string; mandatoId?: string; identidade?: string; detalhesUrl?: string;
  indicadores?: Partial<Record<'aprov' | 'neg' | 'faltas' | 'salario' | 'custo', IndicatorEvidence>>;
  resumosHistoricos?: HistoricalSummary;
  subsidioReferencia?: SubsidyReference;
  foto?: {arquivoLocal?: string; imagemColetadaEm?: string; url: string; fonteUrl: string; casa: Casa; idParlamentar: string; coletadoEm: string};
  projetos?: { aprov: Law[]; neg: Law[] };
}
export interface State { uf: string; nome: string; reg: string; deps: number; c: number; r: number }

export const REG: Record<string, string> = { Norte: '#9FD3C7', Nordeste: '#F6C88F', 'Centro-Oeste': '#E8D27A', Sudeste: '#A9C4EB', Sul: '#C9B6E4' };

// [uf, nome, região, deputados, col, row] — col/row = grade do mobile
export const STATES: State[] = stateData;

export const COR: Record<string, string> = { PL:'#1B1464', PT:'#D12A2F', MDB:'#F2A900', PP:'#0E3D66', 'União':'#F2E200', Republicanos:'#0065B3', PSD:'#2E7D32', PSB:'#F08A24', Novo:'#E8662A', Podemos:'#2DB34A', PSDB:'#1F6F99', PDT:'#9E1B24', Rede:'#3A9E8C', 'Sem partido':'#222222', PSOL:'#B5179E', Avante:'#5E60CE', Solidariedade:'#FF7F11', PCdoB:'#7A0A0A', PV:'#6A994E', Cidadania:'#C08497' };
// Bancadas do protótipo: usadas somente no modo explícito ?demo=1, sem validação oficial.
export const SEN: [string, number][] = [['PL',28],['PT',9],['MDB',8],['PP',6],['União',6],['Republicanos',5],['PSD',5],['PSB',4],['Novo',3],['Podemos',2],['PSDB',2],['PDT',1],['Rede',1],['Sem partido',1]];
export const CAM: [string, number][] = [['PL',99],['PT',68],['União',59],['PP',50],['PSD',45],['MDB',44],['Republicanos',44],['PDT',17],['Podemos',15],['PSB',14],['PSOL',13],['PSDB',13],['Avante',7],['PCdoB',7],['Novo',5],['Solidariedade',5],['PV',4],['Cidadania',4]];

export function buildData() {
  let seed = 2026;
  const rnd = () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const int = (a: number, b: number) => a + Math.floor(rnd() * (b - a + 1));
  const shuffle = <T,>(a: T[]) => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const pool = (list: [string, number][]) => shuffle(list.flatMap(([p, n]) => Array<string>(n).fill(p)));
  const mk = (casa: Casa, nome: string, st: State, partido: string, ini: number, fim: number): Member => ({
    id: `${casa}-${st.uf}-${nome}`, casa, casaNome: casa === 'senado' ? 'Senado' : 'Câmara', nome, uf: st.uf, reg: st.reg, partido, cor: COR[partido],
    ini, fim, mandato: `${ini}–${fim}`, aprov: int(0, casa === 'senado' ? 24 : 14), neg: int(0, 12), faltas: int(0, 18), salario: 46366.19,
    custo: (casa === 'senado' ? int(1900, 3400) : int(1300, 2400)) * 1000,
  });
  const senPool = pool(SEN); senPool.splice(senPool.indexOf('PL'), 1); senPool.splice(senPool.indexOf('PL'), 1);
  const camPool = pool(CAM);
  const senado: Member[] = [], camara: Member[] = [];
  for (const st of STATES) {
    for (let k = 0; k < 3; k++) {
      const sc = st.uf === 'SC' && k < 2;
      const nome = sc ? (k === 0 ? 'Carol de Toni' : 'Carlos Bolsonaro') : `Senador(a) ${k + 1} · ${st.uf}`;
      senado.push(mk('senado', nome, st, sc ? 'PL' : senPool.pop()!, k < 2 ? 2027 : 2023, k < 2 ? 2035 : 2031));
    }
    for (let k = 0; k < st.deps; k++) camara.push(mk('camara', `Deputado(a) ${k + 1} · ${st.uf}`, st, camPool.pop()!, 2027, 2031));
  }
  return { senado, camara };
}

export interface Law { num: string; titulo: string; url: string }
// ponytail: leis fictícias derivadas do id; substituir por proposições reais da API.
export function laws(m: Member, status: 'aprov' | 'neg'): Law[] {
  if (m.fonte) return m.projetos?.[status] ?? [];
  let h = 0; for (const ch of m.id + status) h = (h * 31 + ch.charCodeAt(0)) | 0;
  const T = ['Altera o Código de Trânsito para ampliar a fiscalização eletrônica', 'Institui programa de conectividade em escolas públicas', 'Dispõe sobre transparência em contratos de obras públicas', 'Cria incentivo fiscal à agricultura familiar', 'Regulamenta o uso de inteligência artificial no setor público', 'Amplia a licença-paternidade', 'Estabelece política nacional de segurança hídrica', 'Altera regras do Fundo de Participação dos Municípios', 'Dispõe sobre proteção de dados de crianças online', 'Cria marco legal para energia eólica offshore', 'Institui dia nacional de combate à desinformação', 'Altera a Lei de Licitações para pequenas empresas'];
  const url = m.casa === 'senado' ? 'https://www25.senado.leg.br/web/atividade/materias' : 'https://www.camara.leg.br/busca-portal/proposicoes/pesquisa-simplificada';
  const n = (status === 'aprov' ? m.aprov : m.neg) ?? 0, out: Law[] = [];
  for (let i = 0; i < n; i++) { h = (h * 1103515245 + 12345) | 0; const a = Math.abs(h); out.push({ num: `PL ${100 + (a % 4800)}/${m.ini + (a % 4)}`, titulo: T[a % T.length], url }); }
  return out;
}

export interface Seat { x: number; y: number; m: Member }
export function hemicycle(members: Member[], rows: number, R: number, r0: number, d: number) {
  const n = members.length, radii = Array.from({ length: rows }, (_, i) => r0 + ((R - r0) * i) / (rows - 1));
  const tot = radii.reduce((a, b) => a + b, 0);
  const counts = radii.map((r) => Math.round((n * r) / tot));
  counts[rows - 1] += n - counts.reduce((a, b) => a + b, 0);
  const pts: { t: number; r: number; x: number; y: number }[] = [];
  radii.forEach((r, i) => { const c = counts[i]; for (let j = 0; j < c; j++) { const t = Math.PI - Math.PI * (c === 1 ? 0.5 : j / (c - 1)); pts.push({ t, r, x: R + d / 2 + r * Math.cos(t), y: R + d / 2 - r * Math.sin(t) }); } });
  pts.sort((a, b) => b.t - a.t || a.r - b.r);
  return { seats: pts.map((p, i): Seat => ({ x: p.x, y: p.y, m: members[i] })), W: 2 * R + d, H: R + d, d };
}

export const brl = (v: number | null) => v === null ? 'Indisponível' : v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
export const pct = (a: number | null, b: number | null) => a === null || b === null ? 'Indisponível' : a + b ? Math.round((100 * a) / (a + b)) + '%' : 'Indisponível';
