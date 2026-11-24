"""Executa sql/prevencao.sql num Postgres de verdade. Pulado se `pgserver` não estiver instalado
(pip install pgserver). Não precisa de Postgres instalado nem de root."""
from pathlib import Path

import pytest

pgserver = pytest.importorskip("pgserver")

RAIZ = Path(__file__).resolve().parent.parent
P = "00123451020198260053"


@pytest.fixture(scope="module")
def banco(tmp_path_factory):
    srv = pgserver.get_server(tmp_path_factory.mktemp("pg"), cleanup_mode="stop")
    yield srv
    srv.cleanup()


def tenta(banco, comando):
    """Executa `comando` numa subtransação. Devolve (ok, mensagem); o erro do Postgres vem na mensagem."""
    saida = str(banco.psql(
        "CREATE FUNCTION pg_temp.tenta(cmd text) RETURNS text LANGUAGE plpgsql AS $f$ "
        "BEGIN EXECUTE cmd; RETURN 'ok'; EXCEPTION WHEN others THEN RETURN 'ERRO: ' || SQLERRM; END $f$; "
        f"SELECT pg_temp.tenta($q${comando}$q$);"))
    return "ERRO:" not in saida, saida


@pytest.fixture(scope="module", autouse=True)
def migrado(banco):
    banco.psql((RAIZ / "case" / "schema.sql").read_text())
    banco.psql((RAIZ / "sql" / "prevencao.sql").read_text())
    banco.psql("INSERT INTO ente_devedor (nome) VALUES ('Município de São Paulo');")
    banco.psql(f"INSERT INTO precatorio (numero_processo, ente_devedor, valor_face, ente_id, apresentado_em) "
               f"VALUES ('{P}', 'x', 1000, 1, '2025-04-02');")


def test_prazo_gerado_segue_a_regra(banco):
    casos = {"2025-04-02": "2026-12-31", "2025-04-03": "2027-12-31",
             "2024-02-29": "2025-12-31", "2023-12-31": "2025-12-31"}
    for i, (apres, prazo) in enumerate(casos.items()):
        num = f"{i + 1:07d}0020208260053"
        banco.psql(f"INSERT INTO precatorio (numero_processo, ente_devedor, valor_face, apresentado_em) "
                   f"VALUES ('{num}', 'x', 1, '{apres}');")
        assert prazo in str(banco.psql(f"SELECT prazo_pagamento FROM precatorio WHERE numero_processo='{num}';"))


def test_numero_cnj_formatado_e_derivado(banco):
    assert "0012345-10.2019.8.26.0053" in str(banco.psql(f"SELECT numero_processo_cnj FROM precatorio WHERE numero_processo='{P}';"))


def test_numero_com_mascara_ou_letra_e_recusado(banco):
    ok, _ = tenta(banco, "INSERT INTO precatorio (numero_processo, ente_devedor, valor_face) VALUES ('0012345-10.2019.8.26.0053','x',1);")
    assert not ok
    ok, _ = tenta(banco, "INSERT INTO precatorio (numero_processo, ente_devedor, valor_face) VALUES ('0012345A020198260053','x',1);")
    assert not ok


def test_ente_com_outra_grafia_e_recusado(banco):
    ok, saida = tenta(banco, "INSERT INTO ente_devedor (nome) VALUES ('MUNICIPIO DE SAO PAULO');")
    assert not ok and "unique" in saida.lower()


def test_upsert_e_idempotente_e_versao_nova_vence(banco):
    up = (RAIZ / "sql" / "upsert_pagamento.sql").read_text().split("\n", 4)[-1]
    def run(valor, quando):
        stmt = (up.replace("$1", "1").replace("$2", "'ev-1'").replace("$3", "'pagamento'")
                  .replace("$4", str(valor)).replace("$5", "'2025-03-10'")
                  .replace("$6", f"'{quando}'").replace("$7", "NULL"))
        banco.psql(stmt)
    def estado():
        return str(banco.psql("SELECT count(*), max(valor) FROM pagamento WHERE evento_id='ev-1';"))
    run(15000, "2025-03-10T10:00:00-03")
    run(15000, "2025-03-10T10:00:00-03")  # reexecução do mesmo arquivo
    assert " 1 |" in estado() and "15000" in estado()
    run(15500, "2025-03-11T09:00:00-03")  # correção posterior
    assert " 1 |" in estado() and "15500" in estado()
    run(15000, "2025-03-10T10:00:00-03")  # versão antiga chegando de novo: ignorada
    assert "15500" in estado()


def test_valor_nao_positivo_e_recusado(banco):
    for v in ("0", "-200"):
        ok, _ = tenta(banco, f"INSERT INTO pagamento (precatorio_id, evento_id, tipo, valor, pago_em, atualizado_em) "
                             f"VALUES (1, 'x{v}', 'pagamento', {v}, '2025-01-01', now());")
        assert not ok


def test_duplicata_direta_de_evento_e_recusada(banco):
    ok, saida = tenta(banco, "INSERT INTO pagamento (precatorio_id, evento_id, tipo, valor, pago_em, atualizado_em) "
                             "VALUES (1, 'ev-1', 'pagamento', 1, '2025-01-01', now());")
    assert not ok and "pagamento_evento_unico" in saida


def test_saldo_derivado_desconta_estorno(banco):
    banco.psql("INSERT INTO pagamento (precatorio_id, evento_id, tipo, valor, pago_em, atualizado_em) VALUES "
               "(1, 'ev-6', 'pagamento', 5000, '2025-02-20', now()), (1, 'ev-7', 'estorno', 5000, '2025-02-21', now());")
    assert "15500.00" in str(banco.psql(f"SELECT pago_liquido FROM vw_precatorio_saldo WHERE id=1;"))
