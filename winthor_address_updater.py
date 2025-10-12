"""Automated address updater for Winthor ERP using Receita Federal's CNPJ API.

This module orchestrates the periodic validation of client addresses stored in the
Winthor ERP database. For each client selected for validation, the script fetches the
latest address information from the Receita Federal API, normalizes it, compares it to
the local record, and updates the ERP when necessary. Detailed execution logs are
produced for observability.

Example usage::

    $ export WINTHOR_DSN="Driver=Oracle;Server=..."
    $ export WINTHOR_DB_USER="username"
    $ export WINTHOR_DB_PASSWORD="password"
    $ python winthor_address_updater.py --batch-size 200 --interval-hours 24

The script can be run on demand (using ``--run-once``) or as a long-running process
that sleeps for ``interval-hours`` between executions. Credentials are sourced from
environment variables to avoid leaking secrets in version control.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import logging
import os
import time
from contextlib import contextmanager
from typing import Dict, Iterator, List, Optional, Tuple

import pyodbc  # type: ignore
import requests


DEFAULT_BATCH_SIZE = 500
DEFAULT_INTERVAL_HOURS = 24
LOG_DIRECTORY = "logs"

RECEITA_FEDERAL_CNPJ_ENDPOINT = "https://www.receitaws.com.br/v1/cnpj/{cnpj}"


@dataclasses.dataclass
class ClientRecord:
    """Representation of the relevant client fields fetched from Winthor."""

    client_id: int
    cnpj: str
    razao_social: str
    endereco: Dict[str, Optional[str]]


@dataclasses.dataclass
class Address:
    """Normalized address representation."""

    street: str
    number: str
    complement: str
    district: str
    city: str
    state: str
    zipcode: str

    def to_winthor_payload(self) -> Dict[str, str]:
        """Convert the address to a mapping suitable for Winthor update queries."""

        return {
            "endereco": self.street,
            "numero": self.number,
            "complemento": self.complement,
            "bairro": self.district,
            "cidade": self.city,
            "uf": self.state,
            "cep": self.zipcode,
        }

    def as_tuple(self) -> Tuple[str, str, str, str, str, str, str]:
        """Tuple representation used for comparisons."""

        return (
            self.street,
            self.number,
            self.complement,
            self.district,
            self.city,
            self.state,
            self.zipcode,
        )


class ReceitaFederalClient:
    """HTTP client for the Receita Federal CNPJ endpoint."""

    def __init__(self, timeout: float = 20.0, max_retries: int = 3) -> None:
        self._timeout = timeout
        self._max_retries = max_retries

    def fetch_company_data(self, cnpj: str) -> Dict[str, object]:
        """Fetch company information for a given CNPJ.

        Raises:
            RuntimeError: If the API call fails or returns an error payload.
        """

        normalized_cnpj = self._normalize_cnpj(cnpj)
        last_error: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = requests.get(
                    RECEITA_FEDERAL_CNPJ_ENDPOINT.format(cnpj=normalized_cnpj),
                    timeout=self._timeout,
                )
                if response.status_code != 200:
                    raise RuntimeError(
                        f"Receita Federal API returned status {response.status_code} for CNPJ {cnpj}"
                    )
                payload = response.json()
                if payload.get("status") != "OK":
                    message = payload.get("message") or payload.get("motivo") or "unknown error"
                    raise RuntimeError(f"API error for CNPJ {cnpj}: {message}")
                return payload
            except Exception as exc:  # noqa: BLE001 - propagate after retries
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(2 ** (attempt - 1))
        assert last_error is not None  # for type checkers
        raise RuntimeError(f"Failed to fetch data for CNPJ {cnpj}: {last_error}")

    @staticmethod
    def _normalize_cnpj(cnpj: str) -> str:
        digits = [ch for ch in cnpj if ch.isdigit()]
        if len(digits) != 14:
            raise ValueError(f"Invalid CNPJ: {cnpj}")
        return "".join(digits)


class WinthorDatabase:
    """Database helper encapsulating queries against the Winthor ERP."""

    def __init__(self, dsn: str, user: str, password: str) -> None:
        self._dsn = dsn
        self._user = user
        self._password = password

    @contextmanager
    def connect(self) -> Iterator[pyodbc.Connection]:
        connection = pyodbc.connect(self._dsn, user=self._user, password=self._password)
        try:
            yield connection
        finally:
            connection.close()

    def fetch_clients_pending_validation(
        self, batch_size: int
    ) -> List[ClientRecord]:
        """Fetch clients that require address validation."""

        query = """
            SELECT
                cli.codigo_cliente,
                cli.cnpj,
                cli.razao_social,
                cli.endereco,
                cli.numero,
                cli.complemento,
                cli.bairro,
                cli.cidade,
                cli.uf,
                cli.cep
            FROM pcclient cli
            WHERE cli.cnpj IS NOT NULL
              AND cli.cnpj <> ''
              AND (cli.validar_endereco = 'S' OR cli.endereco IS NULL OR cli.endereco = '')
            FETCH FIRST ? ROWS ONLY
        """
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(query, batch_size)
            records: List[ClientRecord] = []
            for row in cursor.fetchall():
                records.append(
                    ClientRecord(
                        client_id=row.codigo_cliente,
                        cnpj=row.cnpj,
                        razao_social=row.razao_social,
                        endereco={
                            "endereco": row.endereco or "",
                            "numero": row.numero or "",
                            "complemento": row.complemento or "",
                            "bairro": row.bairro or "",
                            "cidade": row.cidade or "",
                            "uf": row.uf or "",
                            "cep": row.cep or "",
                        },
                    )
                )
        return records

    def update_client_address(self, client_id: int, address: Address) -> None:
        """Persist the address fields in Winthor."""

        payload = address.to_winthor_payload()
        query = """
            UPDATE pcclient
               SET endereco = ?,
                   numero = ?,
                   complemento = ?,
                   bairro = ?,
                   cidade = ?,
                   uf = ?,
                   cep = ?,
                   validar_endereco = 'N',
                   dt_atualizacao = SYSDATE
             WHERE codigo_cliente = ?
        """
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                query,
                (
                    payload["endereco"],
                    payload["numero"],
                    payload["complemento"],
                    payload["bairro"],
                    payload["cidade"],
                    payload["uf"],
                    payload["cep"],
                    client_id,
                ),
            )
            connection.commit()

    def record_failure(self, client_id: int, reason: str) -> None:
        """Optionally persist failure metadata for future retries."""

        query = """
            INSERT INTO pcclient_log_endereco (codigo_cliente, motivo_falha, data_registro)
            VALUES (?, ?, SYSDATE)
        """
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(query, (client_id, reason[:255]))
            connection.commit()


def build_logger() -> logging.Logger:
    os.makedirs(LOG_DIRECTORY, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    logfile = os.path.join(LOG_DIRECTORY, f"winthor_address_update_{timestamp}.log")

    logger = logging.getLogger("winthor_address_updater")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(logfile)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def normalize_address(api_payload: Dict[str, object]) -> Address:
    """Normalize the API response into an Address object."""

    def _clean(value: Optional[str]) -> str:
        if not value:
            return ""
        return " ".join(value.strip().upper().split())

    return Address(
        street=_clean(api_payload.get("logradouro")),
        number=_clean(api_payload.get("numero")),
        complement=_clean(api_payload.get("complemento")),
        district=_clean(api_payload.get("bairro")),
        city=_clean(api_payload.get("municipio")),
        state=_clean(api_payload.get("uf")),
        zipcode=_clean(api_payload.get("cep")),
    )


def needs_update(current: Dict[str, Optional[str]], new_address: Address) -> bool:
    """Determine if the existing address differs from the new one."""

    current_tuple = (
        (current.get("endereco") or "").strip().upper(),
        (current.get("numero") or "").strip().upper(),
        (current.get("complemento") or "").strip().upper(),
        (current.get("bairro") or "").strip().upper(),
        (current.get("cidade") or "").strip().upper(),
        (current.get("uf") or "").strip().upper(),
        (current.get("cep") or "").strip().upper(),
    )
    return current_tuple != new_address.as_tuple()


def summarize_execution(
    start_time: dt.datetime,
    end_time: dt.datetime,
    processed: int,
    updated: int,
    failures: List[Tuple[int, str]],
) -> str:
    summary = {
        "started_at": start_time.isoformat(),
        "finished_at": end_time.isoformat(),
        "clients_processed": processed,
        "addresses_updated": updated,
        "failures": [
            {"client_id": client_id, "reason": reason}
            for client_id, reason in failures
        ],
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


def run_batch(
    db: WinthorDatabase,
    api_client: ReceitaFederalClient,
    batch_size: int,
    logger: logging.Logger,
) -> Tuple[int, int, List[Tuple[int, str]]]:
    """Process a single batch of clients."""

    clients = db.fetch_clients_pending_validation(batch_size)
    processed = 0
    updated = 0
    failures: List[Tuple[int, str]] = []

    for client in clients:
        processed += 1
        try:
            api_data = api_client.fetch_company_data(client.cnpj)
            address = normalize_address(api_data)
            if not address.street or not address.city or not address.state:
                raise RuntimeError("Incomplete address received from API")
            if needs_update(client.endereco, address):
                db.update_client_address(client.client_id, address)
                updated += 1
                logger.info(
                    "Updated address for client %s (%s)",
                    client.razao_social,
                    client.cnpj,
                )
            else:
                logger.info(
                    "Address already up-to-date for client %s (%s)",
                    client.razao_social,
                    client.cnpj,
                )
        except Exception as exc:  # noqa: BLE001 - logging unexpected exceptions
            reason = str(exc)
            failures.append((client.client_id, reason))
            logger.error(
                "Failed to process client %s (%s): %s",
                client.razao_social,
                client.cnpj,
                reason,
            )
            try:
                db.record_failure(client.client_id, reason)
            except Exception as db_exc:  # noqa: BLE001 - best effort logging
                logger.error(
                    "Failed to record failure for client %s: %s",
                    client.client_id,
                    db_exc,
                )

    return processed, updated, failures


def run_orchestration(
    db: WinthorDatabase,
    api_client: ReceitaFederalClient,
    batch_size: int,
    logger: logging.Logger,
) -> None:
    start_time = dt.datetime.now()
    processed, updated, failures = run_batch(db, api_client, batch_size, logger)
    end_time = dt.datetime.now()

    summary = summarize_execution(start_time, end_time, processed, updated, failures)
    logger.info("Execution summary:\n%s", summary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Winthor address updater")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Maximum number of clients processed per execution (default: %(default)s)",
    )
    parser.add_argument(
        "--interval-hours",
        type=float,
        default=DEFAULT_INTERVAL_HOURS,
        help="Interval in hours between executions when running continuously",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Execute a single batch and exit",
    )
    return parser.parse_args()


def load_credentials_from_env() -> Tuple[str, str, str]:
    dsn = os.getenv("WINTHOR_DSN")
    user = os.getenv("WINTHOR_DB_USER")
    password = os.getenv("WINTHOR_DB_PASSWORD")

    if not dsn or not user or not password:
        raise EnvironmentError(
            "WINTHOR_DSN, WINTHOR_DB_USER and WINTHOR_DB_PASSWORD environment variables are required"
        )
    return dsn, user, password


def main() -> None:
    args = parse_args()
    logger = build_logger()
    logger.info("Starting Winthor address updater")

    dsn, user, password = load_credentials_from_env()
    db = WinthorDatabase(dsn=dsn, user=user, password=password)
    api_client = ReceitaFederalClient()

    while True:
        run_orchestration(db, api_client, args.batch_size, logger)
        if args.run_once:
            break
        logger.info(
            "Sleeping for %.2f hours before next execution", args.interval_hours
        )
        time.sleep(args.interval_hours * 3600)


if __name__ == "__main__":
    main()
