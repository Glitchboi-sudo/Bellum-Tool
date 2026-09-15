"""Visor de registros en vivo: logcat de Android o el syslog de sistema de PAX.

Ambas fuentes comparten toda la infraestructura de streaming/filtro/guardado;
solo cambia el comando que se lanza: `logcat -v time *:P` o `syslog`
(el servicio `paxlog:system` del terminal).
"""

from __future__ import annotations

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from .. import icons
from ..widgets import Page, icon_button

_MAX_BLOCKS = 5000  # límite de líneas en pantalla para no consumir memoria sin fin


class LogcatPage(Page):
    title = "Registros"
    icon_concept = "logs"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._proc: QProcess | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(12)

        bar = QHBoxLayout()
        self._toggle = icon_button(
            "play", ctx.palette.accent_text, "Iniciar", object_name="Primary"
        )
        self._toggle.clicked.connect(self._toggle_stream)
        self._source = QComboBox()
        self._source.addItem("Logcat (Android)", "logcat")
        self._source.addItem("PAX syslog (sistema)", "syslog")
        self._source.currentIndexChanged.connect(self._on_source_changed)
        self._priority = QComboBox()
        self._priority.addItems(["Verbose", "Debug", "Info", "Warn", "Error", "Fatal"])
        self._priority.setCurrentText("Info")
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filtrar líneas (texto contenido)…")
        self._filter.textChanged.connect(self._reapply_filter)
        clear_btn = icon_button("remove", ctx.palette.text, "Limpiar")
        clear_btn.clicked.connect(self._clear)
        save_btn = icon_button("save", ctx.palette.text, "Guardar…")
        save_btn.clicked.connect(self._save)
        bar.addWidget(self._toggle)
        bar.addWidget(self._source)
        bar.addWidget(self._priority)
        bar.addWidget(self._filter, 1)
        bar.addWidget(clear_btn)
        bar.addWidget(save_btn)
        root.addLayout(bar)

        self._view = QPlainTextEdit()
        self._view.setObjectName("Console")
        self._view.setReadOnly(True)
        self._view.setPlaceholderText("Pulsa «Iniciar» para ver el registro en vivo del terminal…")
        self._view.setMaximumBlockCount(_MAX_BLOCKS)
        self._view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        root.addWidget(self._view, 1)

        self._all_lines: list[str] = []

    # ------------------------------------------------------------------
    def _toggle_stream(self) -> None:
        if self._proc is not None:
            self._stop()
        else:
            self._start()

    def _on_source_changed(self) -> None:
        # La prioridad solo aplica a logcat; el syslog de PAX es un volcado plano.
        self._priority.setEnabled(self._source.currentData() == "logcat")
        if self._proc is not None:
            self._stop()  # reiniciar con la nueva fuente es responsabilidad del usuario

    def _start(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        if self._source.currentData() == "syslog":
            args = ["syslog"]
        else:
            prio = self._priority.currentText()[0]  # V/D/I/W/E/F
            args = ["logcat", "-v", "time", f"*:{prio}"]
        self._proc = self.ctx.adb.start(args)
        if self._proc is None:
            self.ctx.notify("No se pudo iniciar (¿binario pax_adb configurado?).", "error")
            return
        self._proc.readyReadStandardOutput.connect(self._on_output)
        self._proc.finished.connect(self._on_finished)
        self._set_toggle(running=True)

    def _set_toggle(self, running: bool) -> None:
        text = "  Detener" if running else "  Iniciar"
        concept = "stop" if running else "play"
        self._toggle.setText(text)
        ic = icons.icon(concept, self.ctx.palette.accent_text)
        if not ic.isNull():
            self._toggle.setIcon(ic)

    def _stop(self) -> None:
        if self._proc is not None:
            self._proc.kill()

    def _on_finished(self, *_):
        self._proc = None
        self._set_toggle(running=False)

    def _on_output(self) -> None:
        if self._proc is None:
            return
        chunk = bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        needle = self._filter.text().strip().lower()
        for line in chunk.splitlines():
            self._all_lines.append(line)
            if not needle or needle in line.lower():
                self._view.appendPlainText(line)
        # acota el buffer "crudo" usado para re-filtrar
        if len(self._all_lines) > _MAX_BLOCKS * 4:
            self._all_lines = self._all_lines[-_MAX_BLOCKS * 2:]

    def _reapply_filter(self) -> None:
        needle = self._filter.text().strip().lower()
        self._view.clear()
        for line in self._all_lines[-_MAX_BLOCKS:]:
            if not needle or needle in line.lower():
                self._view.appendPlainText(line)

    def _clear(self) -> None:
        self._all_lines.clear()
        self._view.clear()

    def _save(self) -> None:
        default = f"{self._source.currentData()}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Guardar registro", default, "Texto (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(self._all_lines))
            self.ctx.notify(f"Guardado: {path}", "ok")
        except OSError as exc:
            self.ctx.notify(f"No se pudo guardar: {exc}", "error")

    # se llama al salir/ cambiar de dispositivo
    def on_device_changed(self) -> None:
        self._stop()
        self._clear()

    def shutdown(self) -> None:
        self._stop()
