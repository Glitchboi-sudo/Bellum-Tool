"""Diálogo de detalle de una aplicación instalada (dumpsys package <pkg>).

Muestra info clave (versión, fechas, rutas, SDK) y la lista de permisos con su
estado, permitiendo conceder/revocar permisos en tiempo de ejecución
(`pm grant`/`pm revoke`). Los permisos no-runtime devolverán error del propio
`pm`, que se muestra tal cual.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from ..core.adb import CommandResult

_INFO_FIELDS = [
    ("versionName", "Versión"),
    ("versionCode", "Código de versión"),
    ("minSdk", "SDK mínimo"),
    ("targetSdk", "SDK objetivo"),
    ("firstInstallTime", "Instalada"),
    ("lastUpdateTime", "Actualizada"),
    ("codePath", "Ruta del APK"),
    ("dataDir", "Datos"),
]


class AppDetailDialog(QDialog):
    def __init__(self, ctx, package: str, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._package = package
        self.setWindowTitle(f"Detalle · {package}")
        self.setMinimumSize(560, 560)

        layout = QVBoxLayout(self)
        title = QLabel(package)
        title.setObjectName("PageTitle")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(title)

        self._info = QLabel("Cargando…")
        self._info.setObjectName("Mono")
        self._info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._info.setWordWrap(True)
        layout.addWidget(self._info)

        layout.addWidget(QLabel("Permisos (✓ concedido · ✗ denegado · · no-runtime):"))
        self._perms = QListWidget()
        layout.addWidget(self._perms, 1)

        actions = QHBoxLayout()
        grant = QPushButton("Conceder")
        grant.clicked.connect(lambda: self._change_perm(True))
        revoke = QPushButton("Revocar")
        revoke.clicked.connect(lambda: self._change_perm(False))
        actions.addWidget(grant)
        actions.addWidget(revoke)
        actions.addStretch(1)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self._reload()

    # ------------------------------------------------------------------
    def _reload(self) -> None:
        self.ctx.adb.shell(f"dumpsys package {self._package}", self._on_dump)

    def _on_dump(self, res: CommandResult) -> None:
        info, perms = self._parse(res.stdout)
        pal = self.ctx.palette
        rows = []
        for key, label in _INFO_FIELDS:
            if info.get(key):
                rows.append(f"{label:>18}:  {info[key]}")
        self._info.setText("\n".join(rows) or "Sin datos (¿paquete no encontrado?).")

        self._perms.clear()
        for perm, granted in sorted(perms.items()):
            mark = "✓" if granted is True else ("✗" if granted is False else "·")
            item = QListWidgetItem(f"{mark}  {perm}")
            item.setData(Qt.ItemDataRole.UserRole, perm)
            if granted is True:
                from PySide6.QtGui import QColor

                item.setForeground(QColor(pal.ok))
            self._perms.addItem(item)

    @staticmethod
    def _parse(text: str) -> tuple[dict[str, str], dict[str, object]]:
        """Extrae campos clave y {permiso: granted(True|False|None)}.

        Escaneo por línea, sin depender de límites de sección: una entrada
        `perm: granted=X` fija el estado; un permiso «pelado» (solo el nombre)
        se registra como None si aún no se conoce. El estado conocido nunca se
        pisa con None.
        """
        info: dict[str, str] = {}
        perms: dict[str, object] = {}
        for raw in text.splitlines():
            line = raw.strip()
            for field, _ in _INFO_FIELDS:
                token = field + "="
                if token in raw and field not in info:
                    info[field] = raw.split(token, 1)[1].split()[0]
            if not line.startswith(("android.", "com.", "org.")) or "permission" not in line:
                continue
            perm = line.split(":", 1)[0].split()[0]
            if "granted=true" in line:
                perms[perm] = True
            elif "granted=false" in line:
                perms[perm] = False
            elif perm not in perms:
                perms[perm] = None
        return info, perms

    def _selected_perm(self) -> str | None:
        items = self._perms.selectedItems()
        return items[0].data(Qt.ItemDataRole.UserRole) if items else None

    def _change_perm(self, grant: bool) -> None:
        perm = self._selected_perm()
        if not perm:
            self.ctx.notify("Selecciona un permiso.", "warn")
            return
        verb = "grant" if grant else "revoke"

        def after(res: CommandResult) -> None:
            out = res.text.strip()
            if res.ok and not out:
                self.ctx.notify(f"Permiso {'concedido' if grant else 'revocado'}.", "ok")
            else:
                self.ctx.notify(out or "pm devolvió error.", "warn")
            self._reload()

        self.ctx.adb.shell(f"pm {verb} {self._package} {perm}", after)
