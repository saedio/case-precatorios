CREATE TABLE precatorio (
    id              BIGSERIAL PRIMARY KEY,
    numero_processo CHAR(20)      NOT NULL UNIQUE,
    ente_devedor    TEXT          NOT NULL,
    valor_face      NUMERIC(15,2) NOT NULL
);

CREATE TABLE pagamento (
    id            BIGSERIAL PRIMARY KEY,
    precatorio_id BIGINT        NOT NULL REFERENCES precatorio (id),
    evento_id     TEXT          NOT NULL,
    tipo          TEXT          NOT NULL CHECK (tipo IN ('pagamento', 'estorno')),
    valor         NUMERIC(15,2) NOT NULL CHECK (valor > 0),
    pago_em       DATE          NOT NULL,
    criado_em     TIMESTAMPTZ   NOT NULL DEFAULT now()
);
