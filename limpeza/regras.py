"""Regras de normalização. Funções puras, sem I/O.

Convenção: dado que não dá para interpretar com segurança levanta ErroDeDado
(ou DadoAmbiguo). Quem chama decide: quarentena. Nunca se adivinha.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

# Brasília não tem horário de verão desde 2019 e o corte de 2 de abril nunca
# caiu dentro dele nos anos em que existia. Offset fixo evita depender de tzdata.
BRASILIA = timezone(timedelta(hours=-3))

TIPOS_VALIDOS = ("pagamento", "estorno")

_CNJ_FORMATADO = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")
_CNJ_DIGITOS = re.compile(r"\d{20}")


class ErroDeDado(ValueError):
    """Valor inválido ou impossível de interpretar."""


class DadoAmbiguo(ErroDeDado):
    """Valor que admite mais de uma leitura; não escolhemos uma."""


# ---------- número do processo ----------

def normalizar_processo(texto: object) -> str:
    """Devolve os 20 dígitos do número CNJ. Aceita com máscara ou só dígitos."""
    if not isinstance(texto, str):
        raise ErroDeDado(f"processo ausente ou não textual: {texto!r}")
    t = texto.strip()
    if _CNJ_FORMATADO.fullmatch(t):
        return re.sub(r"\D", "", t)
    if _CNJ_DIGITOS.fullmatch(t):
        return t
    raise ErroDeDado(f"número de processo fora do padrão CNJ: {texto!r}")


def formatar_processo(digitos: str) -> str:
    """20 dígitos -> NNNNNNN-DD.AAAA.J.TR.OOOO."""
    if not _CNJ_DIGITOS.fullmatch(digitos):
        raise ErroDeDado(f"esperados 20 dígitos: {digitos!r}")
    d = digitos
    return f"{d[0:7]}-{d[7:9]}.{d[9:13]}.{d[13]}.{d[14:16]}.{d[16:20]}"


# ---------- valores monetários ----------

_BR = re.compile(r"-?(\d{1,3}(\.\d{3})+|\d+),\d{1,2}")  # 2.500,50 | 2500,5
_PONTO = re.compile(r"-?\d+(\.\d{1,2})?")  # 2500.50 | 2500
_MILHAR_SEM_VIRGULA = re.compile(r"-?\d{1,3}(\.\d{3})+")  # 2.500 -> 2,5 ou 2500?


def parse_valor(valor: object) -> Decimal:
    """Converte para Decimal com 2 casas. Nunca usa float binário."""
    if valor is None:
        raise ErroDeDado("valor ausente (null)")
    if isinstance(valor, bool):
        raise ErroDeDado(f"valor booleano: {valor!r}")
    if isinstance(valor, int):
        d = Decimal(valor)
    elif isinstance(valor, float):
        d = Decimal(repr(valor))
    elif isinstance(valor, str):
        d = _valor_de_texto(valor)
    else:
        raise ErroDeDado(f"tipo de valor não suportado: {type(valor).__name__}")
    if not d.is_finite():
        raise ErroDeDado(f"valor não finito: {valor!r}")
    centavos = d.quantize(Decimal("0.01"))
    if centavos != d:
        raise ErroDeDado(f"valor com mais de 2 casas decimais: {valor!r}")
    return centavos


def _valor_de_texto(texto: str) -> Decimal:
    t = texto.strip()
    try:
        if _BR.fullmatch(t):
            return Decimal(t.replace(".", "").replace(",", "."))
        if _PONTO.fullmatch(t):
            return Decimal(t)
    except InvalidOperation as exc:  # pragma: no cover - regex já filtra
        raise ErroDeDado(f"valor ilegível: {texto!r}") from exc
    if _MILHAR_SEM_VIRGULA.fullmatch(t):
        raise DadoAmbiguo(f"valor ambíguo (milhar ou decimal?): {texto!r}")
    raise ErroDeDado(f"valor ilegível: {texto!r}")


# ---------- datas ----------

def parse_data(texto: object, dica: date | None = None) -> date:
    """AAAA-MM-DD ou DD/MM/AAAA.

    DD/MM/AAAA só é aceito quando não pode ser lido como MM/DD (dia > 12 ou dia ==
    mês) ou quando `dica` (ex.: data de atualizado_em) fica a até 31 dias da leitura
    DD/MM. Nunca se escolhe MM/DD.
    """
    if not isinstance(texto, str):
        raise ErroDeDado(f"data ausente ou não textual: {texto!r}")
    t = texto.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
            return date.fromisoformat(t)
        m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", t)
        if m:
            dia, mes, ano = (int(x) for x in m.groups())
            data = date(ano, mes, dia)
            pode_ser_mm_dd = dia <= 12 and dia != mes
            if pode_ser_mm_dd and (dica is None or abs((data - dica).days) > 31):
                raise DadoAmbiguo(f"data ambígua (DD/MM ou MM/DD?): {texto!r}")
            return data
    except ValueError as exc:
        if isinstance(exc, ErroDeDado):
            raise
        raise ErroDeDado(f"data inexistente: {texto!r}") from exc
    raise ErroDeDado(f"formato de data não reconhecido: {texto!r}")


def parse_instante(texto: object) -> datetime:
    """ISO 8601 com offset ou 'Z' -> datetime com fuso. Sem fuso = Brasília."""
    if not isinstance(texto, str):
        raise ErroDeDado(f"instante ausente ou não textual: {texto!r}")
    t = texto.strip()
    if t.endswith(("Z", "z")):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(t)
    except ValueError as exc:
        raise ErroDeDado(f"instante inválido: {texto!r}") from exc
    return dt if dt.tzinfo else dt.replace(tzinfo=BRASILIA)


def data_em_brasilia(texto: object) -> date:
    """Data civil de apresentação no fuso de Brasília.

    '2025-04-02' (só data) vale como está. Com horário, converte para Brasília:
    '2025-04-03T01:00:00Z' é 2 de abril às 22h em Brasília.
    """
    if isinstance(texto, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto.strip()):
        return parse_data(texto)
    return parse_instante(texto).astimezone(BRASILIA).date()


# ---------- prazo constitucional ----------

def prazo_pagamento(apresentado_em: date) -> date:
    """Apresentado até 2/abr (inclusive) -> 31/dez do ano seguinte; depois -> subsequente."""
    limite = date(apresentado_em.year, 4, 2)
    anos = 1 if apresentado_em <= limite else 2
    return date(apresentado_em.year + anos, 12, 31)


# ---------- ente devedor ----------

def chave_ente(nome: str) -> str:
    """Chave de comparação: sem acento, minúscula, espaços colapsados."""
    sem_acento = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento).strip().casefold()
