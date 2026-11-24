-- Prevenção no banco. PostgreSQL >= 12. Aplicar sobre case/schema.sql.
-- Em produção com dados: ver os "ANTES" comentados (duplicatas, backfill) antes de aplicar.

BEGIN;

-- 1. Chave de comparação do ente (mesma regra de limpeza/regras.py::chave_ente):
--    sem acento, minúscula, espaços colapsados. "MUNICIPIO DE SAO PAULO" = "Município de São Paulo".
CREATE FUNCTION chave_ente(nome TEXT) RETURNS TEXT
LANGUAGE sql IMMUTABLE STRICT AS $$
    SELECT btrim(regexp_replace(
        translate(lower(nome),
                  'áàâãäéèêëíìîïóòôõöúùûüçñ',
                  'aaaaaeeeeiiiiooooouuuucn'),
        '\s+', ' ', 'g'))
$$;

CREATE TABLE ente_devedor (
    id         BIGSERIAL PRIMARY KEY,
    nome       TEXT NOT NULL CHECK (btrim(nome) <> ''),
    nome_chave TEXT GENERATED ALWAYS AS (chave_ente(nome)) STORED UNIQUE
);

-- ANTES (produção): popular a partir do que existe e religar os precatórios.
--   INSERT INTO ente_devedor (nome)
--   SELECT DISTINCT ON (chave_ente(ente_devedor)) ente_devedor FROM precatorio
--   ORDER BY chave_ente(ente_devedor), ente_devedor;

-- 2. Controle de importação: o mesmo arquivo (hash) não entra duas vezes e nada é ignorado em silêncio.
CREATE TABLE importacao (
    id           BIGSERIAL PRIMARY KEY,
    arquivo      TEXT        NOT NULL,
    sha256       CHAR(64)    NOT NULL UNIQUE,
    iniciada_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    concluida_em TIMESTAMPTZ,
    lidos        INT,
    aceitos      INT,
    rejeitados   INT
);

CREATE TABLE importacao_rejeitado (
    id            BIGSERIAL PRIMARY KEY,
    importacao_id BIGINT NOT NULL REFERENCES importacao (id),
    linha         INT,
    evento_id     TEXT,
    motivo        TEXT   NOT NULL,
    registro      JSONB  NOT NULL,
    resolvido_em  TIMESTAMPTZ
);

-- 3. Precatório: número só com dígitos (CHAR(20) já era isso na prática; agora é garantido),
--    ente por FK, apresentação e prazo no próprio banco (prazo calculado, nunca digitado).
ALTER TABLE precatorio
    ADD CONSTRAINT precatorio_numero_so_digitos CHECK (numero_processo ~ '^[0-9]{20}$'),
    ADD CONSTRAINT precatorio_valor_face_positivo CHECK (valor_face > 0),
    ADD COLUMN ente_id BIGINT REFERENCES ente_devedor (id),
    -- data civil em America/Sao_Paulo: quem carrega converte timestamps antes (ver README).
    ADD COLUMN apresentado_em DATE,
    ADD COLUMN prazo_pagamento DATE GENERATED ALWAYS AS (
        make_date(
            EXTRACT(YEAR FROM apresentado_em)::int
            + CASE WHEN apresentado_em <= make_date(EXTRACT(YEAR FROM apresentado_em)::int, 4, 2)
                   THEN 1 ELSE 2 END,
            12, 31)
    ) STORED,
    ADD COLUMN numero_processo_cnj TEXT GENERATED ALWAYS AS (
        substr(numero_processo, 1, 7)  || '-' || substr(numero_processo, 8, 2)  || '.' ||
        substr(numero_processo, 10, 4) || '.' || substr(numero_processo, 14, 1) || '.' ||
        substr(numero_processo, 15, 2) || '.' || substr(numero_processo, 17, 4)
    ) STORED;

-- ANTES (produção): backfill de ente_id e apresentado_em (apresentacoes.json), depois:
--   ALTER TABLE precatorio ALTER COLUMN ente_id SET NOT NULL, ALTER COLUMN apresentado_em SET NOT NULL;
--   ALTER TABLE precatorio DROP COLUMN ente_devedor;

-- 4. Pagamento: um evento do tribunal = uma linha, e a versão mais nova vence.
-- ANTES (produção): achar e resolver duplicatas já existentes.
--   SELECT evento_id, count(*) FROM pagamento GROUP BY 1 HAVING count(*) > 1;
ALTER TABLE pagamento
    ADD COLUMN atualizado_em  TIMESTAMPTZ,
    ADD COLUMN importacao_id  BIGINT REFERENCES importacao (id),
    -- só se o tribunal informar qual pagamento o estorno desfaz (pergunta em DIAGNOSTICO.md):
    ADD COLUMN estorno_de_evento_id TEXT;
UPDATE pagamento SET atualizado_em = criado_em WHERE atualizado_em IS NULL;
ALTER TABLE pagamento
    ALTER COLUMN atualizado_em SET NOT NULL,
    ADD CONSTRAINT pagamento_evento_unico UNIQUE (evento_id),
    ADD CONSTRAINT pagamento_estorno_ref FOREIGN KEY (estorno_de_evento_id) REFERENCES pagamento (evento_id),
    ADD CONSTRAINT pagamento_estorno_ref_so_estorno CHECK (tipo = 'estorno' OR estorno_de_evento_id IS NULL);

-- 5. Total pago nunca é somado "no lugar": é sempre derivado do histórico, com sinal pelo tipo.
--    Reprocessar não pode mais dobrar nada, porque não existe total para dobrar.
CREATE VIEW vw_precatorio_saldo AS
SELECT p.id,
       p.numero_processo_cnj,
       p.valor_face,
       p.apresentado_em,
       p.prazo_pagamento,
       COALESCE(SUM(CASE g.tipo WHEN 'pagamento' THEN g.valor ELSE -g.valor END), 0)::numeric(15,2) AS pago_liquido,
       (p.valor_face - COALESCE(SUM(CASE g.tipo WHEN 'pagamento' THEN g.valor ELSE -g.valor END), 0))::numeric(15,2) AS saldo
FROM precatorio p
LEFT JOIN pagamento g ON g.precatorio_id = p.id
GROUP BY p.id;

-- Inconsistências viram consulta, não surpresa. (Excesso sobre a face fica como alerta, e não como
-- CHECK, porque ainda não sabemos se o tribunal paga correção monetária acima do valor de face.)
CREATE VIEW vw_precatorio_alerta AS
SELECT s.*,
       s.pago_liquido > s.valor_face AS excede_face,
       s.pago_liquido < 0            AS liquido_negativo,
       s.saldo > 0 AND s.prazo_pagamento < (now() AT TIME ZONE 'America/Sao_Paulo')::date AS vencido_com_saldo
FROM vw_precatorio_saldo s
WHERE s.pago_liquido > s.valor_face
   OR s.pago_liquido < 0
   OR (s.saldo > 0 AND s.prazo_pagamento < (now() AT TIME ZONE 'America/Sao_Paulo')::date);

COMMIT;
