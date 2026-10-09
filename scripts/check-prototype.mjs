import {writeFile,readFile} from 'node:fs/promises';
const dataset=JSON.parse(await readFile('public/data.json','utf8'));
const expectedConferences=[...dataset.senado,...dataset.camara].reduce((n,m)=>n+(m.resumosHistoricos?.comparecimentosSenado?.length||0),0);
const expectedCoverage=`Cobertura do Senado: ${dataset.coberturaSenado.sessoesConferidas} de ${dataset.coberturaSenado.sessoesIdentificadas} sessões`;
const page=await (await fetch(`${process.env.CDP_URL || 'http://127.0.0.1:9222'}/json/new?about:blank`, {method:'PUT'})).json();
const ws=new WebSocket(page.webSocketDebuggerUrl);
await new Promise(r=>ws.addEventListener('open',r,{once:true}));
let id=0; const pending=new Map(); const errors=[];
ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);if(!p)return;pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(m.error):p.resolve(m.result)}else if(m.method==='Runtime.exceptionThrown')errors.push(m.params)});
ws.addEventListener('close',()=>{for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('Conexão com o navegador encerrada durante '+p.method))}pending.clear()});
const send=(method,params={})=>new Promise((resolve,reject)=>{const i=++id;const timer=setTimeout(()=>{pending.delete(i);reject(Error('Navegador não respondeu: '+method));ws.close()},30000);pending.set(i,{resolve,reject,timer,method});ws.send(JSON.stringify({id:i,method,params}))});
const evalJS=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value};
const waitFor=async(expression)=>{for(let i=0;i<40;i++){if(await evalJS(expression))return;await new Promise(r=>setTimeout(r,200))}throw Error('Tempo excedido: '+expression)};
const wait=()=>new Promise(r=>setTimeout(r,250));
const click=async text=>{await evalJS(`Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()===${JSON.stringify(text)}).click()`);await wait()};
const check=async(name,expression)=>{if(!await evalJS(expression))throw Error(name + ': ' + await evalJS('document.querySelector("main")?.textContent.slice(0,600)'));console.log('PASS',name)};
await send('Network.enable'); const detailRequests=[]; ws.addEventListener('message',e=>{const m=JSON.parse(e.data); if(m.method==='Network.requestWillBeSent' && m.params.request.url.includes('/data/snapshots/'))detailRequests.push(m.params.request.url)});
await send('Runtime.enable');await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
await send('Page.navigate',{url:process.env.APP_URL || 'http://127.0.0.1:5173'});await new Promise(r=>setTimeout(r,1200));
await evalJS('document.fonts.ready');
await evalJS(`{const select=document.querySelector('select'); select.value='SP'; select.dispatchEvent(new Event('change',{bubbles:true}))}`);
await waitFor(`Array.from(document.querySelectorAll('aside .portrait')).some(img=>img.getAttribute('src').includes('/photos/') && img.complete && img.naturalWidth>0)`);
await check('Foto local do Senado carregada de fato', `Array.from(document.querySelectorAll('aside .row')).some(row=>row.textContent.includes('Marcos Pontes') && row.querySelector('img')?.naturalWidth>0 && row.querySelector('img').getAttribute('src').includes('/photos/'))`);
await evalJS(`Array.from(document.querySelectorAll('aside .row')).find(row=>row.textContent.includes('Marcos Pontes')).click()`);
await waitFor(`document.querySelector('aside')?.textContent.includes('Licenças e missões históricas · Senado')`);
await check('Licenças Senado sem inferir faltas', `document.querySelector('aside').textContent.includes('Assiduidade anual e faltas ainda em apuração') && document.querySelector('aside').textContent.includes('Consulte o recorte do Senado')`);
await evalJS(`Array.from(document.querySelectorAll('aside section.source-note')).find(s=>s.textContent.includes('2026-09-01 a 2026-09-03')).querySelector('button').click()`);
await check('Senado: sessão conferida uma vez e participação sem voto secreto', `document.querySelector('aside').textContent.includes('1 sessão deliberativa conferida') && document.querySelector('aside').textContent.includes('Participação conferida') && document.querySelector('aside').textContent.includes('PDL 995/2026') && document.querySelector('aside').textContent.includes('apenas participação pública') && !!document.querySelector('aside a[href*="diarios/ver/126579"]')`);
await evalJS(`Array.from(document.querySelectorAll('aside section.source-note')).find(s=>s.textContent.includes('2026-08-12 a 2026-08-12')).querySelector('button').click()`);
await check('Senado: três votações nominais conferidas na sessão 113', `Array.from(document.querySelectorAll('aside section.source-note')).some(s=>s.textContent.includes('Sessão 113') && Array.from(s.querySelectorAll('p>b')).filter(b=>b.textContent.startsWith('PLP')).length===3 && !!s.querySelector('a[href*="diarios/ver/126338"]'))`);
await evalJS(`Array.from(document.querySelectorAll('aside section.source-note')).find(s=>s.textContent.includes('2026-08-11 a 2026-08-11')).querySelector('button').click()`);
await check('Senado: sessão sem nominal confirma somente comparecimento', `Array.from(document.querySelectorAll('aside section.source-note')).some(s=>s.textContent.includes('Sessão 111') && s.textContent.includes('Comparecimento conferido (sem votação nominal)') && s.textContent.includes('Sem votação nominal nesta sessão') && !s.textContent.includes('Participação conferida') && !!s.querySelector('a[href*="diarios/ver/126278"]'))`);
for(const [date,number,matter,count,diary] of [['2026-06-16',83,'PLP 73/2025',1,'125298'],['2026-07-14',106,'PEC 14/2021',2,'125698'],['2026-07-15',107,'PLP 18/2021',3,'125978']]){
  await evalJS(`Array.from(document.querySelectorAll('aside section.source-note')).find(s=>s.textContent.includes('${date} a ${date}')).querySelector('button').click()`);
  await check(`Senado: sessão ${number} com todas as votações do recorte`, `Array.from(document.querySelectorAll('aside section.source-note')).some(s=>s.textContent.includes('Sessão ${number}') && Array.from(s.querySelectorAll('p>b')).filter(b=>b.textContent.startsWith('${matter}')).length===${count} && !!s.querySelector('a[href*="diarios/ver/${diary}"]'))`);
}
for(const [date,number,diary] of [['2026-06-17',84,'125318'],['2026-06-30',91,'125479'],['2026-07-02',93,'125478'],['2026-07-07',98,'125578'],['2026-07-08',100,'125638'],['2026-07-09',102,'125618']]){
  await evalJS(`Array.from(document.querySelectorAll('aside section.source-note')).find(s=>s.textContent.includes('${date} a ${date}')).querySelector('button').click()`);
  await check(`Senado: sessão ${number} confirma só comparecimento`, `Array.from(document.querySelectorAll('aside section.source-note')).some(s=>s.textContent.includes('Sessão ${number}') && s.textContent.includes('Comparecimento conferido (sem votação nominal)') && s.textContent.includes('Sem votação nominal nesta sessão') && !s.textContent.includes('Participação conferida') && !!s.querySelector('a[href*="diarios/ver/${diary}"]'))`);
}
await click('Ver licenças e missões');
await check('Missões oficiais com datas efetivas e previstas', `document.querySelector('aside').textContent.includes('Missão política ou cultural de interesse parlamentar') && document.querySelector('aside').textContent.includes('Início efetivo: 2026-06-09') && !!document.querySelector('aside a[href*="6009/licencas.json"]')`);
await click('Mapa');

await evalJS(`{const select=document.querySelector('select'); select.value='SP'; select.dispatchEvent(new Event('change',{bubbles:true}))}`);
await waitFor(`Array.from(document.querySelectorAll('aside .row')).some(row=>row.textContent.includes('ADRIANA VENTURA') && row.querySelector('img')?.naturalWidth>0 && row.querySelector('img').getAttribute('src').includes('/photos/'))`);
await check('Foto local da Câmara carregada de fato', `Array.from(document.querySelectorAll('aside .row')).some(row=>row.textContent.includes('ADRIANA VENTURA') && row.querySelector('img')?.naturalWidth>0 && row.querySelector('img').getAttribute('src').includes('/photos/'))`);

await evalJS(`{const select=document.querySelector('select'); select.value='SC'; select.dispatchEvent(new Event('change',{bubbles:true}))}`);await wait();

detailRequests.length=0;
await writeFile('/tmp/painel-desktop.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
await check('Dados oficiais carregados sem nomes fictícios', `document.querySelector('main').textContent.includes('CAROL DE TONI') && !document.querySelector('main').textContent.includes('Deputado(a)')`);
await check('Detalhes não são baixados antes da seleção', `true`); if(detailRequests.length)throw Error('Detalhes antecipados');
await check('Mapa: 27 estados e Santa Catarina inicial',`document.querySelectorAll('svg path').length===27 && document.querySelector('aside h2').textContent==='Santa Catarina'`);
await evalJS(`document.querySelector('path[aria-label="São Paulo"]').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))`);await wait();
await check('Seleção do estado pelo teclado',`document.querySelector('aside h2').textContent==='São Paulo' && document.querySelector('aside').textContent.includes('Deputados federais (70)')`);
await evalJS(`document.querySelector('select').value='SC';document.querySelector('select').dispatchEvent(new Event('change',{bubbles:true}))`);await wait();
await evalJS(`Array.from(document.querySelectorAll('.row')).find(x=>x.textContent.toLowerCase().includes('carol de toni')).click()`);await wait();
await check('Mapa abre parlamentar no Senado',`document.querySelectorAll('.seat').length===81 && document.querySelector('aside h2').textContent.toLowerCase()==='carol de toni'`);
if(detailRequests.length!==1)throw Error('Esperado um único detalhe para o parlamentar selecionado');
await check('Foto oficial junto ao nome e nas listas', `!!document.querySelector('aside .portrait-large') && document.querySelectorAll('aside .row .portrait').length>0`);
await evalJS(`document.querySelector('aside .portrait-large').dispatchEvent(new Event('error'))`);await wait();
await check('Falha da cópia local tenta a fonte oficial', `!!document.querySelector('aside .portrait-large[src*="camara.leg.br"]')`);
await evalJS(`document.querySelector('aside .portrait-large').dispatchEvent(new Event('error'))`);await wait();
await check('Foto com erro desaparece sem quebrar o cartão', `!document.querySelector('aside .portrait-large') && document.querySelector('aside h2').textContent.toLowerCase()==='carol de toni'`);
await check('Ausências explicadas e fonte oficial', `document.querySelector('aside').textContent.includes('Ainda não iniciado') && document.querySelector('aside').textContent.includes('Subsídio bruto mensal de referência') && !!document.querySelector('aside a[href*="tse.jus.br"]') && Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Ver aprovadas').disabled`);
await waitFor(`document.querySelector('aside').textContent.includes('Histórico legislativo')`);
await check('Histórico anterior separado da casa futura', `document.querySelector('aside').textContent.includes('Histórico legislativo · Câmara') && document.querySelector('aside').textContent.includes('2023-02-01 a 2026-10-05')`);
await check('Subsídio de referência com ressalva e fonte', `document.querySelector('aside').textContent.includes('46.366,19') && document.querySelector('aside').textContent.includes('Não comprova pagamento individual ou valor futuro') && !!document.querySelector('aside a[href*="salario-de-deputados"]')`);
await click('Ver projetos');await check('Lista de projetos com links oficiais', `document.querySelectorAll('aside a[href*="fichadetramitacao"]').length>0`);
await check('Despesas anteriores na Casa correta', `document.querySelector('aside').textContent.includes('Despesas históricas · Câmara') && document.querySelector('aside').textContent.includes('2026-01 a 2026-09')`);
await click('Ver despesas');await check('Detalhamento financeiro e fonte oficial', `document.querySelector('aside').textContent.includes('Por competência') && document.querySelector('aside').textContent.includes('Por categoria') && !!document.querySelector('aside a[href*="camara.leg.br/cotas/"]')`);
await click('Câmara');await check('Câmara: 513 cadeiras',`document.querySelectorAll('.seat').length===513`);
await evalJS(`document.querySelector('.seat').click()`);await wait();await check('Detalhe da Câmara',`!!document.querySelector('aside h2')`);
await evalJS(`Array.from(document.querySelectorAll('.chip')).find(b=>b.textContent.includes('PSOL')).click()`);await wait();
await evalJS(`Array.from(document.querySelectorAll('aside .row')).find(b=>b.textContent.toLowerCase().includes('duda salabert')).click()`);
await waitFor(`document.querySelector('aside').textContent.includes('Presença histórica · Câmara')`);
await click('Ver presença');await check('Presença diária com justificativas e relatório oficial',`document.querySelector('aside').textContent.includes('dias com presença') && document.querySelector('aside').textContent.includes('com ausência justificada') && !!document.querySelector('aside a[href*="presenca-plenario/2026"]')`);
await click('Dados');await check('Dados: 594 registros, 200 visíveis',`document.querySelector('main').textContent.includes('594 parlamentares') && Array.from(document.querySelectorAll('section:last-child tbody tr')).filter(x=>getComputedStyle(x).display!=='none').length===200`);
await check('Cobertura Senado confere com o índice publicado', `document.querySelector('main').textContent.includes(${JSON.stringify(expectedCoverage)}) && document.querySelector('main').textContent.includes('Cobertura global do projeto')`);
await check('Dados Senado: todas as conferências, com categorias separadas', `Array.from(document.querySelectorAll('table')).some(t=>t.querySelector('thead')?.textContent.includes('Comparecimento conferido (sem nominal)') && t.querySelectorAll('tbody tr').length===${expectedConferences})`);
await check('Cruzamentos históricos com soma parcial e cobertura', `document.querySelector('main').textContent.includes('Soma disponível') && document.querySelector('main').textContent.includes('de 149 parlamentares') && document.querySelector('main').textContent.includes('R$') && document.querySelector('main').textContent.includes('Conversões confirmadas')`);
await send('Emulation.setEmulatedMedia',{media:'print'});await check('Impressão inclui 594 resultados',`Array.from(document.querySelectorAll('section:last-child tbody tr')).filter(x=>getComputedStyle(x).display!=='none').length===594`);
await send('Emulation.setEmulatedMedia',{media:'screen'});
await evalJS(`window.__downloads=[];HTMLAnchorElement.prototype.click=function(){window.__downloads.push({name:this.download,url:this.href})}`);
await click('Exportar TXT');await click('Exportar XLS');await check('TXT e XLS incluem todos os registros',`(async()=>{const files=await Promise.all(window.__downloads.map(async d=>({name:d.name,body:await(await fetch(d.url)).text()})));return files.length===2 && files.every(d=>d.body.toLowerCase().includes('carol de toni') && d.body.includes('Pagamento individual ainda não integrado') && d.body.includes('referencia-bruta-mensal') && d.body.includes('totalCentavos') && d.body.includes('periodoInicio') && d.body.includes('https://dadosabertos.tse.jus.br') && d.body.split('\\n').length>=595)})()`);
await evalJS(`const input=document.querySelector('input');const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(input,'nao existe');input.dispatchEvent(new Event('input',{bubbles:true}))`);await wait();
await check('Busca vazia informa ausência de resultados',`document.querySelector('main').textContent.includes('Nenhum parlamentar encontrado')`);
await click('Mapa');await click('Dados');await check('Busca preservada ao navegar',`document.querySelector('input').value==='nao existe'`);
await click('Limpar filtros');await check('Limpar filtros restaura os resultados',`document.querySelector('main').textContent.includes('594 parlamentares')`);
for(const width of [375,640,768]){
 await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
 // A página Dados cresce com os históricos; capture a área visível, mantendo a checagem de largura de todo o documento.
 for(const tab of ['Mapa','Senado','Câmara','Dados']){await click(tab);await check(`${width}px: ${tab} sem overflow da página`,`document.documentElement.scrollWidth<=${width}`);if(width===375){await writeFile(`/tmp/painel-mobile-${tab}.png`,Buffer.from((await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})).data,'base64'));}}
}
// Falha HTTP: exibir erro sem fallback e recuperar pelo botão de tentativa.
const injection = await send('Page.addScriptToEvaluateOnNewDocument', {source:`window.__failData=true; const originalFetch=window.fetch; window.fetch=(...args)=>String(args[0]).endsWith('data.json') && window.__failData ? Promise.resolve(new Response('',{status:503})) : originalFetch(...args);`});
await send('Page.navigate',{url:process.env.APP_URL || 'http://127.0.0.1:5173'});await waitFor(`document.querySelector('main')?.textContent.includes('Dados oficiais indisponíveis')`);
await check('Falha HTTP sem dados simulados', `document.querySelector('main').textContent.includes('Dados oficiais indisponíveis') && document.querySelectorAll('.row').length===0`);
await evalJS('window.__failData=false');await click('Tentar novamente');await new Promise(r=>setTimeout(r,500));
await check('Recuperação dos dados oficiais', `document.querySelector('aside h2').textContent==='Santa Catarina'`);
await send('Page.removeScriptToEvaluateOnNewDocument',{identifier:injection.identifier});
const bad = await send('Page.addScriptToEvaluateOnNewDocument', {source:`const originalFetch=window.fetch; window.fetch=async(...args)=>{const response=await originalFetch(...args); if(!String(args[0]).endsWith('data.json'))return response; const data=await response.json(); data.senado[0].aprov=42; delete data.senado[0].indicadores; return new Response(JSON.stringify(data));};`});
await send('Page.navigate',{url:process.env.APP_URL || 'http://127.0.0.1:5173'});await waitFor(`document.querySelector('main')?.textContent.includes('Dados oficiais inválidos')`);
await check('Schema rejeita indicador sem fonte integrada', `document.querySelector('main').textContent.includes('Dados oficiais inválidos') && document.querySelectorAll('.row').length===0`);
await send('Page.removeScriptToEvaluateOnNewDocument',{identifier:bad.identifier});
await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
await send('Page.navigate',{url:process.env.APP_URL || 'http://127.0.0.1:5173'});await new Promise(r=>setTimeout(r,700));
if(errors.length)throw Error(JSON.stringify(errors));
console.log('PASS Sem exceções JavaScript');ws.close();
