from decimal import Decimal

from limpeza.pagamentos import processar_pagamentos
from limpeza.regras import normalizar_processo

P1 = "0012345-10.2019.8.26.0053"
P2 = "0023456-21.2020.8.26.0053"
CONHECIDOS = {normalizar_processo(P1), normalizar_processo(P2)}


def ev(eid="ev-1", processo=P1, valor=100, data="2025-03-10", tipo="pagamento",
       atualizado="2025-03-10T10:00:00-03:00"):
    return {"evento_id": eid, "processo": processo, "valor": valor, "data_pagamento": data,
            "tipo": tipo, "atualizado_em": atualizado}


def rodar(*eventos):
    return processar_pagamentos([(i + 2, e) for i, e in enumerate(eventos)], CONHECIDOS)


def liquido(res):
    return sum((e.efeito for e in res.aceitos), Decimal("0"))


# --- duplicidade e reprocessamento: o erro mais caro (dobra o total pago) ---

def test_duplicata_exata_conta_uma_vez():
    r = rodar(ev(), ev())
    assert liquido(r) == Decimal("100.00") and len(r.aceitos) == 1
    assert [o.categoria for o in r.ocorrencias] == ["descartado"]


def test_mesmo_arquivo_duas_vezes_da_o_mesmo_total():
    base = [ev("a", valor=10), ev("b", valor=20, tipo="estorno"), ev("c", valor=5)]
    uma = rodar(*base)
    duas = rodar(*base, *base)
    assert liquido(uma) == liquido(duas) == Decimal("-5.00")
    assert [e.evento_id for e in uma.aceitos] == [e.evento_id for e in duas.aceitos]


# --- versões do mesmo evento ---

def test_versao_mais_recente_vence_mesmo_vindo_antes_no_arquivo():
    nova = ev(valor=15500, atualizado="2025-03-11T09:00:00-03:00")
    velha = ev(valor=15000, atualizado="2025-03-10T10:00:00-03:00")
    r = rodar(nova, velha)
    assert liquido(r) == Decimal("15500.00")
    assert any("valor mudou" in o.motivo for o in r.ocorrencias if o.categoria == "duvida")


def test_empate_de_atualizado_em_com_conteudo_diferente_vai_para_quarentena():
    r = rodar(ev(valor=1), ev(valor=2))
    assert not r.aceitos and len(r.quarentena) == 1


def test_versao_vencedora_invalida_nao_volta_para_a_antiga():
    boa = ev(valor=100, atualizado="2025-03-10T10:00:00-03:00")
    ruim = ev(valor=None, atualizado="2025-03-11T10:00:00-03:00")
    r = rodar(boa, ruim)
    assert not r.aceitos and r.quarentena[0].evento_id == "ev-1"


def test_fuso_decide_qual_versao_e_mais_recente():
    # 23:00-03:00 é 02:00Z do dia seguinte: mais recente que 01:00Z, embora "23:00" < "01:00" como texto
    a = ev(valor=1, atualizado="2025-03-10T23:00:00-03:00")
    b = ev(valor=2, atualizado="2025-03-11T01:00:00+00:00")
    assert liquido(rodar(b, a)) == Decimal("1.00")


# --- estorno ---

def test_estorno_subtrai_em_vez_de_somar():
    r = rodar(ev("p", valor=5000), ev("e", valor=5000, tipo="estorno", data="2025-03-11"))
    assert liquido(r) == Decimal("0.00")


# --- o que NÃO entra na base ---

def test_valores_invalidos_vao_para_quarentena_e_nao_somam():
    r = rodar(ev("n", valor=None), ev("neg", valor=-200), ev("zero", valor=0),
              ev("vazio", processo=""), ev("tipo", tipo="outro"), ev("ok", valor=7))
    assert [e.evento_id for e in r.aceitos] == ["ok"]
    assert {q.evento_id for q in r.quarentena} == {"n", "neg", "zero", "vazio", "tipo"}


def test_processo_desconhecido_vai_para_quarentena():
    r = rodar(ev(processo="0099999-99.2020.8.26.0053"))
    assert not r.aceitos and "não existe no cadastro" in r.quarentena[0].motivo


def test_processo_sem_mascara_casa_com_o_cadastro():
    r = rodar(ev(processo="00234562120208260053"))
    assert r.aceitos and r.aceitos[0].processo == normalizar_processo(P2)


def test_formato_br_convertido_e_data_ambigua_sem_confirmacao_vai_para_quarentena():
    ok = rodar(ev(valor="2.500,50", data="10/04/2025", atualizado="2025-04-10T09:00:00-03:00"))
    assert liquido(ok) == Decimal("2500.50")
    ruim = rodar(ev(data="10/04/2025", atualizado="2025-12-01T09:00:00-03:00"))
    assert not ruim.aceitos and "ambígua" in ruim.quarentena[0].motivo


def test_registro_sem_evento_id_vai_para_quarentena():
    r = rodar({"processo": P1, "valor": 1})
    assert not r.aceitos and r.quarentena[0].evento_id == "(sem id)"
