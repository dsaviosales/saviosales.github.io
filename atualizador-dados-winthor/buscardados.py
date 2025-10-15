"""Script CLI para buscar dados de fornecedores via API e preencher o cache local."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd
import requests
from ratelimit import RateLimitException, limits, sleep_and_retry
from requests import Response
from requests.exceptions import RequestException
from tinydb import Query, TinyDB
from tqdm import tqdm

from utils.normaliza_dados import normalizar_resposta_api
from utils.tratardados import normalizar_cnpj

BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = BASE_DIR / "eunix.json"
LOG_PATH = BASE_DIR / "log" / "download_info.log"
FILES_DIR = BASE_DIR / "files"
DEFAULT_API_URL = "https://www.receitaws.com.br/v1/cnpj/{cnpj}"
RATE_CALLS = 3
RATE_PERIOD = 1
RETRY_LIMIT = 3
TIMEOUT_SECONDS = 10


def configurar_logging() -> None:
    """Configura logging em arquivo e console apenas uma vez."""

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

    # Dica rápida: handlers definem para onde as mensagens de log são enviadas.
    logger.addHandler(arquivo)
    logger.addHandler(console)


@sleep_and_retry
@limits(calls=RATE_CALLS, period=RATE_PERIOD)
def _chamar_api(session: requests.Session, url: str) -> Response:
    """Executa a chamada HTTP respeitando o rate limit configurado."""

    resposta = session.get(url, timeout=TIMEOUT_SECONDS)
    if resposta.status_code == 429:
        raise RateLimitException("Limite da API atingido", period_remaining=RATE_PERIOD)
    return resposta


def obter_dados_cnpj(session: requests.Session, api_url: str, cnpj: str) -> Dict[str, str]:
    """Chama a API com tentativas extras em caso de falhas transitórias."""

    for tentativa in range(1, RETRY_LIMIT + 1):
        try:
            url = api_url.format(cnpj=cnpj)
            resposta = _chamar_api(session, url)
            resposta.raise_for_status()
            payload = resposta.json()
            if payload.get("status") == "ERROR":
                raise RequestException(payload.get("message", "Erro na API"))
            return payload
        except RateLimitException as erro:
            logging.warning("Rate limit atingido: %s", erro)
        except RequestException as erro:
            logging.warning("Falha ao consultar CNPJ %s (tentativa %s/%s): %s", cnpj, tentativa, RETRY_LIMIT, erro)
        if tentativa < RETRY_LIMIT:
            continue
        raise


def carregar_cnpjs(caminho_csv: Path) -> Iterable[str]:
    """Lê a coluna 'CGC' do CSV informado."""

    caminho_normalizado = caminho_csv.expanduser()
    if not caminho_normalizado.is_absolute():
        caminho_normalizado = (Path.cwd() / caminho_normalizado).resolve()

    if not caminho_normalizado.exists():
        raise FileNotFoundError(f"Arquivo CSV não encontrado em {caminho_normalizado}")

    dados = pd.read_csv(caminho_normalizado, dtype=str)
    if "CGC" not in dados.columns:
        raise ValueError("O arquivo CSV precisa conter a coluna 'CGC'.")
    return dados["CGC"].dropna().astype(str).tolist()


def atualizar_cache(cnpjs: Iterable[str], api_url: str, dry_run: bool) -> None:
    """Busca dados para cada CNPJ e atualiza o cache TinyDB."""

    db = TinyDB(str(CACHE_PATH))
    tabela = db.table("fornecedores")
    session = requests.Session()

    for cnpj in tqdm(cnpjs, desc="Consultando API"):
        cnpj_normalizado = normalizar_cnpj(cnpj)
        try:
            payload = obter_dados_cnpj(session, api_url, cnpj_normalizado)
        except Exception as erro:  # pragma: no cover - feedback essencial em runtime
            logging.error("Erro ao buscar dados do CNPJ %s: %s", cnpj_normalizado, erro)
            continue

        registro = normalizar_resposta_api(cnpj_normalizado, payload)
        logging.info("Dados obtidos para %s", cnpj_normalizado)

        if dry_run:
            logging.info("Dry-run: registro não persistido no cache.")
            continue

        tabela.upsert(registro, Query().cnpj == registro["cnpj"])
        # Explicação: o upsert atualiza se existir ou insere um novo registro.
        logging.info("Registro atualizado no cache para %s", registro["cnpj"])

    session.close()
    db.close()


def parse_args() -> argparse.Namespace:
    """Interpreta argumentos de linha de comando."""

    parser = argparse.ArgumentParser(description="Baixa dados de fornecedores e atualiza o cache local.")
    parser.add_argument("--csv", type=Path, default=BASE_DIR / "files" / "fornecedores.csv", help="Caminho do CSV com a coluna CGC.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="URL da API com placeholder {cnpj}.")
    parser.add_argument("--dry-run", action="store_true", help="Executa sem salvar no cache.")
    return parser.parse_args()


def main() -> None:
    """Função principal para execução como script."""

    FILES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    configurar_logging()
    args = parse_args()

    cnpjs = carregar_cnpjs(args.csv)
    logging.info("Total de CNPJs para consulta: %s", len(cnpjs))
    atualizar_cache(cnpjs, args.api_url, args.dry_run)


if __name__ == "__main__":
    main()
