# Leiaute dos arquivos de integração

Versão 2.1, enviada pelo tribunal.

## pagamentos.json

Lista de eventos de pagamento em JSON.

| Campo | Tipo | Descrição |
|---|---|---|
| evento_id | texto | Identificador único do evento |
| processo | texto | Número do processo no formato CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO) |
| valor | número | Valor pago em reais, com ponto como separador decimal |
| data_pagamento | data | Data do pagamento no formato AAAA-MM-DD |
| tipo | texto | Sempre "pagamento" |
| atualizado_em | data e hora | Momento da última alteração do registro |

## tribunal.csv

Lista de precatórios do tribunal, em CSV com codificação UTF-8 e campos separados por vírgula.

| Campo | Tipo | Descrição |
|---|---|---|
| numero_processo | texto | Número do processo no formato CNJ |
| ente_devedor | texto | Nome do ente devedor |
| valor_face | número | Valor de face em reais, com ponto como separador decimal |
