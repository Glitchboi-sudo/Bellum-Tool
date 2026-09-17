"""Flasheo por fastboot (genérico). El usuario aporta sus propias imágenes.

No se incluye firmware ni secuencias de flasheo prefabricadas. Es un front-end
sobre `fastboot`/`paydroidboot`: flash de una partición con un fichero elegido
por el usuario, erase y reboot. Toda operación destructiva pide confirmación.
"""

from __future__ import annotations

import json
import os

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.adb import CommandResult
from ..widgets import Card, Page, flow_row, hint, icon_button

_COMMON_PARTS = ["boot", "system", "uboot", "logo", "recovery", "userdata", "cache", "vendor"]


def _row(*widgets: QWidget, stretch_index: int | None = None) -> QWidget:
    """Fila horizontal que refluye a varias líneas en ventanas estrechas.

    `stretch_index` ya no estira (el FlowLayout coloca cada widget con su tamaño
    natural); solo se usa para darle al campo señalado un ancho mínimo cómodo."""
    if stretch_index is not None and 0 <= stretch_index < len(widgets):
        widgets[stretch_index].setMinimumWidth(160)
    return flow_row(*widgets)


class FlashPage(Page):
    title = "Flasheo"
    icon_concept = "flash"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)

        warn = hint(
            "Modo bootloader requerido. Aporta tú tus propias imágenes — el toolkit no "
            "incluye firmware ni secuencias de desbloqueo. Flashear una imagen incorrecta "
            "puede inutilizar el terminal (brick). Úsalo solo sobre equipo de tu propiedad."
        )
        warn.setStyleSheet(f"color:{ctx.palette.warn};")
        root.addWidget(warn)

        # --- estado / navegación de modo ---
        mode_card = Card("Estado")
        self._fb_status = QLabel()
        self._fb_status.setObjectName("Mono")
        self._fb_status.setWordWrap(True)
        mode_card.add(self._fb_status)

        to_boot = icon_button("jump", ctx.palette.text, "Reiniciar a bootloader (adb)")
        to_boot.clicked.connect(self._reboot_bootloader)
        detect = icon_button("refresh", ctx.palette.text, "Detectar (fastboot devices)")
        detect.clicked.connect(self._detect)
        reboot = icon_button("reboot", ctx.palette.text, "Reiniciar terminal (fastboot)")
        reboot.clicked.connect(self._reboot)
        mode_card.add(_row(to_boot, detect, reboot))
        root.addWidget(mode_card)

        # --- flashear ---
        flash_card = Card("Flashear partición")
        self._part = QComboBox()
        self._part.setEditable(True)
        self._part.addItems(_COMMON_PARTS)
        self._img = QLineEdit()
        self._img.setPlaceholderText("Ruta de la imagen…")
        browse = icon_button("open", ctx.palette.text, "Examinar…")
        browse.clicked.connect(self._browse)
        flash_btn = icon_button(
            "flash", ctx.palette.accent_text, "Flashear", object_name="Primary"
        )
        flash_btn.clicked.connect(self._flash)
        flash_card.add(
            _row(QLabel("Partición:"), self._part, self._img, browse, flash_btn, stretch_index=2)
        )

        self._erase_part = QComboBox()
        self._erase_part.setEditable(True)
        self._erase_part.addItems(["cache", "userdata", "logo", "system"])
        erase_btn = QPushButton("Borrar (erase)")
        erase_btn.setObjectName("Danger")
        erase_btn.clicked.connect(self._erase)
        flash_card.add(_row(QLabel("Borrar partición:"), self._erase_part, erase_btn))
        root.addWidget(flash_card)

        root.addWidget(self._build_recipe_card())

        self._out = QPlainTextEdit()
        self._out.setObjectName("Console")
        self._out.setReadOnly(True)
        root.addWidget(self._out, 1)

        self._update_status()

    # ------------------------------------------------------------------
    def _update_status(self) -> None:
        if self.ctx.fastboot.available:
            self._fb_status.setText(f"fastboot: {self.ctx.fastboot.binary}")
        else:
            self._fb_status.setText(
                "fastboot no encontrado. Instala 'android-tools' o configúralo en Ajustes."
            )

    def on_device_changed(self) -> None:
        self._update_status()

    def refresh(self) -> None:
        self._update_status()

    def _log(self, res: CommandResult) -> None:
        self._out.appendPlainText((res.text or "(sin salida)").rstrip())
        self._out.appendPlainText("")

    def _reboot_bootloader(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        self._out.appendPlainText("$ adb reboot bootloader")
        self.ctx.adb.run(["reboot", "bootloader"], self._log)

    def _detect(self) -> None:
        self._out.appendPlainText("$ fastboot devices")
        self.ctx.fastboot.list_devices(self._log)

    def _reboot(self) -> None:
        self._out.appendPlainText("$ fastboot reboot")
        self.ctx.fastboot.run(["reboot"], self._log)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Imagen", "", "Imágenes (*.img *.bin *.mbn *.sparse);;Todos (*)"
        )
        if path:
            self._img.setText(path)

    def _confirm(self, title: str, body: str) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _flash(self) -> None:
        part = self._part.currentText().strip()
        img = self._img.text().strip()
        if not part or not img:
            self.ctx.notify("Indica partición e imagen.", "warn")
            return
        if self._confirm(
            "Confirmar flasheo",
            f"Vas a flashear '{img}'\nen la partición '{part}'.\n\n"
            "Una imagen incorrecta puede dejar el terminal inservible. ¿Continuar?",
        ):
            self._out.appendPlainText(f"$ fastboot flash {part} {img}")
            self.ctx.fastboot.run(["flash", part, img], self._log)

    def _erase(self) -> None:
        part = self._erase_part.currentText().strip()
        if not part:
            return
        if self._confirm(
            "Confirmar borrado",
            f"Vas a BORRAR la partición '{part}'. Esta acción es irreversible. ¿Continuar?",
        ):
            self._out.appendPlainText(f"$ fastboot erase {part}")
            self.ctx.fastboot.run(["erase", part], self._log)

    # ------------------------------------------------------------------
    # Receta por lotes: secuencia de pasos fastboot con TUS imágenes.
    # ------------------------------------------------------------------
    _OPS = [
        ("flash (partición + imagen)", "flash"),
        ("erase (partición)", "erase"),
        ("reboot", "reboot"),
        ("reboot bootloader", "reboot-bootloader"),
    ]

    def _build_recipe_card(self) -> Card:
        self._steps: list[dict] = []
        card = Card("Receta por lotes (fastboot)")
        card.add(
            hint(
                "Define una secuencia de pasos con tus propias imágenes y ejecútala en "
                "orden (se detiene si un paso falla). Equivale a un .bat de flasheo, pero "
                "sin firmware incluido: cada paso 'flash' apunta al fichero que elijas."
            )
        )

        self._op = QComboBox()
        for label, key in self._OPS:
            self._op.addItem(label, key)
        self._op.currentIndexChanged.connect(self._sync_step_inputs)
        self._step_part = QComboBox()
        self._step_part.setEditable(True)
        self._step_part.addItems(_COMMON_PARTS)
        self._step_img = QLineEdit()
        self._step_img.setPlaceholderText("Imagen (solo para flash)…")
        step_browse = icon_button("open", self.ctx.palette.text, tooltip="Examinar imagen…")
        step_browse.setFixedWidth(40)
        step_browse.clicked.connect(self._recipe_browse)
        add_btn = icon_button("add", self.ctx.palette.text, "Añadir paso")
        add_btn.clicked.connect(self._add_step)
        card.add(
            _row(
                self._op,
                self._step_part,
                self._step_img,
                step_browse,
                add_btn,
                stretch_index=2,
            )
        )

        self._steps_table = QTableWidget(0, 3)
        self._steps_table.setHorizontalHeaderLabels(["Acción", "Partición", "Imagen"])
        self._steps_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._steps_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._steps_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._steps_table.verticalHeader().setVisible(False)
        self._steps_table.setMinimumHeight(150)
        self._steps_table.setMaximumHeight(200)
        h = self._steps_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        card.add(self._steps_table)

        remove_btn = icon_button("remove", self.ctx.palette.text, "Eliminar")
        remove_btn.clicked.connect(self._remove_step)
        up_btn = icon_button("up", self.ctx.palette.text, tooltip="Mover paso arriba")
        up_btn.setFixedWidth(40)
        up_btn.clicked.connect(lambda: self._move_step(-1))
        down_btn = icon_button("down", self.ctx.palette.text, tooltip="Mover paso abajo")
        down_btn.setFixedWidth(40)
        down_btn.clicked.connect(lambda: self._move_step(1))
        load_btn = icon_button("open", self.ctx.palette.text, "Cargar…")
        load_btn.clicked.connect(self._load_recipe)
        save_btn = icon_button("save", self.ctx.palette.text, "Guardar…")
        save_btn.clicked.connect(self._save_recipe)
        self._run_btn = icon_button(
            "play", self.ctx.palette.accent_text, "Ejecutar receta", object_name="Primary"
        )
        self._run_btn.clicked.connect(self._run_recipe)
        card.add(
            _row(remove_btn, up_btn, down_btn, load_btn, save_btn, self._run_btn)
        )
        self._sync_step_inputs()
        return card

    def _sync_step_inputs(self) -> None:
        op = self._op.currentData()
        self._step_part.setEnabled(op in ("flash", "erase"))
        self._step_img.setEnabled(op == "flash")

    def _recipe_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Imagen", "", "Imágenes (*.img *.bin *.mbn *.sparse);;Todos (*)"
        )
        if path:
            self._step_img.setText(path)

    def _add_step(self) -> None:
        op = self._op.currentData()
        part = self._step_part.currentText().strip()
        img = self._step_img.text().strip()
        if op == "flash" and (not part or not img):
            self.ctx.notify("Un paso 'flash' necesita partición e imagen.", "warn")
            return
        if op == "erase" and not part:
            self.ctx.notify("Un paso 'erase' necesita partición.", "warn")
            return
        step = {"op": op}
        if op in ("flash", "erase"):
            step["partition"] = part
        if op == "flash":
            step["image"] = img
        self._steps.append(step)
        self._step_img.clear()
        self._render_steps()

    def _render_steps(self) -> None:
        self._steps_table.setRowCount(len(self._steps))
        for i, s in enumerate(self._steps):
            self._steps_table.setItem(i, 0, QTableWidgetItem(s["op"]))
            self._steps_table.setItem(i, 1, QTableWidgetItem(s.get("partition", "")))
            img = s.get("image", "")
            item = QTableWidgetItem(os.path.basename(img))
            if img:
                item.setToolTip(img)
            self._steps_table.setItem(i, 2, item)

    def _selected_step(self) -> int:
        rows = self._steps_table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _remove_step(self) -> None:
        i = self._selected_step()
        if 0 <= i < len(self._steps):
            del self._steps[i]
            self._render_steps()

    def _move_step(self, delta: int) -> None:
        i = self._selected_step()
        j = i + delta
        if 0 <= i < len(self._steps) and 0 <= j < len(self._steps):
            self._steps[i], self._steps[j] = self._steps[j], self._steps[i]
            self._render_steps()
            self._steps_table.selectRow(j)

    def _step_to_args(self, s: dict) -> list[str]:
        op = s["op"]
        if op == "flash":
            return ["flash", s["partition"], s["image"]]
        if op == "erase":
            return ["erase", s["partition"]]
        if op == "reboot-bootloader":
            return ["reboot-bootloader"]
        return ["reboot"]

    def _run_recipe(self) -> None:
        if not self._steps:
            self.ctx.notify("La receta está vacía.", "warn")
            return
        summary = "\n".join(
            f"  {i + 1}. fastboot " + " ".join(self._step_to_args(s))
            for i, s in enumerate(self._steps)
        )
        if not self._confirm(
            "Ejecutar receta",
            f"Se ejecutarán {len(self._steps)} pasos en orden (se detiene si uno falla):\n\n"
            f"{summary}\n\nUna imagen incorrecta puede inutilizar el terminal. ¿Continuar?",
        ):
            return
        # valida que las imágenes de flash existen antes de empezar
        for s in self._steps:
            if s["op"] == "flash" and not os.path.isfile(s["image"]):
                self.ctx.notify(f"No existe la imagen: {s['image']}", "error")
                return
        self._run_btn.setEnabled(False)
        self._exec_step(list(self._steps), 0)

    def _exec_step(self, steps: list[dict], i: int) -> None:
        if i >= len(steps):
            self._out.appendPlainText("✓ Receta completada.\n")
            self.ctx.notify("Receta completada.", "ok")
            self._run_btn.setEnabled(True)
            return
        args = self._step_to_args(steps[i])
        self._out.appendPlainText(f"[{i + 1}/{len(steps)}] $ fastboot " + " ".join(args))

        def after(res: CommandResult) -> None:
            self._out.appendPlainText((res.text or "").rstrip())
            if not res.ok:
                self._out.appendPlainText(f"✗ Fallo en el paso {i + 1}. Receta detenida.\n")
                self.ctx.notify(f"Receta detenida en el paso {i + 1}.", "error")
                self._run_btn.setEnabled(True)
                return
            self._exec_step(steps, i + 1)

        self.ctx.fastboot.run(args, after)

    def _save_recipe(self) -> None:
        if not self._steps:
            self.ctx.notify("La receta está vacía.", "warn")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar receta", "receta.json", "Receta JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"steps": self._steps}, fh, indent=2)
            self.ctx.notify(f"Receta guardada: {path}", "ok")
        except OSError as exc:
            self.ctx.notify(f"No se pudo guardar: {exc}", "error")

    def _load_recipe(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Cargar receta", "", "Receta JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            steps = data.get("steps", data if isinstance(data, list) else [])
            clean: list[dict] = []
            for s in steps:
                if isinstance(s, dict) and s.get("op") in {"flash", "erase", "reboot", "reboot-bootloader"}:
                    clean.append(s)
            self._steps = clean
            self._render_steps()
            self.ctx.notify(f"Receta cargada: {len(clean)} pasos.", "ok")
        except (OSError, json.JSONDecodeError) as exc:
            self.ctx.notify(f"No se pudo cargar: {exc}", "error")
