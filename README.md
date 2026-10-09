# Painel Político 2027

Protótipo em React, Vite e TypeScript baseado no PDF e no HTML do Claude Design que acompanham o projeto. A versão principal usa composição oficial: eleitos do TSE em 2026 e mandatos do Senado em continuidade até 2031. Histórico legislativo, despesas e fotos estão disponíveis para vínculos confirmados. Subsídio bruto de referência integrado; presença Câmara tem cobertura parcial. Pagamentos individuais e presença Senado seguem pendentes. O modo demonstrativo é acessível explicitamente em `/?demo=1`.

## Executar

```sh
npm ci
npm run dev
```

Abra http://localhost:5173. Para compilar: `npm run build`.

## Arquitetura

Ingestão modular em Python, SQLite privado e publicação estática com resumo e detalhes por versão. O frontend carrega detalhes ao selecionar um parlamentar. Veja [docs/ARQUITETURA.md](docs/ARQUITETURA.md) para modelo, identidades, cache, recuperação e atualização em produção.

## Atualizar a composição oficial

Requer Python 3.10+ (biblioteca padrão; nenhuma dependência adicional).

```sh
npm run ingest
npm run test:data
npm run test:contract
```

A ingestão baixa o ZIP nacional de candidaturas de 2026 do TSE e o JSON de senadores em exercício. Seleciona apenas deputados federais/senadores eleitos e acrescenta os mandatos 2023–2031. Exclui suplentes eleitorais e candidatos não eleitos. Os dados validados são armazenados em SQLite e os detalhes publicados por versão. As contagens são verificadas por estado antes de substituir `public/data.json` de forma atômica. Em caso de falha, o último conjunto permanece disponível e o diagnóstico fica em `docs/ingest-report.json`.

Para importar downloads oficiais locais:

```sh
npm run ingest -- --tse-zip /caminho/consulta_cand_2026.zip --senado-json /caminho/senado.json
```

O conjunto publicado contém fonte, identificador público, data de geração/coleta e distinção entre partido na eleição e partido na coleta. Não contém CPF, e-mail nem nascimento. As fontes são registradas com SHA-256 para auditoria dos arquivos usados e os arquivos brutos ficam privados em `var/raw`. SQLite fica em `var/painel.sqlite3`.

**Composição ainda sujeita a alterações:** as 27 cadeiras do Senado em continuidade mostram o ocupante em exercício na coleta. Há duas suplências: Jussara Lima (PI) e Lourdinha Pereira (MA), conforme o cadastro consultado. Isso não garante o ocupante da cadeira em fevereiro de 2027. Cada detalhe informa a situação e a fonte.

As bancadas, cores disponíveis e totais são calculados dos dados carregados; partidos sem cor no protótipo usam cor neutra. Indicadores não integrados são nulos e exibidos como “Indisponível”; nunca são somados como zero. TXT/XLS incluem situação, fonte, datas e observação de histórico. O carregamento falha explicitamente se o schema for inválido, sem retorno automático aos dados demonstrativos.

## Funcionalidades

- Mapa por estado, com grade no celular e navegação para o parlamentar.
- Senado e Câmara com cadeiras, filtros por partido e detalhes dos parlamentares.
- Busca, filtros, agrupamentos, ordenação e exportação na tela Dados.
- PDF usa a impressão do navegador: selecione **Salvar como PDF**. Todos os resultados filtrados são incluídos, mesmo quando a tela mostra apenas 200.
- TXT e XLS exportam todos os resultados filtrados. O XLS é texto tabulado compatível com planilhas; alguns aplicativos exibem aviso sobre a extensão.

## Referências visuais

O PDF define a aparência inicial no desktop; o HTML define as interações. As fontes Archivo e Public Sans foram recuperadas dos assets incorporados no HTML, mantendo as fontes do protótipo disponíveis localmente. O crédito do mapa svg-maps/brazil (CC BY 4.0) permanece visível.

## Verificação no navegador

Com o servidor Vite ativo, inicie um navegador Chromium em modo headless e com perfil temporário:

```sh
chromium --headless --remote-debugging-port=9222 --user-data-dir=/tmp/painel-browser about:blank
node scripts/check-prototype.mjs
```

É possível usar Chrome ou Brave no lugar do Chromium. `CDP_URL` e `APP_URL` permitem alterar os endereços. O script verifica seleção de estado por teclado, navegação ao parlamentar, 81/513 cadeiras, indicadores indisponíveis, fontes oficiais, filtros, persistência da busca, exportações e impressão dos 594 registros. Também simula falha HTTP, recuperação e arquivo com indicador indevido. Também verifica overflow em 375, 640 e 768px e salva capturas da área visível em `/tmp/painel-*.png`.

Para a integração futura com dados oficiais, veja HANDOFF.md.

Use `npm run ingest -- --refresh` para ignorar o cache de uma hora e `npm run ingest -- --export-only` para republicar do SQLite sem acessar a rede. `--db` e `--cache` permitem diretórios alternativos. A ingestão permite uma execução por banco por vez no Linux. Para produção, gerar e publicar todo `dist/`, incluindo os detalhes; nenhuma hospedagem ou rotina externa foi configurada nesta etapa.

## Histórico legislativo

`npm run ingest:history` coleta PL/PLP de autoria/coautoria, com identidade verificada, para o período 1/fev/2023–5/out/2026. Listas são separadas por casa; situação e links oficiais aparecem ao selecionar o parlamentar e clicar em **Ver projetos**. Após a coleta complementar, são 402 registros com histórico disponível e 192 sem vínculo confirmado. Foram confirmadas 89 referências de norma ausentes no arquivo; cinco permanecem pendentes. Não interpretar pendência como ausência de atuação.

Veja [docs/HISTORICO-LEGISLATIVO.md](docs/HISTORICO-LEGISLATIVO.md) para critérios, cobertura, fontes, limitações e opções de execução.
# Despesas históricas

As despesas de cota de janeiro a setembro de 2026 estão disponíveis nos detalhes dos parlamentares com identidade confirmada, separadas por Casa. Atualização: `npm run ingest:expenses`; consulta forçada: `npm run ingest:expenses -- --refresh`. Consulte [critério, cobertura e operação](docs/DESPESAS.md).
# Subsídio e presença

Atualização: `npm run ingest:attendance`. Subsídio de referência e presença diária têm conceitos e coberturas próprios; veja [critérios, cobertura parcial e operação](docs/SUBSIDIO-PRESENCA.md).

Licenças e missões do Senado: `npm run ingest:senate-attendance` integra registros oficiais de identidades já verificadas. `npm run ingest:senate-sessions` reconcilia doze recortes: sessões 83 (16/6), 84 (17/6), 91 (30/6), 93 (2/7, extraordinária), 98 (7/7), 100 (8/7), 102 (9/7), 106 (14/7), 107 (15/7), 111 (11/8), 113 (12/8) e 120 (1–3/9/2026), com DSF, todas as nominais, exercício e licenças efetivas. Requer `pdftotext`; `--session` seleciona um recorte. `npm run inventory:senate-sessions` registra a agenda anual; `--publish` publica a referência após validar todos os meses. São **12 de 45 sessões identificadas**, com **504 conferências para 42 vínculos**. Assiduidade anual e faltas permanecem pendentes. Detalhes em [docs/SUBSIDIO-PRESENCA.md](docs/SUBSIDIO-PRESENCA.md).

`npm run inspect:senate-diary -- --month 7` consulta o calendário oficial; `--diary 125698` baixa somente o sumário; `--diary 125698 --pages 65 66` consulta um intervalo de até vinte páginas; `--votes 2026-07-14 --end 2026-07-15` consulta votações. Aceita `--offline`. Esse comando prepara a conferência, informa URL/hash/data e guarda respostas no cache privado; não publica indicadores nem cadastra recortes automaticamente.
