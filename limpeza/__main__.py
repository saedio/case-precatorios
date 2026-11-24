"""python -m limpeza --dados case/dados --saida saida [--hoje AAAA-MM-DD]"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .leitura import ler_csv, ler_json_array, sha256
from .pagamentos import Ocorrencia, processar_pagamentos
from .precatorios import consolidar, interpretar_apresentacoes, interpretar_hub, interpretar_tribunal
from .relatorio import escrever_relatorio, escrever_saida

ARQUIVOS = ("pagamentos.json", "tribunal.csv", "hub.csv", "apresentacoes.json")


def executar(dados: Path, saida: Path, hoje: date) -> dict:
    if saida.resolve() == dados.resolve() or dados.resolve() in saida.resolve().parents:
        raise SystemExit("a pasta de saída não pode ficar dentro da pasta dos dados originais")
    hashes_antes = {n: sha256(dados / n) for n in ARQUIVOS}

    pag = ler_json_array(dados / "pagamentos.json")
    trib_reg, meta_trib = ler_csv(dados / "tribunal.csv")
    hub_reg, meta_hub = ler_csv(dados / "hub.csv")
    apres = ler_json_array(dados / "apresentacoes.json")

    tribunal, oc_t = interpretar_tribunal(trib_reg)
    hub, oc_h = interpretar_hub(hub_reg)
    apresentacoes, oc_a = interpretar_apresentacoes(apres)

    conhecidos = set(tribunal) | set(hub)
    rp = processar_pagamentos(pag, conhecidos)
    precatorios, oc_p = consolidar(tribunal, hub, apresentacoes, rp.aceitos, hoje)

    ocorrencias = oc_t + oc_h + oc_a + rp.ocorrencias + oc_p
    if meta_trib["codificacao"] != "utf-8" or meta_trib["delimitador"] != ",":
        ocorrencias.insert(0, Ocorrencia(
            "corrigido", "tribunal.csv",
            f"arquivo fora do leiaute 2.1: {meta_trib['codificacao']}, delimitador '{meta_trib['delimitador']}' "
            "e valores em pt-BR (45.000,00); lido com essas regras"))

    hashes_depois = {n: sha256(dados / n) for n in ARQUIVOS}
    if hashes_antes != hashes_depois:
        raise SystemExit("os arquivos originais mudaram durante a execução")

    escrever_saida(saida, precatorios, rp.aceitos, rp.quarentena)
    escrever_relatorio(
        saida / "relatorio.md", hoje=hoje, hashes_antes=hashes_antes, hashes_depois=hashes_depois,
        formatos={"tribunal.csv": meta_trib, "hub.csv": meta_hub}, lidos=rp.registros_lidos,
        eventos_unicos=len({r.evento_id for r in rp.aceitos} | {q.evento_id for q in rp.quarentena}),
        aceitos=rp.aceitos, quarentena=rp.quarentena, precatorios=precatorios, ocorrencias=ocorrencias)
    return {"precatorios": precatorios, "eventos": rp.aceitos, "quarentena": rp.quarentena, "ocorrencias": ocorrencias}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="limpeza")
    p.add_argument("--dados", type=Path, default=Path("case/dados"))
    p.add_argument("--saida", type=Path, default=Path("saida"))
    p.add_argument("--hoje", type=date.fromisoformat, default=date.today(),
                   help="data de referência para 'prazo vencido' (padrão: hoje)")
    a = p.parse_args(argv)
    r = executar(a.dados, a.saida, a.hoje)
    print(f"ok: {len(r['eventos'])} eventos, {len(r['quarentena'])} em quarentena, "
          f"{len(r['precatorios'])} precatórios -> {a.saida}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
