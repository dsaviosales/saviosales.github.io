"""Ponto de entrada da aplicação desktop."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app_ui.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)

    tema = None
    try:  # Tema opcional controlado pela janela principal
        import qdarktheme  # type: ignore

        tema = qdarktheme
        tema.setup_theme(theme="light")
    except Exception:  # pragma: no cover - dependência opcional
        tema = None

    janela = MainWindow(qdarktheme_module=tema)
    janela.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
