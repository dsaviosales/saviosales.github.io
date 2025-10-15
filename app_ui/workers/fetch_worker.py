"""Worker responsável por executar a coleta em segundo plano."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

from app_ui.services import backend


class FetchWorker(QThread):
    """Executa a coleta da API para o cache TinyDB sem travar a UI."""

    message = Signal(str)
    error = Signal(str)
    finished = Signal(bool)

    def __init__(
        self,
        csv_path: Path,
        api_url: Optional[str] = None,
        max_rps: Optional[int] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
        dry_run: bool = False,
    ) -> None:
        super().__init__()
        self._csv_path = csv_path
        self._api_url = api_url
        self._max_rps = max_rps
        self._timeout = timeout
        self._retries = retries
        self._dry_run = dry_run

    def run(self) -> None:  # pragma: no cover - roda em QThread
        try:
            backend.coletar_para_cache(
                csv_path=self._csv_path,
                api_url=self._api_url,
                max_rps=self._max_rps,
                timeout=self._timeout,
                retries=self._retries,
                dry_run=self._dry_run,
                callback=self.message.emit,
            )
        except Exception as exc:  # pragma: no cover - relatado na interface
            self.error.emit(str(exc))
            self.finished.emit(False)
            return

        self.finished.emit(True)
