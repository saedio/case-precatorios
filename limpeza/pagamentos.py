"""Limpeza dos eventos de pagamento (pagamentos.json)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from .regras import (
    TIPOS_VALIDOS, DadoAmbiguo, ErroDeDado, formatar_processo, normalizar_processo,
    parse_data, parse_instante, parse_valor,
)


@dataclass(frozen=True)
class Evento:
    evento_id: str
    processo: str  # 20 dígitos
    tipo: str
    valor: Decimal  # sempre positivo; o sinal vem do tipo
    pago_em: date
    atualizado_em: datetime
    linha: int
    alertas: tuple[str, ...] = ()

    @property
    def conteudo(self) -> tuple:
        return (self.processo, self.tipo, self.valor, self.pago_em, self.atualizado_em)

    @property
    def efeito(self) -> Decimal:
        return self.valor if self.tipo == "pagamento" else -self.valor


@dataclass
class Ocorrencia:
    categoria: str  # corrigido | descartado | duvida
    referencia: str  # onde (arquivo:linha / evento / processo)
    motivo: str


@dataclass
class Quarentena:
    evento_id: str
    linhas: list[int]
    motivo: str
    bruto: list[object]


@dataclass
class ResultadoPagamentos:
    aceitos: list[Evento] = field(default_factory=list)
    quarentena: list[Quarentena] = field(default_factory=list)
    ocorrencias: list[Ocorrencia] = field(default_factory=list)
    registros_lidos: int = 0


@dataclass
class _Registro:
    linha: int
    bruto: object
    evento_id: str | None = None
    atualizado_em: datetime | None = None
    evento: Evento | None = None
    erros: list[str] = field(default_factory=list)


def _interpretar(linha: int, bruto: object) -> _Registro:
    reg = _Registro(linha, bruto)
    if not isinstance(bruto, dict):
        reg.erros.append("registro não é um objeto JSON")
        return reg
    erros, alertas = reg.erros, []

    eid = bruto.get("evento_id")
    if isinstance(eid, str) and eid.strip():
        reg.evento_id = eid.strip()
    else:
        erros.append("evento_id ausente")

    try:
        reg.atualizado_em = parse_instante(bruto.get("atualizado_em"))
    except ErroDeDado as e:
        erros.append(f"atualizado_em: {e}")

    processo = None
    try:
        processo = normalizar_processo(bruto.get("processo"))
        if processo == bruto["processo"].strip():
            alertas.append("processo sem máscara CNJ, normalizado")
    except ErroDeDado as e:
        erros.append(f"processo: {e}")

    valor = None
    try:
        valor = parse_valor(bruto.get("valor"))
        if isinstance(bruto.get("valor"), str):
            alertas.append(f"valor em texto pt-BR ({bruto['valor']!r}) convertido")
    except ErroDeDado as e:
        erros.append(f"valor: {e}")

    tipo = bruto.get("tipo")
    if tipo not in TIPOS_VALIDOS:
        erros.append(f"tipo desconhecido: {tipo!r}")
    if valor is not None and valor <= 0:
        erros.append(f"valor não positivo ({valor}) em evento do tipo {tipo!r}; o schema exige valor > 0")

    pago_em = None
    try:
        dica = reg.atualizado_em.date() if reg.atualizado_em else None
        pago_em = parse_data(bruto.get("data_pagamento"), dica=dica)
        if "/" in str(bruto.get("data_pagamento")):
            alertas.append(f"data em DD/MM/AAAA ({bruto['data_pagamento']!r}) convertida")
    except ErroDeDado as e:
        erros.append(f"data_pagamento: {e}")

    if not erros:
        reg.evento = Evento(reg.evento_id, processo, tipo, valor, pago_em,
                            reg.atualizado_em, linha, tuple(alertas))
    return reg


def processar_pagamentos(registros: list[tuple[int, object]],
                         processos_conhecidos: set[str]) -> ResultadoPagamentos:
    """Regras de versão (por evento_id):
    - cópia idêntica: descarta a repetida.
    - versões diferentes: vale a de maior atualizado_em; as anteriores são descartadas.
    - empate de atualizado_em com conteúdo diferente: tudo vai para quarentena.
    - se a versão vencedora é inválida, o evento inteiro vai para quarentena
      (não voltamos silenciosamente a uma versão antiga).
    """
    res = ResultadoPagamentos(registros_lidos=len(registros))
    grupos: dict[str, list[_Registro]] = {}
    sem_id: list[_Registro] = []
    for linha, bruto in registros:
        reg = _interpretar(linha, bruto)
        (grupos.setdefault(reg.evento_id, []) if reg.evento_id else sem_id).append(reg)

    for reg in sem_id:
        res.quarentena.append(Quarentena("(sem id)", [reg.linha], "; ".join(reg.erros), [reg.bruto]))
        res.ocorrencias.append(Ocorrencia("duvida", f"pagamentos.json:{reg.linha}", "; ".join(reg.erros)))

    for eid, regs in grupos.items():
        linhas = [r.linha for r in regs]
        vencedor = _escolher_vencedor(eid, regs, res)
        if vencedor is None:
            continue
        for r in regs:
            if r is vencedor:
                continue
            if r.evento and vencedor.evento and r.evento.conteudo == vencedor.evento.conteudo:
                res.ocorrencias.append(Ocorrencia(
                    "descartado", f"{eid} (pagamentos.json:{r.linha})",
                    f"duplicata exata do registro da linha {vencedor.linha}; contada uma vez"))
            else:
                res.ocorrencias.append(Ocorrencia(
                    "descartado", f"{eid} (pagamentos.json:{r.linha})",
                    f"versão anterior substituída pela da linha {vencedor.linha} (atualizado_em mais recente)"))
        if vencedor.erros:
            motivo = "; ".join(vencedor.erros)
            res.quarentena.append(Quarentena(eid, linhas, motivo, [r.bruto for r in regs]))
            res.ocorrencias.append(Ocorrencia("duvida", f"{eid} (pagamentos.json:{vencedor.linha})",
                                              f"fora da base, em quarentena: {motivo}"))
            continue
        ev = vencedor.evento
        if ev.processo not in processos_conhecidos:
            motivo = f"processo {formatar_processo(ev.processo)} não existe no cadastro (tribunal/hub)"
            res.quarentena.append(Quarentena(eid, linhas, motivo, [r.bruto for r in regs]))
            res.ocorrencias.append(Ocorrencia("duvida", f"{eid} (pagamentos.json:{ev.linha})", motivo))
            continue
        for a in ev.alertas:
            res.ocorrencias.append(Ocorrencia("corrigido", f"{eid} (pagamentos.json:{ev.linha})", a))
        if len(regs) > 1 and any(r is not vencedor and r.evento and r.evento.conteudo != ev.conteudo for r in regs):
            ant = next(r for r in regs if r is not vencedor and r.evento and r.evento.conteudo != ev.conteudo)
            ev = _com_alerta(ev, f"versão corrigida: valor anterior {ant.evento.valor} (linha {ant.linha}) "
                                 f"trocado por {ev.valor}; confirmar com o tribunal")
            res.ocorrencias.append(Ocorrencia(
                "duvida", f"{eid} (pagamentos.json:{ev.linha})",
                f"valor mudou entre versões ({ant.evento.valor} -> {ev.valor}); aplicada a mais recente, falta confirmação do tribunal"))
        res.aceitos.append(ev)

    res.aceitos.sort(key=lambda e: e.evento_id)
    return res


def _com_alerta(ev: Evento, alerta: str) -> Evento:
    from dataclasses import replace
    return replace(ev, alertas=ev.alertas + (alerta,))


def _escolher_vencedor(eid: str, regs: list[_Registro], res: ResultadoPagamentos) -> _Registro | None:
    if len(regs) == 1:
        return regs[0]
    datados = [r for r in regs if r.atualizado_em]
    if not datados:
        motivo = "várias versões sem atualizado_em válido; impossível saber a mais recente"
        res.quarentena.append(Quarentena(eid, [r.linha for r in regs], motivo, [r.bruto for r in regs]))
        res.ocorrencias.append(Ocorrencia("duvida", eid, motivo))
        return None
    mais_recente = max(r.atualizado_em for r in datados)
    topo = [r for r in datados if r.atualizado_em == mais_recente]
    if len(topo) > 1 and len({_chave(r) for r in topo}) > 1:
        motivo = "versões diferentes com o mesmo atualizado_em; sem como decidir qual vale"
        res.quarentena.append(Quarentena(eid, [r.linha for r in regs], motivo, [r.bruto for r in regs]))
        res.ocorrencias.append(Ocorrencia("duvida", eid, motivo))
        return None
    return topo[0]


def _chave(r: _Registro):
    return r.evento.conteudo if r.evento else repr(r.bruto)
