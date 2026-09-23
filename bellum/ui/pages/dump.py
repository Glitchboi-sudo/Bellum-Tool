"""Volcado de particiones (genérico). El usuario elige qué volcar.

Front-end sobre `adb shell dd` + `adb pull`: lista las particiones que el propio
terminal expone bajo su ruta `by-name`, deja que el usuario marque las que quiere
y las copia a imágenes en el terminal, para luego descargarlas al PC.

A diferencia del `dump_firmware` original, aquí **no hay preset**: no se
pre-selecciona ninguna partición (y menos las de material sensible del TPV como
`pax_authinfo`/`pax_config`/`pax_modem_sign`). Es una herramienta de servicio
neutra — tú decides, sobre equipo de tu propiedad.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from ...core.adb import CommandResult
from ..widgets import Card, DangerCard, Page, flow_row, hint, icon_button

# Ruta by-name típica de los PAX A910/A920 (SoC Unisoc). Editable: otros
# modelos/plataformas exponen sus particiones bajo otra ruta.
_DEFAULT_BYNAME = "/dev/block/platform/sdio_emmc/by-name"
# Carpeta de trabajo en el terminal donde se escriben las imágenes antes de bajarlas.
_REMOTE_DIR = "/sdcard/bellum_dump"
# Particiones que pueden contener claves/credenciales del TPV: se marcan en la
# lista para que el usuario sepa lo que hace, nunca se seleccionan solas.
_SENSITIVE = {"pax_authinfo", "pax_config", "pax_modem_sign", "pax_backup", "persist"}


class DumpPage(Page):
    title = "Volcado"
    icon_concept = "download"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._dest_pc: str = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)

        warn = hint(
            "Copia particiones del terminal a imágenes y las descarga al PC. Requiere shell con "
            "permisos de lectura de bloque. Elige tú qué volcar: las particiones marcadas como "
            "«sensible» pueden contener material criptográfico del terminal — vuélcalas solo si "
            "tienes autorización sobre el equipo."
        )
        warn.setStyleSheet(f"color:{ctx.palette.warn};")
        root.addWidget(warn)

        src = Card("Origen")
        self._byname = QLineEdit(_DEFAULT_BYNAME)
        list_btn = icon_button("refresh", ctx.palette.text, "Listar particiones")
        list_btn.clicked.connect(self._list_parts)
        src.add(flow_row(QLabel("Ruta by-name:"), self._byname, list_btn))

        self._parts = QListWidget()
        self._parts.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._parts.setMinimumHeight(200)
        src.add(self._parts)

        # Añadir una partición a mano (por si no aparece en el listado).
        self._manual = QLineEdit()
        self._manual.setPlaceholderText("Añadir partición por nombre…")
        add_btn = icon_button("add", ctx.palette.text, "Añadir")
        add_btn.clicked.connect(self._add_manual)
        src.add(flow_row(self._manual, add_btn))
        root.addWidget(src)

        dest = Card("Destino y volcado")
        self._dest = QLineEdit()
        self._dest.setPlaceholderText("Carpeta de destino en el PC…")
        browse = icon_button("open", ctx.palette.text, "Elegir carpeta…")
        browse.clicked.connect(self._pick_dest)
        self._dump_btn = icon_button(
            "download", ctx.palette.accent_text, "Volcar seleccionadas", object_name="Primary"
        )
        self._dump_btn.clicked.connect(self._dump)
        dest.add(flow_row(QLabel("Carpeta PC:"), self._dest, browse, self._dump_btn))
        root.addWidget(dest)

        # --- Volcado completo del eMMC (equivalente a `cdump`) -------------
        emmc = DangerCard("Volcar eMMC completo (mmcblk0) — ⚠ imagen enorme")
        emmc.add(
            hint(
                "Vuelca el disco entero del terminal a una imagen en el PC vía "
                "`exec-out dd if=/dev/block/mmcblk0`. Puede ocupar varios GB y tardar mucho; "
                "incluye TODAS las particiones (también material sensible). Solo sobre equipo "
                "de tu propiedad."
            )
        )
        self._emmc_dev = QLineEdit("/dev/block/mmcblk0")
        self._emmc_btn = icon_button("download", ctx.palette.text, "Volcar eMMC ⚠")
        self._emmc_btn.setObjectName("Danger")
        self._emmc_btn.clicked.connect(self._dump_emmc)
        emmc.add(flow_row(QLabel("Dispositivo:"), self._emmc_dev, self._emmc_btn))
        root.addWidget(emmc)

        self._out = QPlainTextEdit()
        self._out.setObjectName("Console")
        self._out.setReadOnly(True)
        self._out.setPlaceholderText("La salida del volcado aparecerá aquí…")
        root.addWidget(self._out, 1)

    # ------------------------------------------------------------------
    def _log(self, res: CommandResult) -> None:
        self._out.appendPlainText((res.text or "(sin salida)").rstrip())
        self._out.appendPlainText("")

    def _add_item(self, name: str) -> None:
        name = name.strip()
        if not name:
            return
        # Evita duplicados (se compara con el nombre exacto guardado en UserRole,
        # no con la etiqueta visible, que puede llevar el sufijo «· sensible»).
        for i in range(self._parts.count()):
            if self._parts.item(i).data(Qt.ItemDataRole.UserRole) == name:
                return
        label = f"{name}  ·  sensible" if name in _SENSITIVE else name
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        if name in _SENSITIVE:
            item.setForeground(QColor(self.ctx.palette.warn))
            item.setToolTip("Puede contener claves/credenciales del terminal.")
        self._parts.addItem(item)

    def _add_manual(self) -> None:
        self._add_item(self._manual.text())
        self._manual.clear()

    def _list_parts(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        base = self._byname.text().strip() or _DEFAULT_BYNAME
        self._out.appendPlainText(f"$ adb shell ls {base}")

        def after(res: CommandResult) -> None:
            if not res.ok:
                self._log(res)
                self.ctx.notify("No se pudo listar la ruta by-name.", "error")
                return
            names = sorted(
                {tok for tok in res.text.replace("\r", " ").split() if tok and "/" not in tok}
            )
            if not names:
                self.ctx.notify("No se encontraron particiones en esa ruta.", "warn")
                return
            self._parts.clear()
            for n in names:
                self._add_item(n)
            self._out.appendPlainText(f"✓ {len(names)} particiones listadas.\n")

        self.ctx.adb.shell(f"ls {base}", after)

    def _pick_dest(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Carpeta de destino")
        if path:
            self._dest.setText(path)

    def _checked(self) -> list[str]:
        out = []
        for i in range(self._parts.count()):
            item = self._parts.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(item.data(Qt.ItemDataRole.UserRole))
        return out

    def _dump(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        parts = self._checked()
        if not parts:
            self.ctx.notify("Marca al menos una partición.", "warn")
            return
        dest = self._dest.text().strip()
        if not dest:
            self.ctx.notify("Elige una carpeta de destino en el PC.", "warn")
            return
        if not os.path.isdir(dest):
            self.ctx.notify("La carpeta de destino no existe.", "error")
            return

        base = self._byname.text().strip() or _DEFAULT_BYNAME
        self._dump_btn.setEnabled(False)
        # Se limpia la carpeta antes de volcar: un intento previo abortado deja
        # .img huérfanos que, si no, se colarían en el `adb pull` de esta tanda.
        self._out.appendPlainText(f"$ adb shell rm -rf {_REMOTE_DIR} && mkdir -p {_REMOTE_DIR}")
        self.ctx.adb.shell(
            f"rm -rf {_REMOTE_DIR} && mkdir -p {_REMOTE_DIR}",
            lambda _res: self._dd_next(base, parts, 0, dest),
        )

    def _dd_next(self, base: str, parts: list[str], i: int, dest: str) -> None:
        if i >= len(parts):
            self._out.appendPlainText(f"$ adb pull {_REMOTE_DIR} {dest}")
            self.ctx.adb.run(["pull", _REMOTE_DIR, dest], lambda res: self._after_pull(res))
            return
        part = parts[i]
        cmd = f"dd if={base}/{part} of={_REMOTE_DIR}/{part}.img"
        self._out.appendPlainText(f"[{i + 1}/{len(parts)}] $ adb shell {cmd}")

        def after(res: CommandResult) -> None:
            self._log(res)
            if not res.ok:
                self._out.appendPlainText(f"✗ Fallo volcando '{part}'. Volcado detenido.\n")
                self.ctx.notify(f"Fallo al volcar '{part}'.", "error")
                self._dump_btn.setEnabled(True)
                return
            self._dd_next(base, parts, i + 1, dest)

        self.ctx.adb.shell(cmd, after)

    def _after_pull(self, res: CommandResult) -> None:
        self._log(res)
        self._dump_btn.setEnabled(True)
        if res.ok:
            # Solo se borran las imágenes del terminal si la descarga fue bien;
            # si el `pull` falló, se conservan para poder reintentarlo sin
            # repetir todo el `dd` (sin bloquear la UI).
            self.ctx.adb.shell(f"rm -rf {_REMOTE_DIR}", None)
            self._out.appendPlainText("✓ Volcado completado.\n")
            self.ctx.notify("Volcado descargado al PC.", "ok")
        else:
            self._out.appendPlainText(
                f"✗ Falló la descarga. Las imágenes siguen en el terminal ({_REMOTE_DIR}); "
                "puedes reintentar sin volver a volcar.\n"
            )
            self.ctx.notify("Falló la descarga; las imágenes siguen en el terminal.", "error")

    # ---- volcado completo del eMMC (cdump) ---------------------------
    def _confirm(self, title: str, body: str) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _dump_emmc(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        dev = self._emmc_dev.text().strip() or "/dev/block/mmcblk0"
        if not self._confirm(
            "Volcar eMMC completo",
            f"Se volcará el disco entero ({dev}) a una imagen en el PC.\n\n"
            "Puede ocupar varios GB y tardar bastante. ¿Continuar?",
        ):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar imagen del eMMC", "mmcblk0.img", "Imagen (*.img);;Todos (*)"
        )
        if not path:
            return
        self._emmc_btn.setEnabled(False)
        self._out.appendPlainText(f"$ adb exec-out dd if={dev} bs=4M  > {path}")

        def done(res: CommandResult) -> None:
            self._emmc_btn.setEnabled(True)
            if res.ok and os.path.exists(path) and os.path.getsize(path) > 0:
                mb = os.path.getsize(path) / (1024 * 1024)
                self._out.appendPlainText(f"✓ eMMC volcado ({mb:.0f} MB) → {path}\n")
                self.ctx.notify("eMMC volcado al PC.", "ok")
            else:
                self._out.appendPlainText(f"✗ Falló el volcado del eMMC. {res.stderr}\n")
                self.ctx.notify("Falló el volcado del eMMC (¿shell sin root?).", "error")

        self.ctx.adb.stream_to_file(["exec-out", "dd", f"if={dev}", "bs=4M"], path, done)
