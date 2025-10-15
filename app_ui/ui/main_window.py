"""Janela principal da aplicação desktop."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app_ui.services import backend
from app_ui.workers.fetch_worker import FetchWorker
from app_ui.workers.update_worker import UpdateWorker


class MainWindow(QMainWindow):
    """Interface gráfica com visual inspirado em soluções TOTVS."""

    def __init__(self, qdarktheme_module: Optional[Any] = None) -> None:
        super().__init__()
        self.setWindowTitle("Atualizador WinThor")
        self.resize(1100, 700)

        self._qdarktheme = qdarktheme_module

        self._csv_path: Path = backend.default_csv_path()
        self._fetch_worker: Optional[FetchWorker] = None
        self._update_worker: Optional[UpdateWorker] = None
        self._placeholder_visivel = False
        self._historico_placeholder = False

        caminhos_backend = backend.backend_paths()
        self._log_dir: Path = caminhos_backend.get("logs", self._csv_path.parent / "log")

        self._card_labels: Dict[str, QLabel] = {}

        self._setup_menu()
        self._setup_ui()
        self._connect_signals()
        self._refresh_table()
        self._refresh_history()
        self._log_status("Pronto para iniciar.")

    # ---- Configuração da UI -------------------------------------------------
    def _setup_menu(self) -> None:
        menu = self.menuBar().addMenu("Exibir")
        self._acao_tema = QAction("Tema escuro", self)
        self._acao_tema.setCheckable(True)
        self._acao_tema.triggered.connect(self._toggle_theme)
        if not self._qdarktheme:
            self._acao_tema.setEnabled(False)
            self._acao_tema.setToolTip("Instale qdarktheme para alternar temas.")
        menu.addAction(self._acao_tema)

    def _setup_ui(self) -> None:
        self._aplicar_estilos()

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._criar_top_bar(layout)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._setup_pedidos_tab()
        self._setup_cargas_tab()
        self._setup_logs_tab()
        self._setup_status_bar()

        self._set_badge_state(self.lbl_api_status, "API: aguardando", "idle")
        self._set_badge_state(self.lbl_oracle_status, "Oracle: aguardando", "idle")

    def _setup_status_bar(self) -> None:
        barra_status = QStatusBar(self)
        self.setStatusBar(barra_status)
        self.progresso = QProgressBar()
        self.progresso.setMaximum(1)
        self.progresso.setValue(0)
        self.lbl_status = QLabel("Pronto")
        barra_status.addPermanentWidget(self.progresso)
        barra_status.addPermanentWidget(self.lbl_status)

    def _setup_pedidos_tab(self) -> None:
        pedidos = QWidget()
        pedidos_layout = QVBoxLayout(pedidos)
        pedidos_layout.setContentsMargins(16, 16, 16, 16)
        pedidos_layout.setSpacing(16)

        cards_frame = QFrame()
        cards_layout = QHBoxLayout(cards_frame)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)
        cards_layout.setAlignment(Qt.AlignLeft)

        for titulo, cor in self._cards_info():
            cards_layout.addWidget(self._criar_card(titulo, cor))
        cards_layout.addStretch()
        pedidos_layout.addWidget(cards_frame)

        botoes_layout = QHBoxLayout()
        self.btn_importar = QPushButton("Importar CSV…")
        self.btn_coletar = QPushButton("Coletar API → Cache")
        self.btn_atualizar = QPushButton("Atualizar Oracle")
        self.btn_dry_run = QPushButton("Dry-run")
        botoes_layout.addWidget(self.btn_importar)
        botoes_layout.addWidget(self.btn_coletar)
        botoes_layout.addWidget(self.btn_atualizar)
        botoes_layout.addWidget(self.btn_dry_run)
        botoes_layout.addStretch()
        pedidos_layout.addLayout(botoes_layout)

        filtros_layout = QHBoxLayout()
        filtros_layout.setSpacing(12)
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
        filtros_layout.addStretch()
        pedidos_layout.addLayout(filtros_layout)

        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["CNPJ", "Fantasia", "Cidade", "Status"])
        self.tabela.horizontalHeader().setStretchLastSection(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        pedidos_layout.addWidget(self.tabela)

        self.tab_pedidos = pedidos
        self.tabs.addTab(self.tab_pedidos, "Pedidos")

    def _setup_cargas_tab(self) -> None:
        cargas = QWidget()
        cargas_layout = QVBoxLayout(cargas)
        cargas_layout.setContentsMargins(16, 16, 16, 16)
        cargas_layout.setSpacing(16)

        self.tabela_cargas = QTableWidget(0, 3)
        self.tabela_cargas.setHorizontalHeaderLabels([
            "Execução",
            "Registros",
            "Última atualização",
        ])
        self.tabela_cargas.horizontalHeader().setStretchLastSection(True)
        self.tabela_cargas.setSelectionBehavior(QTableWidget.SelectRows)
        cargas_layout.addWidget(self.tabela_cargas)

        self.tab_cargas = cargas
        self.tabs.addTab(self.tab_cargas, "Cargas")

    def _setup_logs_tab(self) -> None:
        logs = QWidget()
        logs_layout = QVBoxLayout(logs)
        logs_layout.setContentsMargins(16, 16, 16, 16)
        logs_layout.setSpacing(16)

        self.txt_logs = QPlainTextEdit()
        self.txt_logs.setReadOnly(True)
        logs_layout.addWidget(self.txt_logs)

        self.tab_logs = logs
        self.tabs.addTab(self.tab_logs, "Logs")

    def _criar_top_bar(self, parent_layout: QVBoxLayout) -> None:
        barra = QFrame()
        barra.setObjectName("TopBar")
        barra_layout = QHBoxLayout(barra)
        barra_layout.setContentsMargins(20, 14, 20, 14)
        barra_layout.setSpacing(12)

        titulo = QLabel("Atualizador de Fornecedores")
        titulo.setObjectName("TitleLabel")
        barra_layout.addWidget(titulo)
        barra_layout.addStretch()

        self.lbl_api_status = QLabel()
        self.lbl_api_status.setObjectName("StatusBadge")
        barra_layout.addWidget(self.lbl_api_status)

        self.lbl_oracle_status = QLabel()
        self.lbl_oracle_status.setObjectName("StatusBadge")
        barra_layout.addWidget(self.lbl_oracle_status)

        parent_layout.addWidget(barra)

    def _aplicar_estilos(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: palette(base);
            }
            QWidget#TopBar {
                background-color: #004C99;
                color: white;
            }
            QLabel#TitleLabel {
                font-size: 20px;
                font-weight: 600;
            }
            QLabel#StatusBadge {
                border-radius: 12px;
                padding: 4px 12px;
                font-weight: 600;
                color: white;
                background-color: rgba(255, 255, 255, 0.25);
            }
            QFrame#DashboardCard {
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                background-color: rgba(255, 255, 255, 0.08);
            }
            QLabel#CardTitle {
                font-size: 12px;
                font-weight: 500;
                color: palette(midlight);
            }
            QLabel#CardValue {
                font-size: 26px;
                font-weight: 700;
            }
            QTabWidget::pane {
                border: none;
            }
            QStatusBar {
                padding-right: 12px;
            }
            """
        )

    def _cards_info(self) -> List[tuple[str, str]]:
        return [
            ("Em aberto", "#F8B500"),
            ("Em processamento", "#1A73E8"),
            ("Com rejeição", "#D64541"),
            ("Todos", "#00A86B"),
        ]

    def _criar_card(self, titulo: str, cor: str) -> QFrame:
        card = QFrame()
        card.setObjectName("DashboardCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        titulo_label = QLabel(titulo)
        titulo_label.setObjectName("CardTitle")
        valor_label = QLabel("0")
        valor_label.setObjectName("CardValue")
        valor_label.setStyleSheet(f"color: {cor};")

        layout.addWidget(titulo_label)
        layout.addStretch()
        layout.addWidget(valor_label, alignment=Qt.AlignRight | Qt.AlignBottom)

        self._card_labels[titulo] = valor_label
        return card

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
        self._set_badge_state(self.lbl_api_status, "API: processando", "running")
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
        self._set_badge_state(self.lbl_oracle_status, "Oracle: processando", "running")
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
            self._set_badge_state(self.lbl_api_status, "API: ok", "ok")
            self._log_status("Coleta concluída.")
            self._refresh_table()
            self._refresh_history()
        else:
            self._set_badge_state(self.lbl_api_status, "API: erro", "error")
            self._log_status("Coleta encerrada com erros.")
            self._refresh_history()

    def _finalizar_atualizacao(self, sucesso: bool) -> None:
        self._set_controles_habilitados(True)
        self._set_progresso_indeterminado(False)
        if sucesso:
            self._set_badge_state(self.lbl_oracle_status, "Oracle: ok", "ok")
            self._log_status("Atualização finalizada.")
            self._refresh_table()
            self._refresh_history()
        else:
            self._set_badge_state(self.lbl_oracle_status, "Oracle: erro", "error")
            self._log_status("Atualização encerrada com erros.")
            self._refresh_history()

    def _refresh_table(self) -> None:
        registros = backend.carregar_cache(limit=500)

        if not registros:
            self._mostrar_placeholder()
            self._atualizar_cards([])
            return

        self._limpar_placeholder()
        self.tabela.setRowCount(len(registros))
        self.tabela.clearSpans()

        self._atualizar_cards(registros)

        for linha, registro in enumerate(registros):
            self._set_item(self.tabela, linha, 0, registro.get("cnpj", ""))
            self._set_item(self.tabela, linha, 1, registro.get("fantasia", ""))
            self._set_item(self.tabela, linha, 2, registro.get("cidade", ""))
            self._set_item(self.tabela, linha, 3, registro.get("status", ""))

    def _refresh_history(self) -> None:
        if not hasattr(self, "tabela_cargas"):
            return

        registros: List[tuple[str, str, str]] = []
        historicos = [
            ("Coleta API", self._log_dir / "cacheados.csv"),
            ("Atualizações OK", self._log_dir / "atualizados_ok.csv"),
            ("Atualizações com erro", self._log_dir / "atualizados_erros.csv"),
        ]

        for descricao, caminho in historicos:
            if not caminho.exists():
                continue
            try:
                with caminho.open("r", encoding="utf-8", newline="") as arquivo:
                    leitor = csv.reader(arquivo)
                    next(leitor, None)  # cabeçalho
                    total = sum(1 for _ in leitor)
                mod_time = datetime.fromtimestamp(caminho.stat().st_mtime)
                registros.append(
                    (
                        descricao,
                        str(total),
                        mod_time.strftime("%d/%m/%Y %H:%M"),
                    )
                )
            except Exception as exc:  # pragma: no cover - leitura de arquivo externa
                registros.append((descricao, "Erro", str(exc)))

        if not registros:
            self._mostrar_placeholder_historico()
            return

        self._limpar_placeholder_historico()
        self.tabela_cargas.setRowCount(len(registros))
        self.tabela_cargas.clearSpans()
        for linha, (descricao, total, atualizado) in enumerate(registros):
            self._set_item(self.tabela_cargas, linha, 0, descricao)
            self._set_item(self.tabela_cargas, linha, 1, total)
            self._set_item(self.tabela_cargas, linha, 2, atualizado)

    def _mostrar_placeholder(self) -> None:
        if self._placeholder_visivel:
            return
        self.tabela.clearContents()
        self.tabela.setRowCount(1)
        self.tabela.setColumnCount(4)
        self.tabela.setSpan(0, 0, 1, 4)
        item = QTableWidgetItem("<Sem dados para mostrar>")
        item.setTextAlignment(Qt.AlignCenter)
        item.setFlags(Qt.ItemIsEnabled)
        self.tabela.setItem(0, 0, item)
        self._placeholder_visivel = True

    def _limpar_placeholder(self) -> None:
        if not self._placeholder_visivel:
            return
        self.tabela.clearContents()
        self.tabela.setRowCount(0)
        self.tabela.clearSpans()
        self._placeholder_visivel = False

    def _mostrar_placeholder_historico(self) -> None:
        if self._historico_placeholder:
            return
        self.tabela_cargas.clearContents()
        self.tabela_cargas.setRowCount(1)
        self.tabela_cargas.setColumnCount(3)
        self.tabela_cargas.setSpan(0, 0, 1, 3)
        item = QTableWidgetItem("<Nenhuma execução registrada>")
        item.setTextAlignment(Qt.AlignCenter)
        item.setFlags(Qt.ItemIsEnabled)
        self.tabela_cargas.setItem(0, 0, item)
        self._historico_placeholder = True

    def _limpar_placeholder_historico(self) -> None:
        if not self._historico_placeholder:
            return
        self.tabela_cargas.clearContents()
        self.tabela_cargas.setRowCount(0)
        self.tabela_cargas.clearSpans()
        self._historico_placeholder = False

    def _atualizar_cards(self, registros: List[Dict[str, str]]) -> None:
        status_counts = {
            "Em aberto": 0,
            "Em processamento": 0,
            "Com rejeição": 0,
            "Todos": len(registros),
        }

        for registro in registros:
            status = str(registro.get("status", "")).lower()
            if any(palavra in status for palavra in ("reje", "recusa")):
                status_counts["Com rejeição"] += 1
            elif "process" in status:
                status_counts["Em processamento"] += 1
            elif status:
                status_counts["Em aberto"] += 1 if "completo" not in status else 0
            else:
                status_counts["Em aberto"] += 1

        for titulo, _ in self._cards_info():
            label = self._card_labels.get(titulo)
            if label:
                label.setText(str(status_counts.get(titulo, 0)))

    def _set_item(self, tabela: QTableWidget, row: int, column: int, valor: str) -> None:
        item = QTableWidgetItem(valor)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tabela.setItem(row, column, item)

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
        if hasattr(self, "txt_logs"):
            self.txt_logs.appendPlainText(mensagem)
            self.txt_logs.verticalScrollBar().setValue(self.txt_logs.verticalScrollBar().maximum())

    def _exibir_erro(self, mensagem: str) -> None:
        self._set_controles_habilitados(True)
        self._set_progresso_indeterminado(False)
        QMessageBox.critical(self, "Erro", mensagem)
        self._log_status(mensagem)
        if hasattr(self, "tab_logs"):
            self.tabs.setCurrentWidget(self.tab_logs)

    def _set_badge_state(self, badge: QLabel, texto: str, estado: str) -> None:
        cores = {
            "idle": "#3A6EA5",
            "ok": "#27AE60",
            "error": "#C0392B",
            "running": "#F1C40F",
        }
        cor = cores.get(estado, "#3A6EA5")
        badge.setText(texto)
        badge.setStyleSheet(
            f"border-radius: 12px; padding: 4px 12px; font-weight: 600; color: white; background-color: {cor};"
        )

    def _toggle_theme(self, ativo: bool) -> None:
        if not self._qdarktheme:
            return
        tema = "dark" if ativo else "light"
        self._qdarktheme.setup_theme(theme=tema)
        estado = "escuro" if ativo else "claro"
        self._log_status(f"Tema {estado} aplicado.")
