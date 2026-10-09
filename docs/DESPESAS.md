# Despesas históricas de cota

Primeira coleta: 6/10/2026. Competências janeiro a setembro de 2026. São registros disponíveis na fonte, sujeitos a lançamentos tardios e ajustes; não representam o ano completo nem despesas do Congresso eleito para 2027.

354 registros da composição têm despesas vinculadas: 313 da Câmara e 41 do Senado. Em 18 casos, a Casa histórica difere da Casa da composição. A identificação usa exclusivamente vínculos oficiais já confirmados; nomes não são usados para vincular despesas. Ausência de registro ou vínculo não vira gasto zero.

## Fontes e cálculo

- Câmara: [arquivo anual CEAP](https://www.camara.leg.br/cotas/Ano-2026.csv.zip). Identificador `ideCadastro`, igual ao ID de deputado da API. Soma de `vlrLiquido` por `numAno`/`numMes`, incluindo créditos negativos. Não deduplicar por `ideDocumento`: há parcelas e ajustes referentes ao mesmo documento. `vlrRestituicao` é exibido separadamente, sem subtração adicional; o total é o débito registrado na cota, não uma estimativa de custo líquido final. [Definição oficial dos campos](https://dadosabertos.camara.leg.br/howtouse/2023-12-26-dados-ceap.html).
- Senado: [CEAPS por ano](https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/2026), `codSenador` corresponde ao código parlamentar. Soma de `valorReembolsado` por `ano`/`mes`, incluindo ajustes negativos. IDs de registros duplicados impedem publicação. Categoria ausente permanece explicitamente não informada.

Cálculo com Decimal, armazenamento de valores em centavos inteiros. Detalhes públicos incluem apenas totais, categorias, competências, número de registros e evidência. CPF, fornecedor e documentos privados não são copiados para o frontend.

## Operação

`npm run ingest:expenses` atualiza usando cache de uma hora; `npm run ingest:expenses -- --refresh` força consulta. `--start` e `--end` aceitam competências completas anteriores ao mês atual. O recorte padrão é fixo, não avança automaticamente.

SQLite schema 3: tabela `expenses`, preservada na republicação da composição. Fontes são validadas antes de persistir os históricos. Falha de consulta/schema mantém o índice público anterior. Cache inválido é descartado; arquivos brutos continuam privados em `var`.

O frontend carrega despesas junto dos detalhes sob demanda, com total, período, cobertura, coleta, abertura por mês/categoria e link oficial. Saldo mensal zero significa soma dos registros disponíveis, não ausência comprovada de gastos. O indicador `custo` continua nulo: a cobertura disponível não atende ao contrato de indicador completo. O cruzamento histórico mostra somas dos registros disponíveis, separadas por Casa/período/critério, com cobertura por grupo. TXT/XLS incluem os resumos históricos por parlamentar, seus períodos, fontes e cobertura; PDF inclui os cruzamentos visíveis.

Validação: testes de créditos negativos, restituições, competência, documentos repetidos, centavos, duplicação CEAPS, migração/persistência, contrato público e navegador.
