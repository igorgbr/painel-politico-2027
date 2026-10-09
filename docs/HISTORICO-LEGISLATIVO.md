# Histórico legislativo anterior

Recorte implementado: PL e PLP de autoria/coautoria apresentados entre **1/fev/2023 e 5/out/2026**, com situação observada na coleta. A situação atual não reconstrói como o projeto estava em cada data passada.

## Cobertura da primeira execução

- 361 vínculos confirmados com registros da Câmara.
- 14 vínculos eleitorais confirmados com registros do Senado, somados a 27 identidades próprias dos mandatos em continuidade.
- 361 históricos da Câmara e 41 do Senado, disponíveis em 393 dos 594 registros da composição. Alguns têm histórico nas duas casas.
- 201 registros permanecem sem vínculo ou consulta completa confirmados. Isso não prova ausência de mandato anterior ou de projetos.
- Nenhuma consulta individual de perfil da Câmara nem de histórico do Senado falhou nesta execução. Detalhes em `docs/history-report.json`.

## Identidades

Na Câmara, o nome civil e a correspondência privada de CPF na CEAP servem apenas para selecionar perfis candidatos à comparação. A confirmação exige um identificador civil válido coincidente em TSE/Câmara e uma única correspondência. O valor pessoal permanece no processamento/cache privado, fora do JSON público e do relatório.

No Senado, a confirmação exige coincidência de nome civil completo, nascimento e UF de naturalidade, com correspondência única. Esses valores pessoais não são exportados. Para os 27 ocupantes de mandatos em continuidade, o ID do Senado já vem da própria composição oficial.

Vínculos são registrados em `identity_evidence`, com método e URLs oficiais, sem valores pessoais. Uma identidade já associada a outra pessoa gera conflito; a rotina não faz fusão automática. A busca inicial de perfis da Câmara por nome civil pode deixar de encontrar uma pessoa cujo nome cadastral mudou; o relatório de pendências deve continuar explícito.

## Fontes

- [Câmara — arquivos de proposições e autores](https://dadosabertos.camara.leg.br/swagger/api.html?tab=staticfile): arquivos CSV de 2023–2026, filtrados por data de apresentação e PL/PLP; IDs de proposição e de autoria deduplicados. Os arquivos podem incluir proposições relacionadas de outros anos, por isso o filtro de datas é aplicado ao conteúdo.
- [Câmara — API](https://dadosabertos.camara.leg.br/swagger/api.html): perfis individuais para verificar identidade.
- [Senado — API atual](https://legis.senado.leg.br/dadosabertos/docs/): `/processo.json?codigoParlamentarAutor=...&sigla=PL|PLP&dataInicioApresentacao=...&dataFimApresentacao=...`. O endpoint antigo `/senador/{id}/autorias.json` está depreciado e não é usado para coleta de projetos.

## Classificação e limites

Conversão em lei exige referência oficial à norma. Na Câmara: situação “Transformado em Norma Jurídica” e URN de lei federal em `urnFinal`, ou referência explícita à lei no despacho de transformação do próprio projeto. Eventos históricos exigem código de transformação 251 e referência unívoca; uma simples menção à lei não basta. No Senado: `normaGerada` identificando uma lei. Aprovação em comissão ou em uma casa não é conversão em lei.

Rejeição exige situação expressa de rejeição; arquivamento, retirada e demais situações ficam separados. Isso é uma classificação da situação observada na coleta, não uma contagem de todo evento histórico de rejeição.

Alguns projetos da Câmara têm situação “Transformado em Norma Jurídica”, mas o arquivo não fornece referência à lei. Eles aparecem com a situação original na lista e não entram em conversões confirmadas. Quando faltam referências ou situações, os cartões mostram as contagens mínimas confirmadas com aviso de pendência; a proporção exata permanece sem confirmação.

A proporção exibida considera apenas conversões e rejeições classificadas, excluindo projetos em tramitação e outras situações. O denominador vazio aparece como indisponível. Casas, períodos e critérios diferentes não são agregados.

Histórico de deputado de alguém eleito senador aparece em seção **Câmara** e não preenche os indicadores do Senado. O número de projetos corresponde ao universo consultado, não à quantidade de leis sancionadas durante o período.

## Operação

```sh
npm run ingest:history
```

Opções: `--db`, `--cache`, `--output`, `--start AAAA-MM-DD`, `--end AAAA-MM-DD`, `--workers 1..4`. O período padrão termina em 5/out/2026 para manter o recorte aprovado; definir explicitamente a data ao expandi-lo.

Cache privado de 24 horas permite retomar/reexecutar sem repetir consultas concluídas. Requisições têm espaçamento e até quatro trabalhadores; gravações SQLite permanecem em um único escritor. Os arquivos brutos de composição precisam existir no armazenamento privado para verificar identidades.

Históricos completos são armazenados por pessoa/casa/período. Indicadores derivados ficam em `indicators`, com cobertura. Falha em um histórico do Senado preserva o histórico anterior daquela pessoa, com sua data original. Falha na coleta dos arquivos da Câmara impede nova publicação; o índice anterior permanece disponível, e fontes já processadas ficam em cache para retomar.

A publicação da composição reaproveita vínculos/históricos confirmados no banco: atualizar nomes e bancadas não apaga o histórico. Detalhes completos são carregados sob demanda no frontend, com filtros por situação e expansão em blocos de 50 projetos.

## Ampliação da cobertura

Coleta complementar de 6/10/2026: 370 vínculos Câmara e 15 vínculos eleitorais Senado, além dos 27 mandatos em continuidade. São 370 históricos Câmara e 42 Senado em 402 registros da composição; 192 permanecem sem vínculo confirmado. Não classificamos esses casos como primeiro mandato ou ausência de atuação sem evidência.

A CEAP revelou nove correspondências de CPF não encontradas pela seleção inicial de nome civil; cada vínculo foi confirmado novamente no perfil parlamentar, com CPF válido e único. No Senado, o catálogo da legislatura 57 substituiu o recorte apenas de parlamentares em exercício, acrescentando um vínculo histórico de pessoa já identificada na Câmara.

Foram consultados 94 projetos únicos sem referência de norma no arquivo. A API individual e os eventos formais de transformação confirmaram 89; cinco ficaram pendentes. O relatório `history-report.json` lista pendências de identidade e norma, com motivo e fontes, sem dados pessoais usados na comparação. Não confundir 89 projetos com 89 leis únicas: substitutivos/coautorias exigem leitura da referência.

SQLite schema 5: `norms` preserva referência, fonte oficial e data da verificação. Reimportar o arquivo sem URN não apaga uma confirmação válida; resultados são reaplicados somente a projetos com situação de transformação. Listas públicas incluem `fonteNorma` e `normaVerificadaEm`; o protótipo mostra o link “Confirmação oficial”. A situação original e a verificação complementar têm datas próprias.

Quando a situação da API diverge do arquivo, o projeto permanece sem resultado confirmado e recebe observação explícita, fonte e data da verificação. A divergência não é convertida em aprovação ou rejeição. A coleta complementar encontrou um caso entre as cinco referências pendentes.

Pendentes: salário/presença; 192 identidades sem vínculo; cinco referências de norma; ampliação para catálogos adicionais quando houver evidência oficial. Despesas e fotos já aproveitam os novos vínculos.
