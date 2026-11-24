"""Consolidação do cadastro de precatórios: tribunal.csv x hub.csv x apresentacoes.json."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .pagamentos import Evento, Ocorrencia
from .regras import (
    ErroDeDado, chave_ente, data_em_brasilia, formatar_processo, normalizar_processo,
    parse_data, parse_valor, prazo_pagamento,
)


@dataclass
class Cadastro:
    """Um registro de precatório de uma fonte, já tipado."""
    processo: str  # 20 dígitos
    linha: int
    ente: str | None = None
    valor_face: Decimal | None = None
    apresentado_em: date | None = None
    prazo: date | None = None


def interpretar_tribunal(registros, arquivo="tribunal.csv"):
    return _interpretar_csv(registros, arquivo, "numero_processo", "ente_devedor", "valor_face", None, None)


def interpretar_hub(registros, arquivo="hub.csv"):
    return _interpretar_csv(registros, arquivo, "processo", "ente", "valor_face", "apresentado_em", "prazo_pagamento")


def _interpretar_csv(registros, arquivo, c_proc, c_ente, c_valor, c_apres, c_prazo):
    saida: dict[str, Cadastro] = {}
    oc: list[Ocorrencia] = []
    for linha, r in registros:
        ref = f"{arquivo}:{linha}"
        try:
            bruto = r[c_proc]
            proc = normalizar_processo(bruto)
            if proc == bruto.strip():
                oc.append(Ocorrencia("corrigido", ref, f"processo sem máscara CNJ ({bruto}) normalizado"))
            cad = Cadastro(proc, linha, ente=r[c_ente].strip(), valor_face=parse_valor(r[c_valor]))
            if c_apres:
                cad.apresentado_em = data_em_brasilia(r[c_apres])
                cad.prazo = parse_data(r[c_prazo])
        except (ErroDeDado, KeyError) as e:
            oc.append(Ocorrencia("duvida", ref, f"linha ignorada: {e}"))
            continue
        if proc in saida:
            oc.append(Ocorrencia("duvida", ref, f"processo repetido (também na linha {saida[proc].linha}); mantida a primeira"))
            continue
        saida[proc] = cad
    return saida, oc


def interpretar_apresentacoes(registros, arquivo="apresentacoes.json"):
    saida: dict[str, Cadastro] = {}
    oc: list[Ocorrencia] = []
    for linha, r in registros:
        ref = f"{arquivo}:{linha}"
        try:
            proc = normalizar_processo(r["processo"])
            saida[proc] = Cadastro(proc, linha, apresentado_em=data_em_brasilia(r["apresentado_em"]))
        except (ErroDeDado, KeyError, TypeError) as e:
            oc.append(Ocorrencia("duvida", ref, f"registro ignorado: {e}"))
    return saida, oc


def consolidar(tribunal, hub, apresentacoes, eventos: list[Evento], hoje: date):
    """Uma linha por precatório + ocorrências. Conflitos entre fontes não são resolvidos
    em silêncio: a regra de precedência é aplicada e a divergência vai para o relatório."""
    oc: list[Ocorrencia] = []
    canonico = {chave_ente(c.ente): c.ente for c in tribunal.values()}
    linhas = []
    for proc in sorted(set(tribunal) | set(hub) | set(apresentacoes)):
        fmt = formatar_processo(proc)
        t, h, a = tribunal.get(proc), hub.get(proc), apresentacoes.get(proc)
        fontes = [n for n, x in (("tribunal", t), ("hub", h), ("apresentacoes", a)) if x]
        alertas: list[str] = []

        def avisa(cat, msg, alerta=True):
            oc.append(Ocorrencia(cat, fmt, msg))
            if alerta:
                alertas.append(msg)

        # valor de face: o tribunal é a fonte do débito
        if t and h and t.valor_face != h.valor_face:
            avisa("duvida", f"valor_face diverge: tribunal={t.valor_face} hub={h.valor_face}; mantido o do tribunal")
        face = (t or h).valor_face if (t or h) else None
        if not t:
            avisa("duvida", "processo só existe no hub; ausente do tribunal.csv, valor_face e ente não confirmados")
        if not h:
            avisa("duvida", "processo só existe no tribunal; ausente do hub.csv (fora da exportação usada pela operação)")

        # ente
        ente = None
        if t and h and chave_ente(t.ente) != chave_ente(h.ente):
            avisa("duvida", f"ente_devedor diverge: tribunal={t.ente!r} hub={h.ente!r}; mantido o do tribunal")
        elif t and h and t.ente != h.ente:
            oc.append(Ocorrencia("corrigido", fmt, f"ente_devedor igual salvo caixa/acento (hub={h.ente!r}); padronizado como no tribunal"))
        if t:
            ente = t.ente
        elif h:
            ente = canonico.get(chave_ente(h.ente), h.ente)

        # apresentação e prazo
        apres = a.apresentado_em if a else (h.apresentado_em if h else None)
        if a and h and a.apresentado_em != h.apresentado_em:
            avisa("duvida", f"apresentado_em diverge: apresentacoes={a.apresentado_em} hub={h.apresentado_em}; mantido apresentacoes")
        prazo = prazo_pagamento(apres) if apres else None
        if h and prazo and h.prazo != prazo:
            avisa("corrigido", f"prazo_pagamento do hub ({h.prazo}) contraria a regra para apresentado_em={apres}; recalculado: {prazo}")
        if not apres:
            avisa("duvida", "sem data de apresentação; prazo não calculável")

        # pagamentos
        evs = [e for e in eventos if e.processo == proc]
        liquido = sum((e.efeito for e in evs), Decimal("0.00"))
        saldo = (face - liquido) if face is not None else None
        for e in evs:
            if apres and e.pago_em < apres:
                avisa("duvida", f"{e.evento_id} ({e.pago_em}) é anterior à apresentação do precatório ({apres})")
            if e.tipo == "estorno":
                avisa("duvida", f"{e.evento_id} é estorno sem referência ao pagamento original; "
                                f"assumido que desfaz o pagamento de mesmo valor do mesmo processo", alerta=True)
        if face is not None and liquido > face:
            avisa("duvida", f"total líquido pago ({liquido}) excede o valor de face ({face})")
        if liquido < 0:
            avisa("duvida", f"total líquido pago negativo ({liquido})")
        if saldo is not None and saldo > 0 and prazo and prazo < hoje:
            avisa("duvida", f"prazo {prazo} vencido em relação a {hoje} com saldo em aberto de {saldo}")

        linhas.append({
            "numero_processo": fmt, "ente_devedor": ente, "valor_face": face,
            "apresentado_em": apres, "prazo_pagamento": prazo,
            "total_pago_liquido": liquido, "saldo": saldo,
            "fontes": "+".join(fontes), "alertas": " | ".join(alertas),
        })
    return linhas, oc
