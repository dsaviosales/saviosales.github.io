"""Ponto de entrada da aplicação desktop."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app_ui.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    try:  # Tema escuro opcional
        import qdarktheme  # type: ignore

        qdarktheme.setup_theme()
    except Exception:  # pragma: no cover - dependência opcional
        pass

    janela = MainWindow()
    janela.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
