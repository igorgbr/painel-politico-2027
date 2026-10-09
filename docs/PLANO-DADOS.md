# Integração de dados oficiais

Pesquisa inicial: 5/out/2026. Recorte confirmado pelo usuário: Congresso eleito para 2027, com histórico anterior identificado. Preservar o visual e os fluxos aprovados.

## Primeira entrega proposta

Substituir os nomes fictícios e as bancadas fixas por uma composição derivada de registros oficiais, contendo nome, casa, UF, partido, mandato, identificação na fonte e link de consulta. Indicadores ainda não integrados devem aparecer como indisponíveis, sem números simulados junto aos registros reais.

A composição de 2027 deve combinar deputados e senadores eleitos em 2026 com as cadeiras do Senado cujo mandato continua em 2027. Resolver titularidade, suplência, afastamentos e eventuais decisões eleitorais de forma explícita; a lista de parlamentares atualmente em exercício não equivale à lista de eleitos. Partido na eleição e partido atual devem ser campos separados.

Não usar as bancadas SEN/CAM do protótipo como verdade oficial. Calcular contagens, legendas, cadeiras e totais por estado a partir do conjunto importado e validado. Não completar lacunas com dados fictícios.

## Fontes e estado de verificação

| Fonte | Recurso | Verificação inicial |
| --- | --- | --- |
| Senado | https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json | JSON consultado; descreve parlamentares atualmente em exercício, não eleitos para 2027 |
| Senado | https://legis.senado.leg.br/dadosabertos/docs/ | Documentação acessível; redireciona para Swagger |
| Câmara | https://dadosabertos.camara.leg.br/api/v2/api-docs | Especificação JSON consultada |
| Câmara | `/api/v2/deputados`, `/deputados/{id}`, `/deputados/{id}/historico` | Documentados; chamadas de teste à listagem não foram acessíveis pelo navegador de pesquisa; validar por HTTP na implementação |
| Câmara | `/api/v2/deputados/{id}/despesas` | Documentado; despesas de cota, não custo completo de gabinete |
| Câmara | `/api/v2/proposicoes?idDeputadoAutor={id}`, `/proposicoes/{id}/autores`, `/proposicoes/{id}/tramitacoes`, `/proposicoes/{id}/votacoes` | Documentados; autoria, situação e votação exigem tratamentos distintos |
| TSE | https://dadosabertos.tse.jus.br/dataset/candidatos-2026 | Catálogo acessível com arquivos de candidatos e informações complementares; conteúdo dos arquivos e situação eleitoral ainda precisam ser validados |
| Senado/CEAPS | https://www12.senado.leg.br/dados-abertos/administrativo/senadores/cotas-para-exercicio-da-atividade-parlamentar | Catálogo confirmado; endpoint de despesas não validado nesta pesquisa |
| Câmara/salário e gastos | https://www.camara.leg.br/transparencia/gastos-parlamentares | Página oficial distingue salário, verba de gabinete e demais despesas |

O catálogo de candidaturas não comprova eleição por si só. Descobrir recursos oficiais de resultado/situação, registrar data de geração e verificar seu conteúdo antes de publicar a composição. Resultado eleitoral pode ter atualização ou pendência; manter situação e fonte junto ao registro.

## Critérios propostos para os indicadores

Critérios aceitos pelo usuário ao autorizar a continuação. A composição foi integrada primeiro; os indicadores abaixo ainda aguardam implementação.

- Produção legislativa: contar projetos de autoria/coautoria, deduplicados por identificador oficial. Exibir os projetos com link e situação individual.
- Substituir “Leis aprovadas” por “Projetos convertidos em lei” quando houver vínculo oficial à norma publicada. Aprovação em comissão ou em apenas uma casa não satisfaz esse critério.
- Substituir “Leis negadas” por “Projetos rejeitados”, apenas com rejeição formal identificada. Arquivamento, retirada, prejudicialidade e tramitação em curso são situações separadas.
- Votos do parlamentar devem ser um indicador separado de autoria. Votar sim em uma proposta não transforma o parlamentar em autor da lei.
- Remover/reformular a taxa de aprovação atual: sem regras de universo e período, ela mistura resultados legislativos diferentes. Se mantida, declarar fórmula e cobertura; não calcular quando os dados forem incompletos.
- Gastos: começar com despesas efetivamente registradas na cota parlamentar e nomear o card conforme essa cobertura. Verba de gabinete, salário e outras rubricas são integrações separadas. Não chamar apenas a cota de “custo anual (gabinete + cota)”.
- Exibir o intervalo consultado. Para 2026 incompleto, usar “acumulado de 2026 até [data]”; não extrapolar o valor anual.
- Faltas injustificadas: integrar somente quando a fonte permitir distinguir ausência justificada, licença e outras situações. Ausência em votação, isoladamente, não comprova falta injustificada.
- Histórico: associar cada indicador à casa, ao mandato e ao período efetivamente exercido. Um eleito que troca de casa não herda indicadores do cargo anterior como se fossem de 2027.
- Sem histórico localizado deve aparecer como indisponível ou sem mandato anterior identificado. Zero só é válido após consulta completa para o período indicado.

## Modelo e processamento

Evoluir `Member` para permitir indicadores nulos e incluir IDs oficiais, situação eleitoral/exercício e fontes. Separar identidade da pessoa, candidatura, cadeira e exercício de mandato. Não cruzar bases apenas por nome nem publicar documentos pessoais para realizar o vínculo.

Guardar metadados do conjunto: versão do schema, recorte, data de coleta, fontes, cobertura e pendências. Cada indicador deve guardar período, unidade, cobertura e referência oficial. Manter proposições e seus resultados no arquivo; `laws()` não deve fabricar projetos para registros reais.

Um script de ingestão gera `public/data.json`. O frontend carrega esse arquivo, evitando centenas de chamadas às APIs a cada visita. Tratar paginação, limites, retentativas e falhas parciais. Validar antes de substituir o último conjunto válido, com escrita atômica. Nunca trocar silenciosamente um conjunto real por dados simulados em caso de erro.

## Ordem de execução

1. Validar arquivos TSE e mandatos que continuam no Senado; gerar composição oficial e relatório de pendências.
2. Integrar carregamento e tratamento de indisponibilidade no frontend; derivar bancadas e contagens da composição.
3. Integrar histórico de proposições com os critérios acordados.
4. Integrar despesas de cota por período, depois rubricas adicionais e presença quando suas fontes forem verificadas.
5. Automatizar atualização, mantendo data de coleta, último conjunto válido e relatório de qualidade.

## Verificações necessárias

- Identificadores únicos, UF/casa válidas, mandato consistente, partidos conhecidos ou com cor neutra e fontes presentes.
- Nenhuma candidatura não eleita incluída como eleita; nenhuma suplência duplicando a mesma cadeira.
- Contagens por UF/casa confrontadas com vagas oficiais do recorte, sem preencher automaticamente diferenças.
- Paginação completa, projetos deduplicados e despesas sem duplicação de lançamentos/reembolsos.
- Indicadores ausentes não entram nos totais como zero; agregações informam cobertura.
- Navegação, filtros, cadeiras, exportações e impressão preservam as funcionalidades aprovadas e mostram período e fonte.

## Entrega da composição

Implementada em 5/out/2026. Arquivo TSE validado: 513 deputados federais e 54 senadores com situação de eleitos, excluindo suplentes eleitorais. Senado: 27 mandatos até 2031, incluindo dois ocupantes suplentes identificados na coleta. Composição validada por UF e casa.

`npm run ingest` atualiza a composição e `docs/ingest-report.json` registra o resumo. A implementação usa Python com biblioteca padrão para ler ZIP/CSV sem novas dependências. O frontend carrega e valida `public/data.json`, calcula bancadas e diferencia indisponibilidade de zero. A próxima entrega é o histórico legislativo, seguida de despesas e presença conforme as fontes forem verificadas.
