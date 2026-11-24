from datetime import date
from decimal import Decimal

from limpeza.pagamentos import Evento
from limpeza.precatorios import Cadastro, consolidar
from limpeza.regras import normalizar_processo as n

HOJE = date(2026, 11, 24)
P = n("0012345-10.2019.8.26.0053")


def cad(proc=P, ente="Município de São Paulo", face="1000.00", apres=None, prazo=None):
    return Cadastro(proc, 2, ente=ente, valor_face=Decimal(face), apresentado_em=apres, prazo=prazo)


def linha(tribunal, hub, apres, eventos=()):
    linhas, oc = consolidar(tribunal, hub, apres, list(eventos), HOJE)
    return linhas[0], oc


def test_prazo_do_hub_errado_e_recalculado_e_reportado():
    t = {P: cad()}
    h = {P: cad(apres=date(2025, 4, 2), prazo=date(2027, 12, 31))}
    a = {P: Cadastro(P, 2, apresentado_em=date(2025, 4, 2))}
    l, oc = linha(t, h, a)
    assert l["prazo_pagamento"] == date(2026, 12, 31)
    assert any(o.categoria == "corrigido" and "recalculado" in o.motivo for o in oc)


def test_divergencia_de_face_nao_e_resolvida_em_silencio():
    t, h = {P: cad(face="30000.00")}, {P: cad(face="31000.00", apres=date(2025, 4, 3), prazo=date(2027, 12, 31))}
    l, oc = linha(t, h, {})
    assert l["valor_face"] == Decimal("30000.00")  # precedência do tribunal
    assert any(o.categoria == "duvida" and "valor_face diverge" in o.motivo for o in oc)


def test_ente_com_caixa_e_acento_diferentes_nao_e_divergencia():
    t = {P: cad(ente="Município de São Paulo")}
    h = {P: cad(ente="MUNICIPIO DE SAO PAULO", apres=date(2025, 4, 3), prazo=date(2027, 12, 31))}
    _, oc = linha(t, h, {})
    assert not any("ente_devedor diverge" in o.motivo for o in oc)


def test_ente_realmente_diferente_e_divergencia():
    t = {P: cad(ente="União")}
    h = {P: cad(ente="Município de Santos", apres=date(2025, 4, 3), prazo=date(2027, 12, 31))}
    _, oc = linha(t, h, {})
    assert any("ente_devedor diverge" in o.motivo for o in oc)


def test_saldo_usa_total_liquido_com_estorno_e_sinaliza_prazo_vencido():
    from datetime import datetime, timezone
    def e(i, tipo, v):
        return Evento(i, P, tipo, Decimal(v), date(2025, 2, 20), datetime(2025, 2, 20, tzinfo=timezone.utc), 2)
    t = {P: cad(face="12500.00")}
    a = {P: Cadastro(P, 2, apresentado_em=date(2024, 2, 29))}
    l, oc = linha(t, {}, a, [e("p", "pagamento", "5000"), e("e", "estorno", "5000")])
    assert l["total_pago_liquido"] == Decimal("0") and l["saldo"] == Decimal("12500.00")
    assert any("vencido" in o.motivo for o in oc)


def test_so_no_hub_fica_marcado_como_nao_confirmado():
    h = {P: cad(apres=date(2025, 4, 2), prazo=date(2026, 12, 31))}
    l, oc = linha({}, h, {})
    assert "hub" == l["fontes"] and any("só existe no hub" in o.motivo for o in oc)
