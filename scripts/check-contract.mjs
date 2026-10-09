import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {mkdtempSync, readFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createRequire} from 'node:module';
const directory=mkdtempSync(join(tmpdir(),'painel-contract-'));
try {
  execFileSync(process.execPath,['node_modules/typescript/bin/tsc','src/dataset.ts','--module','commonjs','--target','ES2020','--resolveJsonModule','--esModuleInterop','--skipLibCheck','--outDir',directory]);
  const {parseDataset,parseMemberDetails}=createRequire(join(directory,'runner.cjs'))(join(directory,'dataset.js'));
  const {pct}=createRequire(join(directory,'runner.cjs'))(join(directory,'data.js'));assert.equal(pct(0,0),'Indisponível');assert.equal(pct(2,1),'67%');
  const input=JSON.parse(readFileSync('public/data.json','utf8'));
  const original=parseDataset(input);
  const recortes=JSON.parse(readFileSync('src/senate-recortes.json','utf8'));
  assert.equal(original.coberturaSenado.sessoesConferidas,recortes.length);assert.equal(original.coberturaSenado.sessoesIdentificadas,45);
  for(const mutation of [{sessoesConferidas:126},{sessoesIdentificadas:2},{periodoFim:'invalid'},{fontes:['https://example.com']}]){
    const invalid=structuredClone(input);Object.assign(invalid.coberturaSenado,mutation);assert.throws(()=>parseDataset(invalid));
  }
  const {aggregateHistory,missingMetric}=createRequire(join(directory,'runner.cjs'))(join(directory,'history.js'));
  const hasExpense=original.camara.find(m=>m.resumosHistoricos?.despesas.length);
  assert.ok(hasExpense);
  const without=structuredClone(hasExpense);without.id='no-history';without.resumosHistoricos={legislativos:[],despesas:[]};
  const aggregated=aggregateHistory([hasExpense,without],'partido');
  assert.equal(aggregated.despesas[0].participantes,1);assert.equal(aggregated.despesas[0].universo,2);
  assert.equal(aggregated.despesas[0].totalCentavos,hasExpense.resumosHistoricos.despesas[0].totalCentavos);
  assert.equal(missingMetric(hasExpense,'custo'),'Ainda não iniciado');
  const other=structuredClone(hasExpense);other.resumosHistoricos.despesas[0].periodoFim='2026-08-31';
  assert.equal(aggregateHistory([hasExpense,other],'partido').despesas.length,2);
  for(const mutation of [{idParlamentar:'wrong'},{totalCentavos:0.5},{fontes:['https://example.com']},{cobertura:'completa'}]){
    const invalid=structuredClone(input);const target=invalid.camara.find(m=>m.id===hasExpense.id);Object.assign(target.resumosHistoricos.despesas[0],mutation);assert.throws(()=>parseDataset(invalid));
  }
  assert.equal(original.schemaVersion,2);
  assert.equal(original.camara.length,513);
  assert.equal(original.camara[0].subsidioReferencia.tipo,'referencia-bruta-mensal');
  assert.equal(original.camara[0].salario,null);
  for(const mutation of [{valorCentavos:0.5},{tipo:'pagamento-individual'},{fontes:['https://example.com','https://example.org']}]){
    const invalid=structuredClone(input);Object.assign(invalid.camara[0].subsidioReferencia,mutation);assert.throws(()=>parseDataset(invalid));
  }
  const present=original.camara.find(m=>m.resumosHistoricos?.presencas?.length);assert.ok(present);
  const noAttendance=structuredClone(present);noAttendance.resumosHistoricos.presencas=[];
  const attendanceGroup=aggregateHistory([present,noAttendance],'partido').presencas[0];
  assert.equal(attendanceGroup.participantes,1);assert.equal(attendanceGroup.universo,2);
  for(const mutation of [{idParlamentar:'wrong'},{naoJustificada:9999},{unidade:'sessoes'},{fontes:['https://example.com']}]){
    const invalid=structuredClone(input);Object.assign(invalid.camara.find(m=>m.id===present.id).resumosHistoricos.presencas[0],mutation);assert.throws(()=>parseDataset(invalid));
  }
  const withPhoto=original.camara.find(m=>m.foto);assert.ok(withPhoto);
  const localPhotos=[...original.senado,...original.camara].filter(m=>m.foto?.arquivoLocal);
  assert.ok(localPhotos.length>0);
  for(const m of localPhotos){
    const raw=readFileSync('public/'+m.foto.arquivoLocal);
    assert.ok(m.foto.arquivoLocal.includes(createHash('sha256').update(raw).digest('hex')),'Nome imutável da foto deve conferir com o conteúdo');
    assert.ok(raw.length>32 && (raw.subarray(0,3).equals(Buffer.from([255,216,255])) || raw.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))),'Foto local deve ser imagem');
  }

  for(const mutation of [{idParlamentar:'wrong'},{url:'https://example.com/photo.jpg'},{url:'http://www.camara.leg.br/photo.jpg'},{fonteUrl:'https://example.com'},{arquivoLocal:'../photo.jpg'},{arquivoLocal:'https://example.com/photo.jpg'},{arquivoLocal:'photos/'+'a'.repeat(64)+'.jpg',imagemColetadaEm:'invalid'}]){
    const invalid=structuredClone(input);Object.assign(invalid.camara.find(m=>m.id===withPhoto.id).foto,mutation);assert.throws(()=>parseDataset(invalid));
  }
  const withLicenses=[...original.senado,...original.camara].find(m=>m.resumosHistoricos?.licencasSenado?.some(h=>h.registros>0));
  assert.ok(withLicenses);
  for(const mutation of [{idParlamentar:'wrong'},{registros:-1},{fontes:['https://example.com']},{periodoFim:'invalid'}]){
    const invalid=structuredClone(input);const m=[...invalid.senado,...invalid.camara].find(m=>m.id===withLicenses.id);Object.assign(m.resumosHistoricos.licencasSenado[0],mutation);assert.throws(()=>parseDataset(invalid));
  }
  const licenseDetail=JSON.parse(readFileSync('public/'+withLicenses.detalhesUrl,'utf8'));
  parseMemberDetails(licenseDetail,withLicenses,original.versao);
  for(const mutation of [{fim:'2020-01-01'},{inicio:'2027-01-01'},{inicio:'invalid'},{id:''}]){
    const invalid=structuredClone(licenseDetail);Object.assign(invalid.licencasSenado[0].licencas[0],mutation);assert.throws(()=>parseMemberDetails(invalid,withLicenses,original.versao));
  }
  assert.ok([...original.senado,...original.camara].filter(m=>m.resumosHistoricos?.licencasSenado?.length).every(m=>m.faltas===null),'Consulta de licenças não preenche faltas genéricas');
  const session=d=>number=>d.comparecimentosSenado.find(h=>h.sessoes[0].numero===number);
  const session120=d=>session(d)(120);
  const withSessions=original.senado.find(m=>m.resumosHistoricos?.comparecimentosSenado?.some(h=>h.periodoInicio==='2026-09-01' && h.participacoesConferidas));assert.ok(withSessions);
  const sessionDetail=JSON.parse(readFileSync('public/'+withSessions.detalhesUrl,'utf8'));parseMemberDetails(sessionDetail,withSessions,original.versao);
  for(const mutation of [{idParlamentar:'wrong'},{comparecimentosConferidos:null},{naoJustificada:0},{totalSessoes:3},{participacoesConferidas:2},{unidade:'dias'},{fontes:['https://example.com']}]){
    const invalid=structuredClone(input);const m=invalid.senado.find(m=>m.id===withSessions.id);Object.assign(m.resumosHistoricos.comparecimentosSenado[0],mutation);assert.throws(()=>parseDataset(invalid));
  }
  for(const change of [d=>session120(d).sessoes.push(session120(d).sessoes[0]),d=>session120(d).sessoes[0].votacoes[0].registro='Sim',d=>session120(d).sessoes[0].votacoes[0].descricao='Votou Sim',d=>session120(d).sessoes[0].votacoes[0].classificacao='pendente',d=>session120(d).sessoes[0].exercicios=[],d=>delete d.comparecimentosSenado]){
    const invalid=structuredClone(sessionDetail);change(invalid);assert.throws(()=>parseMemberDetails(invalid,withSessions,original.versao));
  }
  const noNominal=sessionDetail.comparecimentosSenado.find(h=>h.periodoInicio==='2026-08-11');assert.ok(noNominal);
  assert.equal(noNominal.sessoes[0].votacoes.length,0);assert.equal(noNominal.participacoesConferidas,0);
  assert.equal(noNominal.sessoes[0].classificacao,'comparecimento-conferido');
  for(const change of [d=>session(d)(111).sessoes[0].classificacao='participacao-conferida',d=>session(d)(111).sessoes[0].registroDiario.votoRegistrado=true,d=>session(d)(111).sessoes[0].votacoes.push(session120(d).sessoes[0].votacoes[0]),d=>session(d)(113).sessoes[0].votacoes.pop(),d=>session(d)(113).fontes[0]='https://legis.senado.leg.br/diarios/ver/126579']){
    const invalid=structuredClone(sessionDetail);change(invalid);assert.throws(()=>parseMemberDetails(invalid,withSessions,original.versao));
  }
  const pendingSenator=original.senado.find(m=>m.resumosHistoricos?.comparecimentosSenado?.some(h=>h.pendentes));assert.ok(pendingSenator);
  const pendingDetail=JSON.parse(readFileSync('public/'+pendingSenator.detalhesUrl,'utf8'));
  pendingDetail.comparecimentosSenado.find(h=>h.pendentes).sessoes[0].classificacao='participacao-conferida';assert.throws(()=>parseMemberDetails(pendingDetail,pendingSenator,original.versao));
  assert.ok([...original.senado,...original.camara].filter(m=>m.resumosHistoricos?.comparecimentosSenado?.length).every(m=>m.faltas===null));
  const member=original.camara[0];
  const details=JSON.parse(readFileSync('public/'+member.detalhesUrl,'utf8'));
  parseMemberDetails(details,member,original.versao);
  assert.throws(()=>parseMemberDetails({...details,versao:'wrong'},member,original.versao));
  assert.throws(()=>parseMemberDetails({...details,pessoaId:'other'},member,original.versao));
  const evidence={periodoInicio:'2025-01-01',periodoFim:'2025-12-31',casa:'camara',unidade:'quantidade',cobertura:'completa',fonteUrl:'https://dadosabertos.camara.leg.br/api/v2/proposicoes',coletadoEm:'2026-10-05T20:00:00-03:00',criterio:'Projetos convertidos em lei'};
  const withMetric=structuredClone(input);
  withMetric.camara[0].aprov=2;
  withMetric.camara[0].indicadores={...withMetric.camara[0].indicadores,aprov:evidence};
  assert.equal(parseDataset(withMetric).camara[0].aprov,2);
  for(const mutation of [{cobertura:'parcial'},{casa:'senado'},{periodoInicio:'2026-01-01'},{unidade:'BRL'},{fonteUrl:'https://example.com'}]){
    const invalid=structuredClone(withMetric);Object.assign(invalid.camara[0].indicadores.aprov,mutation);assert.throws(()=>parseDataset(invalid));
  }
  const missing=structuredClone(withMetric);delete missing.camara[0].indicadores;assert.throws(()=>parseDataset(missing));
  const mismatch=structuredClone(input);mismatch.camara[0].detalhesUrl='data/snapshots/other/id.json';assert.throws(()=>parseDataset(mismatch));
  for(const m of [...original.camara,...original.senado]){
    const d=JSON.parse(readFileSync('public/'+m.detalhesUrl,'utf8'));parseMemberDetails(d,m,original.versao);
    assert.equal(m.resumosHistoricos.legislativos.length,d.historicosLegislativos.length);
    assert.equal(m.resumosHistoricos.despesas.length,d.despesasHistoricas.length);
    assert.equal(m.resumosHistoricos.presencas.length,d.presencasHistoricas.length);
    assert.equal(m.resumosHistoricos.comparecimentosSenado.length,d.comparecimentosSenado.length);
    if(d.presencasHistoricas.length){const bad=structuredClone(d);bad.presencasHistoricas[0].dias.push(bad.presencasHistoricas[0].dias[0]);assert.throws(()=>parseMemberDetails(bad,m,original.versao));}
    for(const summary of m.resumosHistoricos.despesas) assert.equal(summary.totalCentavos,d.despesasHistoricas.find(h=>h.casa===summary.casa && h.periodoInicio===summary.periodoInicio && h.periodoFim===summary.periodoFim).totalCentavos);
    if(d.historicosLegislativos?.length){const bad=structuredClone(d);bad.historicosLegislativos[0].idParlamentar='wrong';assert.throws(()=>parseMemberDetails(bad,m,original.versao));}
    if(d.despesasHistoricas?.length){
      for(const mutation of [{idParlamentar:'wrong'},{totalCentavos:1},{fontes:['https://example.com']},{cobertura:'completa'}]){
        const bad=structuredClone(d);Object.assign(bad.despesasHistoricas[0],mutation);assert.throws(()=>parseMemberDetails(bad,m,original.versao));
      }
    }
  }
  const wrong=structuredClone(details);if(wrong.historicosLegislativos?.length){wrong.historicosLegislativos[0].idParlamentar='0000';assert.throws(()=>parseMemberDetails(wrong,member,original.versao));}
  console.log('PASS Contratos: versão, identidade, detalhes e indicadores com evidência e período');
} finally {rmSync(directory,{recursive:true,force:true});}
