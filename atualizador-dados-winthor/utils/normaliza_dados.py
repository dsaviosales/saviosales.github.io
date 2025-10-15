"""Rotinas de normalização específicas para dados vindos da API de CNPJ."""
from __future__ import annotations

from typing import Any, Dict

from .tratardados import mapear_tipofornec, normalizar_cnpj, somente_digitos


def normalizar_resposta_api(cnpj: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai apenas os campos necessários e aplica normalizações básicas."""

    cnae_principal = ""
    atividades = payload.get("atividade_principal")
    if isinstance(atividades, list) and atividades:
        cnae_principal = atividades[0].get("code", "")

    endereco = payload.get("logradouro", "")
    numero = payload.get("numero", "")
    bairro = payload.get("bairro", "")
    cep = somente_digitos(payload.get("cep", ""))
    cidade = payload.get("municipio", "")
    estado = payload.get("uf", "")
    fantasia = payload.get("fantasia") or payload.get("nome", "")
    email = payload.get("email", "")

    # Comentário breve: consolidamos os campos numa estrutura pronta para o TinyDB.
    return {
        "cnpj": normalizar_cnpj(cnpj),
        "ender": endereco.strip(),
        "numeroend": str(numero).strip(),
        "bairro": bairro.strip(),
        "cep": cep.zfill(8) if cep else "",
        "cidade": cidade.strip(),
        "estado": estado.strip(),
        "fantasia": fantasia.strip(),
        "email": email.strip(),
        "tipofornec": mapear_tipofornec(cnae_principal),
    }
