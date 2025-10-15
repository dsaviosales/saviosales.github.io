"""Testes unitários para o mapeamento de TIPOFORNEC."""
from importlib import import_module
from pathlib import Path
import sys

PROJETO_DIR = Path(__file__).resolve().parents[1] / "atualizador-dados-winthor"
if str(PROJETO_DIR) not in sys.path:
    sys.path.insert(0, str(PROJETO_DIR))

tratardados = import_module("utils.tratardados")
mapear_tipofornec = getattr(tratardados, "mapear_tipofornec")


def test_tipofornec_industria():
    assert mapear_tipofornec("01.23-4") == "I"


def test_tipofornec_comercio():
    assert mapear_tipofornec("45.10-0") == "C"


def test_tipofornec_varejo():
    assert mapear_tipofornec("47.19-2") == "V"


def test_tipofornec_outros_intervalo_superior():
    assert mapear_tipofornec("72.10-0") == "O"


def test_tipofornec_valor_invalido():
    assert mapear_tipofornec("") == "O"


def test_tipofornec_none():
    assert mapear_tipofornec(None) == "O"
