# Subsídio de referência e presença histórica

Implementação de 6/10/2026. A composição continua sendo a de 2027; referências normativas e atividade anterior têm indicação própria de período e fonte.

## Subsídio

O [guia oficial da Câmara](https://www2.camara.leg.br/comunicacao/assessoria-de-imprensa/guia-para-jornalistas/salario-de-deputados) e o [Decreto Legislativo 172/2022](https://www2.camara.leg.br/legin/fed/decleg/2022/decretolegislativo-172-21-dezembro-2022-793529-publicacaooriginal-166604-pl.html) confirmam a referência bruta mensal de R$ 46.366,19, com vigência inicial em 1/2/2025, aplicável a deputados federais e senadores. O adaptador exige concordância entre guia e norma; mudança de vigência/formato exige revisão, sem preencher valor por suposição.

`subsidioReferencia` é uma referência normativa, com valor em centavos, vigência, data da verificação e fontes. Não é folha de pagamento, valor líquido, soma de benefícios ou promessa de remuneração em 2027. `salario` individual continua nulo até haver integração da folha. Cartões e tabela foram renomeados para explicitar essa diferença; TXT/XLS exportam também a evidência e o estado do pagamento individual.

## Presença Câmara

Fonte: `https://www.camara.leg.br/deputados/{id}/presenca-plenario/{ano}`, por identidade oficial já confirmada. A página separa a classificação por dia e as sessões daquele dia. O adaptador considera exclusivamente linhas diárias, preserva a situação original e confronta os totais com o resumo oficial.

Categorias: presença, ausência justificada, ausência não justificada e outras situações. Uma licença ou rótulo desconhecido não vira falta. Dias duplicados, identidade/ano divergentes, registros fora do período e contagem incompatível impedem publicação daquela consulta. Comissões e votos não entram nesse cálculo.

Primeira coleta: 104 consultas validadas entre 370 vínculos Câmara. 241 relatórios falharam na reconciliação de contagens e 25 responderam com erro HTTP 500. Uma tentativa complementar foi interrompida após bloqueio/expiração das consultas; a versão parcial permanece publicada. Nenhuma pendência foi preenchida com zero. A presença deve continuar identificada como cobertura parcial, sem concluir assiduidade da bancada inteira a partir desse subconjunto.

Recorte: 1/1/2026 a 6/10/2026, no período de exercício informado pela fonte. As justificativas podem ser atualizadas posteriormente, conforme explica o guia oficial da Câmara. O coletor preserva respostas completas no cache privado para conferência e reutilização; falhas não substituem históricos anteriores.

O frontend mostra contagens, período e coleta, botão “Ver presença”, lista diária e link oficial. Cruzamentos somam dias por parlamentar, separando Casa/período/critério e exibindo a cobertura. Históricos Câmara de um eleito para o Senado aparecem como Câmara. O indicador genérico `faltas` permanece nulo; o histórico distingue unidade e cobertura e não é transferido para o mandato futuro.

## Presença Senado

Primeiro recorte de comparecimento/participação integrado (sessão 120, 1–3/9/2026); assiduidade anual e faltas continuam pendentes. O [tutorial oficial de assiduidade](https://www12.senado.leg.br/assessoria-de-imprensa/guia-para-jornalistas/tutorial-de-verificacao-da-assiduidade-dos-senadores) exige conferir sessões, presenças e afastamentos/justificativas. Listas de votantes ou ausência em uma votação não comprovam falta injustificada. A reconciliação abaixo cobre somente uma sessão encerrada; o restante do ano e justificativas ainda sem comprovação permanecem pendentes.

## Operação

- `npm run ingest:attendance`: consulta referência e relatórios com até quatro trabalhadores e intervalo entre requisições. Timeout padrão de 15 segundos por requisição, configurável com `--timeout` de 1 a 60.
- `--year 2026`: ano do histórico; a referência de subsídio continua sendo a vigente na verificação.
- `--refresh`: força consulta; `--offline`: processa apenas arquivos disponíveis no cache. Cache de 24 horas. A coleta de cada histórico usa a data da resposta armazenada.
- SQLite schema 6: `reference_values` e `attendance`. A publicação da composição preserva ambos; detalhes mantêm dias, resumo mantém contagens/metadados. Sem nenhuma consulta de presença validada, a nova publicação é recusada.
- Cobertura e falhas: `docs/attendance-report.json`. Não executar simultaneamente com outros coletores do mesmo banco.

Validação: classificação diária, justificativas separadas, dias repetidos, período/identidade, conferência de totais, norma divergente, persistência, contrato público, cobertura parcial, exportações e navegador.

## Retomada de 6/10/2026

As 104 respostas disponíveis no cache foram revalidadas. As outras 266 consultas ainda precisam de nova resposta da fonte; os relatórios que haviam falhado na primeira reconciliação não estão no cache atual. O motivo da divergência não pôde ser confirmado sem esses documentos. A nova tentativa externa falhou por conexão em quatro consultas e interrompeu as demais, mantendo os 104 históricos publicados.

O coletor agora trabalha em lotes de quatro. Um lote inteiro com falhas de conexão interrompe novas chamadas; arquivos existentes continuam sendo validados. Erros HTTP e erros de validação permanecem separados. Divergências de contagem incluem resumo oficial, contagem extraída e distribuição dos rótulos originais, para investigar o problema sem relaxar a conferência. Respostas completas com divergência continuam preservadas no cache privado.

`npm run ingest:attendance -- --diagnose-only --timeout 5` consulta e registra `docs/attendance-attempt.json`, sem salvar históricos ou publicar nova versão. Adicionar `--offline` permite reprocessar apenas o cache. O relatório da tentativa é separado do relatório da última publicação. Períodos e datas de verificação respeitam as datas dos arquivos coletados, inclusive em reprocessamento offline.

Validação desta alteração: 33 testes Python, incluindo interrupção de chamadas durante queda da fonte, continuidade pelo cache, diagnóstico sem publicação e detalhes de divergência.

## Recuperação de 8/10/2026

A Câmara voltou a responder. As divergências foram investigadas com os documentos oficiais: “Missão Autorizada”, “Decisão da Mesa”, licenças para tratamento de saúde, maternidade e paternidade aparecem no resumo como ausências justificadas; o rótulo “Ausência” corresponde a ausência não justificada nas páginas reconciliadas. O adaptador preserva cada rótulo original e só publica quando todas as contagens conferem com o resumo da própria página. Rótulos novos ou resumos incompatíveis continuam impedindo a publicação; uma licença genérica não é classificada por suposição.

A cobertura passou de 104 para **322 consultas validadas entre 370 vínculos Câmara**, no recorte de 1/1 a 8/10/2026. As 48 pendências são: 23 páginas com mensagem explícita de ausência de dados em 2026 e 25 erros HTTP 500, inclusive na tentativa complementar. Não são preenchidas com zero. A mensagem de ausência de dados não prova motivo de afastamento nem ausência de mandato.

As **402 fotos oficiais vinculadas** também foram baixadas sem falhas e armazenadas em `public/photos`, com referência à fonte e data de coleta. A interface prioriza a cópia local.

## Primeira integração do Senado — 08/10/2026

Integradas **42 consultas de licenças oficiais, com 118 registros** no recorte de 01/01 a 08/10/2026. Duas respostas inicialmente retornaram HTTP 503; ambas responderam na tentativa complementar. Identidade conferida pelo `Parlamentar.Codigo`, vinculada aos códigos Senado já verificados. O serviço oficial documentado no Swagger é `/dadosabertos/senador/{codigo}/licencas`, versão 6, com parâmetros `dataInicio` e `dataFim`.

Esta é a primeira evidência da apuração do Senado, e **não conclui a integração de presença/faltas**. O [tutorial oficial](https://www12.senado.leg.br/assessoria-de-imprensa/guia-para-jornalistas/tutorial-de-verificacao-da-assiduidade-dos-senadores) exige cruzar comparecimento, votações e afastamentos/justificativas. Nos documentos pesquisados há sessões suspensas e retomadas com o mesmo painel; contar cada data ou sessão da agenda como oportunidade independente sem conferir a ata produz resultados incorretos. Os serviços de agenda e de encontro retornam planejamento, realização e pauta, mas os dados consultados não oferecem uma classificação diária consolidada de assiduidade. Os relatórios mensais atuais apresentam quantidades de requerimentos de licença, não uma tabela individual de faltas.

Os Diários oficiais foram pesquisados pelo calendário do portal. Os registros analisados de 01/09 e sua continuação de 02/09 exigem conferir o encerramento, o painel mantido e as justificativas. Nenhuma lista de comissão, inscrição como orador, presença em uma votação isolada ou ausência de licença foi convertida em falta ou presença plena. A etapa seguinte é obter e reconciliar o registro de comparecimento/voto do DSF por sessão encerrada, incluindo exercício e justificativas publicadas.

`licencasSenado` contém tipos e descrições oficiais, início/fim efetivos e previstos separados. Datas previstas não completam datas efetivas ausentes. Registros fora do recorte são excluídos; duplicação de código, identidade divergente e datas inválidas impedem publicação da consulta. Um resultado sem registros representa apenas uma consulta validada de licenças. Não prova ausência de faltas.

SQLite schema 7 adiciona `senate_licenses`; indicadores e históricos de presença permanecem separados. Detalhes guardam licenças; o índice guarda contagens, período, fonte e coleta. Cartões apresentam “Licenças e missões históricas · Senado”; a aba Dados lista consultas e exporta seus resumos com fontes. Os 322 históricos Câmara e as 402 fotos locais foram preservados.

Operação: `npm run ingest:senate-attendance`, com `--offline`, `--refresh` e `--year`; cache privado de 24 horas, quatro trabalhadores, um escritor por banco. Relatório: `docs/senate-attendance-report.json`, que mantém a assiduidade como pendente.

Validação: 40 testes Python, build, contratos de identidade/fontes/datas e teste prático dos cartões, missões oficiais, estados sem apuração, exportações e navegação.

## Primeiro recorte reconciliado do Senado — 08/10/2026

O [DSF de 4/9/2026](https://legis.senado.leg.br/diarios/ver/126579), páginas 55–56, registra **76 comparecimentos** na sessão deliberativa ordinária 120, legislatura 57 / sessão legislativa 874. A sessão começou em 1/9, foi suspensa/retomada e encerrou em 3/9: **uma sessão**, com duas votações nominais (7104 e 7105), não três oportunidades de presença. Os IDs de encontro mudam nas continuações e não são usados como sessões distintas.

Reconciliados **42 vínculos oficiais** existentes no projeto: 38 comparecimentos no DSF, **33 participações conferidas**, **cinco justificativas registradas**, **três pendências** e **um fora do exercício**. As quatro últimas categorias somam 42; comparecimento é uma evidência independente e não deve ser somado às categorias. Todos os períodos de exercício e consultas de licença foram conferidos. Duas falhas HTTP 503 na consulta de mandatos responderam na repetição.

O X de voto no DSF comprova participação em pelo menos uma votação. Para “participação conferida”, exige-se comparecimento no DSF e participação em todas as votações do recorte nas quais estava em exercício. Votações fora do exercício são excluídas da obrigação, inclusive na troca titular/suplente de Santa Catarina. “AP” é preservado como atividade parlamentar / justificativa registrada na votação, sem conclusão jurídica sobre falta ou assiduidade. Licenças só cobrem uma votação quando início **e fim efetivos** incluem a data; previsões e fins em aberto não completam essa prova. “P-NRV”, “NR”, “AUS”, “NCom”, códigos desconhecidos e ausência de registro sem evidência suficiente permanecem pendentes, nunca faltas não justificadas. Uma licença justificada não representa automaticamente comparecimento.

A primeira votação é secreta: publicamos apenas o registro público de participação “Votou”, jamais uma escolha individual. A segunda é aberta. Dados por votação, registros originais, página do Diário e exercício aparecem sob “Ver conferência da sessão”. Detalhes usam `comparecimentosSenado.sessoes`; o índice usa `resumosHistoricos.comparecimentosSenado`. `unidade: sessoes`, `cobertura: recorte-conferido`; `naoJustificada` e indicador genérico `faltas` continuam nulos. Dias Câmara permanecem separados. Dados, impressão e TXT/XLS incluem resumos com cobertura e fontes.

A associação dos nomes do DSF é somente à lista **oficial de votação (código Senado + nome + UF)**, com normalização de acentos/partículas e duas abreviações documentadas (“Astr.” e “Prof.”). Exige correspondência única, 76 registros únicos e reconciliação do rodapé; não cria vínculo candidato/parlamentar por nome. O conjunto das duas votações contém 82 identidades devido à troca de suplente. Identidades eleitorais continuam vinculadas pelas evidências anteriores.

Operação: `npm run ingest:senate-sessions`, `--offline` ou `--refresh`. Requer `pdftotext` (Poppler). Recorte deliberadamente fixo, com votos, número da sessão, períodos, páginas e contagens conferidos; expandir requer incluir e validar novos Diários encerrados. Fontes originais completas ficam no cache e em `var/artifacts`, com SHA-256, URL e data no SQLite. Não publicar os PDFs completos. A tabela `attendance` (schema 7) guarda cada Casa separadamente; o publicador separa dias Câmara de sessões Senado. Relatório: `docs/senate-sessions-report.json`; o relatório de licenças é independente.

**Ainda falta:** ampliar a cobertura de sessões encerradas e reconciliar justificativas publicadas posteriormente nos Diários para os casos pendentes. Este recorte não conclui presença ou assiduidade anual do Senado e não autoriza preencher faltas com zero. Validação: 49 testes Python, contratos dos 594 detalhes, build e navegador (incluindo fontes, voto secreto, exportações e telas móveis).

## Ampliação para três recortes e inventário anual — 08/10/2026

A publicação atual contém as sessões **111 (11/8), 113 (12/8) e 120 (1–3/9/2026)**, totalizando **126 conferências parlamentar/sessão para 42 vínculos**. São 117 comparecimentos registrados, 39 comparecimentos conferidos sem votação nominal, 64 participações conferidas nas sessões com nominais, cinco justificativas registradas, 13 conferências pendentes e cinco fora do exercício. Comparecimento registrado é evidência independente; as demais cinco categorias somam 126. Esses totais repetem pessoas entre sessões e não representam 126 parlamentares nem assiduidade anual.

O [DSF de 12/8](https://legis.senado.leg.br/diarios/ver/126278), páginas 110–111, registra 80 comparecimentos na sessão 111, encerrada às 20h02. A consulta oficial de votações de 11–13/8 não retorna nominal dessa sessão; o cadastro de identidades utilizado para associar nome + UF vem dos códigos oficiais nas votações da sessão 113. Confirma-se apenas comparecimento, com categoria `comparecimento-conferido` e contador `comparecimentosConferidos`, sem afirmar participação em nominal inexistente. Quem não consta no Diário e estava em exercício continua pendente; ausência na lista não é automaticamente falta não justificada.

O [DSF de 13/8](https://legis.senado.leg.br/diarios/ver/126338), páginas 101–102, registra 80 comparecimentos na sessão 113. As três nominais 7101/7102/7103 têm resultados Sim/Não/Presidente de 69/0/1, 61/2/1 e 43/20/1. São 31 participações conferidas, nove pendências e dois fora do exercício entre os vínculos do projeto. Há cinco campos de voto em branco no Diário, incluindo o presidente Davi Alcolumbre; a presidência está documentada nas três votações da API. Um X em presença não pode ser confundido com X de voto, nem participação em uma nominal com todas. O adaptador confere as posições de coluna verificadas, além de páginas, períodos, nomes/UF, código, contagens e resultados.

Os recortes agora têm manifesto compartilhado em `src/senate-recortes.json`, utilizado pelo coletor e pelos validadores do frontend. Somente sessões encerradas e fontes/contagens previamente conferidas entram nesse manifesto. A chave da tabela SQLite continua por pessoa/Casa/início; datas iniciais duplicadas no manifesto são rejeitadas para impedir sobrescrever sessões do mesmo dia. Para duas sessões distintas no mesmo dia, adaptar a chave ou agrupá-las explicitamente antes de habilitar a coleta. `--session 111`, `--session 113` e `--session 120` reprocessam um recorte; por padrão, todos os recortes conferidos são coletados.

A coleta usa o recurso **oficial de intervalo de páginas** (`paginaInicial`/`paginaFinal`), com tamanho e páginas impressas conferidos. Os três PDFs de registro somam aproximadamente 924 KB, sem baixar anexos completos a cada atualização. As respostas originais desse recurso ficam no cache/artefatos com URL exata, SHA-256 e data. Alteração de layout/colunas, contagem, identidade ou resultado bloqueia a publicação do recorte, preservando registros anteriores. O sigilo é protegido também na descrição textual: somente rótulos públicos de participação previamente conferidos são publicados; a direção de voto secreto não é propagada.

`npm run inventory:senate-sessions` consulta as agendas mensais de 2026 até a data local, deduplica sessões continuadas pelo número/legislatura/sessão legislativa/tipo e registra as que a agenda informa como realizadas e encerradas. Todos os dez meses de janeiro a outubro foram validados: **45 sessões identificadas**, das quais **três têm recortes conferidos**, restando 42 sessões no inventário. Agenda não comprova presença individual. Não chamar essa contagem de assiduidade ou cobertura de todos os senadores.

`npm run inventory:senate-sessions -- --offline --publish` publica a referência `coberturaSenado` somente com todos os meses validados. O publicador recalcula o número de sessões conferidas por IDs distintos, sem contar os 126 registros individuais como sessões. O indicador aparece na aba Dados, independente dos filtros, com período e dez fontes oficiais sob demanda. Metadados guardados em `reference_values` (schema 7); detalhes individuais, períodos Câmara, licenças e fotos preservados. Relatórios: `docs/senate-sessions-inventory.json` e `docs/senate-sessions-report.json`.

Também foram consultados os Diários [5/9](https://legis.senado.leg.br/diarios/ver/126538) e [11/9](https://legis.senado.leg.br/diarios/ver/126638). A leitura dos textos disponíveis não ofereceu comprovação suficiente para resolver Wellington Fagundes, Sergio Moro e Rogerio Marinho na sessão 120. Requerimento de justificativa não comprova deferimento; busca sem resultado não prova inexistência de justificativa. Auditoria em `docs/senate-justifications-audit.json`, com hash/data/fontes. Documentos sem texto e publicações posteriores ainda podem conter evidências adicionais.

A sessão 114 (13/8), identificada na agenda, continua sem extração/reconciliação verificável do registro e **não foi publicada**. O Diário completo inclui anexos muito extensos; não inferir falta da dificuldade de extração. As três sessões de outubro e as demais 38 do inventário também precisam de DSF e conferência. Pagamentos individuais e faltas regimentais continuam sem integração completa.

Validação: **54 testes Python**, contratos dos 594 detalhes e da referência de cobertura, build e navegador. Verificadas três nominais, sessão sem nominal, voto secreto, fontes, 126 linhas de conferência, indicação 3/45, fotos locais, exportações, impressão e 375/640/768 px.

## Cinco recortes conferidos — 09/10/2026

Integradas as sessões **106 (14/7) e 107 (15/7)**. O [DSF de 15/7](https://legis.senado.leg.br/diarios/ver/125698) confirma encerramento às 20h48 (p. 64) e 78 comparecimentos (pp. 65–66). As listas nominais da PEC 14/2021 nos dois turnos (pp. 143–148) confirmam, em cada votação, 73 Sim, um Não, uma Abstenção e um Presidente, total 76. São duas votações e uma sessão.

O [DSF de 16/7](https://legis.senado.leg.br/diarios/ver/125978) confirma encerramento às 19h25 (p. 79) e 76 comparecimentos (pp. 80–81; intervalo do painel até 20h00m59s, preservado como publicado). As três listas nominais do PLP 18/2021 (pp. 122–128) confirmam totais 68, 59 e 52, incluindo um Presidente em cada votação. Participação no texto principal não confirma participação nos destaques; quem não tem evidência suficiente em todos os votos aplicáveis permanece pendente.

A cobertura atual é **5/45 sessões identificadas**, **210 conferências para 42 vínculos**: 192 comparecimentos registrados (evidência independente); 39 comparecimentos sem nominal, 124 participações conferidas, oito justificativas registradas, 28 pendências e 11 fora do exercício. Essas últimas categorias somam 210. Restam 40 sessões no inventário. Agendas reprocessadas do cache até 09/10 com suas datas de consulta preservadas; não houve nova coleta das dez agendas nessa republicação.

O comando `npm run inspect:senate-diary` ajuda a localizar fontes sem baixar anexos completos: `--month`, `--diary` (sumário por padrão), `--pages INICIO FIM` (até vinte páginas), `--votes YYYY-MM-DD --end YYYY-MM-DD`, e `--offline`. Informa URL/hash/data do cache privado. Não publica indicadores. A inclusão no manifesto ainda exige conferência do encerramento, registro e resultados. Auditoria das fontes desta etapa: `docs/senate-july-audit.json`, com respostas originais preservadas em `var/artifacts`.

A sessão 114 teve suas páginas 57–58 localizadas e preservadas, mas a extração tem erros nos nomes/cabeçalhos; permanece sem publicação. O calendário oficial de outubro consultado em 09/10 mostra os Diários de 6–9 em elaboração: as sessões 128–130 ainda aguardam os documentos finais. Não inferir ausência da indisponibilidade da fonte.

Validação: **57 testes Python**, contratos dos 594 detalhes, build e navegador (sessões 106/107, 210 linhas, 5/45, fotos, fontes, exportações, impressão e telas móveis). Snapshot final `18e8d2fd3f41cb8a56db59c5`. Faltas regimentais, assiduidade anual e pagamentos individuais seguem sem integração completa.

## Oito sessões conferidas — 09/10/2026

Acrescentadas sessões sem nominal: **98 (7/7), 100 (8/7) e 102 (9/7)**. O [DSF de 8/7](https://legis.senado.leg.br/diarios/ver/125578) confirma encerramento às 18h30 (p. 78) e 80 comparecimentos (pp. 79–80); o [DSF de 9/7](https://legis.senado.leg.br/diarios/ver/125638) confirma encerramento às 18h39 (p. 90) e 76 comparecimentos (pp. 91–92); o [DSF de 10/7](https://legis.senado.leg.br/diarios/ver/125618) confirma encerramento às 16h05 (p. 28) e 68 comparecimentos (pp. 29–30). Os intervalos dos painéis até 20h00m59s foram preservados como publicados, sem apresentá-los como horário da ata.

A consulta de 7–9/7 não retorna nominais; os três Diários apresentam registro de comparecimento sem coluna de voto. A consulta ampliada de 7–15/7 confirma exatamente as cinco nominais das sessões 106/107 já conferidas e oferece os 81 códigos/nomes/UF oficiais para associação única aos registros DSF. O manifesto e os cinco recortes de julho passaram a usar essa consulta ampliada. As votações são filtradas pela sessão: comparecimento e justificativas posteriores não são transportados para as anteriores. Uma resposta vazia isolada, sem associação de identidades e conferência do Diário, não é aceita pelo coletor.

Acrescentadas **126 conferências** para 42 vínculos: 109 comparecimentos confirmados sem nominal, oito pendências e nove fora do exercício. A publicação totaliza **8/45 sessões identificadas e 336 conferências**: 301 comparecimentos registrados (evidência independente), 148 comparecimentos conferidos, 124 participações conferidas, oito justificativas registradas, 36 pendências e 20 fora do exercício. As cinco categorias de classificação somam 336; não representam pessoas distintas ou assiduidade anual.

Fontes e critérios da etapa em `docs/senate-july-presence-audit.json`, com URL/hash/data e originais preservados em artefatos privados. Inventário atualizado do cache, com datas de coleta preservadas. Restam **37 sessões sem recorte publicado**, além das conferências pendentes. Faltas regimentais e pagamentos individuais seguem incompletos.

Validação: **59 testes Python**, contratos dos 594 detalhes, build e navegador (três cartões sem nominal, 336 linhas, 8/45, fotos, fontes, exportações, impressão e telas móveis). Snapshot `419b42b4b248fe0102d7851c`.

## Doze sessões conferidas — 09/10/2026

Acrescentadas sessões **83 (16/6), 84 (17/6), 91 (30/6) e 93 (2/7, extraordinária)**. Os Diários confirmam encerramento e registros: [DSF de 17/6](https://legis.senado.leg.br/diarios/ver/125298), p. 94 e pp. 95–96, 75 comparecimentos; [DSF de 18/6](https://legis.senado.leg.br/diarios/ver/125318), p. 57 e pp. 58–59, 75 comparecimentos; [DSF de 1/7](https://legis.senado.leg.br/diarios/ver/125479), p. 85 e pp. 86–87, 79 comparecimentos; [DSF de 3/7](https://legis.senado.leg.br/diarios/ver/125478), p. 21 e pp. 22–23, 71 comparecimentos. Horários da ata e intervalos do painel foram preservados separadamente.

A sessão 83 teve uma nominal, 7095, do PLP 73/2025: 51 Sim, 17 Não, uma Abstenção e um Presidente, total 70, conferido com a lista impressa (pp. 104–106). Os códigos LS/LAP só produzem justificativa quando uma licença efetiva com início e fim cobre a data; sem essa prova permanecem pendentes. Datas previstas não são suficientes. Essa classificação não afirma presença nem resolve falta regimental.

As demais três sessões não têm nominal. A consulta de 16–17/6 fornece identidades oficiais para 83/84; a de 30/6–15/7 confirma as cinco nominais já conferidas de julho e fornece identidades para 91/93 e os recortes posteriores. Uma consulta limitada a 30/6–2/7 retorna vazia. O filtro por sessão impede atribuir votos vizinhos aos dias sem nominal. O cabeçalho da sessão extraordinária é validado contra `DEX`, enquanto a sessão legislativa do ano continua ordinária; tipos incompatíveis são rejeitados.

Agora são **12/45 sessões identificadas**, **504 conferências para 42 vínculos**: 444 comparecimentos registrados (evidência independente), 255 comparecimentos conferidos, 157 participações conferidas, 11 justificativas registradas, 49 pendências e 32 fora do exercício. As cinco categorias de classificação somam 504. Restam **33 sessões** do inventário. Assiduidade anual, faltas regimentais e pagamentos individuais permanecem incompletos.

Auditoria desta etapa: `docs/senate-june-july-audit.json`, com páginas, resultados e fontes originais preservadas por URL/hash/data. Agendas reprocessadas do cache com suas datas de consulta mantidas. Snapshot `f077c1663dd88ebea1aa3712`. **62 testes Python**, contratos dos 594 detalhes, build e navegador aprovados, incluindo sessão extraordinária, licenças com datas efetivas, 504 linhas, 12/45, fotos, exportações, impressão e telas móveis.
