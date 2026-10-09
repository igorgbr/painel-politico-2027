import { useEffect, useMemo, useState } from 'react';
import geo from './geo.json';
import {aggregateHistory, missingMetric, moneyCents, resultHistory, attendanceHistory, senateSessionLabel} from './history';
import { STATES, REG, COR, buildData, laws, hemicycle, brl, pct, type Member, type Casa, type LegislativeHistory } from './data';

import { parseDataset, parseMemberDetails, partyCounts, type Dataset, type MemberDetails } from './dataset';

const demo = new URLSearchParams(window.location.search).get('demo') === '1';
const metric = (n: number | null) => n === null ? 'Indisponível' : n;
const date = (value: string) => new Date(value).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' });

type Tab = 'mapa' | Casa | 'dados';
const GEO = geo as unknown as Record<string, [string, number, number]>;
const SMALL = new Set(['DF', 'RJ', 'ES', 'SE', 'AL', 'PE', 'PB', 'RN']);

export default function App() {
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (demo) return;
    const controller = new AbortController();
    setError('');
    fetch(`${import.meta.env.BASE_URL}data.json`, { signal: controller.signal, cache: 'no-cache' })
      .then(response => { if (!response.ok) throw new Error('Não foi possível carregar a composição oficial.'); return response.json(); })
      .then(value => setDataset(parseDataset(value)))
      .catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Falha ao carregar dados oficiais.'); });
    return () => controller.abort();
  }, [attempt]);
  const demoData = useMemo(() => demo ? buildData() : null, []);
  const D = useMemo(() => {
    const d = demoData ?? dataset ?? { senado: [], camara: [] };
    const parties = { senado: partyCounts(d.senado), camara: partyCounts(d.camara) };
    const order = (list: Member[], counts: [string, number][]) => counts.flatMap(([p]) => list.filter(m => m.partido === p));
    return { ...d, parties, hemi: { senado: hemicycle(order(d.senado, parties.senado), 5, 290, 110, 32), camara: hemicycle(order(d.camara, parties.camara), 12, 330, 100, 12) } };
  }, [dataset, demoData]);
  const ready = demo || dataset !== null;
  const provenance = demo ? 'Demonstração — nomes, bancadas e indicadores ilustrativos.' : dataset ? `Composição para 2027 · coleta ${date(dataset.atualizadoEm)} · TSE: eleitos em 2026; Senado: mandatos até 2031 e ocupantes na coleta. Histórico e indicadores conforme cobertura e período de cada parlamentar.` : 'Carregando composição oficial para 2027…';
  const [tab, setTab] = useState<Tab>('mapa');
  const [uf, setUf] = useState('SC');
  const [sel, setSel] = useState<Record<Casa, { party: string | null; member: string | null }>>({ senado: { party: null, member: null }, camara: { party: null, member: null } });

  const go = (m: Member) => { setSel((s) => ({ ...s, [m.casa]: { party: m.partido, member: m.id } })); setTab(m.casa); };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header className="noprint" style={{ background: '#fff', borderBottom: '1px solid #E1E1DA', padding: '14px 24px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>Painel Político <span style={{ color: '#1F4E8C' }}>2027</span></h1>
          <span className="muted" style={{ fontSize: 13 }}>Eleitos em 2026 e mandatos em continuidade</span>
        </div>
        <nav aria-label="Navegação principal" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {([['mapa', 'Mapa'], ['senado', 'Senado'], ['camara', 'Câmara'], ['dados', 'Dados']] as [Tab, string][]).map(([id, l]) => (
            <button key={id} onClick={() => setTab(id)} aria-current={tab === id ? 'page' : undefined} className="btn" style={tab === id ? undefined : { background: '#fff', color: '#16181D' }}>{l}</button>
          ))}
        </nav>
      </header>
      <div className="noprint" style={{ background: '#FFF4D6', color: '#5A4300', fontSize: 12, padding: '8px 24px' }}>
        {provenance}
      </div>
      <main style={{ flex: 1, width: '100%', maxWidth: 1440, margin: '0 auto', padding: 24, boxSizing: 'border-box' }}>
        {!ready && <section className="card" aria-live="polite">{error ? <><h2>Dados oficiais indisponíveis</h2><p>{error}</p><button className="btn" onClick={() => setAttempt(n => n + 1)}>Tentar novamente</button></> : <p>Carregando dados oficiais…</p>}</section>}
        {ready && <>
        {tab === 'mapa' && <MapView D={D} uf={uf} setUf={setUf} go={go} />}
        {(tab === 'senado' || tab === 'camara') && (
          <House key={tab} casa={tab} list={D[tab]} hemi={D.hemi[tab]} parties={D.parties[tab]}
            version={dataset?.versao} sel={sel[tab]} setSel={(v) => setSel((s) => ({ ...s, [tab]: v }))} />
        )}
        <div hidden={tab !== 'dados'}><Dados all={[...D.senado, ...D.camara]} provenance={provenance} coberturaSenado={dataset?.coberturaSenado} /></div>
        </>}
      </main>
    </div>
  );
}

function Portrait({ m, large = false }: {m: Member; large?: boolean}) {
  const [failed, setFailed] = useState<string[]>([]);
  const [loaded, setLoaded] = useState('');
  const local = m.foto?.arquivoLocal ? import.meta.env.BASE_URL + m.foto.arquivoLocal : undefined;
  const url = [local, m.foto?.url].find((candidate): candidate is string => !!candidate && !failed.includes(candidate));
  useEffect(() => {
    if (!large || !url || loaded === url) return;
    const timer = window.setTimeout(() => setFailed(previous => [...previous, url]), 12000);
    return () => window.clearTimeout(timer);
  }, [url, loaded, large]);
  if (!url) return null;
  return <img className={`portrait${large ? ' portrait-large' : ''}`} src={url} alt="" width={large ? 64 : 32} height={large ? 64 : 32} loading={large ? 'eager' : 'lazy'} decoding="async" referrerPolicy="no-referrer" style={loaded === url ? undefined : {background: 'transparent'}} onLoad={() => setLoaded(url)} onError={() => setFailed(previous => [...previous, url])} />;
}

function Row({ m, onClick, right, active }: { m: Member; onClick: () => void; right: string; active?: boolean }) {
  return (
    <button className="row" onClick={onClick} style={active ? { background: '#EAF0F8' } : undefined}>
      <span className="dot" style={{ background: m.cor }} />
      <Portrait m={m} />
      <span style={{ flex: 1 }}>{m.nome}</span>
      <span className="muted" style={{ fontSize: 13 }}>{right}</span>
    </button>
  );
}

function MapView({ D, uf, setUf, go }: { D: { senado: Member[]; camara: Member[] }; uf: string; setUf: (u: string) => void; go: (m: Member) => void }) {
  const cur = STATES.find((s) => s.uf === uf)!;
  const fill = (s: typeof cur) => (s.uf === uf ? '#16181D' : REG[s.reg]);
  const ink = (s: typeof cur) => (s.uf === uf ? '#fff' : '#16181D');
  const deps = D.camara.filter((m) => m.uf === uf);
  const sorted = [...STATES].sort((a, b) => a.nome.localeCompare(b.nome));
  return (
    <div className="wrap">
      <section className="card" style={{ flex: '1 1 600px', minWidth: 0 }}>
        <h2 style={{ fontSize: 20 }}>Mapa político do Brasil</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-end', gap: 12, margin: '6px 0 16px' }}>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>Clique em um estado para ver senadores e deputados federais eleitos.</p>
          <label>Estado
            <select value={uf} onChange={(e) => setUf(e.target.value)}>{sorted.map((s) => <option key={s.uf} value={s.uf}>{s.nome}</option>)}</select>
          </label>
        </div>
        <div className="mob" style={{ gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', gap: 5, maxWidth: 420, margin: '0 auto' }}>
          {STATES.map((s) => (
            <button key={s.uf} className="gtile" aria-label={s.nome} aria-pressed={s.uf === uf} onClick={() => setUf(s.uf)}
              style={{ gridColumn: s.c + 1, gridRow: s.r + 1, background: fill(s), color: ink(s) }}>{s.uf}</button>
          ))}
        </div>
        <div className="desk" style={{ position: 'relative', width: '100%', maxWidth: 640, margin: '0 auto' }}>
          <svg viewBox="0 0 613 639" role="group" aria-label="Mapa do Brasil por estado" style={{ display: 'block', width: '100%', height: 'auto' }}>
            {STATES.map((s) => (
              <path key={s.uf} d={GEO[s.uf][0]} fill={fill(s)} stroke="#fff" strokeWidth={1.2} role="button" tabIndex={0} aria-label={s.nome} aria-pressed={s.uf === uf} style={{ cursor: 'pointer' }} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setUf(s.uf); } }} onClick={() => setUf(s.uf)}><title>{s.nome}</title></path>
            ))}
            {STATES.map((s) => (
              <text key={s.uf} x={GEO[s.uf][1]} y={GEO[s.uf][2]} textAnchor="middle" dominantBaseline="middle" fill={ink(s)}
                fontSize={SMALL.has(s.uf) ? 9 : 14} fontFamily="Archivo, sans-serif" fontWeight={700} style={{ pointerEvents: 'none' }}>{s.uf}</text>
            ))}
          </svg>
          <p className="muted" style={{ fontSize: 11, textAlign: 'center', margin: '4px 0 0' }}>Mapa: svg-maps/brazil (CC BY 4.0)</p>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 16, fontSize: 13 }}>
          {Object.entries(REG).map(([n, c]) => <span key={n} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><span className="dot" style={{ background: c }} />{n}</span>)}
        </div>
      </section>
      <aside className="card" style={{ flex: '1 1 420px', minWidth: 0 }}>
        <div className="muted" style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em' }}>{cur.reg}</div>
        <h2 style={{ fontSize: 28, marginTop: 4 }}>{cur.nome}</h2>
        <h3 style={{ fontSize: 15, margin: '20px 0 6px' }}>Senadores ({D.senado.filter(m => m.uf === uf).length})</h3>
        {D.senado.filter((m) => m.uf === uf).map((m) => <Row key={m.id} m={m} onClick={() => go(m)} right={`${m.partido} · ${m.mandato}`} />)}
        <h3 style={{ fontSize: 15, margin: '20px 0 6px' }}>Deputados federais ({deps.length})</h3>
        <div style={{ maxHeight: 420, overflowY: 'auto', border: '1px solid #EEEEE8', borderRadius: 8 }}>
          {deps.map((m) => <Row key={m.id} m={m} onClick={() => go(m)} right={m.partido} />)}
        </div>
      </aside>
    </div>
  );
}

const lsFor = (m: Member, d: MemberDetails | null, key: 'aprov'|'neg') => (d?.projetos[key] ?? laws(m,key)).length > 0;

type Sel = { party: string | null; member: string | null };
function House({ casa, list, hemi, parties, sel, setSel, version }: { casa: Casa; list: Member[]; hemi: ReturnType<typeof hemicycle>; parties: [string, number][]; version?: string; sel: Sel; setSel: (s: Sel) => void }) {
  const [lawTab, setLawTab] = useState<'aprov' | 'neg' | null>(null);
  const pick = (s: Sel) => { setSel(s); setLawTab(null); };
  const members = sel.party ? list.filter((m) => m.partido === sel.party).sort((a, b) => a.uf.localeCompare(b.uf)) : [];
  const mem = list.find((m) => m.id === sel.member);
  const hist = mem ? resultHistory(mem) : undefined;
  const attendance = mem ? attendanceHistory(mem) : undefined;
  const [details, setDetails] = useState<MemberDetails | null>(null);
  const [detailsError, setDetailsError] = useState(false);
  useEffect(() => {
    setDetails(null); setDetailsError(false);
    if (!mem?.detalhesUrl || !version) return;
    const controller = new AbortController();
    fetch(`${import.meta.env.BASE_URL}${mem.detalhesUrl}`, {signal: controller.signal})
      .then(r => { if (!r.ok) throw new Error('Detalhes indisponíveis'); return r.json(); })
      .then(d => setDetails(parseMemberDetails(d, mem, version)))
      .catch(() => { if (!controller.signal.aborted) setDetailsError(true); });
    return () => controller.abort();
  }, [mem, version]);
  const currentDetails = details?.mandatoId === mem?.mandatoId ? details : null;
  const ls = mem && lawTab ? currentDetails?.projetos[lawTab] ?? laws(mem, lawTab) : [];
  return (
    <div className="wrap">
      <section className="card" style={{ flex: '2 1 640px', minWidth: 0 }}>
        <h2 style={{ fontSize: 20 }}>{casa === 'senado' ? 'Cadeiras do Senado Federal — 2027' : 'Cadeiras da Câmara dos Deputados — 2027'}</h2>
        <p className="muted" style={{ margin: '6px 0 16px', fontSize: 14 }}>{list.length} cadeiras. Selecione um partido (ou uma cadeira) para listar os parlamentares.</p>
        <div style={{ overflowX: 'auto' }}>
          <div style={{ position: 'relative', width: '100%', maxWidth: hemi.W, aspectRatio: `${hemi.W} / ${hemi.H}`, margin: '0 auto' }}>
            {hemi.seats.map(({ x, y, m }) => (
              <button key={m.id} className="seat" aria-label={`${m.nome} (${m.partido}-${m.uf})`} onClick={() => pick({ party: m.partido, member: m.id })}
                style={{ left: `${100 * (x - hemi.d / 2) / hemi.W}%`, top: `${100 * (y - hemi.d / 2) / hemi.H}%`, width: `${100 * hemi.d / hemi.W}%`, height: `${100 * hemi.d / hemi.H}%`, background: m.cor,
                  opacity: !sel.party || m.partido === sel.party ? 1 : 0.18, outline: m.id === sel.member ? '3px solid #16181D' : undefined, outlineOffset: 2 }} />
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 20 }}>
          <button className="chip" aria-pressed={!sel.party} onClick={() => pick({ party: null, member: null })}>Todos</button>
          {parties.map(([p, n]) => (
            <button key={p} className="chip" onClick={() => pick({ party: p, member: null })} aria-pressed={p === sel.party}
              style={p === sel.party ? { borderColor: '#16181D', boxShadow: 'inset 0 0 0 1px #16181D' } : undefined}>
              <span className="dot" style={{ background: COR[p] ?? '#55585F' }} />{p} <span className="muted">{n}</span>
            </button>
          ))}
        </div>
      </section>
      <aside style={{ flex: '1 1 380px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card">
          <h3 style={{ fontSize: 16 }}>{sel.party ? `${sel.party} · ${members.length} parlamentares` : 'Parlamentares'}</h3>
          {!sel.party && <p className="muted" style={{ fontSize: 14, margin: '8px 0 0' }}>Nenhum partido selecionado.</p>}
          <div style={{ maxHeight: 300, overflowY: 'auto', marginTop: 8 }}>
            {members.map((m) => <Row key={m.id} m={m} right={m.uf} active={m.id === sel.member} onClick={() => pick({ party: m.partido, member: m.id })} />)}
          </div>
        </div>
        {mem && (
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="dot" style={{ background: mem.cor, width: 16, height: 16 }} />
              <span className="muted" style={{ fontSize: 13, fontWeight: 600 }}>{mem.partido} · {mem.uf}</span>
            </div>
            <div style={{display:'flex',alignItems:'center',gap:12,marginTop:8}}><Portrait m={mem} large /><h2 style={{fontSize:24,minWidth:0,overflowWrap:'anywhere'}}>{mem.nome}</h2></div>
            <p className="muted" style={{ margin: '4px 0 16px', fontSize: 14 }}>
              Mandato {mem.mandato} · {mem.fim - mem.ini} anos de mandato · {new Date().getFullYear() > mem.ini ? `${new Date().getFullYear() - mem.ini} cumpridos` : `inicia em fev/${mem.ini}`}
            </p>
            {mem.fonte && <div className="source-note"><p>{mem.situacao} · {mem.participacao}{mem.titular ? ` · Titular registrado na fonte: ${mem.titular}` : ''}</p><p>{mem.partidoEleicao ? `Partido na eleição: ${mem.partidoEleicao}` : `Partido no cadastro da coleta: ${mem.partidoAtual}`}</p><p aria-live="polite">{detailsError ? 'Histórico temporariamente indisponível.' : currentDetails?.historico ?? mem.historico}</p><a href={mem.fonte.url} target="_blank" rel="noopener noreferrer">Consultar fonte oficial</a><p>Fonte gerada em {date(mem.fonte.geradoEm)}</p>{Object.entries(mem.indicadores ?? {}).map(([key, evidence]) => <p key={key}>{({aprov:'Convertidos em lei',neg:'Rejeitados',faltas:'Faltas',salario:'Salário',custo:'Despesas'} as Record<string,string>)[key]}: {evidence.periodoInicio} a {evidence.periodoFim} · {evidence.criterio}</p>)}</div>}
            {currentDetails?.historicosLegislativos?.map(h => <HistoryPanel key={`${h.casa}-${h.periodoInicio}`} history={h} />)}
            {currentDetails?.despesasHistoricas?.map(h => <ExpensePanel key={`${h.casa}-${h.periodoInicio}`} history={h} />)}
            {currentDetails?.comparecimentosSenado?.slice().sort((a,b)=>b.periodoFim.localeCompare(a.periodoFim)).map(h => <SenateSessionsPanel key={h.periodoInicio} history={h} />)}
            {currentDetails?.licencasSenado?.map(h => <SenateLicensesPanel key={h.periodoInicio} history={h} />)}
            {currentDetails?.presencasHistoricas?.map(h => <AttendancePanel key={`${h.casa}-${h.periodoInicio}`} history={h} />)}
            {mem.subsidioReferencia && <div className="source-note"><p>Subsídio bruto de referência vigente na coleta: {moneyCents(mem.subsidioReferencia.valorCentavos)} por mês, desde {mem.subsidioReferencia.inicioVigencia}. Não comprova pagamento individual ou valor futuro.</p>{mem.subsidioReferencia.fontes.map(url => <p key={url}><a href={url} target="_blank" rel="noopener noreferrer">Fonte oficial do subsídio</a></p>)}<p>Verificado em {date(mem.subsidioReferencia.verificadoEm)}</p></div>}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
              <div className="stat"><b style={{ color: hist || mem.aprov !== null ? '#1A6B3C' : undefined }}>{hist?.aprov ?? mem.aprov ?? missingMetric(mem,'aprov')}</b><span>Conversões confirmadas · {mem.casaNome}{hist && <><br/>{hist.periodoInicio} a {hist.periodoFim}{hist.pendentes > 0 && <><br/>Contagem mínima; há resultados pendentes</>}</>}</span></div>
              <div className="stat"><b style={{ color: hist || mem.neg !== null ? '#A3261F' : undefined }}>{hist?.neg ?? mem.neg ?? missingMetric(mem,'neg')}</b><span>Rejeições confirmadas · {mem.casaNome}{hist && <><br/>{hist.periodoInicio} a {hist.periodoFim}{hist.pendentes > 0 && <><br/>Contagem mínima; há resultados pendentes</>}</>}</span></div>
              <div className="stat"><b>{mem.subsidioReferencia ? moneyCents(mem.subsidioReferencia.valorCentavos) : mem.salario === null ? missingMetric(mem,'salario') : brl(mem.salario)}</b><span>{mem.subsidioReferencia ? 'Subsídio bruto mensal de referência' : 'Pagamento mensal'}</span></div>
              <div className="stat"><b>{mem.custo === null ? missingMetric(mem,'custo') : brl(mem.custo)}</b><span>Despesas de cota do mandato {mem.mandato}</span></div>
              <div className="stat"><b>{attendance?.naoJustificada ?? mem.faltas ?? (mem.resumosHistoricos?.presencas?.length ? 'Histórico de presença em outra Casa' : missingMetric(mem,'faltas'))}</b><span>Ausências não justificadas {attendance ? <>(dias) · Câmara<br/>{attendance.periodoInicio} a {attendance.periodoFim}</> : '— classificação histórica'}</span></div>
              <div className="stat"><b>{hist?.pendentes ? 'Resultados pendentes de confirmação' : mem.aprov === null || mem.neg === null ? 'Histórico sem proporção confirmada' : mem.aprov + mem.neg === 0 ? 'Sem resultados classificados' : pct(mem.aprov, mem.neg)}</b><span>Conversões entre resultados classificados</span></div>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
              <button className="btn alt" disabled={(!!mem.detalhesUrl && !currentDetails) || !lsFor(mem, currentDetails, 'aprov')} onClick={() => setLawTab('aprov')}>Ver aprovadas</button>
              <button className="btn alt" disabled={(!!mem.detalhesUrl && !currentDetails) || !lsFor(mem, currentDetails, 'neg')} onClick={() => setLawTab('neg')}>Ver negadas</button>
            </div>
            {lawTab && (
              <>
                <h3 style={{ fontSize: 14, margin: '16px 0 6px' }}>{lawTab === 'aprov' ? 'Projetos convertidos em lei' : 'Projetos rejeitados'} ({ls.length})</h3>
                <div style={{ maxHeight: 260, overflowY: 'auto' }}>
                  {!ls.length && <p className="muted">Nenhuma lei nesta categoria.</p>}
                  {ls.map((l, i) => (
                    <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'baseline', padding: '8px 0', borderBottom: '1px solid #EEEEE8', fontSize: 13 }}>
                      <b style={{ whiteSpace: 'nowrap' }}>{l.num}</b><span style={{ flex: 1 }}>{l.titulo}</span>
                      <a href={l.url} target="_blank" rel="noopener noreferrer">Abrir</a>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}

function SenateSessionsPanel({history:h}: {history:import('./data').SenateSessionHistory}) {
  const [open,setOpen]=useState(false);
  return <section className="source-note"><h3 style={{fontSize:14}}>Comparecimento e participação · Senado</h3>
    <p>{h.periodoInicio} a {h.periodoFim} · {h.totalSessoes} sessão deliberativa conferida</p>
    <p><b>{senateSessionLabel(h.sessoes[0].classificacao)}</b><br/>{h.comparecimentosRegistrados} comparecimento registrado no Diário.</p>
    <p>Recorte parcial de 2026. Faltas não justificadas ainda sem classificação; participação conferida neste recorte não mede assiduidade anual.</p>
    <button className="btn alt" aria-expanded={open} onClick={()=>setOpen(v=>!v)}>{open?'Ocultar conferência':'Ver conferência da sessão'}</button>
    {open&&<><p>{h.criterio}</p>{h.sessoes.map(r=><div key={r.id}><p><b>Sessão {r.numero}</b> · continuações contadas uma vez.<br/>{r.registroDiario?`${r.registroDiario.nomeDiario} · ${r.registroDiario.uf} · Diário, página ${r.registroDiario.pagina}`:'Nome não consta no registro de comparecimento; isso não comprova falta não justificada.'}</p>
    {!r.votacoes.length&&<p>Sem votação nominal nesta sessão. A conferência confirma apenas o comparecimento registrado no Diário.</p>}
    {r.votacoes.map(v=><p key={v.id}><b>{v.materia} · {v.data}</b><br/>{v.descricao} {v.secreta&&'· Votação secreta: apenas participação pública.'}<br/>{v.classificacao==='pendente'?'Sem evidência suficiente para classificar a participação.':v.classificacao==='fora-exercicio'?'Fora do exercício nesta votação.':v.classificacao==='justificativa-registrada'?'Justificativa registrada; não classifica falta regimental.':'Participação registrada.'}{v.licencasEfetivas.length>0&&<><br/>Licenças com datas efetivas: {v.licencasEfetivas.join(', ')}</>}</p>)}</div>)}
    {h.fontes.map((url,i)=><p key={url}><a href={url} target="_blank" rel="noopener noreferrer">{['Diário oficial (registro de comparecimento)','Votações oficiais','Legenda dos registros','Mandatos e exercício','Licenças oficiais'][i]}</a></p>)}<p>Conferido com fontes coletadas até {date(h.coletadoEm)}.</p></>}
  </section>;
}

function SenateLicensesPanel({history:h}: {history:import('./data').SenateLicenseHistory}) {
  const [open,setOpen]=useState(false);
  const [limit,setLimit]=useState(50);
  return <section className="source-note"><h3 style={{fontSize:14}}>Licenças e missões históricas · Senado</h3>
    <p>{h.periodoInicio} a {h.periodoFim} · {h.registros} registros oficiais disponíveis</p>
    <p>Assiduidade anual e faltas ainda em apuração. Licenças não equivalem a dias de sessão nem comprovam assiduidade.</p>
    <p>Consulta de {date(h.coletadoEm)}. Datas previstas são identificadas separadamente; não representam atividade do mandato de 2027.</p>
    <button className="btn alt" aria-expanded={open} onClick={()=>setOpen(v=>!v)}>{open?'Ocultar licenças e missões':'Ver licenças e missões'}</button>
    {open&&<><p>{h.criterio}</p>{!h.registros&&<p>A fonte não retornou licenças no período consultado. Isso não comprova ausência de faltas.</p>}
    <div style={{maxHeight:260,overflowY:'auto'}}>{h.licencas.slice(0,limit).map(r=><p key={r.id}><b>{r.descricao}</b><br/>Início efetivo: {r.inicio??'Não informado'} · Fim efetivo: {r.fim??'Não informado'}<br/>Início previsto: {r.inicioPrevisto??'Não informado'} · Fim previsto: {r.fimPrevisto??'Não informado'}</p>)}</div>
    {h.licencas.length>limit&&<button className="btn alt" onClick={()=>setLimit(n=>n+50)}>Mostrar mais licenças</button>}
    <a href={h.fontes[0]} target="_blank" rel="noopener noreferrer">Consultar licenças oficiais</a> · <a href="https://www12.senado.leg.br/assessoria-de-imprensa/guia-para-jornalistas/tutorial-de-verificacao-da-assiduidade-dos-senadores" target="_blank" rel="noopener noreferrer">Critérios de assiduidade do Senado</a></>}
  </section>;
}

function AttendancePanel({history:h}: {history:import('./data').AttendanceHistory}) {
  const [open,setOpen]=useState(false);
  const [limit,setLimit]=useState(50);
  return <section className="source-note"><h3 style={{fontSize:14}}>Presença histórica · Câmara</h3>
    <p>{h.periodoInicio} a {h.periodoFim} · {h.totalDias} dias classificados no período de exercício</p>
    <p>{h.presenca} dias com presença · {h.justificada} com ausência justificada · {h.naoJustificada} com ausência não justificada · {h.outros} em outras situações.</p>
    <p>Classificação disponível na coleta de {date(h.coletadoEm)}, sujeita a atualização. Não representa atividade do mandato de 2027.</p>
    <button className="btn alt" aria-expanded={open} onClick={()=>setOpen(v=>!v)}>{open?'Ocultar presença':'Ver presença'}</button>
    {open&&<><p>{h.criterio}</p><div style={{maxHeight:260,overflowY:'auto'}}>{h.dias.slice(0,limit).map(d=><p key={d.data}>{d.data} · {d.situacao}</p>)}</div>{h.dias.length>limit&&<button className="btn alt" onClick={()=>setLimit(n=>n+50)}>Mostrar mais dias</button>}<a href={h.fontes[0]} target="_blank" rel="noopener noreferrer">Consultar relatório oficial de presença</a></>}
  </section>;
}

function ExpensePanel({ history: h }: { history: import('./data').ExpenseHistory }) {
  const [open, setOpen] = useState(false);
  const money = (cents: number) => (cents / 100).toLocaleString('pt-BR', {style:'currency',currency:'BRL'});
  return <section className="source-note">
    <h3 style={{fontSize:14}}>Despesas históricas · {h.casa === 'camara' ? 'Câmara' : 'Senado'}</h3>
    <p style={{fontSize:20,fontWeight:700}}>{money(h.totalCentavos)}</p>
    <p>Competências {h.periodoInicio.slice(0,7)} a {h.periodoFim.slice(0,7)} · {h.registros.toLocaleString('pt-BR')} registros</p>
    <p>Registros disponíveis na coleta de {date(h.coletadoEm)}. Sujeitos a atualizações; não representam despesas do mandato de 2027.</p>
    <button className="btn alt" aria-expanded={open} onClick={() => setOpen(v => !v)}>{open ? 'Ocultar despesas' : 'Ver despesas'}</button>
    {open && <>
      <p>{h.criterio}</p>
      <h4>Por competência</h4>
      {h.meses.map(m => <p key={m.competencia}>{m.competencia} · {money(m.totalCentavos)}</p>)}
      <p>Zero indica saldo dos registros disponíveis; não comprova ausência de gastos.</p>
      <h4>Por categoria</h4>
      {h.categorias.map(c => <p key={c.nome}>{c.nome} · {money(c.totalCentavos)}</p>)}
      {h.restituicoesCentavos !== null && <p>Restituições informadas: {money(h.restituicoesCentavos)} (separadas do total acima).</p>}
      {h.fontes.map(url => <p key={url}><a href={url} target="_blank" rel="noopener noreferrer">Consultar arquivo oficial · {h.casa === 'camara' ? 'CEAP' : 'CEAPS'}</a></p>)}
    </>}
  </section>;
}

function HistoryPanel({ history: h }: { history: LegislativeHistory }) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('todos');
  const [limit, setLimit] = useState(50);
  const projects = h.projetos.filter(p => filter === 'todos' || p.classificacao === filter);
  return <section className="source-note">
    <h3 style={{fontSize:14}}>Histórico legislativo · {h.casa === 'camara' ? 'Câmara' : 'Senado'}</h3>
    <p>{h.periodoInicio} a {h.periodoFim} · {h.total} projetos de autoria/coautoria</p>
    <p>PL e PLP apresentados no período. Situação observada em {date(h.coletadoEm)}.</p><p>{h.aprov} conversões em lei confirmadas · {h.neg} rejeições confirmadas · {h.total-h.aprov-h.neg} em outras situações ou sem resultado confirmado.</p>
    <button className="btn alt" aria-expanded={open} onClick={() => setOpen(v => !v)}>{open ? 'Ocultar projetos' : 'Ver projetos'}</button>
    {open && <>
      <label style={{marginTop:12}}>Situação dos projetos<select value={filter} onChange={e => {setFilter(e.target.value);setLimit(50);}}><option value="todos">Todas</option><option value="aprov">Conversão em lei confirmada ({h.aprov})</option><option value="neg">Rejeição expressa ({h.neg})</option><option value="outros">Demais situações</option></select></label>
      {!projects.length && <p style={{marginTop:12}}>Nenhum projeto nesta seleção.</p>}
      <div style={{maxHeight:320,overflowY:'auto',marginTop:12}}>{projects.slice(0,limit).map(p => <div key={p.id} style={{padding:'10px 0',borderBottom:'1px solid #D6D6CE'}}><a href={p.url} target="_blank" rel="noopener noreferrer"><b>{p.num}</b></a><p>{p.titulo}</p><p>{p.situacao} · apresentação {p.dataApresentacao}</p>{p.observacaoResultado && <p>{p.observacaoResultado} <a href={p.fonteVerificacao} target="_blank" rel="noopener noreferrer">Verificação oficial</a> · {date(p.resultadoVerificadoEm!)}</p>}{p.norma && <p>Norma: {p.norma}{p.fonteNorma && <> · <a href={p.fonteNorma} target="_blank" rel="noopener noreferrer">Confirmação oficial</a> · verificada em {date(p.normaVerificadaEm!)}</>}</p>}</div>)}</div>
      {projects.length > limit && <button className="btn alt" onClick={() => setLimit(n => n + 50)}>Mostrar mais projetos ({Math.min(limit,projects.length)} de {projects.length})</button>}
    </>}
  </section>;
}

const GL = { partido: 'Partido', uf: 'Estado', reg: 'Região', casaNome: 'Casa' } as const;
type GroupKey = keyof typeof GL;
type SortKey = 'nome' | 'aprov' | 'neg' | 'faltas' | 'custo';

function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement('a'); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Dados({ all, provenance, coberturaSenado }: { all: Member[]; provenance: string; coberturaSenado?:import('./data').SenateCoverage }) {
  const [q, setQ] = useState(''); const [casa, setCasa] = useState(''); const [fUf, setFUf] = useState(''); const [party, setParty] = useState('');
  const [group, setGroup] = useState<GroupKey>('partido'); const [sort, setSort] = useState<SortKey>('nome');
  const rows = useMemo(() => {
    const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const ql = normalize(q.trim());
    return all.filter((m) => (!casa || m.casa === casa) && (!fUf || m.uf === fUf) && (!party || m.partido === party) && (!ql || normalize(m.nome).includes(ql)))
      .sort((a, b) => (sort === 'nome' ? a.nome.localeCompare(b.nome) : (a[sort] === b[sort] ? a.nome.localeCompare(b.nome, 'pt-BR') : a[sort] === null ? 1 : b[sort] === null ? -1 : b[sort]! - a[sort]!)));
  }, [all, q, casa, fUf, party, sort]);
  const agg = useMemo(() => aggregateHistory(rows, group), [rows, group]);

  const cols = ['Nome', 'Casa', 'UF', 'Partido', 'Mandato', 'Convertidos em lei', 'Rejeitados', 'Ausências não justificadas — dias históricos', 'Subsídio bruto mensal de referência — BRL', 'Despesas de cota', 'Situação', 'Participação', 'Partido na eleição', 'Partido atual na coleta', 'Fonte', 'Fonte gerada em', 'Coleta', 'Histórico', 'Indicadores — períodos e fontes', 'Históricos disponíveis — cobertura, períodos e fontes', 'Subsídio — norma, vigência e fontes', 'Pagamento individual'];
  const line = (m: Member) => [m.nome, m.casaNome, m.uf, m.partido, m.mandato, m.aprov ?? missingMetric(m,'aprov'), m.neg ?? missingMetric(m,'neg'), attendanceHistory(m)?.naoJustificada ?? m.faltas ?? missingMetric(m,'faltas'), m.subsidioReferencia ? (m.subsidioReferencia.valorCentavos/100).toFixed(2) : m.salario?.toFixed(2) ?? missingMetric(m,'salario'), m.custo ?? missingMetric(m,'custo'), m.situacao ?? 'Demonstração', m.participacao ?? '', m.partidoEleicao ?? 'Indisponível', m.partidoAtual ?? 'Indisponível', m.fonte?.url ?? 'Demonstração', m.fonte?.geradoEm ?? '', m.fonte?.coletadoEm ?? '', m.historico ?? 'Ilustrativo', JSON.stringify(m.indicadores ?? {}), JSON.stringify(m.resumosHistoricos ?? {}), JSON.stringify(m.subsidioReferencia ?? {}), m.salario?.toFixed(2) ?? missingMetric(m,'salario')];
  const table = (sep: string) => [cols, ...rows.map(line)].map((r) => r.map(v => String(v).replace(/[\t\r\n]/g, ' ').replace(/^[=+@-]/, "'" + String(v)[0])).join(sep)).join('\n');
  // ponytail: XLS = TSV com extensão .xls (Excel abre com aviso). Trocar por SheetJS se precisar de .xlsx nativo.
  const exportTxt = () => download('painel-politico.txt', `Painel Político 2027 — exportado em ${new Date().toLocaleString('pt-BR')}\n${provenance}\n\n${table(' | ')}`, 'text/plain;charset=utf-8');
  const exportXls = () => download('painel-politico.xls', '﻿' + table('\t'), 'application/vnd.ms-excel;charset=utf-8');

  const displayCols = cols.slice(0, 10);
  const ufs = STATES.map((s) => s.uf).sort();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <section className="card noprint">
        <h2 style={{ fontSize: 20 }}>Compilação de dados</h2>
        <p className="muted" style={{ margin: '6px 0 16px', fontSize: 14 }}>Monte sua busca, cruze os dados por um agrupamento e exporte.</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>
          <label style={{ flex: '2 1 220px' }}>Busca por nome<input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ex.: Carol" /></label>
          <label style={{ flex: '1 1 140px' }}>Casa<select value={casa} onChange={(e) => setCasa(e.target.value)}><option value="">Ambas</option><option value="senado">Senado</option><option value="camara">Câmara</option></select></label>
          <label style={{ flex: '1 1 140px' }}>Estado<select value={fUf} onChange={(e) => setFUf(e.target.value)}><option value="">Todos</option>{ufs.map((u) => <option key={u}>{u}</option>)}</select></label>
          <label style={{ flex: '1 1 140px' }}>Partido<select value={party} onChange={(e) => setParty(e.target.value)}><option value="">Todos</option>{[...new Set(all.map(m => m.partido))].sort().map((p) => <option key={p}>{p}</option>)}</select></label>
          <label style={{ flex: '1 1 160px' }}>Cruzar por<select value={group} onChange={(e) => setGroup(e.target.value as GroupKey)}>{Object.entries(GL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
          <label style={{ flex: '1 1 160px' }}>Ordenar por<select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
            <option value="nome">Nome</option><option value="aprov">Projetos convertidos em lei</option><option value="neg">Projetos rejeitados</option><option value="faltas">Faltas</option><option value="custo">Custo</option>
          </select></label>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
          <button className="btn" onClick={() => window.print()}>Exportar PDF</button>
          <button className="btn alt" onClick={exportTxt}>Exportar TXT</button>
          <button className="btn alt" onClick={exportXls}>Exportar XLS</button>
          <button className="btn alt" onClick={() => { setQ(''); setCasa(''); setFUf(''); setParty(''); setGroup('partido'); setSort('nome'); }}>Limpar filtros</button>
        </div>
      </section>
      <div className="print-only"><h1>Painel Político 2027</h1><p>{provenance} · {rows.length} parlamentares · Busca: {q || 'Todos'} · Casa: {casa || 'Ambas'} · UF: {fUf || 'Todas'} · Partido: {party || 'Todos'}</p></div>
      <section className="card">
        <p className="muted" style={{fontSize:12}}>{provenance} Agrupamento pela composição de 2027; histórico separado por Casa, período e critério. Cobertura indica quantos parlamentares do grupo têm consulta vinculada. Somas parciais não representam toda a bancada.</p>
        <h3 style={{ fontSize: 16, marginBottom: 10 }}>Cruzamento por {GL[group]} · {rows.length} parlamentares</h3>
        <h4>Histórico legislativo disponível</h4>
        <p className="muted" style={{fontSize:12}}>Contagem por autor/coautor: um mesmo projeto pode participar de mais de um histórico. Conversões e rejeições são apenas resultados confirmados; demais situações não equivalem a rejeição.</p>
        <div style={{overflowX:'auto'}}><table>
          <thead><tr><th>{GL[group]}</th><th>Casa histórica / período</th><th>Cobertura</th><th>PL/PLP por autor</th><th>Conversões confirmadas</th><th>Rejeições confirmadas</th><th>Resultados pendentes de confirmação</th></tr></thead>
          <tbody>{agg.legislativos.map(g => <tr key={g.key}><td><b>{g.grupo}</b></td><td>{g.casa === 'camara' ? 'Câmara' : 'Senado'}<br/>{g.periodoInicio} a {g.periodoFim}</td><td>{g.participantes} de {g.universo} parlamentares</td><td>{g.total}</td><td>{g.aprov}</td><td>{g.neg}</td><td>{g.pendentes ? `${g.pendentes} resultados ainda não confirmados` : 'Sem pendências de confirmação'}<br/><small>Demais situações: {g.total-g.aprov-g.neg-g.pendentes}</small></td></tr>)}
          {agg.grupos.filter(([k]) => !agg.legislativos.some(g => g.grupo === k)).map(([k,n]) => <tr key={k}><td><b>{k}</b></td><td colSpan={6}>Histórico ainda não vinculado · 0 de {n} parlamentares com consulta</td></tr>)}
          {!rows.length && <tr><td colSpan={7}>Nenhum resultado para os filtros selecionados.</td></tr>}</tbody>
        </table></div>
        <h4 style={{marginTop:20}}>Despesas históricas disponíveis</h4>
        <p className="muted" style={{fontSize:12}}>Soma dos registros disponíveis na coleta, sujeita a atualizações. Valores da Câmara e do Senado seguem critérios próprios. Não são despesas do mandato de 2027.</p>
        <div style={{overflowX:'auto'}}><table>
          <thead><tr><th>{GL[group]}</th><th>Casa histórica / competências</th><th>Cobertura</th><th>Soma disponível</th><th>Critério / última coleta</th></tr></thead>
          <tbody>{agg.despesas.map(g => <tr key={g.key}><td><b>{g.grupo}</b></td><td>{g.casa === 'camara' ? 'Câmara' : 'Senado'}<br/>{g.periodoInicio.slice(0,7)} a {g.periodoFim.slice(0,7)}</td><td>{g.participantes} de {g.universo} parlamentares</td><td>{moneyCents(g.totalCentavos)}</td><td>{g.criterio}<br/>{date(g.coletadoEm)}</td></tr>)}
          {agg.grupos.filter(([k]) => !agg.despesas.some(g => g.grupo === k)).map(([k,n]) => <tr key={k}><td><b>{k}</b></td><td colSpan={4}>Sem registros de despesas vinculados · 0 de {n} parlamentares com dados</td></tr>)}
          {!rows.length && <tr><td colSpan={5}>Nenhum resultado para os filtros selecionados.</td></tr>}</tbody>
        </table></div>
        <h4 style={{marginTop:20}}>Comparecimento e participação · Senado</h4>
        {coberturaSenado&&<div className="source-note"><p><b>Cobertura do Senado: {coberturaSenado.sessoesConferidas} de {coberturaSenado.sessoesIdentificadas} sessões identificadas na agenda com recortes conferidos.</b><br/>Inventário de {coberturaSenado.periodoInicio} a {coberturaSenado.periodoFim}. Cobertura global do projeto, independente dos filtros; os recortes abrangem apenas identidades previamente vinculadas.</p><details><summary>Fontes da cobertura</summary><p>{coberturaSenado.criterio}</p>{coberturaSenado.fontes.map((url,i)=><p key={url}><a href={url} target="_blank" rel="noopener noreferrer">Agenda oficial · mês {String(i+1).padStart(2,'0')}/2026</a></p>)}<p>Fontes coletadas até {date(coberturaSenado.coletadoEm)}.</p></details></div>}

        <p className="muted" style={{fontSize:12}}>Recortes conferidos separados por sessão e período. Sem votação nominal, confirma apenas comparecimento. Continuações contam uma vez. Justificativas registradas e pendências não classificam faltas; não mede assiduidade anual.</p>
        <div style={{overflowX:'auto'}}><table><thead><tr><th>Parlamentar</th><th>Período / sessões</th><th>Comparecimento no Diário</th><th>Comparecimento conferido (sem nominal)</th><th>Participações conferidas</th><th>Justificativas registradas</th><th>Pendentes</th><th>Fora do exercício</th></tr></thead><tbody>
        {rows.flatMap(m=>(m.resumosHistoricos?.comparecimentosSenado??[]).map(h=><tr key={`${m.id}-${h.periodoInicio}`}><td>{m.nome}</td><td>{h.periodoInicio} a {h.periodoFim}<br/>{h.totalSessoes} sessão · <a href={h.fontes[0]} target="_blank" rel="noopener noreferrer">Diário oficial</a></td><td>{h.comparecimentosRegistrados}</td><td>{h.comparecimentosConferidos??0}</td><td>{h.participacoesConferidas}</td><td>{h.justificativasRegistradas}</td><td>{h.pendentes}</td><td>{h.foraExercicio}</td></tr>))}
        {!rows.some(m=>m.resumosHistoricos?.comparecimentosSenado?.length)&&<tr><td colSpan={8}>Sem recortes conferidos para os filtros selecionados.</td></tr>}
        </tbody></table></div>
        <h4 style={{marginTop:20}}>Licenças e missões históricas · Senado</h4>
        <p className="muted" style={{fontSize:12}}>Consultas oficiais por parlamentar. Registros não equivalem a faltas ou dias de sessão; assiduidade anual e faltas do Senado ainda em apuração.</p>
        <div style={{overflowX:'auto'}}><table><thead><tr><th>Parlamentar</th><th>Período</th><th>Registros de licenças</th><th>Fonte / coleta</th></tr></thead><tbody>
        {rows.flatMap(m=>(m.resumosHistoricos?.licencasSenado??[]).map(h=><tr key={`${m.id}-${h.periodoInicio}`}><td>{m.nome}</td><td>{h.periodoInicio} a {h.periodoFim}</td><td>{h.registros}</td><td><a href={h.fontes[0]} target="_blank" rel="noopener noreferrer">Fonte oficial</a><br/>{date(h.coletadoEm)}</td></tr>))}
        {!rows.some(m=>m.resumosHistoricos?.licencasSenado?.length)&&<tr><td colSpan={4}>Sem consultas de licenças vinculadas aos filtros selecionados.</td></tr>}
        </tbody></table></div>
        <h4 style={{marginTop:20}}>Presença histórica disponível · Câmara</h4>
        <p className="muted" style={{fontSize:12}}>Somatório de dias por parlamentar em Plenário, no período de exercício. Ausências podem ser justificadas posteriormente; comissões e votos individuais não entram nesta contagem.</p>
        <div style={{overflowX:'auto'}}><table><thead><tr><th>{GL[group]}</th><th>Casa / período</th><th>Cobertura</th><th>Dias com presença</th><th>Dias com ausência justificada</th><th>Dias com ausência não justificada</th><th>Outras classificações</th></tr></thead><tbody>
        {agg.presencas.map(g => <tr key={g.key}><td><b>{g.grupo}</b></td><td>Câmara<br/>{g.periodoInicio} a {g.periodoFim}</td><td>{g.participantes} de {g.universo} parlamentares</td><td>{g.presenca}</td><td>{g.justificada}</td><td>{g.naoJustificada}</td><td>{g.outros}</td></tr>)}
        {agg.grupos.filter(([k])=>!agg.presencas.some(g=>g.grupo===k)).map(([k,n])=><tr key={k}><td><b>{k}</b></td><td colSpan={6}>Presença ainda sem consulta confirmada · 0 de {n} parlamentares</td></tr>)}
        {!rows.length&&<tr><td colSpan={7}>Nenhum resultado para os filtros selecionados.</td></tr>}
        </tbody></table></div>
        <p className="muted" style={{fontSize:12}}>Subsídio exibido como referência bruta vigente na coleta, não pagamento individual. Presença Senado: classificação depende de reconciliação com licenças e justificativas. Partido/UF/região referem-se à composição selecionada, não necessariamente à filiação no período histórico.</p>
      </section>
      <section className="card">
        <h3 style={{ fontSize: 16, marginBottom: 10 }}>Resultados <span className="muted" style={{ fontWeight: 500, fontSize: 13 }}>{rows.length > 200 ? `mostrando 200 de ${rows.length} (exportação inclui todos)` : `${rows.length} registros`}</span></h3>
        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead><tr>{displayCols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>{!rows.length && <tr><td colSpan={10}>Nenhum parlamentar encontrado. Ajuste a busca ou limpe os filtros.</td></tr>}{rows.map((m, i) => <tr key={m.id} className={i >= 200 ? 'print-extra' : undefined}><td>{m.nome}</td><td>{m.casaNome}</td><td>{m.uf}</td><td>{m.partido}</td><td>{m.mandato}</td><td>{m.aprov ?? missingMetric(m,'aprov')}</td><td>{m.neg ?? missingMetric(m,'neg')}</td><td>{attendanceHistory(m) ? `${attendanceHistory(m)!.naoJustificada} dias (${attendanceHistory(m)!.periodoInicio} a ${attendanceHistory(m)!.periodoFim})` : m.faltas ?? missingMetric(m,'faltas')}</td><td>{m.subsidioReferencia ? moneyCents(m.subsidioReferencia.valorCentavos) : m.salario === null ? missingMetric(m,'salario') : brl(m.salario)}</td><td>{m.custo === null ? missingMetric(m,'custo') : brl(m.custo)}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
