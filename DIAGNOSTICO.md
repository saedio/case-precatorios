# Diagnóstico, prevenção e dúvidas

Escopo: `case/dados/` (pagamentos.json, tribunal.csv, hub.csv, apresentacoes.json), `case/DOCUMENTACAO_TRIBUNAL.md` (v2.1), `case/schema.sql` e o fluxo descrito em `case/ENUNCIADO.md`.

Convenções: "linha" é a linha do arquivo onde o registro começa. Números de reais foram recalculados pelo código deste repositório (`saida/relatorio.md`). Quando algo é hipótese e não fato dos dados, está escrito "hipótese". Ordem: do mais grave ao menos grave. "Causa" e "consequência" ligam os itens entre si; o mapa está no fim do bloco.

## 1. Diagnóstico

### P1. A importação soma sem chave de idempotência e sem versão do evento (causa)

**Evidência**
- `ev-002` aparece duas vezes idêntico (pagamentos.json linhas 10 e 26).
- `ev-001` aparece com dois valores: R$ 15.000,00 (linha 2, `atualizado_em` 10/03 10h) e R$ 15.500,00 (linha 66, `atualizado_em` 11/03 09h). A segunda é uma correção da primeira.
- `schema.sql`: `pagamento` não tem `UNIQUE (evento_id)` nem `atualizado_em`. O banco aceita a mesma linha quantas vezes ela chegar.
- Fluxo, itens 1 e 2: o arquivo traz "os últimos 7 dias" todo dia, então um evento chega em vários arquivos seguidos, e o script "soma cada valor". A reexecução com "o mesmo arquivo" soma tudo de novo.

**Impacto**
- Somando tudo que o arquivo traz, o processo 0012345-10.2019.8.26.0053 fica com R$ 35.501,00 pagos. O correto é R$ 18.000,50 (15.500,00 + 2.500,50). Diferença: R$ 17.500,50 (97%).
- No arquivo inteiro, a soma bruta dos valores é R$ 62.251,00 contra R$ 34.200,50 na base limpa. Da diferença de R$ 28.050,50, R$ 17.500,50 vêm de duplicata e correção somadas (este item), R$ 10.000,00 de estorno somado como pagamento (P4) e R$ 550,00 de eventos inválidos (P2).
- Em produção o erro cresce a cada sobreposição de janela e a cada reexecução.

**Relação:** causa direta de "os números não batem". É agravado por P2 (falha no meio do arquivo leva à reexecução, que duplica a primeira metade).

### P2. Falhas são engolidas em silêncio e a importação não é atômica (causa, e esconde todo o resto)

**Evidência**
- Fluxo, item 5: "o script ignora e segue. Ninguém é avisado".
- Quatro dos 11 eventos distintos não conseguem entrar no banco como estão:
  - `ev-004` (linha 34): `valor` null, viola `NOT NULL`.
  - `ev-009` (linha 82): `valor` -200 em evento `pagamento`, viola `CHECK (valor > 0)`.
  - `ev-010` (linha 90): `processo` vazio, não resolve a FK.
  - `ev-005` (linha 42): processo escrito sem máscara (`00234562120208260053`), não casa com o precatório 0023456-21.2020.8.26.0053 (ver P6).
- Fluxo, item 2: o operador roda de novo "quando a importação falha no meio". Não há transação nem registro do que já entrou.

**Impacto**
- Perdas sem rastro: R$ 1.200,00 do `ev-005` somem do total do 0023456 (o certo é R$ 9.200,00, o sistema teria R$ 8.000,00), R$ 750,00 do `ev-010` não pertencem a processo nenhum, e `ev-004` e `ev-009` têm valor desconhecido ou suspeito.
- Ninguém consegue responder "onde e por quê", que é exatamente a pergunta da operação. Esse é o motivo de este item vir logo depois de P1.

**Relação:** causa da invisibilidade de P1, P4 e P6. Consequência de P6 e P8, porque dado fora do padrão faz o script falhar.

### P3. Prazo de pagamento errado no hub, e prazo fora do banco (independente; exposição jurídica)

Regra: apresentado até 2 de abril (inclusive) do ano X, prazo 31/12 de X+1. Depois, 31/12 de X+2.

**Evidência** (hub.csv, comparado com `apresentacoes.json`, que concorda com o hub nas datas):

| Processo | apresentado_em | Prazo no hub | Prazo pela regra |
|---|---|---|---|
| 0012345-10.2019.8.26.0053 | 2025-04-02 (só data) | 2027-12-31 | **2026-12-31** |
| 0045678-43.2021.5.02.0011 | 2025-04-02T23:30-03:00 | 2026-12-31 | 2026-12-31 |
| 0056789-54.2017.4.03.6100 | 2025-04-03T01:00Z (= 2/abr 22h em Brasília) | 2027-12-31 | **2026-12-31** |
| 0067890-65.2016.8.26.0053 | 2023-12-31 | **ausente do hub** | 2025-12-31 |

Os três casos de fronteira (2/abr só data, 2/abr com offset, 3/abr em UTC) deveriam dar o mesmo prazo e deram 2027, 2026 e 2027. O hub não segue uma regra única. Não consegui reconstruir a lógica pelos dados. Hipótese: a data é tratada de formas diferentes conforme o formato de entrada (só data, offset, `Z`).

Além disso, `schema.sql` não tem `apresentado_em` nem `prazo_pagamento`. O prazo é calculado fora do banco, sem fonte única.

**Impacto**
- A equipe prioriza a carteira por esse prazo. Tomando 24/11/2026 como hoje, 0012345 e 0056789 vencem em 37 dias (31/12/2026), mas o hub mostra mais um ano. Saldo em aberto: R$ 26.999,50 e R$ 22.000,00.
- 0067890 não está no hub, então não aparece na priorização. Seu prazo (31/12/2025) já passou e ainda há R$ 3.000,00 de saldo.

**Relação:** causa independente. Parte da regra de data e de fuso, e não dos demais problemas.

### P4. Estornos entram como pagamento, e a documentação diz que eles não existem (consequência de P8, causa de total inflado)

**Evidência**
- `DOCUMENTACAO_TRIBUNAL.md`: `tipo` é "sempre pagamento". `schema.sql` aceita `estorno`. O arquivo traz `ev-006` pagamento de 5.000,00 (linha 50) e `ev-007` estorno de 5.000,00 (linha 58) no mesmo processo. O estorno não tem campo que diga qual pagamento ele desfaz.
- "Soma cada valor" (fluxo, item 2) ignora o tipo.

**Impacto:** o 0034567-32.2018.8.26.0405 apareceria com R$ 10.000,00 pagos de R$ 12.500,00 (80%). O líquido é R$ 0,00 e o prazo (31/12/2025) já venceu. Um precatório vencido e sem pagamento líquido parece quase quitado.

**Relação:** consequência da documentação desatualizada (P8). Causa de total inflado (parte dos R$ 28.050,50 de P1).

### P5. Hub e tribunal divergem no cadastro (consequência de P7; não sei qual lado está certo)

**Evidência**
- 0023456-21.2020.8.26.0053: `valor_face` R$ 30.000,00 (tribunal.csv linha 3) contra R$ 31.000,00 (hub.csv linha 3).
- 0045678-43.2021.5.02.0011: ente "União" (tribunal.csv linha 5) contra "Município de Santos" (hub.csv linha 5).
- 0056789-54.2017.4.03.6100: só no hub (linha 6), ausente de tribunal.csv.
- 0067890-65.2016.8.26.0053: só no tribunal (linha 6), ausente do hub, mas com apresentação e com pagamento (`ev-011`, R$ 4.000,00).
- Hipótese sobre o ente do 0056789: o hub diz "Estado de São Paulo", mas o número CNJ tem J=4 e TR=03 (Justiça Federal, TRF-3). Precatório federal contra estado é atípico. Vale perguntar.

**Impacto:** valor de face errado distorce o saldo (R$ 1.000,00 no 0023456). Ente errado pode mandar cobrança ao devedor errado. R$ 22.000,00 de um precatório que o tribunal nem lista ficam sem confirmação. Um precatório com R$ 3.000,00 em aberto não é visto pela operação.

**Relação:** consequência da conciliação manual (P7) e de P6, que gera falsos alarmes e esconde os reais.

### P6. O número do processo não tem forma canônica, e o schema não comporta a forma documentada (causa de P2 e de falsos alarmes em P5/P7)

**Evidência**
- Três grafias: com máscara (a maioria), 20 dígitos (hub.csv linha 3, pagamentos `ev-005` linha 42) e vazio (`ev-010`).
- Documentação: formato `NNNNNNN-DD.AAAA.J.TR.OOOO` (25 caracteres). `schema.sql`: `numero_processo CHAR(20)`. Testei no Postgres: valor acima de 20 caracteres é recusado (`value too long for type character(20)`).
- A comparação da operação é por texto exato (fluxo, item 3).

**Impacto:** o mesmo processo vira dois, e o pagamento fica órfão (`ev-005`). Risco adicional, não ocorrido nestes arquivos: ao abrir um número de 20 dígitos no Excel, ele vira número, perde zeros e dígitos (precisão de 15 dígitos).

**Relação:** causa das perdas de P2 (`ev-005`) e dos falsos alarmes de P5. Consequência de contrato sem padrão (P8).

### P7. A conciliação semanal é manual, no Excel, por texto exato (causa de P5 e dos formatos fora do leiaute)

**Evidência**
- `tribunal.csv` foge do leiaute: delimitador `;` (o leiaute diz vírgula), valores em pt-BR (`45.000,00`, o leiaute diz ponto decimal), codificação cp1252 (byte `0xED` em "Município", o leiaute diz UTF-8).
- Hipótese: esse é o resultado típico de abrir e salvar no Excel configurado em pt-BR, que é o passo do item 3 do fluxo. Não consigo provar pelo arquivo.
- hub.csv linha 2 diz "MUNICIPIO DE SAO PAULO"; tribunal.csv linha 2 diz "Município de São Paulo". Mesmo ente, texto diferente.

**Impacto:** o operador compara texto: vê diferença onde não há (caixa e acento) e deixa passar a real (30.000 contra 31.000 está num milhar de diferença, numa tabela de números parecidos). Ao "salvar", sobrescreve o original, sem trilha de auditoria.

**Relação:** causa de P5 ser percebido de forma errada. Parte do problema de formato de P8.

### P8. O leiaute v2.1 não descreve o que de fato chega (causa de P2 e P4)

**Evidência**
- `ev-002` (linha 10): `valor` é texto pt-BR (`"2.500,50"`), documentado como número; `data_pagamento` é `10/04/2025`, documentada como AAAA-MM-DD.
- `tipo` aceita `estorno` (P4).
- A documentação fala em "últimos 7 dias", mas o arquivo cobre de 20/02/2025 a 10/08/2025.
- `apresentacoes.json` não está no leiaute nem no fluxo, e é a única fonte de `apresentado_em` do 0067890.
- `10/04/2025` é ambígua (10 de abril ou 4 de outubro). Só o `atualizado_em` do mesmo registro (2025-04-10) permite decidir.

**Impacto:** um parser escrito pela documentação falha (P2) ou lê errado. Quem confia na data DD/MM lê dia e mês trocados em metade dos casos.

**Relação:** causa de P2 e P4.

### P9. Eventos com conteúdo inválido na origem (ficam em quarentena, dependem de resposta)

- `ev-004`: `valor` null.
- `ev-009`: `valor` -200 tipado como `pagamento`. Pode ser um estorno com tipo errado (hipótese).
- `ev-010`: `processo` vazio, R$ 750,00.
- `ev-001`: pagamento de 10/03/2025 é anterior à apresentação do precatório (02/04/2025). Está na base com alerta, e a data é uma pergunta ao tribunal.

**Relação:** é a fonte dos itens de quarentena. Nada se corrige sem o tribunal, e a decisão do que fazer fica registrada em `saida/quarentena.csv`.

### Mapa de causas

```
P8 contrato desatualizado ──► P2 falhas em silêncio ◄── P6 processo sem padrão
        │                        │  ▲                         │
        └──► P4 estorno          │  └── reexecução           P5 cadastro divergente ◄── P7 Excel/texto exato
                    │            ▼
                    └──────► P1 totais inflados          P3 prazo errado (independente)
```

### Verificado e sem problema
- `apresentado_em` do hub e de `apresentacoes.json` concordam nos cinco processos em comum, depois de converter para Brasília.
- Nenhum total líquido excede o valor de face na base limpa.
- Dígito verificador CNJ: nenhum dos seis números passa na conferência módulo 97. Como o enunciado diz que processos e valores são fictícios, não usei isso para descartar nada. Fica como validação recomendada para produção.

## 2. Limpeza (resumo das decisões; detalhes e linhas exatas em `saida/relatorio.md`)

Regras de decisão: normalizar o que tem uma única leitura segura, descartar só repetição comprovada, mandar para quarentena o que exige decisão humana. Nada é inventado.

- Versão do evento: vale o de maior `atualizado_em`. Cópia idêntica conta uma vez. Empate com conteúdo diferente vai para quarentena. Se a versão vencedora é inválida, o evento inteiro vai para quarentena (não volta à versão antiga em silêncio).
- Estorno subtrai. Assumi que desfaz o pagamento de mesmo valor no mesmo processo, e marquei como dúvida porque não há referência.
- Data DD/MM/AAAA só é aceita quando não pode ser MM/DD ou quando o `atualizado_em` fica a até 31 dias da leitura DD/MM. Nunca escolho MM/DD.
- Fuso: datas de apresentação com horário são convertidas para Brasília antes de aplicar o corte de 2 de abril.
- Precedência em conflito de cadastro: o tribunal vale para `valor_face` e `ente_devedor`; `apresentacoes.json` vale para `apresentado_em`. A divergência sempre vira dúvida no relatório, nunca decisão silenciosa.

## 3. Prevenção

### Processo
- Arquivos recebidos viram imutáveis: guardados com hash, nunca abertos e salvos no Excel. A conciliação semanal passa a ser feita por script (este código, `python -m limpeza`), que gera o relatório de divergências com chave normalizada. O operador trata o relatório, não o texto.
- Contrato com o tribunal em esquema versionado (JSON Schema e esquema de CSV), validado pelo tribunal antes de enviar. Atualizar a v2.1 para o que existe (estorno, formatos, janela) e pedir o campo de referência do estorno.
- Alerta de rejeitados para um responsável por e-mail ou chat, e relatório semanal de prazos próximos e vencidos, calculados pelo banco.
- Um dono nomeado para o prazo e para a fila de quarentena.

### Script de importação
- Uma transação por arquivo, com o hash registrado em `importacao`. Reexecutar o mesmo arquivo é no-op; falha no meio desfaz tudo.
- Validação por registro com as mesmas regras de `limpeza/regras.py` (Decimal, processo, data, fuso). O que falha vai para `importacao_rejeitado` com motivo e registro original, e o script termina com código de saída diferente de zero e avisa. Nunca "ignora e segue".
- Gravação por `sql/upsert_pagamento.sql`: idempotente por `evento_id`, versão mais nova substitui, antiga é ignorada. O resultado não depende da ordem do arquivo.
- Datas de apresentação convertidas para a data civil de Brasília antes de gravar.

### Banco (`sql/prevencao.sql`, testado num Postgres real em `tests/test_sql_postgres.py`)
- `UNIQUE (evento_id)` e `atualizado_em` em `pagamento`: duplicar passa a ser impossível.
- `numero_processo` com `CHECK` de 20 dígitos e coluna derivada com o formato CNJ de exibição: uma grafia só, e o formatado nunca é digitado.
- `ente_devedor` em tabela própria, com chave sem acento e caixa, única: "MUNICIPIO DE SAO PAULO" e "Município de São Paulo" não coexistem.
- `apresentado_em` e `prazo_pagamento` no banco, o prazo como coluna gerada pela regra (inclusive em 2 de abril): o prazo deixa de ser calculado fora e de variar.
- Total pago derivado do histórico, com sinal pelo tipo, em `vw_precatorio_saldo`: não existe total para dobrar. `vw_precatorio_alerta` lista excesso sobre a face, líquido negativo e vencido com saldo.
- `importacao` e `importacao_rejeitado`: rastreio de cada arquivo e de cada recusa.
- Decisão consciente: excesso sobre a face fica como alerta, e não como `CHECK`, porque não sei se o tribunal paga correção acima do valor de face (pergunta 6).

## 4. Dúvidas antes de pôr a limpeza em produção

### Ao tribunal
1. `ev-001`: o valor correto é 15.000,00 ou 15.500,00, e por que mudou? O pagamento é de 10/03/2025 e o precatório só foi apresentado em 02/04/2025: a data está certa?
2. `ev-004` (0023456, 03/05/2025): o `valor` null será reenviado? É um pagamento sem valor ou um erro de exportação?
3. `ev-009` (0056789, -200): é um estorno ou ajuste com tipo errado? Qual pagamento ele desfaz?
4. `ev-010`: de qual processo são os R$ 750,00?
5. Estornos: todo estorno vem com pagamento anterior? Podem informar qual evento ele desfaz? `ev-007` desfaz `ev-006`? A documentação passa a prever `estorno`?
6. `valor_face` do 0023456: 30.000,00 (lista) ou 31.000,00 (hub)? O valor de face é atualizado por correção monetária ao longo do tempo? Pagamentos podem passar do valor de face?
7. 0045678: o ente é União ou Município de Santos?
8. 0056789: existe na lista do tribunal? A lista semanal é completa ou parcial? O ente "Estado de São Paulo" faz sentido num processo da Justiça Federal (4.03)?
9. O arquivo de pagamentos cobre mesmo 7 dias ou é histórico (o recebido vai de 20/02 a 10/08/2025)? Um evento é reenviado com o mesmo `evento_id`? Existe cancelamento de evento?
10. `valor` e `data_pagamento` em formato pt-BR (`ev-002`) acontecem sempre ou foi exceção? Qual é o formato oficial? `tribunal.csv` sai assim do tribunal ou foi alterado no Excel?
11. Prazo "até 2 de abril": inclusivo até que horas, em que fuso? `2025-04-03T01:00:00Z` vale como 2 de abril em Brasília?
12. De onde vem `apresentacoes.json` e quem o mantém? Pode virar parte do leiaute?

### À operação
13. Onde o prazo é calculado hoje, já que o schema não tem a coluna? 0012345 e 0056789 foram priorizados com o prazo errado? Como tratar os prazos vencidos (0034567 e 0067890)?
14. Onde o total pago é guardado hoje, já que o schema também não tem essa coluna? É um acumulado ou é calculado?
15. O script roda numa transação? Há log? Quantas vezes já foi reexecutado depois de falha? (para estimar o estrago já feito no banco)
16. Existem os arquivos diários originais (e-mails) desde o início, para reconstruir os totais a partir deles em vez de corrigir o banco no escuro?
17. Posso adotar "tribunal vence em divergência de face e ente" até as respostas chegarem? Ou há outra regra de precedência?
18. Para que o operador abre e salva `tribunal.csv`? É só conferir, ou há ajuste manual que precisa ser mantido?
