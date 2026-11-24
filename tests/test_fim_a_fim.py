"""Roda sobre os arquivos reais do case."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from limpeza.__main__ import executar
from limpeza.leitura import sha256

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "case" / "dados"
HOJE = date(2026, 11, 24)


@pytest.fixture(scope="module")
def resultado(tmp_path_factory):
    saida = tmp_path_factory.mktemp("saida")
    return executar(DADOS, saida, HOJE), saida


def test_originais_nao_foram_alterados(resultado):
    for linha in (RAIZ / "case" / "dados.sha256").read_text().splitlines():
        h, nome = linha.split()
        assert sha256(RAIZ / "case" / nome) == h


def test_totais_liquidos_por_processo(resultado):
    por = {p["numero_processo"][:7]: p for p in resultado[0]["precatorios"]}
    esperado = {"0012345": "18000.50", "0023456": "9200.00", "0034567": "0.00",
                "0045678": "3000.00", "0056789": "0.00", "0067890": "4000.00"}
    assert {k: str(v["total_pago_liquido"]) for k, v in por.items()} == esperado


def test_prazos_seguem_a_regra_inclusive_com_fuso(resultado):
    por = {p["numero_processo"][:7]: str(p["prazo_pagamento"]) for p in resultado[0]["precatorios"]}
    assert por == {"0012345": "2026-12-31", "0023456": "2027-12-31", "0034567": "2025-12-31",
                   "0045678": "2026-12-31", "0056789": "2026-12-31", "0067890": "2025-12-31"}


def test_quarentena_exata(resultado):
    assert sorted(q.evento_id for q in resultado[0]["quarentena"]) == ["ev-004", "ev-009", "ev-010"]


def test_nenhum_evento_duplicado_na_base(resultado):
    ids = [e.evento_id for e in resultado[0]["eventos"]]
    assert len(ids) == len(set(ids)) == 8


def test_arquivos_de_saida_gerados(resultado):
    saida = resultado[1]
    for nome in ("precatorios_limpos.csv", "pagamentos_limpos.csv", "quarentena.csv", "relatorio.md"):
        assert (saida / nome).stat().st_size > 0


def test_saida_dentro_da_pasta_de_dados_e_recusada():
    with pytest.raises(SystemExit):
        executar(DADOS, DADOS / "saida", HOJE)
