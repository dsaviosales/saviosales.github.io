"""Funções utilitárias para tratar dados de fornecedores."""
from __future__ import annotations

from typing import Optional


def somente_digitos(valor: str) -> str:
    """Remove qualquer caractere não numérico do valor informado."""

    # Para iniciantes: usar compreensão simples deixa claro que filtramos apenas números.
    return "".join(ch for ch in valor if ch.isdigit())


def normalizar_cnpj(cnpj: str) -> str:
    """Normaliza um CNPJ para conter exatamente 14 dígitos."""

    apenas_numeros = somente_digitos(cnpj)
    return apenas_numeros.zfill(14)


def mapear_tipofornec(cnae: Optional[str]) -> str:
    """Retorna o código TIPOFORNEC baseado no CNAE principal."""

    if not cnae:
        return "O"

    codigo = somente_digitos(cnae)[:2]

    # Para entendermos a regra: os dois primeiros dígitos definem o tipo do fornecedor.
    if not codigo:
        return "O"

    valor = int(codigo)
    if 0 <= valor <= 44:
        return "I"
    if 45 <= valor <= 46:
        return "C"
    if valor == 47:
        return "V"
    return "O"
