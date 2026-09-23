"""Reciclaje de terminal: wipe estándar (userdata + cache) para reutilización.

Esto es un factory-reset genérico vía fastboot, pensado para dejar un terminal
limpio antes de reasignarlo/revenderlo. No toca paquetes del sistema ni la
pila de pago de PAX — eso se gestiona (uno a uno, con aviso) desde la página
de Aplicaciones. Ver core/models.KNOWN_PAX_PACKAGES.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.adb import CommandResult
from ..widgets import DangerCard, Page, hint


class RecyclePage(Page):
    title = "Reciclaje"
    icon_concept = "recycle"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)

        warn = hint(
            "Restablece el terminal para reutilizarlo: borra datos de usuario y caché "
            "(equivalente a un factory reset). Requiere modo bootloader. No modifica "
            "paquetes del sistema — eso se gestiona desde Aplicaciones."
        )
        warn.setStyleSheet(f"color:{ctx.palette.warn};")
        root.addWidget(warn)

        # --- Acción principal: wipe completo en un paso ---
        quick = DangerCard("Restablecer terminal")
        quick.add(
            hint(
                "Borra userdata + cache y reinicia, todo de una vez. Es la vía habitual "
                "para dejar un terminal limpio."
            )
        )
        self._full = QPushButton("Wipe completo   ·   userdata + cache + reboot")
        self._full.setObjectName("Danger")
        self._full.setMinimumHeight(42)
        self._full.clicked.connect(self._full_wipe)
        quick.add(self._full)
        root.addWidget(quick)

        # --- Paso a paso ---
        steps = DangerCard("Paso a paso")
        steps.add(hint("O ejecuta cada operación por separado, en orden:"))
        steps.add(self._step_row(0, "Quitar tampered", "Quitar Tampered", self._remove_tampered))
        steps.add(self._step_row(1, "Reiniciar a bootloader", "Reiniciar", self._reboot_bootloader))
        steps.add(self._step_row(2, "Borrar datos de usuario (userdata)", "Borrar", lambda: self._erase("userdata")))
        steps.add(self._step_row(3, "Borrar caché (cache)", "Borrar", lambda: self._erase("cache")))
        steps.add(self._step_row(4, "Reiniciar terminal", "Reiniciar", self._reboot))
        root.addWidget(steps)

        self._out = QPlainTextEdit()
        self._out.setObjectName("Console")
        self._out.setReadOnly(True)
        self._out.setPlaceholderText("La salida de las operaciones de reciclaje aparecerá aquí…")
        root.addWidget(self._out, 1)

    # ------------------------------------------------------------------
    def _step_row(self, number: int, title: str, action: str, on_click: Callable) -> QWidget:
        """Fila de paso: insignia numérica + descripción + botón de acción."""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(12)
        num = QLabel(str(number))
        num.setObjectName("StepNum")
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(title)
        btn = QPushButton(action)
        btn.setMinimumWidth(120)
        btn.clicked.connect(on_click)
        lay.addWidget(num)
        lay.addWidget(label, 1)
        lay.addWidget(btn)
        return w

    def _log(self, res: CommandResult) -> None:
        self._out.appendPlainText((res.text or "(sin salida)").rstrip())
        self._out.appendPlainText("")

    def _confirm(self, title: str, body: str) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _reboot_bootloader(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        self._out.appendPlainText("$ adb reboot bootloader")
        self.ctx.adb.run(["reboot", "bootloader"], self._log)

    # Componentes de PAX que este paso desinstala ("quitar tampered").
    _TAMPER_PKGS = ("com.pax.ipp.neptune", "com.pax.daemon")

    def _remove_tampered(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        if not self._confirm(
            "Quitar tampered",
            "Vas a desinstalar componentes de PAX:\n\n"
            "  • com.pax.ipp.neptune (núcleo de pago seguro)\n"
            "  • com.pax.daemon\n\n"
            "Es una acción destructiva sobre la pila de pago y requiere el shell de "
            "adbd desbloqueado en el terminal. ¿Continuar?",
        ):
            return
        # Cada uninstall es un `adb shell pm uninstall …`. Van ENCADENADOS: cada
        # uno espera a que termine el anterior (en su callback) en vez de dispararse
        # todos a la vez. Disparar dos `adb shell` en ráfaga sobre el mismo
        # dispositivo hacía que el segundo no llegara a ejecutarse.
        self._uninstall_next(list(self._TAMPER_PKGS), 0)

    def _uninstall_next(self, pkgs: list[str], i: int) -> None:
        if i >= len(pkgs):
            self.ctx.notify("Quitar tampered: completado.", "ok")
            return
        pkg = pkgs[i]
        cmd = f"pm uninstall --user 0 {pkg}"
        self._out.appendPlainText(f"[{i + 1}/{len(pkgs)}] $ adb shell {cmd}")

        def after(res: CommandResult) -> None:
            self._log(res)
            # Se continúa con el siguiente aunque uno falle: `pm uninstall`
            # devuelve 0 con «Failure» en texto, y el usuario querrá intentar el
            # resto igualmente.
            self._uninstall_next(pkgs, i + 1)

        self.ctx.adb.shell(cmd, after)

    def _erase(self, part: str) -> None:
        if not self._confirm(
            "Confirmar borrado",
            f"Vas a BORRAR la partición '{part}'. Esta acción es irreversible. ¿Continuar?",
        ):
            return
        self._out.appendPlainText(f"$ fastboot erase {part}")
        self.ctx.fastboot.run(["erase", part], self._log)

    def _reboot(self) -> None:
        self._out.appendPlainText("$ fastboot reboot")
        self.ctx.fastboot.run(["reboot"], self._log)

    def _full_wipe(self) -> None:
        if not self._confirm(
            "Confirmar wipe completo",
            "Vas a borrar 'userdata' y 'cache' y reiniciar el terminal.\n\n"
            "Todos los datos de usuario se perderán de forma irreversible. "
            "Asegúrate de estar en modo bootloader. ¿Continuar?",
        ):
            return
        self._run_sequence(["userdata", "cache"], 0)

    def _run_sequence(self, parts: list[str], i: int) -> None:
        if i >= len(parts):
            self._out.appendPlainText("$ fastboot reboot")
            self.ctx.fastboot.run(["reboot"], self._log)
            self.ctx.notify("Wipe completo enviado.", "ok")
            return
        part = parts[i]
        self._out.appendPlainText(f"$ fastboot erase {part}")

        def after(res: CommandResult) -> None:
            self._log(res)
            if not res.ok:
                self.ctx.notify(f"Wipe detenido: fallo al borrar '{part}'.", "error")
                return
            self._run_sequence(parts, i + 1)

        self.ctx.fastboot.run(["erase", part], after)
