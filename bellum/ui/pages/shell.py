"""Consola: ejecuta comandos `adb shell` y muestra la salida.

No es un PTY interactivo; es un ejecutor de comandos de un disparo (cada Enter
lanza `pax_adb shell <cmd>`), que cubre el 99% del uso de diagnóstico.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from ...core.adb import CommandResult
from ..widgets import Page, icon_button

_QUICK = [
    ("Propiedades (getprop)", "getprop"),
    ("Apps de terceros", "pm list packages -3"),
    ("Uso de batería", "dumpsys battery"),
    ("Pantalla/resolución", "wm size"),
    ("Almacenamiento", "df -h"),
    ("Procesos", "ps -A"),
    ("Versión Android", "getprop ro.build.version.release"),
]


class ShellPage(Page):
    title = "Consola"
    icon_concept = "terminal"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._history: list[str] = []
        self._hist_idx = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(12)

        top = QHBoxLayout()
        self._quick = QComboBox()
        self._quick.addItem("Comandos rápidos…", "")
        for label, cmd in _QUICK:
            self._quick.addItem(label, cmd)
        self._quick.activated.connect(self._pick_quick)
        clear_btn = icon_button("remove", ctx.palette.text, "Limpiar")
        clear_btn.clicked.connect(lambda: self._out.clear())
        top.addWidget(self._quick)
        top.addStretch(1)
        top.addWidget(clear_btn)
        root.addLayout(top)

        self._out = QPlainTextEdit()
        self._out.setObjectName("Console")
        self._out.setReadOnly(True)
        self._out.setPlaceholderText(
            "La salida de los comandos aparecerá aquí. Prueba un comando rápido o escribe el tuyo."
        )
        root.addWidget(self._out, 1)

        entry = QHBoxLayout()
        prompt = QLineEdit()
        prompt.setPlaceholderText("escribe un comando y pulsa Enter (p.ej. getprop ro.product.model)")
        prompt.returnPressed.connect(self._run)
        prompt.installEventFilter(self)
        run_btn = icon_button("play", ctx.palette.accent_text, "Ejecutar", object_name="Primary")
        run_btn.clicked.connect(self._run)
        self._prompt = prompt
        entry.addWidget(prompt, 1)
        entry.addWidget(run_btn)
        root.addLayout(entry)

    def _pick_quick(self, index: int) -> None:
        cmd = self._quick.itemData(index)
        if cmd:
            self._prompt.setText(cmd)
            self._prompt.setFocus()
        self._quick.setCurrentIndex(0)

    def eventFilter(self, obj, event):  # noqa: N802 (API Qt)
        if obj is self._prompt and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Up:
                self._recall(-1)
                return True
            if key == Qt.Key.Key_Down:
                self._recall(1)
                return True
        return super().eventFilter(obj, event)

    def _recall(self, delta: int) -> None:
        if not self._history:
            return
        self._hist_idx = max(0, min(len(self._history), self._hist_idx + delta))
        if self._hist_idx >= len(self._history):
            self._prompt.clear()
        else:
            self._prompt.setText(self._history[self._hist_idx])

    def _run(self) -> None:
        cmd = self._prompt.text().strip()
        if not cmd:
            return
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        self._history.append(cmd)
        self._hist_idx = len(self._history)
        self._out.appendPlainText(f"$ {cmd}")
        self._prompt.clear()
        self.ctx.adb.shell(cmd, self._on_result)

    def _on_result(self, res: CommandResult) -> None:
        text = res.text.rstrip()
        if text:
            self._out.appendPlainText(text)
        if not res.ok:
            self._out.appendPlainText(f"[exit {res.returncode}]")
        self._out.appendPlainText("")
