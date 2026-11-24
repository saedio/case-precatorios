from datetime import date
from decimal import Decimal

import pytest

from limpeza.regras import (
    DadoAmbiguo, ErroDeDado, chave_ente, data_em_brasilia, formatar_processo,
    normalizar_processo, parse_data, parse_valor, prazo_pagamento,
)


# ----- prazo: regra mais arriscada (prioridade da carteira depende dela) -----

@pytest.mark.parametrize("apresentado,esperado", [
    (date(2025, 4, 1), date(2026, 12, 31)),
    (date(2025, 4, 2), date(2026, 12, 31)),   # 2 de abril é "até": inclusivo
    (date(2025, 4, 3), date(2027, 12, 31)),
    (date(2024, 2, 29), date(2025, 12, 31)),  # ano bissexto
    (date(2023, 12, 31), date(2025, 12, 31)),
    (date(2025, 1, 1), date(2026, 12, 31)),
])
def test_prazo_pagamento(apresentado, esperado):
    assert prazo_pagamento(apresentado) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("2025-04-02T23:30:00-03:00", date(2025, 4, 2)),  # ainda 2/abr em Brasília
    ("2025-04-03T01:00:00Z", date(2025, 4, 2)),       # UTC já é dia 3, Brasília não
    ("2025-04-03T02:59:59Z", date(2025, 4, 2)),
    ("2025-04-03T03:00:00Z", date(2025, 4, 3)),       # 00:00 em Brasília
    ("2025-04-02", date(2025, 4, 2)),                 # só data: vale como está
    ("2025-04-02T10:00:00", date(2025, 4, 2)),        # sem fuso = Brasília
])
def test_data_em_brasilia(texto, esperado):
    assert data_em_brasilia(texto) == esperado


def test_prazo_com_fuso_fim_a_fim():
    assert prazo_pagamento(data_em_brasilia("2025-04-03T01:00:00Z")) == date(2026, 12, 31)
    assert prazo_pagamento(data_em_brasilia("2025-04-02T23:30:00-03:00")) == date(2026, 12, 31)


# ----- valor: dinheiro nunca vira float, nada ambíguo é chutado -----

@pytest.mark.parametrize("entrada,esperado", [
    (15000.0, "15000.00"), (8000, "8000.00"), ("2.500,50", "2500.50"),
    ("45.000,00", "45000.00"), ("45000.00", "45000.00"), ("0,10", "0.10"),
    (0.1, "0.10"), ("1.234.567,89", "1234567.89"), ("-200", "-200.00"),
])
def test_parse_valor_ok(entrada, esperado):
    assert parse_valor(entrada) == Decimal(esperado)


def test_parse_valor_nao_acumula_erro_binario():
    assert sum(parse_valor(x) for x in [0.1] * 10) == Decimal("1.00")


@pytest.mark.parametrize("ruim", [None, True, "", "abc", "1,500.00", "12,345", float("nan"), "1,234,56", 1.005])
def test_parse_valor_rejeita(ruim):
    with pytest.raises(ErroDeDado):
        parse_valor(ruim)


def test_parse_valor_milhar_sem_virgula_e_ambiguo():
    with pytest.raises(DadoAmbiguo):
        parse_valor("2.500")


# ----- data -----

def test_data_iso():
    assert parse_data("2025-05-02") == date(2025, 5, 2)


def test_data_br_confirmada_por_dica():
    assert parse_data("10/04/2025", dica=date(2025, 4, 10)) == date(2025, 4, 10)


def test_data_br_ambigua_sem_dica():
    with pytest.raises(DadoAmbiguo):
        parse_data("10/04/2025")


def test_data_br_ambigua_com_dica_distante_nunca_vira_mm_dd():
    # "04/10/2025" com dica de 10 de abril: MM/DD bateria com a dica, mas não adivinhamos.
    with pytest.raises(DadoAmbiguo):
        parse_data("04/10/2025", dica=date(2025, 4, 10))


@pytest.mark.parametrize("texto", ["25/04/2025", "05/05/2025"])
def test_data_br_sem_ambiguidade(texto):
    assert parse_data(texto).year == 2025


@pytest.mark.parametrize("ruim", ["31/02/2025", "2025-02-30", "2025/04/10", None, 20250410])
def test_data_invalida(ruim):
    with pytest.raises(ErroDeDado):
        parse_data(ruim)


# ----- processo e ente -----

def test_processo_com_e_sem_mascara_dao_a_mesma_chave():
    assert normalizar_processo("0023456-21.2020.8.26.0053") == normalizar_processo("00234562120208260053")


def test_processo_roundtrip():
    p = "0012345-10.2019.8.26.0053"
    assert formatar_processo(normalizar_processo(p)) == p


@pytest.mark.parametrize("ruim", ["", None, "123", "0012345-10.2019.8.26.005", "0012345-10.2019.8.26.00533"])
def test_processo_invalido(ruim):
    with pytest.raises(ErroDeDado):
        normalizar_processo(ruim)


def test_chave_ente_ignora_caixa_e_acento():
    assert chave_ente("MUNICIPIO DE SAO PAULO") == chave_ente("Município de  São Paulo")
    assert chave_ente("União") != chave_ente("Município de Santos")
