"""Script CLI para aplicar updates no Oracle com base no cache local."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd
from tinydb import Query, TinyDB
from tqdm import tqdm

from database import connectOracle
from utils.tratardados import normalizar_cnpj

BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = BASE_DIR / "eunix.json"
LOG_PATH = BASE_DIR / "log" / "download_info.log"
FILES_DIR = BASE_DIR / "files"


SQL_UPDATE = """
UPDATE PCFORNEC
   SET ENDER = :ender,
       CIDADE = :cidade,
       TIPOFORNEC = :tipofornec,
       FANTASIA = :fantasia,
       NUMEROEND = :numeroend,
       BAIRRO = :bairro,
       CEP = :cep,
       ESTADO = :estado,
       EMAIL = :email
 WHERE CGC = :cgc
"""


def configurar_logging() -> None:
    """Garante que logs sejam registrados em arquivo e console."""

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    if logger.handlers:
        return

    logger.setLevel(logging.INFO)
    formato = "%(asctime)s - %(levelname)s - %(message)s"
    arquivo = logging.FileHandler(LOG_PATH, encoding="utf-8")
    console = logging.StreamHandler(sys.stdout)
    arquivo.setFormatter(logging.Formatter(formato))
    console.setFormatter(logging.Formatter(formato))
    # Observação: reaproveitamos a mesma configuração de logging do coletor.
    logger.addHandler(arquivo)
    logger.addHandler(console)


def carregar_cnpjs(caminho_csv: Path) -> Iterable[str]:
    """Carrega a lista de CNPJs do CSV informado."""

    caminho_normalizado = caminho_csv.expanduser()
    if not caminho_normalizado.is_absolute():
        caminho_normalizado = (Path.cwd() / caminho_normalizado).resolve()

    if not caminho_normalizado.exists():
        raise FileNotFoundError(f"Arquivo CSV não encontrado em {caminho_normalizado}")

    dados = pd.read_csv(caminho_normalizado, dtype=str)
    if "CGC" not in dados.columns:
        raise ValueError("O arquivo CSV precisa conter a coluna 'CGC'.")
    return dados["CGC"].dropna().astype(str).tolist()


def montar_parametros(registro: Dict[str, str]) -> Dict[str, str]:
    """Prepara os parâmetros do UPDATE com os nomes esperados."""

    def _texto_limpo(chave: str, limite: int) -> str:
        valor = registro.get(chave)
        return str(valor or "").strip()[:limite]

    # Dica: manter o dicionário explícito evita erros de digitação em chaves.
    return {
        "ender": _texto_limpo("ender", 60),
        "cidade": _texto_limpo("cidade", 40),
        "tipofornec": str(registro.get("tipofornec", "O") or "O"),
        "fantasia": _texto_limpo("fantasia", 60),
        "numeroend": _texto_limpo("numeroend", 10),
        "bairro": _texto_limpo("bairro", 40),
        "cep": _texto_limpo("cep", 8),
        "estado": _texto_limpo("estado", 2),
        "email": _texto_limpo("email", 80),
        "cgc": normalizar_cnpj(registro.get("cnpj", "")),
    }


def aplicar_updates(cnpjs: Iterable[str], dry_run: bool) -> None:
    """Lê registros do cache e aplica UPDATE usando bind parameters."""

    db = TinyDB(str(CACHE_PATH))
    tabela = db.table("fornecedores")

    registros_atualizados = 0

    with connectOracle() as conexao:
        cursor = conexao.cursor()
        for cnpj in tqdm(cnpjs, desc="Atualizando Oracle"):
            cnpj_normalizado = normalizar_cnpj(cnpj)
            resultado = tabela.get(Query().cnpj == cnpj_normalizado)
            if not resultado:
                logging.warning("CNPJ %s não encontrado no cache.", cnpj_normalizado)
                continue

            parametros = montar_parametros(resultado)
            if dry_run:
                logging.info("Dry-run: update preparado para %s com dados %s", cnpj_normalizado, parametros)
                continue

            cursor.execute(SQL_UPDATE, parametros)
            registros_atualizados += cursor.rowcount
            logging.info("Update aplicado para %s", cnpj_normalizado)

        if not dry_run:
            conexao.commit()
            logging.info("Total de registros afetados: %s", registros_atualizados)

    db.close()


def parse_args() -> argparse.Namespace:
    """Lê argumentos da linha de comando."""

    parser = argparse.ArgumentParser(description="Atualiza fornecedores no Oracle com base no cache local.")
    parser.add_argument("--csv", type=Path, default=BASE_DIR / "files" / "fornecedores.csv", help="CSV usado como referência de CNPJs.")
    parser.add_argument("--dry-run", action="store_true", help="Executa sem aplicar o commit no banco.")
    return parser.parse_args()


def main() -> None:
    """Ponto de entrada do script."""

    FILES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    configurar_logging()
    args = parse_args()

    cnpjs = carregar_cnpjs(args.csv)
    logging.info("Total de CNPJs para atualização: %s", len(cnpjs))
    aplicar_updates(cnpjs, args.dry_run)


if __name__ == "__main__":
    main()
