"""Leitura dos arquivos de entrada. Só abre em modo 'rb': os originais nunca são alterados."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def decodificar(dados: bytes) -> tuple[str, str]:
    """UTF-8 se for válido; senão cp1252 (padrão do Excel no Windows em pt-BR)."""
    try:
        return dados.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return dados.decode("cp1252"), "cp1252"


def ler_json_array(caminho: Path) -> list[tuple[int, object]]:
    """Lista de (linha_inicial, objeto) para cada elemento do array raiz."""
    texto, _ = decodificar(caminho.read_bytes())
    dec = json.JSONDecoder()
    i = texto.index("[") + 1
    saida: list[tuple[int, object]] = []
    while True:
        while i < len(texto) and texto[i] in " \t\r\n,":
            i += 1
        if texto[i] == "]":
            return saida
        obj, fim = dec.raw_decode(texto, i)
        saida.append((texto.count("\n", 0, i) + 1, obj))
        i = fim


def ler_csv(caminho: Path) -> tuple[list[tuple[int, dict[str, str]]], dict[str, str]]:
    """Lê CSV detectando codificação e delimitador (',' ou ';').

    Devolve ((linha, registro)..., metadados do formato encontrado).
    """
    texto, codificacao = decodificar(caminho.read_bytes())
    cabecalho = texto.splitlines()[0]
    delim = ";" if cabecalho.count(";") > cabecalho.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto, newline=""), delimiter=delim)
    registros = [(leitor.line_num, dict(r)) for r in leitor]
    meta = {"codificacao": codificacao, "delimitador": delim}
    return registros, meta
