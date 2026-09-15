"""Diálogo de ADB inalámbrico: conectar a un terminal por IP y habilitar
`tcpip` en el dispositivo USB actual.

Flujo típico: con el terminal por USB, pulsar «Habilitar en USB actual»
(ejecuta `tcpip 5555`); luego desconectar el USB e introducir la IP del
terminal para conectarse por red.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..core.adb import CommandResult


class WirelessDialog(QDialog):
    def __init__(self, ctx, on_changed: Callable[[], None], parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._on_changed = on_changed
        self.setWindowTitle("ADB inalámbrico (Wi-Fi)")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Con el terminal por USB, habilita el modo Wi-Fi ADB; después "
                "introduce su IP para conectarte por red."
            )
        )

        enable_btn = QPushButton("Habilitar Wi-Fi ADB en el dispositivo USB actual (tcpip 5555)")
        enable_btn.clicked.connect(self._enable_tcpip)
        layout.addWidget(enable_btn)

        row = QHBoxLayout()
        self._ip = QLineEdit()
        self._ip.setPlaceholderText("IP del terminal (p. ej. 192.168.1.50 o 192.168.1.50:5555)")
        self._ip.returnPressed.connect(self._connect)
        connect_btn = QPushButton("Conectar")
        connect_btn.setObjectName("Primary")
        connect_btn.clicked.connect(self._connect)
        row.addWidget(self._ip, 1)
        row.addWidget(connect_btn)
        layout.addLayout(row)

        self._status = QLabel("")
        self._status.setObjectName("Hint")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    def _enable_tcpip(self) -> None:
        if not self.ctx.adb.serial:
            self._status.setText("Selecciona primero el dispositivo USB en la ventana principal.")
            return
        self._status.setText("Habilitando tcpip 5555…")

        def after(res: CommandResult) -> None:
            self._status.setText(res.text.strip() or "tcpip 5555 habilitado.")

        self.ctx.adb.tcpip(5555, after)

    def _connect(self) -> None:
        host = self._ip.text().strip()
        if not host:
            self._status.setText("Introduce la IP del terminal.")
            return
        if ":" not in host:
            host += ":5555"
        self._status.setText(f"Conectando a {host}…")

        def after(res: CommandResult) -> None:
            self._status.setText(res.text.strip() or f"Conectado a {host}.")
            self._on_changed()

        self.ctx.adb.connect(host, after)
