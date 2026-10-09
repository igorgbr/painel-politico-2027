# Painel Político 2027

**Versão beta no ar:** https://painel-politico-2027.pages.dev · [Envie seu feedback](https://docs.google.com/forms/d/1fXrBZAGG1jPIEsmI-PQ2etNhapi6CuMX64FTTf4Krow/viewform)

Código sob licença MIT ([LICENSE](LICENSE)). Os dados vêm de fontes públicas oficiais (TSE, Câmara dos Deputados e Senado Federal); o mapa usa svg-maps/brazil (CC BY 4.0). Erros nos dados podem ser relatados pelo formulário ou por issue.

Protótipo em React, Vite e TypeScript baseado em um protótipo do Claude Design (o HTML acompanha o projeto). A versão principal usa composição oficial: eleitos do TSE em 2026 e mandatos do Senado em continuidade até 2031. Histórico legislativo, despesas e fotos estão disponíveis para vínculos confirmados. Subsídio bruto de referência integrado; presença Câmara tem cobertura parcial. Senado tem recorte parcial de sessões conferidas, com painel agregado e cobertura explícita; assiduidade anual e faltas regimentais não estão concluídas. Pagamentos individuais ficam fora da v1. O modo demonstrativo é acessível explicitamente em `/?demo=1`.

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

O protótipo do Claude Design definiu a aparência inicial no desktop; o HTML define as interações. As fontes Archivo e Public Sans foram recuperadas dos assets incorporados no HTML, mantendo as fontes do protótipo disponíveis localmente. O crédito do mapa svg-maps/brazil (CC BY 4.0) permanece visível.

## Verificação no navegador

Com o servidor Vite ativo, inicie um navegador Chromium em modo headless e com perfil temporário:

```sh
chromium --headless --remote-debugging-port=9222 --user-data-dir=/tmp/painel-browser about:blank
node scripts/check-prototype.mjs
```

É possível usar Chrome ou Brave no lugar do Chromium. `CDP_URL` e `APP_URL` permitem alterar os endereços. O script verifica seleção de estado por teclado, navegação ao parlamentar, 81/513 cadeiras, indicadores indisponíveis, fontes oficiais, filtros, persistência da busca, exportações e impressão dos 594 registros. Também simula falha HTTP, recuperação e arquivo com indicador indevido. Também verifica overflow em 375, 640 e 768px e salva capturas da área visível em `/tmp/painel-*.png`.


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


## Preparar a publicação estática da v1

Node.js 24 e Python 3.10+ no computador de operação. O site publicado não precisa de Python ou banco. Na branch `main`, com as dependências instaladas:

```sh
npm ci
npm run release:check
npm run preview -- --host 127.0.0.1
```

`release:check` executa testes Python, contratos dos dados, build e inspeção do `dist/`: índice igual ao publicado, detalhes da versão correta, fotos locais presentes, somente arquivos públicos e no máximo dois snapshots. Exibe quantidade de arquivos, tamanho e maior arquivo para conferir os limites do provedor. Não faz ingestão nem deploy. Abra a URL indicada pelo preview e confira mapa, seleção de parlamentar, painel agregado Senado, Dados e exportações. O teste completo de navegador descrito acima também pode usar `APP_URL=http://127.0.0.1:4173` para testar o build.

Publique **todo o `dist/` na mesma implantação**, depois de todas as verificações passarem. `var/`, SQLite, cache, downloads brutos, relatórios privados e código Python ficam no computador de operação. A poda mantém o snapshot atual e um anterior por data de modificação; isso não é backup. Arquive privadamente cada pacote aprovado para poder restaurar uma publicação anterior.

## Cloudflare Pages: token e primeiro deploy

Hospedagem aprovada: **Cloudflare Pages com Direct Upload via Wrangler**, inicialmente no endereço `*.pages.dev`. Wrangler está fixado no `package-lock.json` e instalado por `npm ci`. O projeto remoto ainda depende da conta e do token fornecidos pelo operador.

1. No [painel Cloudflare](https://dash.cloudflare.com/), selecione sua conta, abra **API Tokens** (tokens da conta; também acessível pelo perfil em **My Profile → API Tokens**), clique **Create Token → Custom token / Get started**.
2. Nome sugerido: `painel-politico-pages-deploy`. Em **Permissions**, configure somente **Account → Cloudflare Pages → Edit**. Em **Account Resources**, selecione **Include → Specific account → sua conta**. Esta permissão vale para Pages nessa conta; não fica restrita a um projeto. Não são necessárias permissões de DNS, zonas, Workers, R2 ou a chave global da conta.
3. Clique **Continue to summary → Create Token** e guarde o token no seu gerenciador de senhas. Essa é a [permissão documentada para Direct Upload](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/).
4. Copie o **Account ID** na página **Workers & Pages**, conforme [localizar o ID da conta](https://developers.cloudflare.com/fundamentals/account/find-account-and-zone-ids/). Não é necessário adicionar um domínio.

Configure as variáveis **no terminal que executará Wrangler e `npm run deploy`**, não nas configurações de build do site. Em zsh, leia o token de forma oculta, sem colocá-lo no histórico do terminal:

```sh
read -rs 'CLOUDFLARE_API_TOKEN?Token Cloudflare: '
export CLOUDFLARE_API_TOKEN
export CLOUDFLARE_ACCOUNT_ID='SEU_ACCOUNT_ID_DE_32_CARACTERES'
export CLOUDFLARE_PAGES_PROJECT='painel-politico-2027'
```

O token fica apenas no ambiente dessa sessão. Não use prefixo `VITE_`, não grave em `.env`, scripts, README, configuração Wrangler ou arquivos versionados. Se houver CI no futuro, cadastre o token no cofre de secrets do executor e injete essas variáveis no processo; não no frontend. `.gitignore` também exclui arquivos locais de ambiente e `.wrangler/` como proteção adicional.

Crie o projeto **uma vez**, com branch de produção `main`, usando o Wrangler instalado:

```sh
npx --no-install wrangler pages project create "$CLOUDFLARE_PAGES_PROJECT" --production-branch main
```

Se o nome estiver ocupado, escolha outro e atualize `CLOUDFLARE_PAGES_PROJECT`. Para todas as publicações, depois de revisar os relatórios:

```sh
npm run deploy
```

O comando valida as três variáveis, executa `release:check` sem entregar o token aos testes/build e somente após sucesso envia todo o `dist/` com `wrangler pages deploy`, projeto explícito e `--branch main`. Não executa ingestão, não cria domínio e não pede login interativo. O projeto precisa existir; ausência de credenciais, falha de validação ou falha do Wrangler encerra com código diferente de zero. A URL será informada pelo Wrangler; o endereço estável de produção fica no painel do projeto em `*.pages.dev`.

`public/_headers` é copiado ao build: `no-cache` para `/`, `/index.html` e `/data.json`; `public, max-age=31536000, immutable` para `/assets/*`, `/data/snapshots/*` e `/photos/*`. `no-cache` permite armazenamento, exigindo revalidação. Cloudflare normaliza URLs HTML, por isso a raiz também recebe a regra. O preview Vite não aplica `_headers`; após o primeiro deploy, verifique `Cache-Control` com `curl -I` na raiz, no índice de dados e em um arquivo real de cada diretório imutável. [Formato oficial dos cabeçalhos](https://developers.cloudflare.com/pages/configuration/headers/).

Após usar o token, remova-o dessa sessão:

```sh
unset CLOUDFLARE_API_TOKEN
```

Para reverter o site, use **Workers & Pages → projeto → Deployments → publicação anterior de produção → Rollback**. Guarde também o pacote aprovado anterior em backup privado. A recuperação do site não restaura o SQLite local.

## Rotina de atualização dos dados da v1

Rotina proposta: uma execução semanal no computador de operação; ajuste a competência das despesas após cada fechamento mensal. Nenhum agendamento foi criado. Execute:

```sh
npm run update
```

`scripts/update.py` faz primeiro um backup consistente com a API SQLite, executa `PRAGMA quick_check` e guarda a cópia com permissão `0600` em `var/backups/` (diretório `0700`, ignorado pelo Git). Banco ausente, banco bloqueado por coletor ou falha no backup impedem a coleta. As cópias têm data UTC e nome único, não são podadas automaticamente. Preserve também `var/raw`, `var/cache`, os relatórios e o pacote aprovado anterior.

Depois do backup, executa em sequência os oito comandos: composição com refresh, histórico, despesas com refresh, presença Câmara, licenças Senado, perfis de fotos, cópias locais das fotos e `release:check`. Para no primeiro código de erro e **nunca executa deploy**. Um lock impede duas rotinas `update` simultâneas. Interrompa coletores individuais antes de iniciar e não os execute durante a rotina: o lock do banco protege cada etapa individual, não toda a sequência.

Padrões explícitos para repetir a v1: histórico de `2023-02-01` a `2026-10-05`, despesas de `2026-01-01` a `2026-09-30`, presença/licenças no ano `2026`. Para alterar somente os fins dos períodos:

```sh
npm run update -- --history-end 2026-10-09 --expenses-end 2026-09-30
```

O fim das despesas deve ser o último dia de um mês completo anterior ao atual. Datas futuras ou intervalos inválidos são rejeitados antes do backup. Não há avanço automático de períodos. Histórico usa cache de 24 horas; fotos reutilizam perfis por cache e preservam cópias existentes. Em 2027, revise o ano fixo e os critérios no script antes de executar: composição futura e histórico anterior continuam separados.

A rotina **não amplia as sessões conferidas do Senado**, não executa inventário nem edita o manifesto. Mantém o recorte parcial já publicado; atualização de licenças não reconcilia retroativamente as sessões. Novos recortes dependem de automação e validação próprias, fora desta rotina.

Revise os relatórios de composição, histórico, despesas, presença e licenças em `docs/`: datas das fontes, erros, vínculos e cobertura. Alguns coletores terminam com sucesso mesmo com cobertura parcial; compare com a publicação anterior e investigue quedas inesperadas. Não trate dado ausente como zero nem a data geral do índice como data de todas as fontes. Confira no preview que as pendências continuam visíveis.

Depois da revisão e dos testes, faça commit dos arquivos públicos, relatórios e documentação alterados na `main`. Execute `npm run deploy` e registre commit, snapshot, data e URL. Se os testes ou a revisão falharem, mantenha o site anterior; os coletores podem já ter alterado o estado local, portanto não use `--export-only` como rollback. Restaure o pacote aprovado anterior para reverter o site e o backup privado para recuperar a operação.

Para apenas reconstruir a publicação existente, use `npm run release:check`. Se precisar regenerar os arquivos a partir do banco sem consultar fontes, use `npm run ingest -- --export-only` antes; isso republica o estado armazenado, sem atualizar datas de coleta das evidências.
