"""Script CLI para aplicar updates no Oracle com base no cache local."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd
from tinydb import Query, TinyDB
from tqdm import tqdm

from database import connectOracle
from utils.tratardados import normalizar_cnpj

BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = BASE_DIR / "eunix.json"
LOG_PATH = BASE_DIR / "log" / "download_info.log"
FILES_DIR = BASE_DIR / "files"
RELATORIO_OK = LOG_PATH.parent / "atualizados_ok.csv"
RELATORIO_ERROS = LOG_PATH.parent / "atualizados_erros.csv"


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


def escrever_relatorio(caminho: Path, linhas: list[list[str]]) -> None:
    """Grava o relatório CSV garantindo compatibilidade cross-platform."""

    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as relatorio:
        escritor = csv.writer(relatorio)
        escritor.writerow(["cnpj", "mensagem"])
        escritor.writerows(linhas)


def aplicar_updates(
    cnpjs: Iterable[str],
    dry_run: bool,
    limite: Optional[int],
    criterios: Optional[Dict[str, object]],
) -> None:
    """Lê registros do cache e aplica UPDATE usando bind parameters."""

    if limite is not None and limite <= 0:
        logging.info("Limite informado é %s; nenhuma atualização será processada.", limite)
        escrever_relatorio(RELATORIO_OK, [])
        escrever_relatorio(RELATORIO_ERROS, [])
        return

    db = TinyDB(str(CACHE_PATH))
    tabela = db.table("fornecedores")

    filtro_query = Query().fragment(criterios) if criterios else None
    registros_atualizados = 0
    processados = 0
    sucesso_relatorio: list[list[str]] = []
    erros_relatorio: list[list[str]] = []

    with connectOracle() as conexao:
        cursor = conexao.cursor()
        for cnpj in tqdm(cnpjs, desc="Atualizando Oracle"):
            if limite is not None and processados >= limite:
                logging.info("Limite de %s registros atingido; encerrando a execução.", limite)
                break

            cnpj_normalizado = normalizar_cnpj(cnpj)
            consulta = Query().cnpj == cnpj_normalizado
            if filtro_query is not None:
                consulta = consulta & filtro_query

            resultado = tabela.get(consulta)
            if not resultado:
                mensagem = "não encontrado no cache ou fora do filtro"
                logging.warning("CNPJ %s não encontrado no cache ou fora do filtro.", cnpj_normalizado)
                erros_relatorio.append([cnpj_normalizado, mensagem])
                continue

            parametros = montar_parametros(resultado)
            processados += 1
            if dry_run:
                logging.info(
                    "Dry-run: update preparado para %s com dados %s",
                    cnpj_normalizado,
                    parametros,
                )
                sucesso_relatorio.append([cnpj_normalizado, "dry-run (não aplicado)"])
                continue

            try:
                cursor.execute(SQL_UPDATE, parametros)
            except Exception as erro:  # pragma: no cover - depende do Oracle em runtime
                mensagem = str(erro)
                logging.error("Falha ao aplicar update para %s: %s", cnpj_normalizado, mensagem)
                erros_relatorio.append([cnpj_normalizado, mensagem])
                continue

            registros_atualizados += cursor.rowcount
            mensagem = f"{cursor.rowcount} linha(s) afetada(s)"
            logging.info("Update aplicado para %s", cnpj_normalizado)
            sucesso_relatorio.append([cnpj_normalizado, mensagem])

        if not dry_run:
            conexao.commit()
            logging.info("Total de registros afetados: %s", registros_atualizados)

    db.close()

    escrever_relatorio(RELATORIO_OK, sucesso_relatorio)
    escrever_relatorio(RELATORIO_ERROS, erros_relatorio)


def interpretar_criterios(select: Optional[str]) -> Optional[Dict[str, object]]:
    """Converte o JSON informado na flag --select em dicionário do TinyDB."""

    if not select:
        return None

    try:
        criterios = json.loads(select)
    except json.JSONDecodeError as erro:
        raise ValueError("Valor inválido para --select; informe um JSON com pares chave/valor.") from erro

    if not isinstance(criterios, dict):
        raise ValueError("O parâmetro --select deve ser um objeto JSON (ex.: {\"cidade\": \"SAO PAULO\"}).")

    # Comentário: retornamos o dicionário cru para que Query().fragment use os valores diretamente.
    return {str(chave): valor for chave, valor in criterios.items()}


def parse_args() -> argparse.Namespace:
    """Lê argumentos da linha de comando."""

    parser = argparse.ArgumentParser(description="Atualiza fornecedores no Oracle com base no cache local.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=BASE_DIR / "files" / "fornecedores.csv",
        help="CSV usado como referência de CNPJs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa sem aplicar o commit no banco.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limita a quantidade de registros atualizados nesta execução.",
    )
    parser.add_argument(
        "--select",
        type=str,
        default=None,
        help="Filtro em JSON simples aplicado aos registros do TinyDB.",
    )
    return parser.parse_args()


def main() -> None:
    """Ponto de entrada do script."""

    FILES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    configurar_logging()
    args = parse_args()

    cnpjs = carregar_cnpjs(args.csv)
    logging.info("Total de CNPJs para atualização: %s", len(cnpjs))
    criterios = interpretar_criterios(args.select)
    aplicar_updates(cnpjs, args.dry_run, args.limit, criterios)


if __name__ == "__main__":
    main()
