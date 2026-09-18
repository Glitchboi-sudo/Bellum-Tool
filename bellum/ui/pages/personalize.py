"""Personalización de arranque: generar splash.img y empujar bootanimation.

Dos utilidades cosméticas, sin exploit ni bypass:

* **BootLogo Maker** — reimplementación del `mkblsp` original con Qt puro
  (`QImage` + `gzip` de la stdlib, sin Pillow): toma una imagen del usuario, la
  redimensiona a 720×1280, la guarda como BMP, la comprime con gzip y produce un
  `splash.img` (≤1024 KB) listo para flashear. Es solo generación de fichero
  local; no toca el terminal.
* **Bootanimation** — empuja un `bootanimation.zip` que aporta el usuario a la
  ruta de medios del cliente (`/cache/customer/media/`, editable). Es una copia
  de fichero (equivalente al `btchge` original), no escribe particiones.
"""

from __future__ import annotations

import gzip
import os

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from ...core.adb import CommandResult
from ..widgets import Card, Page, flow_row, hint, icon_button

# Parámetros del splash del PAX A910/A920, fieles al mkblsp original.
_SPLASH_W, _SPLASH_H = 720, 1280
_SPLASH_MAX_KB = 1024
# Ruta de medios de personalización del cliente (destino del bootanimation.zip).
_BOOTANIM_DIR = "/cache/customer/media/"


class PersonalizePage(Page):
    title = "Personalización"
    icon_concept = "camera"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._splash_out: str = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)

        root.addWidget(
            hint(
                "Personalización cosmética del arranque. Es un cambio de imagen/animación "
                "sobre equipo de tu propiedad — no habilita ADB ni modifica la seguridad del "
                "terminal (eso presupone que ya tienes acceso al shell)."
            )
        )

        # --- BootLogo Maker (generación local de splash.img) ---------------
        maker = Card("BootLogo Maker · genera splash.img")
        maker.add(
            hint(
                f"Convierte una imagen ({_SPLASH_W}×{_SPLASH_H}, BMP comprimido con gzip) en un "
                f"splash.img listo para flashear. Límite {_SPLASH_MAX_KB} KB: si se pasa, usa una "
                "imagen más ligera. Formatos: PNG, JPG, BMP, TIFF."
            )
        )
        self._src = QLineEdit()
        self._src.setPlaceholderText("Imagen de origen…")
        pick = icon_button("open", ctx.palette.text, "Elegir imagen…")
        pick.clicked.connect(self._pick_source)
        make_btn = icon_button(
            "save", ctx.palette.accent_text, "Generar splash.img", object_name="Primary"
        )
        make_btn.clicked.connect(self._make_splash)
        maker.add(flow_row(QLabel("Origen:"), self._src, pick, make_btn))
        root.addWidget(maker)

        # --- Bootanimation (push del zip al terminal) ----------------------
        anim = Card("Bootanimation · empuja al terminal")
        anim.add(
            hint(
                "Copia un bootanimation.zip a la carpeta de medios del cliente. Requiere un "
                "dispositivo adb seleccionado con shell disponible."
            )
        )
        self._anim = QLineEdit()
        self._anim.setPlaceholderText("bootanimation.zip…")
        anim_pick = icon_button("open", ctx.palette.text, "Elegir zip…")
        anim_pick.clicked.connect(self._pick_anim)
        self._anim_dst = QLineEdit(_BOOTANIM_DIR)
        push_btn = icon_button(
            "run", ctx.palette.accent_text, "Empujar al terminal", object_name="Primary"
        )
        push_btn.clicked.connect(self._push_anim)
        anim.add(flow_row(QLabel("Archivo:"), self._anim, anim_pick))
        anim.add(flow_row(QLabel("Destino:"), self._anim_dst, push_btn))
        root.addWidget(anim)

        self._out = QPlainTextEdit()
        self._out.setObjectName("Console")
        self._out.setReadOnly(True)
        self._out.setPlaceholderText("La salida aparecerá aquí…")
        root.addWidget(self._out, 1)

    # ------------------------------------------------------------------
    def _log(self, res: CommandResult) -> None:
        self._out.appendPlainText((res.text or "(sin salida)").rstrip())
        self._out.appendPlainText("")

    # ---- BootLogo Maker ----------------------------------------------
    def _pick_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Imagen de origen", "", "Imágenes (*.png *.jpg *.jpeg *.bmp *.tiff);;Todos (*)"
        )
        if path:
            self._src.setText(path)

    def _make_splash(self) -> None:
        src = self._src.text().strip()
        if not src:
            self.ctx.notify("Elige una imagen de origen.", "warn")
            return
        img = QImage(src)
        if img.isNull():
            self.ctx.notify("No se pudo leer la imagen (formato no soportado).", "error")
            return

        out, _ = QFileDialog.getSaveFileName(
            self, "Guardar splash.img", self._splash_out or "splash.img", "Imagen (*.img)"
        )
        if not out:
            return

        # Redimensiona (estirado exacto a la resolución del panel, como mkblsp)
        # y serializa a BMP en memoria; luego comprime con gzip.
        scaled = img.scaled(
            _SPLASH_W,
            _SPLASH_H,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.ReadWrite)
        if not scaled.save(buf, "BMP"):
            self.ctx.notify("No se pudo codificar el BMP.", "error")
            return
        compressed = gzip.compress(bytes(buf.data()))

        size_kb = len(compressed) / 1024
        if size_kb > _SPLASH_MAX_KB:
            self.ctx.notify(
                f"splash.img supera {_SPLASH_MAX_KB} KB ({int(size_kb)} KB). "
                "Prueba con una imagen más ligera.",
                "error",
            )
            return
        try:
            with open(out, "wb") as fh:
                fh.write(compressed)
        except OSError as exc:
            self.ctx.notify(f"No se pudo guardar: {exc}", "error")
            return

        self._splash_out = out
        self._out.appendPlainText(
            f"✓ Generado {out} ({int(size_kb)} KB, {_SPLASH_W}×{_SPLASH_H} BMP+gzip)\n"
        )
        self.ctx.notify("splash.img listo para flashear.", "ok")

    # ---- Bootanimation -----------------------------------------------
    def _pick_anim(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "bootanimation.zip", "", "Archivos ZIP (*.zip);;Todos (*)"
        )
        if path:
            self._anim.setText(path)

    def _push_anim(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        src = self._anim.text().strip()
        dst = self._anim_dst.text().strip() or _BOOTANIM_DIR
        if not src:
            self.ctx.notify("Elige un bootanimation.zip.", "warn")
            return
        if not os.path.isfile(src):
            self.ctx.notify(f"No existe el archivo: {src}", "error")
            return
        self._out.appendPlainText(f"$ adb push {src} {dst}")
        self.ctx.adb.run(["push", src, dst], self._log)
