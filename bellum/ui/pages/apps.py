"""Gestor de aplicaciones: listar, instalar, desinstalar, activar/desactivar.

Es un gestor de paquetes genérico (equivalente a `pm list/install/uninstall`).
El usuario elige sobre qué paquete actúa. Los paquetes críticos de PAX se
marcan y requieren una confirmación reforzada: el toolkit no trae ninguna macro
que los elimine en bloque.
"""

from __future__ import annotations

import glob
import os
import posixpath
import re
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...core.adb import CommandResult
from ...core.models import KNOWN_PAX_PACKAGES, Package
from ..app_detail_dialog import AppDetailDialog
from ..widgets import EmptyState, Page, busy_bar, hint, icon_button, stacked_with_empty

# Centinela para las descargas aún en curso en self._pending: un pull fallido
# guarda None (fichero ilegible), que es un valor legítimo y no debe confundirse
# con "todavía no ha respondido".
_PENDING = object()

# Atributos de las etiquetas de apertura <package …> / <pkg …> del XML del
# PackageManager. Parseamos solo la etiqueta de apertura (regex), sin cargar los
# bloques anidados de permisos/firmas, y evitamos <updated-package>/<pkg-restr>.
_PKG_RE = re.compile(r"<package\s+([^>]*?)/?>", re.S)
_RESTR_PKG_RE = re.compile(r"<pkg\s+([^>]*?)/?>", re.S)
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


class AppsPage(Page):
    title = "Aplicaciones"
    icon_concept = "apps"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._packages: list[Package] = []
        self._versions: dict[str, tuple[str, str]] = {}
        self._pending: dict[str, object] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(12)

        # --- barra de filtros ---
        bar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filtrar por nombre de paquete…")
        self._search.textChanged.connect(self._apply_filter)
        self._filter = QComboBox()
        self._filter.addItems(["Todos", "Usuario (3rd-party)", "Sistema", "Desactivados"])
        self._filter.currentIndexChanged.connect(self._apply_filter)
        reload_btn = icon_button("refresh", ctx.palette.text, "Actualizar")
        reload_btn.clicked.connect(self.refresh)
        folder_btn = icon_button("open", ctx.palette.text, "Instalar carpeta…")
        folder_btn.clicked.connect(self._install_folder)
        install_btn = icon_button(
            "add", ctx.palette.accent_text, "Instalar APK…", object_name="Primary"
        )
        install_btn.clicked.connect(self._install_apk)
        bar.addWidget(self._search, 1)
        bar.addWidget(self._filter)
        bar.addWidget(reload_btn)
        bar.addWidget(folder_btn)
        bar.addWidget(install_btn)
        root.addLayout(bar)

        self._busy = busy_bar()
        self._busy.hide()
        root.addWidget(self._busy)

        # --- tabla (+ estado vacío) ---
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Paquete", "Versión", "Tipo", "Estado", "Nota"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.itemDoubleClicked.connect(self._open_detail)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)          # Paquete
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Versión
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Tipo
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Estado
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)          # Nota

        self._empty_no_device = EmptyState(
            "Sin dispositivo conectado.\nConecta un terminal PAX por USB para ver sus aplicaciones.",
            ctx.palette,
            icon_concept="device",
        )
        self._empty_no_match = EmptyState(
            "No hay paquetes que coincidan con el filtro actual.",
            ctx.palette,
            icon_concept="apps",
        )
        self._stack = stacked_with_empty(self._table, self._empty_no_device)
        self._stack.addWidget(self._empty_no_match)  # índice 2
        root.addWidget(self._stack, 1)

        # --- acciones ---
        actions = QHBoxLayout()
        self._count = hint("0 paquetes")
        actions.addWidget(self._count)
        actions.addStretch(1)
        launch_btn = icon_button("play", ctx.palette.text, "Lanzar")
        launch_btn.clicked.connect(self._launch_sel)
        actions.addWidget(launch_btn)
        for text, slot in (
            ("Forzar detención", self._force_stop_sel),
            ("Desactivar", self._disable_sel),
            ("Activar", self._enable_sel),
            ("Limpiar datos", self._clear_sel),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            actions.addWidget(b)
        extract_btn = icon_button("save", ctx.palette.text, "Extraer APK…")
        extract_btn.clicked.connect(self._extract_sel)
        actions.addWidget(extract_btn)
        # Sin icono: el botón "Danger" invierte fondo/texto en :hover (ver
        # theme.py), y un icono horneado en un color fijo se volvería
        # invisible sobre su propio fondo al pasar el ratón.
        uninstall_btn = QPushButton("Desinstalar (user 0)")
        uninstall_btn.setObjectName("Danger")
        uninstall_btn.clicked.connect(self._uninstall_sel)
        actions.addWidget(uninstall_btn)
        root.addLayout(actions)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._packages = []
        self._table.setRowCount(0)
        if not self.ctx.adb.serial:
            self._busy.hide()
            self._count.setText("Sin dispositivo")
            self._stack.setCurrentWidget(self._empty_no_device)
            return
        self._count.setText("Cargando…")
        self._busy.show()
        # Los terminales PAX de producción bloquean el shell de adbd: `pm list
        # packages` / `dumpsys` devuelven vacío (el device cierra el stream sin
        # datos). Así que la lista de apps se obtiene igual que el PaydroidTool
        # oficial: descargando por 'sync' (pull) el packages.xml del
        # PackageManager y parseándolo. El estado activado/desactivado vive en
        # package-restrictions.xml (por usuario); es opcional, ya que en muchos
        # firmwares no es accesible por permisos (se degrada a "todo activado").
        self._tmpdir = tempfile.mkdtemp(prefix="bellum-apps-")
        self._pending = {"packages": _PENDING, "restrictions": _PENDING}
        self._pull_text("packages", "/data/system/packages.xml")
        self._pull_text("restrictions", "/data/system/users/0/package-restrictions.xml")

    def _pull_text(self, key: str, remote: str) -> None:
        """Descarga `remote` a un temporal y entrega su contenido (o None) a _collect."""
        local = os.path.join(self._tmpdir, key + ".xml")

        def after(res: CommandResult) -> None:
            text: str | None = None
            if res.ok and os.path.exists(local):
                try:
                    with open(local, encoding="utf-8", errors="replace") as fh:
                        text = fh.read()
                except OSError:
                    text = None
            self._collect(key, text)

        self.ctx.adb.run(["pull", remote, local], after)

    def _collect(self, key: str, value: str | None) -> None:
        self._pending[key] = value
        if any(v is _PENDING for v in self._pending.values()):
            return
        self._busy.hide()
        self._build()

    @staticmethod
    def _parse_packages(xml_text: str) -> tuple[list[tuple[str, str, bool]], dict[str, tuple[str, str]]]:
        """De packages.xml extrae (name, codePath, system) y {pkg: (versionName, versionCode)}.

        Solo se parsean las etiquetas de apertura <package …>; <updated-package>
        (versión de sistema reemplazada) y <renamed-package> quedan fuera porque
        no empiezan por '<package'.
        """
        pkgs: list[tuple[str, str, bool]] = []
        versions: dict[str, tuple[str, str]] = {}
        for m in _PKG_RE.finditer(xml_text):
            attrs = dict(_ATTR_RE.findall(m.group(1)))
            name = attrs.get("name")
            if not name:
                continue
            code_path = attrs.get("codePath", "")
            system = code_path.startswith(("/system", "/vendor", "/product", "/oem"))
            if not system:
                flags = attrs.get("publicFlags", "")
                if flags.lstrip("-").isdigit():
                    system = bool(int(flags) & 0x1)  # ApplicationInfo.FLAG_SYSTEM
            pkgs.append((name, code_path, system))
            versions[name] = (attrs.get("versionName", ""), attrs.get("version", ""))
        return pkgs, versions

    @staticmethod
    def _parse_restrictions(xml_text: str | None) -> set[str]:
        """De package-restrictions.xml devuelve el conjunto de paquetes desactivados.

        Atributo 'enabled': 0=default, 1=enabled, 2=disabled, 3=disabled-user,
        4=disabled-until-used. Consideramos desactivado 2 y 3.
        """
        disabled: set[str] = set()
        if not xml_text:
            return disabled
        for m in _RESTR_PKG_RE.finditer(xml_text):
            attrs = dict(_ATTR_RE.findall(m.group(1)))
            name = attrs.get("name")
            if name and attrs.get("enabled", "") in ("2", "3"):
                disabled.add(name)
        return disabled

    def _build(self) -> None:
        pkg_xml = self._pending.get("packages")
        if not pkg_xml:
            # No se pudo leer packages.xml (sin permisos de sync, ruta distinta…).
            self._packages = []
            self._versions = {}
            self._apply_filter()
            self.ctx.notify(
                "No se pudo leer /data/system/packages.xml del terminal "
                "(¿sin acceso por sync?).",
                "warn",
            )
            return

        disabled = self._parse_restrictions(self._pending.get("restrictions"))
        parsed, self._versions = self._parse_packages(pkg_xml)

        pkgs = [
            Package(
                name=name,
                apk_path=code_path,
                system=system,
                enabled=name not in disabled,
            )
            for name, code_path, system in parsed
        ]
        pkgs.sort(key=lambda p: p.name)
        self._packages = pkgs
        self._apply_filter()

    def _apply_filter(self) -> None:
        needle = self._search.text().strip().lower()
        mode = self._filter.currentIndex()
        rows = []
        for p in self._packages:
            if needle and needle not in p.name.lower():
                continue
            if mode == 1 and p.system:
                continue
            if mode == 2 and not p.system:
                continue
            if mode == 3 and p.enabled:
                continue
            rows.append(p)

        pal = self.ctx.palette
        self._table.setRowCount(len(rows))
        for i, p in enumerate(rows):
            name_item = QTableWidgetItem(p.name)
            name_item.setData(Qt.ItemDataRole.UserRole, p.name)
            self._table.setItem(i, 0, name_item)
            vname, vcode = self._versions.get(p.name, ("", ""))
            ver_item = QTableWidgetItem(vname or "—")
            if vcode:
                ver_item.setToolTip(f"versionCode {vcode}")
            self._table.setItem(i, 1, ver_item)
            self._table.setItem(i, 2, QTableWidgetItem("Sistema" if p.system else "Usuario"))
            state = QTableWidgetItem("Activado" if p.enabled else "Desactivado")
            if not p.enabled:
                state.setForeground(Qt.GlobalColor.gray)
            self._table.setItem(i, 3, state)
            note = KNOWN_PAX_PACKAGES.get(p.name, "")
            note_item = QTableWidgetItem(note)
            if "crítico" in note:
                from PySide6.QtGui import QColor

                note_item.setForeground(QColor(pal.danger))
            self._table.setItem(i, 4, note_item)
        self._count.setText(f"{len(rows)} de {len(self._packages)} paquetes")

        if not self.ctx.adb.serial:
            self._stack.setCurrentWidget(self._empty_no_device)
        elif not rows:
            self._stack.setCurrentWidget(self._empty_no_match)
        else:
            self._stack.setCurrentWidget(self._table)

    # ------------------------------------------------------------------
    def _selected(self) -> list[str]:
        names = []
        for idx in self._table.selectionModel().selectedRows():
            item = self._table.item(idx.row(), 0)
            if item:
                names.append(item.data(Qt.ItemDataRole.UserRole) or item.text())
        return names

    def _open_detail(self, item) -> None:
        if not self.ctx.adb.serial:
            return
        row = item.row()
        pkg_item = self._table.item(row, 0)
        if pkg_item:
            pkg = pkg_item.data(Qt.ItemDataRole.UserRole) or pkg_item.text()
            AppDetailDialog(self.ctx, pkg, self).exec()

    def _launch_sel(self) -> None:
        names = self._selected()
        if not names:
            self.ctx.notify("Selecciona una app.", "warn")
            return
        pkg = names[0]

        def after(res: CommandResult) -> None:
            ok = res.ok and "No activities found" not in res.stdout and "Error" not in res.stdout
            self.ctx.notify(
                f"Lanzando {pkg}." if ok else f"No se pudo lanzar {pkg}.", "ok" if ok else "warn"
            )

        # monkey con la categoría LAUNCHER arranca la actividad principal.
        self.ctx.adb.shell(
            f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1", after
        )

    def _force_stop_sel(self) -> None:
        names = self._selected()
        if not names:
            self.ctx.notify("Selecciona al menos una app.", "warn")
            return
        done = {"n": 0}
        total = len(names)

        def after(_res: CommandResult) -> None:
            done["n"] += 1
            if done["n"] >= total:
                self.ctx.notify(f"Forzada la detención de {total} app(s).", "ok")

        for pkg in names:
            self.ctx.adb.shell(f"am force-stop {pkg}", after)

    def _confirm(self, verb: str, names: list[str]) -> bool:
        if not names:
            self.ctx.notify("Selecciona al menos un paquete.", "warn")
            return False
        critical = [n for n in names if "crítico" in KNOWN_PAX_PACKAGES.get(n, "")]
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning if critical else QMessageBox.Icon.Question)
        box.setWindowTitle(f"Confirmar: {verb}")
        text = f"Vas a {verb.lower()} {len(names)} paquete(s):\n\n" + "\n".join(
            f"  • {n}" for n in names[:12]
        )
        if len(names) > 12:
            text += f"\n  … y {len(names) - 12} más"
        box.setText(text)
        if critical:
            box.setInformativeText(
                "⚠ Uno o más son componentes CRÍTICOS de seguridad/pago de PAX "
                f"({', '.join(critical)}). Tocarlos puede inutilizar el terminal como "
                "dispositivo de pago o dejarlo sin arrancar. Procede solo si sabes lo que haces "
                "y es tu equipo."
            )
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _run_each(self, names: list[str], make_args, verb: str) -> None:
        done = {"n": 0, "fail": 0}
        total = len(names)

        def after(res: CommandResult) -> None:
            done["n"] += 1
            # pm imprime "Success" o "Failure" en stdout (con canales fusionados).
            if not res.ok or "Failure" in res.stdout or "Error" in res.stdout:
                done["fail"] += 1
            if done["n"] >= total:
                if done["fail"]:
                    self.ctx.notify(
                        f"{verb}: {total - done['fail']}/{total} OK, {done['fail']} con error.",
                        "warn",
                    )
                else:
                    self.ctx.notify(f"{verb}: {total} paquete(s) OK.", "ok")
                self.refresh()

        for name in names:
            self.ctx.adb.shell(make_args(name), after)

    def _uninstall_sel(self) -> None:
        names = self._selected()
        if self._confirm("Desinstalar", names):
            self._run_each(names, lambda n: f"pm uninstall --user 0 {n}", "Desinstalar")

    def _disable_sel(self) -> None:
        names = self._selected()
        if self._confirm("Desactivar", names):
            self._run_each(names, lambda n: f"pm disable-user --user 0 {n}", "Desactivar")

    def _enable_sel(self) -> None:
        names = self._selected()
        if self._confirm("Activar", names):
            self._run_each(names, lambda n: f"pm enable {n}", "Activar")

    def _clear_sel(self) -> None:
        names = self._selected()
        if self._confirm("Limpiar datos de", names):
            self._run_each(names, lambda n: f"pm clear {n}", "Limpiar datos")

    def _install_apk(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar APK(s)", "", "Android Package (*.apk);;Todos (*)"
        )
        if not files:
            return
        done = {"n": 0, "fail": 0}
        total = len(files)

        def after(res: CommandResult) -> None:
            done["n"] += 1
            if not res.ok or "Success" not in res.stdout:
                done["fail"] += 1
            if done["n"] >= total:
                ok = total - done["fail"]
                level = "ok" if not done["fail"] else "warn"
                self.ctx.notify(f"Instalación: {ok}/{total} OK.", level)
                self.refresh()

        for path in files:
            self.ctx.adb.run(["install", "-r", path], after, merge_stderr=True)

    def _install_folder(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        folder = QFileDialog.getExistingDirectory(self, "Carpeta con APKs")
        if not folder:
            return
        apks = sorted(glob.glob(os.path.join(folder, "*.apk")))
        if not apks:
            self.ctx.notify("No hay .apk en esa carpeta.", "warn")
            return
        done = {"n": 0, "fail": 0}
        total = len(apks)

        def after(res: CommandResult) -> None:
            done["n"] += 1
            if not res.ok or "Success" not in res.stdout:
                done["fail"] += 1
            if done["n"] >= total:
                ok = total - done["fail"]
                self.ctx.notify(
                    f"Instalar carpeta: {ok}/{total} OK.", "ok" if not done["fail"] else "warn"
                )
                self.refresh()

        for path in apks:
            self.ctx.adb.run(["install", "-r", path], after, merge_stderr=True)

    def _extract_sel(self) -> None:
        """Extrae (pull) el/los .apk de los paquetes seleccionados a una carpeta."""
        names = self._selected()
        if not names:
            self.ctx.notify("Selecciona al menos un paquete.", "warn")
            return
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        dest = QFileDialog.getExistingDirectory(self, "Guardar APKs en…")
        if not dest:
            return

        # Fase 1: resolver rutas remotas de cada paquete (pueden ser splits).
        paths: dict[str, list[str]] = {}
        state = {"pending": len(names)}

        def on_path(name: str, res: CommandResult) -> None:
            remotes = [
                ln[len("package:"):].strip()
                for ln in res.stdout.splitlines()
                if ln.startswith("package:")
            ]
            paths[name] = remotes
            state["pending"] -= 1
            if state["pending"] == 0:
                self._pull_apks(paths, dest)

        for name in names:
            self.ctx.adb.shell(f"pm path {name}", lambda r, n=name: on_path(n, r))

    def _pull_apks(self, paths: dict[str, list[str]], dest: str) -> None:
        # Fase 2: descargar cada apk. Nombre plano: <pkg>.apk (o <pkg>-<base> en splits).
        jobs: list[tuple[str, str]] = []
        for name, remotes in paths.items():
            if not remotes:
                continue
            for remote in remotes:
                base = posixpath.basename(remote)
                if len(remotes) == 1:
                    local = os.path.join(dest, f"{name}.apk")
                else:
                    local = os.path.join(dest, f"{name}-{base}")
                jobs.append((remote, local))

        if not jobs:
            self.ctx.notify("No se pudo resolver ninguna ruta de APK.", "warn")
            return

        done = {"n": 0, "fail": 0}
        total = len(jobs)

        def after(res: CommandResult) -> None:
            done["n"] += 1
            if not res.ok:
                done["fail"] += 1
            if done["n"] >= total:
                ok = total - done["fail"]
                self.ctx.notify(
                    f"Extraer APK: {ok}/{total} OK → {dest}", "ok" if not done["fail"] else "warn"
                )

        for remote, local in jobs:
            self.ctx.adb.run(["pull", remote, local], after)
