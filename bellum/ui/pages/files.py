"""Explorador de ficheros del terminal con transferencia push/pull y borrado."""

from __future__ import annotations

import posixpath

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ...core.adb import CommandResult
from .. import icons
from ..widgets import (
    EmptyState,
    Page,
    busy_bar,
    flow_row,
    hint,
    icon_button,
    stacked_with_empty,
)

class FilesPage(Page):
    title = "Ficheros"
    icon_concept = "folder"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._cwd = "/sdcard"

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(12)

        up = icon_button("up", ctx.palette.text, tooltip="Subir un nivel")
        up.clicked.connect(self._go_up)
        self._path = QLineEdit(self._cwd)
        self._path.setMinimumWidth(160)
        self._path.returnPressed.connect(self._navigate_to_path)
        go = QPushButton("Ir")
        go.clicked.connect(self._navigate_to_path)
        reload_btn = icon_button("refresh", ctx.palette.text, "Actualizar")
        reload_btn.clicked.connect(self.refresh)
        root.addWidget(flow_row(up, self._path, go, reload_btn))

        self._busy = busy_bar()
        self._busy.hide()
        root.addWidget(self._busy)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.itemDoubleClicked.connect(self._on_double)
        self._empty_state = EmptyState(
            "Sin dispositivo conectado.\nConecta un terminal PAX por USB para explorar sus ficheros.",
            ctx.palette,
            icon_concept="device",
        )
        self._stack = stacked_with_empty(self._list, self._empty_state)
        root.addWidget(self._stack, 1)

        self._status = hint("—")
        root.addWidget(self._status)
        push_btn = icon_button(
            "add", ctx.palette.accent_text, "Subir fichero…", object_name="Primary"
        )
        push_btn.clicked.connect(self._push)
        pull_btn = icon_button("save", ctx.palette.text, "Descargar selección…")
        pull_btn.clicked.connect(self._pull)
        # Borrado remoto vía 'unlink' (petición sync ULNK). Sin icono: el estilo
        # Danger invierte fondo/texto en :hover y horneaba el icono en un color fijo.
        delete_btn = QPushButton("Borrar (unlink)")
        delete_btn.setObjectName("Danger")
        delete_btn.clicked.connect(self._unlink)
        root.addWidget(flow_row(push_btn, pull_btn, delete_btn))

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._list.clear()
        if not self.ctx.adb.serial:
            self._busy.hide()
            self._status.setText("Sin dispositivo")
            self._stack.setCurrentWidget(self._empty_state)
            return
        self._stack.setCurrentWidget(self._list)
        self._path.setText(self._cwd)
        self._status.setText("Listando…")
        self._busy.show()
        # -p añade '/' a los directorios; -A omite . y .. ; -1 uno por línea.
        self.ctx.adb.shell(f"ls -1Ap '{self._cwd}'", self._on_listed)

    def _on_listed(self, res: CommandResult) -> None:
        self._busy.hide()
        text = res.stdout
        if (not res.ok) or "No such file" in text or "Permission denied" in text:
            self._status.setText(text.strip().splitlines()[0] if text.strip() else "Error al listar")
            return
        entries = [e for e in text.splitlines() if e.strip()]
        dirs = sorted([e for e in entries if e.endswith("/")], key=str.lower)
        files = sorted([e for e in entries if not e.endswith("/")], key=str.lower)
        folder_ic = icons.icon("folder", self.ctx.palette.accent, size=16)
        file_ic = icons.icon("logs", self.ctx.palette.text_dim, size=16)
        for d in dirs:
            it = QListWidgetItem(d.rstrip("/"))
            if not folder_ic.isNull():
                it.setIcon(folder_ic)
            it.setData(Qt.ItemDataRole.UserRole, ("dir", d.rstrip("/")))
            self._list.addItem(it)
        for f in files:
            it = QListWidgetItem(f)
            if not file_ic.isNull():
                it.setIcon(file_ic)
            it.setData(Qt.ItemDataRole.UserRole, ("file", f))
            self._list.addItem(it)
        self._status.setText(f"{len(dirs)} carpetas · {len(files)} ficheros")

    def _on_double(self, item: QListWidgetItem) -> None:
        kind, name = item.data(Qt.ItemDataRole.UserRole)
        if kind == "dir":
            self._cwd = posixpath.normpath(posixpath.join(self._cwd, name))
            self.refresh()

    def _go_up(self) -> None:
        if self._cwd != "/":
            self._cwd = posixpath.dirname(self._cwd.rstrip("/")) or "/"
            self.refresh()

    def _navigate_to_path(self) -> None:
        self._cwd = self._path.text().strip() or "/"
        self.refresh()

    # ------------------------------------------------------------------
    def _push(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Subir al terminal", "", "Todos (*)")
        if not files:
            return
        done = {"n": 0, "fail": 0}
        total = len(files)

        def after(res: CommandResult) -> None:
            done["n"] += 1
            if not res.ok:
                done["fail"] += 1
            if done["n"] >= total:
                level = "ok" if not done["fail"] else "warn"
                self.ctx.notify(f"Subida: {total - done['fail']}/{total} OK.", level)
                self.refresh()

        for local in files:
            remote = posixpath.join(self._cwd, posixpath.basename(local))
            self.ctx.adb.run(["push", local, remote], after)

    def _pull(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        items = self._list.selectedItems()
        if not items:
            self.ctx.notify("Selecciona algo para descargar.", "warn")
            return
        dest = QFileDialog.getExistingDirectory(self, "Guardar en…")
        if not dest:
            return
        done = {"n": 0, "fail": 0}
        total = len(items)

        def after(res: CommandResult) -> None:
            done["n"] += 1
            if not res.ok:
                done["fail"] += 1
            if done["n"] >= total:
                level = "ok" if not done["fail"] else "warn"
                self.ctx.notify(f"Descarga: {total - done['fail']}/{total} OK → {dest}", level)

        for it in items:
            _, name = it.data(Qt.ItemDataRole.UserRole)
            remote = posixpath.join(self._cwd, name)
            self.ctx.adb.run(["pull", "-a", remote, dest], after)

    def _unlink(self) -> None:
        """Borra los ficheros seleccionados en el terminal (comando `unlink`).

        `unlink` es *version-aware* en el binario: en firmware con
        `sysver ≥ 100`, borrar bajo /data/resource/app/ se enruta por systool
        (persist-app); en el resto usa la petición sync ULNK. Aquí solo pasamos
        la ruta remota; el binario decide.
        """
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        items = self._list.selectedItems()
        if not items:
            self.ctx.notify("Selecciona algo para borrar.", "warn")
            return
        targets = []
        for it in items:
            kind, name = it.data(Qt.ItemDataRole.UserRole)
            targets.append((kind, posixpath.join(self._cwd, name)))

        dirs = [p for k, p in targets if k == "dir"]
        text = "Vas a BORRAR del terminal (irreversible):\n\n" + "\n".join(
            f"  • {p}" for _, p in targets[:12]
        )
        if len(targets) > 12:
            text += f"\n  … y {len(targets) - 12} más"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Confirmar borrado")
        box.setText(text)
        if dirs:
            box.setInformativeText(
                "Nota: `unlink` borra ficheros; sobre carpetas puede fallar según el "
                "firmware. Selecciona ficheros para un borrado fiable."
            )
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        done = {"n": 0, "fail": 0}
        total = len(targets)

        def after(res: CommandResult) -> None:
            done["n"] += 1
            if not res.ok:
                done["fail"] += 1
            if done["n"] >= total:
                level = "ok" if not done["fail"] else "warn"
                self.ctx.notify(f"Borrado: {total - done['fail']}/{total} OK.", level)
                self.refresh()

        for _, remote in targets:
            self.ctx.adb.run(["unlink", remote], after)
