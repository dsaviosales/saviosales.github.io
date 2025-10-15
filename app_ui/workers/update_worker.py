"""Worker responsável pela etapa de atualização no Oracle."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

from app_ui.services import backend


class UpdateWorker(QThread):
    """Encapsula a execução do script de atualização."""

    message = Signal(str)
    error = Signal(str)
    finished = Signal(bool)

    def __init__(
        self,
        csv_path: Path,
        dry_run: bool = False,
        limit: Optional[int] = None,
        select: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._csv_path = csv_path
        self._dry_run = dry_run
        self._limit = limit
        self._select = select

    def run(self) -> None:  # pragma: no cover - roda em QThread
        try:
            backend.atualizar_oracle(
                csv_path=self._csv_path,
                dry_run=self._dry_run,
                limit=self._limit,
                select=self._select,
                callback=self.message.emit,
            )
        except Exception as exc:  # pragma: no cover - relatado na interface
            self.error.emit(str(exc))
            self.finished.emit(False)
            return

        self.finished.emit(True)
