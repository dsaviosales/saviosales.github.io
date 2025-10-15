"""Janela principal da aplicação desktop."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)

from app_ui.services import backend
from app_ui.workers.fetch_worker import FetchWorker
from app_ui.workers.update_worker import UpdateWorker


class MainWindow(QMainWindow):
    """Interface gráfica mínima para orquestrar o pipeline."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Atualizador WinThor")
        self.resize(960, 640)

        self._csv_path: Path = backend.default_csv_path()
        self._fetch_worker: Optional[FetchWorker] = None
        self._update_worker: Optional[UpdateWorker] = None

        self._setup_ui()
        self._connect_signals()
        self._refresh_table()
        self._log_status("Pronto para iniciar.")

    # ---- Configuração da UI -------------------------------------------------
    def _setup_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        central.setLayout(layout)
        self.setCentralWidget(central)

        # Linha de botões principais
        botoes_layout = QHBoxLayout()
        self.btn_importar = QPushButton("Importar CSV…")
        self.btn_coletar = QPushButton("Coletar API → Cache")
        self.btn_atualizar = QPushButton("Atualizar Oracle")
        self.btn_dry_run = QPushButton("Dry-run")
        botoes_layout.addWidget(self.btn_importar)
        botoes_layout.addWidget(self.btn_coletar)
        botoes_layout.addWidget(self.btn_atualizar)
        botoes_layout.addWidget(self.btn_dry_run)
        layout.addLayout(botoes_layout)

        # Linha de filtros simples (a lógica pode evoluir futuramente)
        filtros_layout = QHBoxLayout()
        self.ed_busca = QLineEdit()
        self.ed_busca.setPlaceholderText("Buscar por CNPJ ou fantasia (placeholder)")
        self.combo_periodo = QComboBox()
        self.combo_periodo.addItems([
            "Últimos 30 dias",
            "Últimos 90 dias",
            "Todo o histórico",
        ])
        filtros_layout.addWidget(QLabel("Busca:"))
        filtros_layout.addWidget(self.ed_busca)
        filtros_layout.addWidget(QLabel("Período:"))
        filtros_layout.addWidget(self.combo_periodo)
        layout.addLayout(filtros_layout)

        # Tabela com registros do cache TinyDB
        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["CNPJ", "Fantasia", "Cidade", "Status"])
        self.tabela.horizontalHeader().setStretchLastSection(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.tabela)

        # Barra de status com progresso
        barra_status = QStatusBar(self)
        self.setStatusBar(barra_status)
        self.progresso = QProgressBar()
        self.progresso.setMaximum(1)
        self.progresso.setValue(0)
        self.lbl_status = QLabel("Pronto")
        barra_status.addPermanentWidget(self.progresso)
        barra_status.addPermanentWidget(self.lbl_status)

    def _connect_signals(self) -> None:
        self.btn_importar.clicked.connect(self._selecionar_csv)
        self.btn_coletar.clicked.connect(self._iniciar_coleta)
        self.btn_atualizar.clicked.connect(self._iniciar_atualizacao)
        self.btn_dry_run.clicked.connect(lambda: self._iniciar_atualizacao(dry_run=True))

    # ---- Ações ---------------------------------------------------------------
    def _selecionar_csv(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo CSV",
            str(self._csv_path.parent),
            "Arquivos CSV (*.csv)",
        )
        if caminho:
            self._csv_path = Path(caminho)
            self._log_status(f"CSV selecionado: {self._csv_path}")

    def _iniciar_coleta(self) -> None:
        if self._fetch_worker and self._fetch_worker.isRunning():
            return

        self._set_controles_habilitados(False)
        self._set_progresso_indeterminado(True)
        self._log_status("Iniciando coleta via API…")

        self._fetch_worker = FetchWorker(csv_path=self._csv_path)
        self._fetch_worker.message.connect(self._log_status)
        self._fetch_worker.error.connect(self._exibir_erro)
        self._fetch_worker.finished.connect(self._finalizar_coleta)
        self._fetch_worker.start()

    def _iniciar_atualizacao(self, dry_run: bool = False) -> None:
        if self._update_worker and self._update_worker.isRunning():
            return

        self._set_controles_habilitados(False)
        self._set_progresso_indeterminado(True)
        mensagem = "Dry-run no Oracle…" if dry_run else "Atualizando Oracle…"
        self._log_status(mensagem)

        self._update_worker = UpdateWorker(csv_path=self._csv_path, dry_run=dry_run)
        self._update_worker.message.connect(self._log_status)
        self._update_worker.error.connect(self._exibir_erro)
        self._update_worker.finished.connect(self._finalizar_atualizacao)
        self._update_worker.start()

    # ---- Atualização de interface -------------------------------------------
    def _finalizar_coleta(self, sucesso: bool) -> None:
        self._set_controles_habilitados(True)
        self._set_progresso_indeterminado(False)
        if sucesso:
            self._log_status("Coleta concluída.")
            self._refresh_table()
        else:
            self._log_status("Coleta encerrada com erros.")

    def _finalizar_atualizacao(self, sucesso: bool) -> None:
        self._set_controles_habilitados(True)
        self._set_progresso_indeterminado(False)
        if sucesso:
            self._log_status("Atualização finalizada.")
            self._refresh_table()
        else:
            self._log_status("Atualização encerrada com erros.")

    def _refresh_table(self) -> None:
        registros = backend.carregar_cache(limit=500)
        self.tabela.setRowCount(len(registros))
        for linha, registro in enumerate(registros):
            self._set_item(linha, 0, registro.get("cnpj", ""))
            self._set_item(linha, 1, registro.get("fantasia", ""))
            self._set_item(linha, 2, registro.get("cidade", ""))
            self._set_item(linha, 3, registro.get("status", ""))

    def _set_item(self, row: int, column: int, valor: str) -> None:
        item = QTableWidgetItem(valor)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.tabela.setItem(row, column, item)

    def _set_controles_habilitados(self, habilitado: bool) -> None:
        self.btn_importar.setEnabled(habilitado)
        self.btn_coletar.setEnabled(habilitado)
        self.btn_atualizar.setEnabled(habilitado)
        self.btn_dry_run.setEnabled(habilitado)

    def _set_progresso_indeterminado(self, ativo: bool) -> None:
        if ativo:
            self.progresso.setRange(0, 0)
        else:
            self.progresso.setRange(0, 1)
            self.progresso.setValue(0)

    def _log_status(self, mensagem: str) -> None:
        self.lbl_status.setText(mensagem)

    def _exibir_erro(self, mensagem: str) -> None:
        self._set_controles_habilitados(True)
        self._set_progresso_indeterminado(False)
        QMessageBox.critical(self, "Erro", mensagem)
        self._log_status(mensagem)
