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

# Para robustez cross-platform, forçamos o caminho absoluto e ignoramos se não existir.
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


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

    host = config["ORA_HOST"].strip()
    porta = int(config["ORA_PORT"].strip())
    service = config["ORA_SID"].strip()
    # Nota: makedsn garante compatibilidade independentemente do SO.
    return cx_Oracle.makedsn(host, porta, service_name=service)


def connectOracle() -> cx_Oracle.Connection:
    """Retorna uma conexão única com o Oracle usando variáveis de ambiente."""

    config = _obter_variaveis_necessarias()
    dsn = criar_dsn(config)
    logger = logging.getLogger(__name__)
    logger.debug("Conectando ao Oracle usando DSN %s", dsn)

    try:
        return cx_Oracle.connect(
            config["ORA_USER"],
            config["ORA_PASS"],
            dsn,
            encoding="UTF-8",
            nencoding="UTF-8",
        )
    except cx_Oracle.DatabaseError as exc:  # pragma: no cover - dependente do ambiente Oracle
        logger.error("Não foi possível estabelecer conexão com o Oracle: %s", exc)
        raise


def obter_conexao() -> cx_Oracle.Connection:
    """Compatibilidade com versões anteriores (alias para connectOracle)."""

    return connectOracle()


def testar_conexao() -> bool:
    """Retorna True quando a conexão puder ser aberta com sucesso."""

    try:
        with obter_conexao() as conexao:
            conexao.ping()
        return True
    except cx_Oracle.Error as exc:  # pragma: no cover - feedback útil apenas em runtime real
        logging.getLogger(__name__).error("Falha ao validar a conexão: %s", exc)
        return False
