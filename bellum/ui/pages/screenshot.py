"""Captura de pantalla del terminal (screencap → pull → visor)."""

from __future__ import annotations

import os
import shutil
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
)

from ...core.adb import CommandResult
from ..widgets import Page, busy_bar, icon_button

_REMOTE = "/sdcard/.tpv_shot.png"


class ScreenshotPage(Page):
    title = "Captura"
    icon_concept = "camera"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._local = os.path.join(tempfile.gettempdir(), "tpv_shot.png")
        self._pixmap: QPixmap | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(12)

        bar = QHBoxLayout()
        self._capture = icon_button(
            "camera", ctx.palette.accent_text, "Capturar", object_name="Primary"
        )
        self._capture.clicked.connect(self._do_capture)
        self._save = icon_button("save", ctx.palette.text, "Guardar como…")
        self._save.clicked.connect(self._do_save)
        self._save.setEnabled(False)
        self._status = QLabel("Pulsa «Capturar» para tomar una captura del terminal.")
        self._status.setObjectName("Hint")
        bar.addWidget(self._capture)
        bar.addWidget(self._save)
        bar.addSpacing(8)
        bar.addWidget(self._status)
        bar.addStretch(1)
        root.addLayout(bar)

        self._busy = busy_bar()
        self._busy.hide()
        root.addWidget(self._busy)

        self._image = QLabel()
        self._image.setText("Sin capturas todavía.")
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Fondo fijo (oscuro) independiente del tema — como el visor siempre
        # es oscuro, el texto de marcador debe ser un gris claro fijo, no
        # heredar el color de texto del tema (en claro sería casi negro
        # sobre casi negro).
        self._image.setStyleSheet("background:#0c0e13; border-radius:12px; color:#6b7484;")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._image)
        self._scroll = scroll
        root.addWidget(scroll, 1)

    # ------------------------------------------------------------------
    def _do_capture(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        self._status.setText("Capturando…")
        self._capture.setEnabled(False)
        self._busy.show()
        # 1) toma la captura en el terminal (a fichero, compatible con adb 1.0.32)
        self.ctx.adb.shell(f"screencap -p {_REMOTE}", self._after_screencap)

    def _after_screencap(self, res: CommandResult) -> None:
        if not res.ok:
            self._fail(res.text.strip() or "screencap falló")
            return
        # 2) descarga el PNG al equipo
        self.ctx.adb.run(["pull", _REMOTE, self._local], self._after_pull)

    def _after_pull(self, res: CommandResult) -> None:
        # limpia el fichero temporal del terminal (sin bloquear)
        self.ctx.adb.shell(f"rm -f {_REMOTE}", None)
        if not res.ok or not os.path.exists(self._local):
            self._fail(res.text.strip() or "no se pudo descargar la captura")
            return
        pix = QPixmap(self._local)
        if pix.isNull():
            self._fail("el fichero descargado no es una imagen válida")
            return
        self._busy.hide()
        self._pixmap = pix
        self._render()
        self._save.setEnabled(True)
        self._capture.setEnabled(True)
        self._status.setText(f"{pix.width()}×{pix.height()} px")

    def _fail(self, msg: str) -> None:
        self._busy.hide()
        self._capture.setEnabled(True)
        self._status.setText("Error.")
        self.ctx.notify(f"Captura: {msg}", "error")

    def _render(self) -> None:
        if not self._pixmap:
            return
        area = self._scroll.viewport().size()
        scaled = self._pixmap.scaled(
            area * 0.98,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image.setPixmap(scaled)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._render()

    def _do_save(self) -> None:
        if not self._pixmap:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar captura", "captura.png", "Imagen PNG (*.png)"
        )
        if not path:
            return
        try:
            shutil.copyfile(self._local, path)
            self.ctx.notify(f"Guardada: {path}", "ok")
        except OSError as exc:
            self.ctx.notify(f"No se pudo guardar: {exc}", "error")
