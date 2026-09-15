"""Herramientas de diagnóstico: grabación de pantalla, bug report y dumpsys.

Se agrupa como pestaña dentro de la sección Diagnóstico.
"""

from __future__ import annotations

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core.adb import CommandResult
from ..widgets import Card, Page, hint, icon_button

_REMOTE_REC = "/sdcard/bellum_rec.mp4"

# Servicios dumpsys frecuentes (la lista es editable).
_SERVICES = [
    "battery", "package", "meminfo", "cpuinfo", "activity activities",
    "connectivity", "wifi", "power", "display", "window", "input",
    "alarm", "netstats", "usb", "bluetooth_manager",
]


def _row(*widgets: QWidget, stretch_index: int | None = None) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    for i, x in enumerate(widgets):
        lay.addWidget(x, 1 if i == stretch_index else 0)
    if stretch_index is None:
        lay.addStretch(1)
    return w


class DiagToolsPage(Page):
    title = "Herramientas"
    icon_concept = "tools"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._rec_proc: QProcess | None = None
        self._rec_local = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)

        # --- grabación + bugreport ---
        cap_card = Card("Grabación y reportes")
        self._rec_btn = icon_button("play", ctx.palette.accent_text, "Grabar pantalla", object_name="Primary")
        self._rec_btn.clicked.connect(self._toggle_record)
        bug_btn = icon_button("save", ctx.palette.text, "Generar bug report…")
        bug_btn.clicked.connect(self._bugreport)
        cap_card.add(_row(self._rec_btn, bug_btn))
        cap_card.add(
            hint(
                "La grabación se guarda en el terminal y se descarga al detenerla "
                "(límite de Android: 180 s; se detiene sola al llegar)."
            )
        )
        root.addWidget(cap_card)

        # --- explorador dumpsys ---
        dump_card = Card("Explorador de dumpsys")
        self._service = QComboBox()
        self._service.setEditable(True)
        self._service.addItems(_SERVICES)
        view_btn = icon_button("run", ctx.palette.accent_text, "Ver", object_name="Primary")
        view_btn.clicked.connect(self._run_dumpsys)
        save_btn = icon_button("save", ctx.palette.text, "Guardar…")
        save_btn.clicked.connect(self._save_output)
        dump_card.add(_row(QLabel("Servicio:"), self._service, view_btn, save_btn, stretch_index=1))
        root.addWidget(dump_card)

        self._out = QPlainTextEdit()
        self._out.setObjectName("Console")
        self._out.setReadOnly(True)
        self._out.setPlaceholderText("La salida de dumpsys/bugreport aparecerá aquí…")
        root.addWidget(self._out, 1)

    # ------------------------------------------------------------------
    def _log(self, res: CommandResult) -> None:
        self._out.appendPlainText((res.text or "(sin salida)").rstrip())
        self._out.appendPlainText("")

    # ---- dumpsys ----
    def _run_dumpsys(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        service = self._service.currentText().strip()
        if not service:
            return
        self._out.appendPlainText(f"$ pax_adb shell dumpsys {service}")
        self.ctx.adb.shell(f"dumpsys {service}", self._log)

    def _save_output(self) -> None:
        text = self._out.toPlainText()
        if not text.strip():
            self.ctx.notify("No hay salida que guardar.", "warn")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar salida", "dumpsys.txt", "Texto (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.ctx.notify(f"Guardado: {path}", "ok")
        except OSError as exc:
            self.ctx.notify(f"No se pudo guardar: {exc}", "error")

    # ---- bug report ----
    def _bugreport(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar bug report", "bugreport.txt", "Texto (*.txt)"
        )
        if not path:
            return
        self._out.appendPlainText("$ pax_adb bugreport  (puede tardar…)")

        def after(res: CommandResult) -> None:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(res.stdout)
                self.ctx.notify(f"Bug report guardado: {path}", "ok")
            except OSError as exc:
                self.ctx.notify(f"No se pudo guardar: {exc}", "error")

        self.ctx.adb.run(["bugreport"], after)

    # ---- grabación de pantalla ----
    def _toggle_record(self) -> None:
        if self._rec_proc is not None:
            self._stop_record()
        else:
            self._start_record()

    def _start_record(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar grabación como…", "grabacion.mp4", "Vídeo MP4 (*.mp4)"
        )
        if not path:
            return
        self._rec_local = path
        self._rec_proc = self.ctx.adb.start(
            ["shell", f"screenrecord --time-limit 180 {_REMOTE_REC}"]
        )
        if self._rec_proc is None:
            self.ctx.notify("No se pudo iniciar la grabación.", "error")
            self._rec_local = ""
            return
        self._rec_proc.finished.connect(self._on_rec_finished)
        self._set_rec(running=True)
        self._out.appendPlainText("$ pax_adb shell screenrecord … (grabando)")

    def _set_rec(self, running: bool) -> None:
        from .. import icons

        self._rec_btn.setText("  Detener y guardar" if running else "  Grabar pantalla")
        ic = icons.icon("stop" if running else "play", self.ctx.palette.accent_text)
        if not ic.isNull():
            self._rec_btn.setIcon(ic)

    def _stop_record(self) -> None:
        # SIGINT en el terminal para que screenrecord finalice el MP4 limpiamente;
        # al salir, el stream termina y dispara _on_rec_finished (que descarga).
        self.ctx.adb.shell("kill -INT $(pidof screenrecord)", None)

    def _on_rec_finished(self, *_) -> None:
        self._rec_proc = None
        self._set_rec(running=False)
        if not self._rec_local:
            return
        local = self._rec_local
        self._rec_local = ""

        def after_pull(res: CommandResult) -> None:
            self.ctx.adb.shell(f"rm -f {_REMOTE_REC}", None)
            if res.ok:
                self.ctx.notify(f"Grabación guardada: {local}", "ok")
            else:
                self.ctx.notify("No se pudo descargar la grabación.", "error")

        # pequeña espera implícita: el fichero ya está finalizado al terminar el proceso
        self.ctx.adb.run(["pull", _REMOTE_REC, local], after_pull)

    def shutdown(self) -> None:
        if self._rec_proc is not None:
            self._rec_proc.kill()
