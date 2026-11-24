"""Escrita da base limpa e do relatório."""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from .pagamentos import Evento, Ocorrencia, Quarentena
from .regras import formatar_processo

ROTULOS = {
    "corrigido": "Corrigido (valor ou formato normalizado por regra explícita)",
    "descartado": "Descartado (registro repetido ou substituído)",
    "duvida": "Em dúvida (não decidido sozinho: quarentena ou alerta)",
}


def escrever_saida(saida: Path, precatorios: list[dict], eventos: list[Evento], quarentena: list[Quarentena]) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    _csv(saida / "precatorios_limpos.csv", list(precatorios[0].keys()), precatorios)
    _csv(saida / "pagamentos_limpos.csv",
         ["evento_id", "numero_processo", "tipo", "valor", "pago_em", "atualizado_em", "alertas"],
         [{"evento_id": e.evento_id, "numero_processo": formatar_processo(e.processo), "tipo": e.tipo,
           "valor": e.valor, "pago_em": e.pago_em, "atualizado_em": e.atualizado_em.isoformat(),
           "alertas": " | ".join(e.alertas)} for e in eventos])
    _csv(saida / "quarentena.csv", ["evento_id", "linhas", "motivo", "registro_original"],
         [{"evento_id": q.evento_id, "linhas": ",".join(map(str, q.linhas)), "motivo": q.motivo,
           "registro_original": json.dumps(q.bruto, ensure_ascii=False)} for q in quarentena])


def _csv(caminho: Path, colunas: list[str], linhas: list[dict]) -> None:
    # UTF-8, vírgula, ponto decimal, datas ISO: o formato que o leiaute 2.1 promete.
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas, lineterminator="\n")
        w.writeheader()
        w.writerows({k: ("" if v is None else v) for k, v in l.items()} for l in linhas)


def escrever_relatorio(caminho: Path, *, hoje: date, hashes_antes: dict, hashes_depois: dict,
                       formatos: dict, lidos: int, eventos_unicos: int, aceitos: list[Evento],
                       quarentena: list[Quarentena], precatorios: list[dict],
                       ocorrencias: list[Ocorrencia]) -> None:
    intacto = hashes_antes == hashes_depois
    L = ["# Relatório de limpeza", "",
         f"Data de referência para prazos vencidos: {hoje}.", "",
         "## Resumo", "",
         f"- Registros em pagamentos.json: {lidos}; eventos distintos (evento_id): {eventos_unicos}.",
         f"- Eventos na base limpa: {len(aceitos)}; em quarentena: {len(quarentena)}.",
         f"- Precatórios na base limpa: {len(precatorios)}.",
         f"- Formato real de tribunal.csv: {formatos['tribunal.csv']['codificacao']}, delimitador "
         f"'{formatos['tribunal.csv']['delimitador']}' (o leiaute 2.1 promete UTF-8 e vírgula).",
         f"- Arquivos originais {'inalterados (SHA-256 igual antes e depois)' if intacto else 'ALTERADOS, abortar'}.", ""]
    for cat in ("corrigido", "descartado", "duvida"):
        itens = [o for o in ocorrencias if o.categoria == cat]
        L += [f"## {ROTULOS[cat]} ({len(itens)})", "", "| Onde | Por quê |", "|---|---|"]
        L += [f"| {o.referencia} | {o.motivo.replace('|', '/')} |" for o in itens]
        L.append("")
    L += ["## Totais por precatório (base limpa)", "",
          "| Processo | Face | Pago líquido | Saldo | Prazo | Fontes |", "|---|---|---|---|---|---|"]
    L += [f"| {p['numero_processo']} | {p['valor_face']} | {p['total_pago_liquido']} | {p['saldo']} | "
          f"{p['prazo_pagamento'] or ''} | {p['fontes']} |" for p in precatorios]
    L += ["", "## Hashes dos originais", "", "```"]
    L += [f"{h}  {n}" for n, h in sorted(hashes_depois.items())]
    L += ["```", ""]
    caminho.write_text("\n".join(L), encoding="utf-8")
