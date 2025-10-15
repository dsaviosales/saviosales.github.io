"""Utilitário simples para empacotar os executáveis com PyInstaller."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, List

try:
    from PyInstaller import __main__ as pyinstaller
except ImportError as exc:  # pragma: no cover - depende do ambiente de build
    raise SystemExit(
        "PyInstaller não está instalado. Execute 'pip install pyinstaller' antes de rodar o build."
    ) from exc

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"

TARGETS = {
    "buscardados": REPO_ROOT / "atualizador-dados-winthor" / "buscardados.py",
    "atualizadados": REPO_ROOT / "atualizador-dados-winthor" / "atualizadados.py",
    "atualizador-ui": REPO_ROOT / "app_ui" / "main.py",
}


def _run_pyinstaller(name: str, entrypoint: Path, onefile: bool) -> None:
    """Invoca o PyInstaller com parâmetros consistentes para cada binário."""

    if not entrypoint.exists():
        raise FileNotFoundError(f"Entrypoint '{entrypoint}' não encontrado.")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    args: List[str] = [
        "--clean",
        "--noconfirm",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        f"--name={name}",
    ]

    if onefile:
        args.append("--onefile")

    if name == "atualizador-ui":
        # Inclui tema alternativo por padrão para evitar falhas em tempo de execução.
        args.extend(["--hidden-import=qdarktheme"])

    args.append(str(entrypoint))

    logging.info("Empacotando %s a partir de %s", name, entrypoint)
    pyinstaller.run(args)


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera executáveis com PyInstaller.")
    parser.add_argument(
        "--target",
        choices=sorted(TARGETS.keys()),
        action="append",
        help="Nome do alvo a ser empacotado. Se omitido, todos serão construídos.",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Gera executáveis em arquivo único (--onefile).",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> None:
    args = _parse_args(argv or sys.argv[1:])
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    alvos = args.target or sorted(TARGETS.keys())
    for nome in alvos:
        entry = TARGETS[nome]
        _run_pyinstaller(nome, entry, args.onefile)

    logging.info("Build finalizado. Artefatos disponíveis em %s", DIST_DIR)


if __name__ == "__main__":  # pragma: no cover - script de linha de comando
    main()
