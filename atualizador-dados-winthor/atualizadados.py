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

from database import obter_conexao
from utils.tratardados import normalizar_cnpj

BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = BASE_DIR / "eunix.json"
LOG_PATH = BASE_DIR / "log" / "download_info.log"


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

    dados = pd.read_csv(caminho_csv, dtype=str)
    if "CGC" not in dados.columns:
        raise ValueError("O arquivo CSV precisa conter a coluna 'CGC'.")
    return dados["CGC"].dropna().astype(str).tolist()


def montar_parametros(registro: Dict[str, str]) -> Dict[str, str]:
    """Prepara os parâmetros do UPDATE com os nomes esperados."""

    # Dica: manter o dicionário explícito evita erros de digitação em chaves.
    return {
        "ender": registro.get("ender", "")[:60],
        "cidade": registro.get("cidade", "")[:40],
        "tipofornec": registro.get("tipofornec", "O"),
        "fantasia": registro.get("fantasia", "")[:60],
        "numeroend": registro.get("numeroend", "")[:10],
        "bairro": registro.get("bairro", "")[:40],
        "cep": registro.get("cep", "")[:8],
        "estado": registro.get("estado", "")[:2],
        "email": registro.get("email", "")[:80],
        "cgc": registro["cnpj"],
    }


def aplicar_updates(cnpjs: Iterable[str], dry_run: bool) -> None:
    """Lê registros do cache e aplica UPDATE usando bind parameters."""

    db = TinyDB(CACHE_PATH)
    tabela = db.table("fornecedores")

    registros_atualizados = 0

    with obter_conexao() as conexao:
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

    configurar_logging()
    args = parse_args()

    cnpjs = carregar_cnpjs(args.csv)
    logging.info("Total de CNPJs para atualização: %s", len(cnpjs))
    aplicar_updates(cnpjs, args.dry_run)


if __name__ == "__main__":
    main()
