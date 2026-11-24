-- Comando que o script de importação executa por evento, dentro de UMA transação por arquivo.
-- Idempotente: repetir o mesmo evento não muda nada; versão mais nova (atualizado_em) substitui;
-- versão mais antiga é ignorada. Parâmetros: $1 precatorio_id, $2 evento_id, $3 tipo, $4 valor,
-- $5 pago_em, $6 atualizado_em, $7 importacao_id.
INSERT INTO pagamento (precatorio_id, evento_id, tipo, valor, pago_em, atualizado_em, importacao_id)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (evento_id) DO UPDATE
   SET precatorio_id = EXCLUDED.precatorio_id,
       tipo          = EXCLUDED.tipo,
       valor         = EXCLUDED.valor,
       pago_em       = EXCLUDED.pago_em,
       atualizado_em = EXCLUDED.atualizado_em,
       importacao_id = EXCLUDED.importacao_id
 WHERE EXCLUDED.atualizado_em > pagamento.atualizado_em;
