"""Consola serie interactiva (puerto COM/tty) con QtSerialPort.

Reimplementación neutra del `SPC_YAT` original: lista los puertos serie, abre el
elegido y permite enviar comandos arbitrarios y ver la respuesta en vivo. Usa
`PySide6.QtSerialPort` (parte de PySide6) — sin pyserial ni dependencias nuevas,
e integrado con el bucle de eventos de Qt (lectura asíncrona por `readyRead`).

A diferencia del original **no lleva ningún comando precargado**: es una terminal
serie genérica. Los parámetros por defecto (9600 8N1, control de flujo RTS/CTS +
DSR/DTR) replican los del SPC_YAT, pero son ajustables.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from ..widgets import Card, Page, flow_row, hint, icon_button

_BAUDS = ["9600", "19200", "38400", "57600", "115200"]
# Terminador de línea que se añade al comando enviado.
_ENDINGS = [("CR (\\r)", "\r"), ("LF (\\n)", "\n"), ("CR+LF (\\r\\n)", "\r\n"), ("(ninguno)", "")]
# Código de servicio fijo del SPC_Sender original (se envía sin terminador).
# Efecto exacto no documentado (inferido: activa un modo de servicio).
_SERVICE_CODE = "A*#*#*#!952701=#*#*#*"


class SerialConsolePage(Page):
    title = "Consola serie"
    icon_concept = "terminal"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._port: QSerialPort | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)

        root.addWidget(
            hint(
                "Terminal serie genérica para el terminal (canal de servicio USB-ACM). No lleva "
                "ningún comando precargado: escribe tú los comandos. Úsala solo sobre equipo de "
                "tu propiedad."
            )
        )

        conn = Card("Conexión")
        self._ports = QComboBox()
        self._ports.setMinimumWidth(160)
        refresh = icon_button("refresh", ctx.palette.text, "Actualizar puertos")
        refresh.clicked.connect(self._refresh_ports)
        self._baud = QComboBox()
        self._baud.addItems(_BAUDS)
        self._flow = QCheckBox("Control de flujo HW (RTS/CTS + DSR/DTR)")
        self._flow.setChecked(True)
        self._ending = QComboBox()
        for label, _val in _ENDINGS:
            self._ending.addItem(label)
        self._open_btn = icon_button(
            "play", ctx.palette.accent_text, "Abrir", object_name="Primary"
        )
        self._open_btn.clicked.connect(self._toggle_open)
        conn.add(flow_row(QLabel("Puerto:"), self._ports, refresh))
        conn.add(
            flow_row(
                QLabel("Baudios:"), self._baud,
                QLabel("Fin de línea:"), self._ending,
                self._open_btn,
            )
        )
        conn.add(self._flow)
        self._desc = QLabel("Sin puerto seleccionado.")
        self._desc.setObjectName("Hint")
        self._desc.setWordWrap(True)
        conn.add(self._desc)
        self._ports.currentIndexChanged.connect(self._update_desc)
        root.addWidget(conn)

        self._out = QPlainTextEdit()
        self._out.setObjectName("Console")
        self._out.setReadOnly(True)
        self._out.setPlaceholderText("La respuesta del dispositivo aparecerá aquí…")
        root.addWidget(self._out, 1)

        self._cmd = QLineEdit()
        self._cmd.setPlaceholderText("Comando a enviar…")
        self._cmd.returnPressed.connect(self._send)
        self._send_btn = icon_button("run", ctx.palette.text, "Enviar")
        self._send_btn.clicked.connect(self._send)
        clear = icon_button("remove", ctx.palette.text, "Limpiar")
        clear.clicked.connect(self._out.clear)
        # Preset: código de servicio fijo del SPC_Sender (se envía sin terminador).
        self._svc_btn = icon_button("play", ctx.palette.text, "Código servicio (952701)")
        self._svc_btn.setToolTip(f"Envía «{_SERVICE_CODE}» — efecto inferido (modo servicio)")
        self._svc_btn.clicked.connect(self._send_service_code)
        root.addWidget(flow_row(self._cmd, self._send_btn, self._svc_btn, clear))

        self._refresh_ports()
        self._update_controls()

    # ------------------------------------------------------------------
    def _refresh_ports(self) -> None:
        current = self._ports.currentData()
        self._ports.blockSignals(True)
        self._ports.clear()
        for info in QSerialPortInfo.availablePorts():
            desc = info.description() or "—"
            self._ports.addItem(f"{info.portName()}  ({desc})", info.portName())
        self._ports.blockSignals(False)
        if self._ports.count() == 0:
            self._ports.addItem("— sin puertos —", "")
        else:
            idx = self._ports.findData(current)
            self._ports.setCurrentIndex(max(idx, 0))
        self._update_desc()

    def _update_desc(self) -> None:
        name = self._ports.currentData() or ""
        for info in QSerialPortInfo.availablePorts():
            if info.portName() == name:
                bits = [info.description(), info.manufacturer()]
                self._desc.setText("  ·  ".join(b for b in bits if b) or name)
                return
        self._desc.setText("Sin puerto seleccionado." if not name else name)

    # ------------------------------------------------------------------
    def _is_open(self) -> bool:
        return self._port is not None and self._port.isOpen()

    def _toggle_open(self) -> None:
        if self._is_open():
            self._close_port()
            return
        name = self._ports.currentData() or ""
        if not name:
            self.ctx.notify("Selecciona un puerto serie.", "warn")
            return
        port = QSerialPort(self)
        port.setPortName(name)
        port.setBaudRate(int(self._baud.currentText()))
        port.setDataBits(QSerialPort.DataBits.Data8)
        port.setParity(QSerialPort.Parity.NoParity)
        port.setStopBits(QSerialPort.StopBits.OneStop)
        port.setFlowControl(
            QSerialPort.FlowControl.HardwareControl
            if self._flow.isChecked()
            else QSerialPort.FlowControl.NoFlowControl
        )
        if not port.open(QSerialPort.OpenModeFlag.ReadWrite):
            self.ctx.notify(f"No se pudo abrir {name}: {port.errorString()}", "error")
            return
        port.readyRead.connect(self._on_ready_read)
        port.errorOccurred.connect(self._on_error)
        self._port = port
        self._out.appendPlainText(f"— Abierto {name} @ {self._baud.currentText()} 8N1 —")
        self._update_controls()

    def _close_port(self) -> None:
        if self._port is not None:
            try:
                self._port.close()
                self._port.deleteLater()
            except RuntimeError:
                pass
            self._port = None
            self._out.appendPlainText("— Puerto cerrado —")
        self._update_controls()

    def _on_error(self, error) -> None:
        if error == QSerialPort.SerialPortError.NoError:
            return
        if self._port is not None:
            self._out.appendPlainText(f"⚠ {self._port.errorString()}")
        # Un error de recurso (desconexión) deja el puerto inutilizable: ciérralo.
        if error in (
            QSerialPort.SerialPortError.ResourceError,
            QSerialPort.SerialPortError.PermissionError,
        ):
            self._close_port()

    def _on_ready_read(self) -> None:
        if self._port is None:
            return
        data = bytes(self._port.readAll()).decode("utf-8", "replace")
        if data:
            # Inserta sin forzar salto de línea (el dispositivo aporta el suyo).
            self._out.moveCursor(self._out.textCursor().MoveOperation.End)
            self._out.insertPlainText(data)
            self._out.moveCursor(self._out.textCursor().MoveOperation.End)

    def _send(self) -> None:
        if not self._is_open():
            self.ctx.notify("Abre un puerto primero.", "warn")
            return
        cmd = self._cmd.text()
        if not cmd:
            return
        ending = _ENDINGS[self._ending.currentIndex()][1]
        self._out.appendPlainText(f"» {cmd}")
        self._port.write((cmd + ending).encode())
        self._cmd.clear()

    def _send_service_code(self) -> None:
        """Envía el código de servicio fijo del SPC_Sender (sin terminador)."""
        if not self._is_open():
            self.ctx.notify("Abre un puerto primero.", "warn")
            return
        self._out.appendPlainText(f"» {_SERVICE_CODE}  (código de servicio)")
        self._port.write(_SERVICE_CODE.encode())

    # ------------------------------------------------------------------
    def _update_controls(self) -> None:
        opened = self._is_open()
        self._open_btn.setText("Cerrar" if opened else "Abrir")
        self._ports.setEnabled(not opened)
        self._baud.setEnabled(not opened)
        self._flow.setEnabled(not opened)
        self._send_btn.setEnabled(opened)
        self._cmd.setEnabled(opened)

    def shutdown(self) -> None:
        self._close_port()
