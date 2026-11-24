# Case técnico: precatórios

Entregáveis pedidos no enunciado:

| Item | Onde |
|---|---|
| Diagnóstico, prevenção e dúvidas | [`DIAGNOSTICO.md`](DIAGNOSTICO.md) |
| Limpeza em Python 3.10+ | `limpeza/` (`python -m limpeza`) |
| Testes das regras mais arriscadas | `tests/` |
| SQL de prevenção | `sql/prevencao.sql`, `sql/upsert_pagamento.sql` |
| Resultado da limpeza | `saida/` (`relatorio.md`, `precatorios_limpos.csv`, `pagamentos_limpos.csv`, `quarentena.csv`) |
| Material original do case, intocado | `case/` |

## Como rodar

```bash
python -m limpeza                       # lê case/dados, escreve em saida/
python -m limpeza --hoje 2026-11-24     # fixa a data usada para "prazo vencido"

pip install pytest                      # única dependência, só para os testes
pytest -q
pip install pgserver                    # opcional: sobe um Postgres embutido e testa o SQL
```

O programa usa só a biblioteca padrão. Os arquivos de `case/dados/` são abertos apenas para leitura, e o programa compara o SHA-256 antes e depois (o relatório registra os hashes e a execução aborta se algo mudar). Recusa também gravar a saída dentro da pasta de dados. `case/dados.sha256` guarda os hashes originais, e um teste confere que eles continuam iguais.

## O que a limpeza decide

Normaliza o que só tem uma leitura segura (máscara do processo, valor pt-BR, data DD/MM confirmada, fuso), descarta apenas repetição comprovada, e manda o que exige decisão humana para quarentena. O relatório separa corrigido, descartado e em dúvida, cada item com o arquivo e a linha. Regras de precedência e justificativas estão em `DIAGNOSTICO.md`, seção 2.

Testes cobrem o que mais custa se errar: prazo (2 de abril inclusivo, ano bissexto, fuso), dinheiro (Decimal, formatos ambíguos), versão e duplicata de evento, estorno, reprocessar o mesmo arquivo, e o SQL em Postgres real. Para ver que os testes pegam erro, troquei temporariamente três regras (prazo exclusivo, estorno somando, fuso em UTC) e confirmei que cada troca derruba testes.

## Uso de IA

Usei o Claude como apoio para levantar hipóteses, escrever o código com base na arquitetura e no plano de ação criado por mim, realizar os testes linha por linha, para as consultas SQL e o texto do diagnóstico.

Como conferi o que ela produziu:
- Li todos os arquivos do case e recalculei à mão os números do diagnóstico (totais por processo, prazos, diferenças em reais) contra os registros e as linhas citadas.
- Rodei os testes, inclusive o do SQL num Postgres de verdade, e fiz a troca temporária de regras descrita acima para confirmar que os testes falham quando deveriam.
- Marquei como "hipótese" no diagnóstico o que não consigo provar pelos dados (por exemplo, a causa do `tribunal.csv` fora do leiaute e o ente do 0056789).
- Conferi que os hashes dos arquivos originais não mudam.
