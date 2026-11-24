# Case técnico - engenharia de software júnior

Obrigado por chegar até aqui. Este case é uma versão pequena de uma situação real da nossa operação. Os processos e valores são fictícios.

Esperamos que você leve se divirta e mostre sua linha de raciocínio. 

## Contexto

Um precatório é uma dívida do poder público (União, estados ou municípios) reconhecida pela Justiça. Cada precatório é identificado pelo número do processo no padrão CNJ. O órgão que deve pagar é chamado de ente devedor.

Pela Constituição, um precatório apresentado até 2 de abril de um ano deve ser pago até 31 de dezembro do ano seguinte. Se for apresentado depois de 2 de abril, o prazo passa para 31 de dezembro do ano subsequente ao seguinte.

## O fluxo Operacional

1. Todo dia o tribunal manda por e-mail o arquivo `pagamentos.json` com os eventos de pagamento dos últimos 7 dias.
2. Um script importa o arquivo e soma cada valor ao total pago do processo no sistema. Quando a importação falha no meio, o operador roda o script de novo com o mesmo arquivo.
3. Uma vez por semana o tribunal manda a lista de precatórios, `tribunal.csv`. O operador abre o arquivo no Excel, confere, salva e compara com a exportação, `hub.csv`, procurando o nome do ente e o número do processo exatamente como estão escritos.
4. O sistema calcula o prazo de pagamento de cada precatório a partir da data de apresentação. A equipe usa esse prazo para priorizar a carteira.
5. Quando um evento não pode ser importado, o script ignora e segue. Ninguém é avisado.

O tribunal documentou os arquivos em `DOCUMENTACAO_TRIBUNAL.md`. O esquema atual do banco está em `schema.sql`.

## O que pedimos

A operação acha que os números não batem com os do tribunal, mas ninguém sabe dizer onde nem por quê. 
Queremos a sua análise.

1. **Diagnóstico.** Liste os problemas que você encontrar nos dados, na documentação e no processo. Para cada um, mostre a evidência (arquivo, registro, linha), explique o impacto para o negócio e diga se ele é causa ou consequência de outro problema. Ordene do mais grave para o menos grave.
2. **Limpeza.** Escreva um programa em Python que leia os arquivos como vieram e produza uma base confiável, junto com um relatório do que foi corrigido, descartado ou ficou em dúvida e por quê. Os arquivos originais não podem ser alterados.
3. **Prevenção.** Proponha o que você mudaria no processo, no script de importação e no banco para que esses problemas não voltem. Se envolver o banco, escreva o SQL.
4. **Dúvidas.** Liste o que você perguntaria ao tribunal ou à operação antes de pôr a limpeza em produção.

Não existe lista fechada de problemas. Encontrar menos problemas, mas com evidência e impacto bem explicados, vale mais que uma lista longa sem justificativa.

## O que entregar

Um repositório Git (link do GitHub ou um zip com a pasta `.git`) contendo os itens abaixo.

* O diagnóstico, as propostas de prevenção e as dúvidas em um arquivo Markdown.
* O código da limpeza em Python 3.10 ou mais recente, com testes para as regras que você considerar mais arriscadas.
* Um README curto com como rodar o projeto e como você usou IA, se usou. Nesse caso, conte também como conferiu o que ela produziu.

O histórico de commits também é avaliado. Não precisa ser perfeito, mas queremos ver como o trabalho evoluiu.

## Próxima etapa

Na conversa técnica você vai apresentar o diagnóstico e responder a perguntas sobre ele. 
Pode ser solicitado para fazer uma pequena alteração no código ao vivo. Pode usar IA durante a conversa, desde que explique o que está fazendo.
