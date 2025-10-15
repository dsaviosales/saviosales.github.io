"""Configurações e utilitários para acesso ao Oracle."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict

import cx_Oracle
from dotenv import load_dotenv

# Configuramos o carregamento do .env apenas uma vez ao importar o módulo.
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(ENV_PATH)


class OracleConfigError(RuntimeError):
    """Erro lançado quando variáveis obrigatórias estão ausentes."""


def _obter_variaveis_necessarias() -> Dict[str, str]:
    """Valida e retorna as variáveis de ambiente necessárias."""

    chaves = ["ORA_USER", "ORA_PASS", "ORA_HOST", "ORA_PORT", "ORA_SID"]
    valores: Dict[str, str] = {}
    for chave in chaves:
        valor = os.getenv(chave)
        if not valor:
            raise OracleConfigError(f"Variável de ambiente '{chave}' não definida.")
        valores[chave] = valor
    return valores


def criar_dsn(config: Dict[str, str]) -> str:
    """Cria um DSN compatível com cx_Oracle usando service name."""

    # Nota: o cx_Oracle aceita service_name ou sid; aqui usamos service_name por padrão.
    return cx_Oracle.makedsn(
        config["ORA_HOST"],
        int(config["ORA_PORT"]),
        service_name=config["ORA_SID"],
    )


def obter_conexao() -> cx_Oracle.Connection:
    """Abre e retorna uma conexão com o Oracle."""

    config = _obter_variaveis_necessarias()
    dsn = criar_dsn(config)
    logging.getLogger(__name__).debug("Conectando ao Oracle usando DSN %s", dsn)
    # Explicação curta: cx_Oracle.connect cria a conexão real usando usuário/senha/DSN.
    return cx_Oracle.connect(config["ORA_USER"], config["ORA_PASS"], dsn)


def testar_conexao() -> bool:
    """Retorna True quando a conexão puder ser aberta com sucesso."""

    try:
        with obter_conexao() as conexao:
            conexao.ping()
        return True
    except cx_Oracle.Error as exc:  # pragma: no cover - feedback útil apenas em runtime real
        logging.getLogger(__name__).error("Falha ao validar a conexão: %s", exc)
        return False
