"""Camada de integração entre a interface gráfica e os scripts CLI existentes."""
from __future__ import annotations

import importlib.util
import logging
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, List, Optional

from tinydb import TinyDB

# Diretórios básicos do projeto
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "atualizador-dados-winthor"


class _StatusHandler(logging.Handler):
    """Encaminha mensagens de log para um callback da interface."""

    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - interação com UI
        mensagem = self.format(record)
        self._callback(mensagem)


@lru_cache(maxsize=None)
def _load_backend_module(nome: str, arquivo: str):
    caminho = BACKEND_DIR / arquivo
    if not caminho.exists():
        raise FileNotFoundError(f"Módulo backend não encontrado: {caminho}")

    spec = importlib.util.spec_from_file_location(nome, caminho)
    if spec is None or spec.loader is None:
        raise ImportError(f"Não foi possível carregar o módulo em {caminho}")

    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)  # type: ignore[arg-type]
    return modulo


def _buscardados_module():
    return _load_backend_module("app_backend_buscardados", "buscardados.py")


def _atualizadados_module():
    return _load_backend_module("app_backend_atualizadados", "atualizadados.py")


def default_csv_path() -> Path:
    """Retorna o caminho padrão do CSV usado pelo backend."""

    modulo = _buscardados_module()
    return Path(modulo.FILES_DIR) / "fornecedores.csv"


def carregar_cache(limit: Optional[int] = None) -> List[Dict[str, str]]:
    """Lê os registros atuais do TinyDB para exibição na interface."""

    modulo = _buscardados_module()
    caminho_cache: Path = Path(modulo.CACHE_PATH)
    if not caminho_cache.exists():
        return []

    db = TinyDB(str(caminho_cache))
    tabela = db.table("fornecedores")
    registros = tabela.all()
    db.close()

    if limit is not None:
        registros = registros[:limit]

    itens: List[Dict[str, str]] = []
    for registro in registros:
        fantasia = str(registro.get("fantasia", "") or "").strip()
        cidade = str(registro.get("cidade", "") or "").strip()
        status = "Completo" if fantasia and cidade else "Incompleto"
        itens.append(
            {
                "cnpj": str(registro.get("cnpj", "")),
                "fantasia": fantasia,
                "cidade": cidade,
                "status": status,
            }
        )
    return itens


def _executar_com_logs(callback: Optional[Callable[[str], None]]) -> Optional[_StatusHandler]:
    if callback is None:
        return None

    handler = _StatusHandler(callback)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logging.getLogger().addHandler(handler)
    return handler


def _remover_handler(handler: Optional[_StatusHandler]) -> None:
    if handler:
        logging.getLogger().removeHandler(handler)


def coletar_para_cache(
    csv_path: Path,
    api_url: Optional[str] = None,
    max_rps: Optional[int] = None,
    timeout: Optional[float] = None,
    retries: Optional[int] = None,
    dry_run: bool = False,
    callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Executa o fluxo de coleta reutilizando as funções do script CLI."""

    modulo = _buscardados_module()
    modulo.FILES_DIR.mkdir(parents=True, exist_ok=True)
    modulo.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    modulo.configurar_logging()

    handler = _executar_com_logs(callback)
    try:
        cnpjs = modulo.carregar_cnpjs(Path(csv_path))
        if callback:
            callback(f"{len(cnpjs)} CNPJ(s) carregados do CSV.")
        modulo.atualizar_cache(
            cnpjs,
            api_url or modulo.DEFAULT_API_URL,
            dry_run,
            timeout=timeout or modulo.DEFAULT_TIMEOUT_SECONDS,
            retry_limit=retries or modulo.DEFAULT_RETRY_LIMIT,
            max_rps=max_rps or modulo.DEFAULT_MAX_RPS,
        )
    finally:
        _remover_handler(handler)


def atualizar_oracle(
    csv_path: Path,
    dry_run: bool = False,
    limit: Optional[int] = None,
    select: Optional[str] = None,
    callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Executa o fluxo de atualização no Oracle reaproveitando o backend existente."""

    modulo = _atualizadados_module()
    modulo.FILES_DIR.mkdir(parents=True, exist_ok=True)
    modulo.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    modulo.configurar_logging()

    handler = _executar_com_logs(callback)
    try:
        cnpjs = modulo.carregar_cnpjs(Path(csv_path))
        if callback:
            callback(f"{len(cnpjs)} CNPJ(s) preparados para atualização.")
        criterios = modulo.interpretar_criterios(select)
        modulo.aplicar_updates(cnpjs, dry_run, limit, criterios)
    finally:
        _remover_handler(handler)


def backend_paths() -> Dict[str, Path]:
    """Exibe caminhos úteis para debug ou telemetria."""

    modulo = _buscardados_module()
    return {
        "base": Path(modulo.BASE_DIR),
        "cache": Path(modulo.CACHE_PATH),
        "logs": Path(modulo.LOG_PATH.parent),
    }
