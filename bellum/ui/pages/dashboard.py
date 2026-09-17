"""Dashboard: resumen e información del terminal seleccionado."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...core.adb import CommandResult
from ..widgets import Card, Page, busy_bar, hint, icon_button, state_badge

# Un solo comando compuesto para el estado del sistema (una ida y vuelta),
# separado por un marcador que luego partimos.
_MARK = "@@BELLUM@@"
_STATUS_CMD = (
    f"dumpsys battery; echo {_MARK}; df -h /data; echo {_MARK}; "
    f"wm size; echo {_MARK}; wm density; echo {_MARK}; cat /proc/uptime"
)

# Propiedades destacadas (getprop) con etiqueta amigable.
_FEATURED = [
    ("ro.product.model", "Modelo"),
    ("ro.product.manufacturer", "Fabricante"),
    ("pax.ctrl.androidver", "Android (PAX)"),
    ("ro.build.version.release", "Android"),
    ("ro.build.version.sdk", "SDK"),
    ("ro.serialno", "Nº de serie"),
    ("pax.sn", "Nº de serie PAX"),
    ("ro.build.display.id", "Build"),
    ("ro.product.cpu.abi", "ABI"),
    ("pax.ctrl.termtype", "Tipo de terminal"),
]


class DashboardPage(Page):
    title = "Resumen"
    icon_concept = "dashboard"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._last_props: dict[str, str] = {}
        self._last_status: dict[str, str] = {}
        self._via_pax = False
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(16)

        # --- Cabecera de estado ---
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        self._status = QLabel("Sin dispositivo seleccionado")
        self._status.setObjectName("PageTitle")
        title_row.addWidget(self._status)
        self._title_row = title_row
        self._state_badge = state_badge("offline", ctx.palette)
        self._state_badge.hide()
        title_row.addWidget(self._state_badge)
        title_row.addStretch(1)
        self._substatus = hint("Conecta un terminal PAX por USB con la depuración habilitada.")
        head = QVBoxLayout()
        head.setSpacing(2)
        head.addLayout(title_row)
        head.addWidget(self._substatus)

        refresh_btn = icon_button("refresh", ctx.palette.text, "Actualizar")
        refresh_btn.clicked.connect(self.refresh)
        report_btn = icon_button("save", ctx.palette.text, "Informe…", tooltip="Exportar informe del terminal")
        report_btn.clicked.connect(self._export_report)
        reboot_btn = icon_button("reboot", ctx.palette.text, "Reiniciar")
        reboot_btn.clicked.connect(lambda: self._reboot(""))
        boot_btn = icon_button("jump", ctx.palette.text, "Bootloader", tooltip="Reiniciar a bootloader")
        boot_btn.clicked.connect(lambda: self._reboot("bootloader"))

        top = QHBoxLayout()
        top.addLayout(head)
        top.addStretch(1)
        top.addWidget(refresh_btn)
        top.addWidget(report_btn)
        top.addWidget(reboot_btn)
        top.addWidget(boot_btn)
        root.addLayout(top)
        self._action_btns = (report_btn, reboot_btn, boot_btn)

        self._busy = busy_bar()
        self._busy.hide()
        root.addWidget(self._busy)

        # --- Tarjeta de propiedades ---
        self._info_card = Card("Información del dispositivo")
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(24)
        self._grid.setVerticalSpacing(10)
        self._grid.setColumnStretch(1, 1)
        self._grid.setColumnStretch(3, 1)
        holder = QWidget()
        holder.setLayout(self._grid)
        self._info_card.add(holder)
        self._empty = hint("—")
        self._info_card.add(self._empty)
        root.addWidget(self._info_card)

        # --- Tarjeta de estado del sistema ---
        self._status_card = Card("Estado del sistema")
        stat_row = QHBoxLayout()
        stat_row.setSpacing(28)
        self._stat_labels: dict[str, QLabel] = {}
        for key, caption in (
            ("battery", "Batería"),
            ("storage", "Almacenamiento /data"),
            ("screen", "Pantalla"),
            ("uptime", "Encendido"),
        ):
            cap = QLabel(caption)
            cap.setStyleSheet(f"color:{ctx.palette.text_dim}; font-size:12px;")
            val = QLabel("—")
            val.setStyleSheet("font-size:15px; font-weight:600;")
            cell = QVBoxLayout()
            cell.setSpacing(1)
            cell.addWidget(cap)
            cell.addWidget(val)
            wrap = QWidget()
            wrap.setLayout(cell)
            stat_row.addWidget(wrap)
            self._stat_labels[key] = val
        stat_row.addStretch(1)
        holder2 = QWidget()
        holder2.setLayout(stat_row)
        self._status_card.add(holder2)
        root.addWidget(self._status_card)
        root.addStretch(1)

        self._set_enabled(False)

    # ------------------------------------------------------------------
    def _replace_badge(self, state: str) -> None:
        """`state_badge()` crea una QLabel nueva cada vez; la sustituimos en
        su posición dentro de `_title_row` (índice 1, tras el título)."""
        old = self._state_badge
        self._state_badge = state_badge(state, self.ctx.palette)
        self._title_row.insertWidget(1, self._state_badge)
        self._title_row.removeWidget(old)
        # hide() de inmediato: sacar un widget de un layout con removeWidget()
        # no lo oculta (solo deja de posicionarlo), y deleteLater() difiere la
        # destrucción real al siguiente ciclo de eventos. Sin el hide(), el
        # widget viejo puede seguir pintándose superpuesto en su posición
        # anterior hasta que Qt procese la baja.
        old.hide()
        old.deleteLater()

    def _set_enabled(self, on: bool) -> None:
        for b in self._action_btns:
            b.setEnabled(on)

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w:
                # hide() inmediato: takeAt() saca el widget del layout pero no
                # lo oculta, y deleteLater() difiere la destrucción real. Sin
                # el hide(), refrescos consecutivos (p. ej. dos "Actualizar"
                # seguidos) dejaban restos de la cuadrícula anterior pintados
                # debajo de la nueva.
                w.hide()
                w.deleteLater()

    def refresh(self) -> None:
        serial = self.ctx.adb.serial
        self._clear_grid()
        self._state_badge.hide()
        for lbl in self._stat_labels.values():
            lbl.setText("—")
        if not serial:
            self._busy.hide()
            self._status.setText("Sin dispositivo seleccionado")
            self._substatus.setText(
                "Conecta un terminal PAX por USB con la depuración habilitada."
            )
            self._empty.setText("—")
            self._empty.show()
            self._set_enabled(False)
            self._last_props = {}
            return

        self._set_enabled(True)
        self._via_pax = False
        self._status.setText("Leyendo propiedades…")
        self._empty.setText("Cargando…")
        self._busy.show()
        self.ctx.adb.getprops(self._on_props)

    def _on_props(self, props: dict[str, str]) -> None:
        # Los terminales PAX de producción bloquean el shell de adbd, así que
        # `getprop` (shell) vuelve vacío. Antes de darlo por desconectado,
        # reintentamos por la vía PAX: `systool get sysprop <key>`, que sí
        # responde en esos firmwares (igual que hace el PaydroidTool oficial).
        if not props and not self._via_pax:
            self._via_pax = True
            self._load_props_via_pax()
            return

        self._busy.hide()
        self._last_props = props
        if not props:
            self._status.setText("Dispositivo no disponible")
            self._substatus.setText(
                "No se pudieron leer las propiedades (¿no autorizado u offline?)."
            )
            self._empty.setText("Sin datos.")
            self._empty.show()
            self._replace_badge("offline")
            return

        model = props.get("ro.product.model") or props.get("ro.product.name") or "Terminal PAX"
        self._status.setText(model)
        self._substatus.setText(self.ctx.adb.serial)
        self._empty.hide()
        self._replace_badge("device")
        # El estado del sistema (batería/almacenamiento/pantalla) se lee por
        # shell; en terminales bloqueados no está disponible, así que solo se
        # intenta cuando las propiedades vinieron por shell.
        if not self._via_pax:
            self._load_status()

        pal = self.ctx.palette
        row = 0
        col = 0
        shown = 0
        for key, label in _FEATURED:
            val = props.get(key)
            if not val:
                continue
            name = QLabel(label)
            name.setStyleSheet(f"color:{pal.text_dim}; font-size:12px;")
            value = QLabel(val)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            cell = QVBoxLayout()
            cell.setSpacing(1)
            cell.addWidget(name)
            cell.addWidget(value)
            wrap = QWidget()
            wrap.setLayout(cell)
            self._grid.addWidget(wrap, row, col * 2, 1, 2)
            col += 1
            if col >= 2:
                col = 0
                row += 1
            shown += 1
        if shown == 0:
            self._empty.setText("El dispositivo respondió pero sin propiedades reconocidas.")
            self._empty.show()

    # ---- fallback PAX: propiedades vía systool (shell bloqueado) ----------
    def _load_props_via_pax(self) -> None:
        """Lee las propiedades destacadas con `systool get sysprop <key>`.

        Se usa cuando `shell getprop` no devuelve nada (shell bloqueado). Cada
        clave es una ida y vuelta; se acumulan y, al terminar todas, se
        reutiliza `_on_props` con el dict resultante.
        """
        self._status.setText("Leyendo propiedades (systool)…")
        self._pax_props: dict[str, str] = {}
        self._pax_remaining = len(_FEATURED)
        for key, _ in _FEATURED:
            self.ctx.adb.run(
                ["systool", "get", "sysprop", key],
                lambda r, k=key: self._on_pax_prop(k, r),
            )

    def _on_pax_prop(self, key: str, res: CommandResult) -> None:
        # Salida de systool: '.<key>=<valor>' (una línea) + '[SYSTOOL:0] ok'.
        for raw in res.stdout.splitlines():
            line = raw.strip()
            if line.startswith(".") and "=" in line:
                k, _, v = line[1:].partition("=")
                if k == key and v.strip():
                    self._pax_props[key] = v.strip()
        self._pax_remaining -= 1
        if self._pax_remaining == 0:
            self._on_props(self._pax_props)

    def _reboot(self, mode: str) -> None:
        if not self.ctx.adb.serial:
            return
        args = ["reboot"] + ([mode] if mode else [])
        target = "bootloader" if mode else "normal"
        self.ctx.adb.run(args, lambda r: self._after_reboot(r, target))

    def _after_reboot(self, res: CommandResult, target: str) -> None:
        if res.ok:
            self.ctx.notify(f"Reinicio ({target}) enviado.", "ok")
        else:
            self.ctx.notify(f"Fallo al reiniciar: {res.text.strip() or 'error'}", "error")

    # ---- estado del sistema (batería/almacenamiento/pantalla/uptime) ----
    def _load_status(self) -> None:
        self.ctx.adb.shell(_STATUS_CMD, self._on_status)

    @staticmethod
    def _fmt_uptime(seconds: float) -> str:
        s = int(seconds)
        d, s = divmod(s, 86400)
        h, s = divmod(s, 3600)
        m, _ = divmod(s, 60)
        if d:
            return f"{d}d {h}h {m}m"
        if h:
            return f"{h}h {m}m"
        return f"{m}m"

    def _parse_status(self, text: str) -> dict[str, str]:
        parts = text.split(_MARK)
        out = {"battery": "—", "storage": "—", "screen": "—", "uptime": "—"}
        # batería
        if len(parts) >= 1:
            level = temp = None
            for line in parts[0].splitlines():
                st = line.strip()
                if st.startswith("level:"):
                    level = st.split(":", 1)[1].strip()
                elif st.startswith("temperature:"):
                    temp = st.split(":", 1)[1].strip()
            if level:
                val = f"{level}%"
                if temp and temp.lstrip("-").isdigit():
                    val += f" · {int(temp) / 10:.0f}°C"
                out["battery"] = val
        # almacenamiento (df -h /data): busca la línea cuyo último campo es la ruta
        if len(parts) >= 2:
            for line in reversed([ln for ln in parts[1].splitlines() if ln.strip()]):
                f = line.split()
                if len(f) >= 5 and f[-1].startswith("/"):
                    used, size, avail = f[-4], f[-5], f[-3]
                    out["storage"] = f"{used} / {size} · {avail} libre"
                    break
        # pantalla
        size = density = None
        if len(parts) >= 3:
            for line in parts[2].splitlines():
                if "Physical size:" in line:
                    size = line.split("Physical size:", 1)[1].strip()
        if len(parts) >= 4:
            for line in parts[3].splitlines():
                if "Physical density:" in line:
                    density = line.split("Physical density:", 1)[1].strip()
        if size:
            out["screen"] = f"{size} · {density} dpi" if density else size
        # uptime
        if len(parts) >= 5:
            tok = parts[4].split()
            if tok:
                try:
                    out["uptime"] = self._fmt_uptime(float(tok[0]))
                except ValueError:
                    pass
        return out

    def _on_status(self, res: CommandResult) -> None:
        self._last_status = self._parse_status(res.stdout)
        for key, lbl in self._stat_labels.items():
            lbl.setText(self._last_status.get(key, "—"))

    # ---- exportar informe ----
    def _export_report(self) -> None:
        if not self.ctx.adb.serial or not self._last_props:
            self.ctx.notify("Sin datos: actualiza con un dispositivo conectado.", "warn")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar informe del terminal",
            f"informe_{self.ctx.adb.serial}.json",
            "JSON (*.json);;Texto (*.txt)",
        )
        if not path:
            return
        report = {
            "serial": self.ctx.adb.serial,
            "estado": self._last_status,
            "propiedades": self._last_props,
        }
        try:
            with open(path, "w", encoding="utf-8") as fh:
                if path.lower().endswith(".txt"):
                    fh.write(f"# Informe del terminal {self.ctx.adb.serial}\n\n")
                    fh.write("## Estado\n")
                    for k, v in self._last_status.items():
                        fh.write(f"{k}: {v}\n")
                    fh.write("\n## Propiedades (getprop)\n")
                    for k, v in sorted(self._last_props.items()):
                        fh.write(f"{k} = {v}\n")
                else:
                    json.dump(report, fh, indent=2, ensure_ascii=False)
            self.ctx.notify(f"Informe guardado: {path}", "ok")
        except OSError as exc:
            self.ctx.notify(f"No se pudo guardar: {exc}", "error")
