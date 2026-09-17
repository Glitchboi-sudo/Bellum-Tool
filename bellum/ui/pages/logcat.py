"""Visor de registros en vivo: logcat de Android o el syslog de sistema de PAX.

Ambas fuentes comparten toda la infraestructura de streaming/filtro/guardado;
solo cambia el comando que se lanza: `logcat -v time *:P` o `syslog`
(el servicio `paxlog:system` del terminal).
"""

from __future__ import annotations

import re

from PySide6.QtCore import QProcess
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from .. import icons
from ..widgets import Page, flow_row, icon_button

_MAX_BLOCKS = 5000  # límite de líneas en pantalla para no consumir memoria sin fin

# Cabecera típica de una línea logcat/syslog: "<nivel>/<tag>( <pid>):"
#   E/DcSwitchStateMachine-0( 1380): mensaje…
_LOG_RE = re.compile(r"([VDIWEF])/(.+?)\(\s*(\d+)\s*\):")


class LogHighlighter(QSyntaxHighlighter):
    """Colorea cada línea de log por nivel para hacer legible el volcado denso.

    Atenúa el timestamp y el pid, resalta el tag, colorea la letra de nivel
    (V/D/I/W/E/F) y tiñe el mensaje en warnings/errores. El texto sigue siendo
    plano (copiar/guardar no se ven afectados)."""

    def __init__(self, document, palette):
        super().__init__(document)

        def fmt(color: str, bold: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            return f

        self._dim = fmt(palette.text_dim)
        self._tag = fmt(palette.accent)
        self._lvl = {
            "V": fmt(palette.text_dim, True),
            "D": fmt(palette.accent, True),
            "I": fmt(palette.ok, True),
            "W": fmt(palette.warn, True),
            "E": fmt(palette.danger, True),
            "F": fmt(palette.danger, True),
        }
        # Solo se tiñe el mensaje en niveles llamativos (warn/error/fatal).
        self._msg = {"W": fmt(palette.warn), "E": fmt(palette.danger), "F": fmt(palette.danger)}

    def highlightBlock(self, text: str) -> None:
        m = _LOG_RE.search(text)
        if not m:
            return
        lvl = m.group(1)
        if m.start(1) > 0:
            self.setFormat(0, m.start(1), self._dim)  # timestamp/cabecera
        self.setFormat(m.start(1), 1, self._lvl.get(lvl, self._dim))  # nivel
        self.setFormat(m.start(2), len(m.group(2)), self._tag)  # tag
        self.setFormat(m.start(3), len(m.group(3)), self._dim)  # pid
        msg_fmt = self._msg.get(lvl)
        if msg_fmt is not None:
            self.setFormat(m.end(), len(text) - m.end(), msg_fmt)  # mensaje


class LogcatPage(Page):
    title = "Registros"
    icon_concept = "logs"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._proc: QProcess | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(12)

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
        self._filter.setMinimumWidth(180)
        self._filter.textChanged.connect(self._reapply_filter)
        clear_btn = icon_button("remove", ctx.palette.text, "Limpiar")
        clear_btn.clicked.connect(self._clear)
        save_btn = icon_button("save", ctx.palette.text, "Guardar…")
        save_btn.clicked.connect(self._save)
        self._color = QCheckBox("Colorear")
        self._color.setChecked(True)
        self._color.toggled.connect(self._toggle_color)
        root.addWidget(
            flow_row(
                self._toggle, self._source, self._priority, self._filter,
                self._color, clear_btn, save_btn,
            )
        )

        self._view = QPlainTextEdit()
        self._view.setObjectName("Console")
        self._view.setReadOnly(True)
        self._view.setPlaceholderText("Pulsa «Iniciar» para ver el registro en vivo del terminal…")
        self._view.setMaximumBlockCount(_MAX_BLOCKS)
        self._view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        root.addWidget(self._view, 1)

        # Pretty-print: colorea por nivel (se puede desactivar con «Colorear»).
        self._highlighter = LogHighlighter(self._view.document(), ctx.palette)

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

    def _toggle_color(self, on: bool) -> None:
        # Conectar/desconectar el highlighter del documento activa o quita el color.
        self._highlighter.setDocument(self._view.document() if on else None)

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
