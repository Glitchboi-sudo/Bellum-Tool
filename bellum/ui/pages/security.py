"""Sección «Seguridad»: ayudas de evaluación (solo lectura) para pruebas
autorizadas sobre terminales PAX de tu propiedad.

Tres páginas:

* **Postura** — recoge propiedades de seguridad (vía systool, funciona con el
  shell bloqueado) y las puntúa en hallazgos con severidad. Exportable.
* **Superficie** — enumera la superficie de ataque (puertos a la escucha,
  servicios, procesos, montajes). Requiere shell.
* **Paquetes** — lista e inspecciona paquetes instalados para mapear la
  superficie de aplicaciones. Requiere shell.

Todo es enumeración/recon y documentación: nada de bypass ni de extracción de
material criptográfico del terminal.
"""

from __future__ import annotations

import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core import audit
from ...core.adb import CommandResult
from ..widgets import Card, Page, flow_row, hint, icon_button

# Texto de la píldora de severidad, por nivel.
_PILL = {
    "danger": "CRÍTICO",
    "warn": "AVISO",
    "info": "INFO",
    "ok": "OK",
    "na": "N/D",
}


def _pill_colors(pal, level: str) -> tuple[str, str]:
    return {
        "danger": (pal.danger_bg, pal.danger),
        "warn": (pal.warn_bg, pal.warn),
        "info": (pal.neutral_bg, pal.neutral_fg),
        "ok": (pal.ok_bg, pal.ok),
        "na": (pal.neutral_bg, pal.text_dim),
    }.get(level, (pal.neutral_bg, pal.text_dim))


# ======================================================================
# Postura de seguridad
# ======================================================================
class PosturaPage(Page):
    title = "Postura"
    icon_concept = "warning"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._findings: list[audit.Finding] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)
        root.addWidget(
            hint(
                "Auditoría de postura de solo lectura para evaluaciones autorizadas sobre equipo "
                "de tu propiedad. Recoge propiedades de seguridad vía systool (funciona aunque el "
                "shell esté bloqueado) y las puntúa. No modifica nada del terminal."
            )
        )

        self._analyze = icon_button(
            "refresh", ctx.palette.accent_text, "Analizar postura", object_name="Primary"
        )
        self._analyze.clicked.connect(self._run_audit)
        self._export = icon_button("save", ctx.palette.text, "Exportar informe…")
        self._export.clicked.connect(self._export_report)
        self._export.setEnabled(False)
        root.addWidget(flow_row(self._analyze, self._export))

        self._summary = QLabel("Pulsa «Analizar postura» para evaluar el terminal seleccionado.")
        self._summary.setObjectName("Hint")
        root.addWidget(self._summary)

        # Contenedor de hallazgos (se repuebla en cada análisis).
        self._box = QVBoxLayout()
        self._box.setSpacing(8)
        holder = QWidget()
        holder.setLayout(self._box)
        root.addWidget(holder)
        root.addStretch(1)

    # ------------------------------------------------------------------
    def _run_audit(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        self._analyze.setEnabled(False)
        self._summary.setText("Recogiendo propiedades de seguridad…")
        audit.collect_security(
            self.ctx.adb,
            self._on_props,
            on_progress=lambda h: self._summary.setText(f"Leyendo {h}…"),
        )

    def _on_props(self, props: dict[str, str]) -> None:
        self._analyze.setEnabled(True)
        self._findings = audit.evaluate(props)
        self._render()

    def _render(self) -> None:
        # Vacía el contenedor.
        while self._box.count():
            item = self._box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        order = {lvl: i for i, lvl in enumerate(audit.LEVELS)}
        for f in sorted(self._findings, key=lambda x: order.get(x.level, 99)):
            self._box.addWidget(self._row(f))

        counts = audit.summarize(self._findings)
        self._summary.setText(
            f"{counts['danger']} críticos · {counts['warn']} avisos · "
            f"{counts['info']} informativos · {counts['ok']} correctos · {counts['na']} sin dato"
        )
        self._export.setEnabled(True)

    def _row(self, f: audit.Finding) -> QWidget:
        pal = self.ctx.palette
        bg, fg = _pill_colors(pal, f.level)
        frame = QFrame()
        frame.setObjectName("Card")
        row = QHBoxLayout(frame)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)

        pill = QLabel(_PILL.get(f.level, "?"))
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill.setFixedWidth(74)
        pill.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:8px; padding:4px 0; "
            "font-weight:800; font-size:11px;"
        )
        row.addWidget(pill)

        text = QVBoxLayout()
        text.setSpacing(1)
        name = QLabel(f.label)
        name.setStyleSheet("font-weight:600;")
        detail = QLabel(f.detail)
        detail.setStyleSheet(f"color:{pal.text_dim}; font-size:12px;")
        detail.setWordWrap(True)
        text.addWidget(name)
        text.addWidget(detail)
        row.addLayout(text, 1)

        value = QLabel(f.value)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        value.setStyleSheet(f"color:{pal.text}; font-family:'JetBrains Mono','Fira Code',monospace;")
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(value)
        return frame

    def _export_report(self) -> None:
        if not self._findings:
            return
        serial = self.ctx.adb.serial or "terminal"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar informe de postura", f"postura_{serial}.txt", "Texto (*.txt);;Todos (*)"
        )
        if not path:
            return
        counts = audit.summarize(self._findings)
        lines = [
            "Bellum Tool — Auditoría de postura de seguridad",
            f"Terminal : {serial}",
            f"Fecha    : {datetime.datetime.now().isoformat(timespec='seconds')}",
            f"Resumen  : {counts['danger']} críticos, {counts['warn']} avisos, "
            f"{counts['info']} info, {counts['ok']} ok, {counts['na']} sin dato",
            "=" * 60,
            "",
        ]
        order = {lvl: i for i, lvl in enumerate(audit.LEVELS)}
        for f in sorted(self._findings, key=lambda x: order.get(x.level, 99)):
            lines.append(f"[{_PILL.get(f.level, '?')}] {f.label}: {f.value}")
            lines.append(f"    {f.detail}")
            lines.append("")
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
            self.ctx.notify(f"Informe de postura → {path}", "ok")
        except OSError as exc:
            self.ctx.notify(f"No se pudo guardar: {exc}", "error")


# ======================================================================
# Base para páginas de recon por shell
# ======================================================================
class _ReconPage(Page):
    intro = ""

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._warned = False
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)
        if self.intro:
            root.addWidget(hint(self.intro))
        self._build_controls(root)
        self._out = QPlainTextEdit()
        self._out.setObjectName("Console")
        self._out.setReadOnly(True)
        self._out.setPlaceholderText("La salida de la enumeración aparecerá aquí…")
        root.addWidget(self._out, 1)

    def _build_controls(self, root: QVBoxLayout) -> None:  # override
        ...

    def _probe(self, title: str, cmd: str) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        self._out.appendPlainText(f"# {title}\n$ adb shell {cmd}")
        self.ctx.adb.shell(cmd, self._show)

    def _show(self, res: CommandResult) -> None:
        text = (res.text or "").rstrip()
        self._out.appendPlainText(text if text else "(sin salida)")
        if res.ok and not text and not self._warned:
            self._warned = True
            self._out.appendPlainText(
                "· El shell parece restringido en este terminal. En unidades bloqueadas usa "
                "«Seguridad › Postura» (systool) para la parte que no necesita shell."
            )
        self._out.appendPlainText("")

    def _btn_row(self, root: QVBoxLayout, title: str, probes: list[tuple[str, str]]) -> None:
        card = Card(title)
        btns = []
        for label, cmd in probes:
            b = icon_button("tools", self.ctx.palette.text, label)
            b.clicked.connect(lambda _=False, t=label, c=cmd: self._probe(t, c))
            btns.append(b)
        card.add(flow_row(*btns))
        root.addWidget(card)


# ======================================================================
# Superficie de ataque
# ======================================================================
class SuperficiePage(_ReconPage):
    title = "Superficie"
    icon_concept = "device"
    intro = (
        "Enumera la superficie de ataque del terminal (solo lectura). Requiere un shell "
        "disponible; sobre equipo de tu propiedad y con autorización."
    )

    def _build_controls(self, root: QVBoxLayout) -> None:
        self._btn_row(root, "Red y servicios", [
            ("Puertos a la escucha", "ss -tulpn 2>/dev/null || netstat -tulpn 2>/dev/null"),
            ("Servicios del sistema", "service list"),
            ("Conexiones", "ss -tun 2>/dev/null || netstat -tun 2>/dev/null"),
        ])
        self._btn_row(root, "Procesos y sistema de ficheros", [
            ("Procesos", "ps -A 2>/dev/null || ps"),
            ("Montajes", "mount"),
            ("Escritura en /data/local/tmp", "ls -la /data/local/tmp"),
            ("Ejecutables SUID", "find / -perm -4000 -type f 2>/dev/null"),
        ])


# ======================================================================
# Escaneo de paquetes
# ======================================================================
class PaquetesPage(_ReconPage):
    title = "Paquetes"
    icon_concept = "apps"
    intro = (
        "Lista e inspecciona paquetes instalados para mapear la superficie de aplicaciones. "
        "Requiere shell. La inspección muestra flags (p. ej. DEBUGGABLE) y permisos."
    )

    def _build_controls(self, root: QVBoxLayout) -> None:
        self._btn_row(root, "Listar paquetes", [
            ("Terceros", "pm list packages -3"),
            ("Sistema", "pm list packages -s"),
            ("Deshabilitados", "pm list packages -d"),
            ("Paquetes PAX", "pm list packages | grep -i pax"),
        ])

        card = Card("Inspeccionar un paquete")
        card.add(hint("Muestra flags (DEBUGGABLE), permisos, firma e instalador del paquete."))
        self._pkg = QLineEdit()
        self._pkg.setPlaceholderText("nombre del paquete (p. ej. com.pax.…)")
        self._pkg.returnPressed.connect(self._inspect)
        run = icon_button("run", self.ctx.palette.accent_text, "Inspeccionar", object_name="Primary")
        run.clicked.connect(self._inspect)
        card.add(flow_row(QLabel("Paquete:"), self._pkg, run))
        root.addWidget(card)

    def _inspect(self) -> None:
        pkg = self._pkg.text().strip()
        if not pkg:
            self.ctx.notify("Escribe el nombre de un paquete.", "warn")
            return
        cmd = (
            f"dumpsys package {pkg} | grep -iE "
            "'versionName|flags|pkgFlags|permission|installerPackageName|signatures|codePath'"
        )
        self._probe(f"dumpsys package {pkg}", cmd)
