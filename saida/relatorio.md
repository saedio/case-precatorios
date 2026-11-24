# Relatório de limpeza

Data de referência para prazos vencidos: 2026-11-24.

## Resumo

- Registros em pagamentos.json: 13; eventos distintos (evento_id): 11.
- Eventos na base limpa: 8; em quarentena: 3.
- Precatórios na base limpa: 6.
- Formato real de tribunal.csv: cp1252, delimitador ';' (o leiaute 2.1 promete UTF-8 e vírgula).
- Arquivos originais inalterados (SHA-256 igual antes e depois).

## Corrigido (valor ou formato normalizado por regra explícita) (8)

| Onde | Por quê |
|---|---|
| tribunal.csv | arquivo fora do leiaute 2.1: cp1252, delimitador ';' e valores em pt-BR (45.000,00); lido com essas regras |
| hub.csv:3 | processo sem máscara CNJ (00234562120208260053) normalizado |
| ev-002 (pagamentos.json:10) | valor em texto pt-BR ('2.500,50') convertido |
| ev-002 (pagamentos.json:10) | data em DD/MM/AAAA ('10/04/2025') convertida |
| ev-005 (pagamentos.json:42) | processo sem máscara CNJ, normalizado |
| 0012345-10.2019.8.26.0053 | ente_devedor igual salvo caixa/acento (hub='MUNICIPIO DE SAO PAULO'); padronizado como no tribunal |
| 0012345-10.2019.8.26.0053 | prazo_pagamento do hub (2027-12-31) contraria a regra para apresentado_em=2025-04-02; recalculado: 2026-12-31 |
| 0056789-54.2017.4.03.6100 | prazo_pagamento do hub (2027-12-31) contraria a regra para apresentado_em=2025-04-02; recalculado: 2026-12-31 |

## Descartado (registro repetido ou substituído) (2)

| Onde | Por quê |
|---|---|
| ev-001 (pagamentos.json:2) | versão anterior substituída pela da linha 66 (atualizado_em mais recente) |
| ev-002 (pagamentos.json:26) | duplicata exata do registro da linha 10; contada uma vez |

## Em dúvida (não decidido sozinho: quarentena ou alerta) (12)

| Onde | Por quê |
|---|---|
| ev-001 (pagamentos.json:66) | valor mudou entre versões (15000.00 -> 15500.00); aplicada a mais recente, falta confirmação do tribunal |
| ev-004 (pagamentos.json:34) | fora da base, em quarentena: valor: valor ausente (null) |
| ev-009 (pagamentos.json:82) | fora da base, em quarentena: valor não positivo (-200.00) em evento do tipo 'pagamento'; o schema exige valor > 0 |
| ev-010 (pagamentos.json:90) | fora da base, em quarentena: processo: número de processo fora do padrão CNJ: '' |
| 0012345-10.2019.8.26.0053 | ev-001 (2025-03-10) é anterior à apresentação do precatório (2025-04-02) |
| 0023456-21.2020.8.26.0053 | valor_face diverge: tribunal=30000.00 hub=31000.00; mantido o do tribunal |
| 0034567-32.2018.8.26.0405 | ev-007 é estorno sem referência ao pagamento original; assumido que desfaz o pagamento de mesmo valor do mesmo processo |
| 0034567-32.2018.8.26.0405 | prazo 2025-12-31 vencido em relação a 2026-11-24 com saldo em aberto de 12500.00 |
| 0045678-43.2021.5.02.0011 | ente_devedor diverge: tribunal='União' hub='Município de Santos'; mantido o do tribunal |
| 0056789-54.2017.4.03.6100 | processo só existe no hub; ausente do tribunal.csv, valor_face e ente não confirmados |
| 0067890-65.2016.8.26.0053 | processo só existe no tribunal; ausente do hub.csv (fora da exportação usada pela operação) |
| 0067890-65.2016.8.26.0053 | prazo 2025-12-31 vencido em relação a 2026-11-24 com saldo em aberto de 3000.00 |

## Totais por precatório (base limpa)

| Processo | Face | Pago líquido | Saldo | Prazo | Fontes |
|---|---|---|---|---|---|
| 0012345-10.2019.8.26.0053 | 45000.00 | 18000.50 | 26999.50 | 2026-12-31 | tribunal+hub+apresentacoes |
| 0023456-21.2020.8.26.0053 | 30000.00 | 9200.00 | 20800.00 | 2027-12-31 | tribunal+hub+apresentacoes |
| 0034567-32.2018.8.26.0405 | 12500.00 | 0.00 | 12500.00 | 2025-12-31 | tribunal+hub+apresentacoes |
| 0045678-43.2021.5.02.0011 | 9800.00 | 3000.00 | 6800.00 | 2026-12-31 | tribunal+hub+apresentacoes |
| 0056789-54.2017.4.03.6100 | 22000.00 | 0.00 | 22000.00 | 2026-12-31 | hub+apresentacoes |
| 0067890-65.2016.8.26.0053 | 7000.00 | 4000.00 | 3000.00 | 2025-12-31 | tribunal+apresentacoes |

## Hashes dos originais

```
0da8be22859b58fa618fae00fedad2afead6605da6c6184e7de8e8d26a93ccc2  apresentacoes.json
75fcf6e07dc05078c35b5c7d4a3b1d38cfb3df165ab05cf5d73e155a73b83108  hub.csv
83e761b199bfea3413e4b614ac2c55643f2ccd0bd294d365af02a839de8f2cf8  pagamentos.json
0ce8aab43966f28bb12920956b38bb2573454c49c997f20e0dae07a8c7b2c841  tribunal.csv
```
