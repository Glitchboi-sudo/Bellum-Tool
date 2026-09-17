"""Comandos propietarios de PAX: systool y getappinfo.

- `systool <subcomando> [args] [fichero]` — ejecuta `shell:systool …` en el
  terminal. Los subcomandos con fichero (update/write/install/apn/puk) toman un
  fichero local como último argumento; el binario lo sube a /data/local/tmp,
  ejecuta y lo borra (todo transparente aquí).
- `getappinfo [<local>]` — descarga /data/resource/public/appinfo.bin.

Estos comandos actúan sobre el firmware del terminal. No hay presets de bypass;
el usuario compone el subcomando de systool que necesita.
"""

from __future__ import annotations

import shlex

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core.adb import CommandResult
from ..widgets import Card, Page, flow_row, hint, icon_button

# Subcomandos de systool que toman un fichero local como último argumento.
_FILE_BASED = {"update", "write", "install", "apn", "puk"}

# Presets frecuentes (rellenan el campo de argumentos; no se ejecutan solos).
_PRESETS = [
    ("Comando systool…", ""),
    ("getversion", "getversion"),
    ("puk write (necesita fichero)", "puk write"),
    ("apn (necesita fichero)", "apn"),
    ("update (necesita fichero)", "update"),
    ("install (necesita fichero)", "install"),
    ("remove persist-app <ruta>", "remove persist-app "),
]


def _hrow(*widgets: QWidget, stretch_index: int | None = None) -> QWidget:
    # Refluye a varias líneas cuando la ventana es estrecha (evita recortes por
    # la derecha); el campo señalado por stretch_index recibe un ancho mínimo.
    if stretch_index is not None and 0 <= stretch_index < len(widgets):
        widgets[stretch_index].setMinimumWidth(160)
    return flow_row(*widgets)


class SystoolPage(Page):
    title = "Sistema PAX"
    icon_concept = "tools"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)

        root.addWidget(
            hint(
                "Comandos propietarios de PAX que actúan sobre el firmware del terminal. "
                "Requieren un terminal con soporte de systool en su firmware."
            )
        )

        # --- systool ---
        systool_card = Card("systool (comando remoto)")
        self._preset = QComboBox()
        for label, value in _PRESETS:
            self._preset.addItem(label, value)
        self._preset.activated.connect(self._apply_preset)
        self._args = QLineEdit()
        self._args.setPlaceholderText("argumentos de systool (p. ej. puk write, getversion)")
        self._args.returnPressed.connect(self._run_systool)
        run_btn = icon_button("run", ctx.palette.accent_text, "Ejecutar", object_name="Primary")
        run_btn.clicked.connect(self._run_systool)
        systool_card.add(_hrow(self._preset, self._args, run_btn, stretch_index=1))

        self._file = QLineEdit()
        self._file.setPlaceholderText("fichero local (solo para update/write/install/apn/puk)…")
        browse = icon_button("open", ctx.palette.text, "Examinar…")
        browse.clicked.connect(self._browse_file)
        clear_file = icon_button("remove", ctx.palette.text, tooltip="Quitar fichero")
        clear_file.setFixedWidth(40)
        clear_file.clicked.connect(lambda: self._file.clear())
        systool_card.add(
            _hrow(QLabel("Fichero:"), self._file, browse, clear_file, stretch_index=1)
        )
        systool_card.add(
            hint(
                "Los subcomandos update/write/install/apn/puk necesitan un fichero: se sube "
                "a /data/local/tmp, se ejecuta systool contra él y se borra automáticamente."
            )
        )
        root.addWidget(systool_card)

        # --- PUK (puktools) ---
        puk_card = Card("PUK (paquetes puktools)")
        self._puk_sub = QComboBox()
        self._puk_sub.addItems(["list", "install", "uninstall"])
        self._puk_sub.currentTextChanged.connect(self._on_puk_sub)
        self._puk_arg = QLineEdit()
        puk_browse = icon_button("open", ctx.palette.text, "Examinar…")
        puk_browse.clicked.connect(self._browse_puk)
        self._puk_browse = puk_browse
        puk_run = icon_button("run", ctx.palette.accent_text, "Ejecutar", object_name="Primary")
        puk_run.clicked.connect(self._run_puk)
        puk_card.add(
            _hrow(
                QLabel("Acción:"), self._puk_sub, self._puk_arg, puk_browse, puk_run,
                stretch_index=2,
            )
        )
        puk_card.add(
            hint(
                "list: enumera los paquetes PUK · install: sube e instala un fichero .puk · "
                "uninstall: elimina por nombre de paquete."
            )
        )
        root.addWidget(puk_card)
        self._on_puk_sub("list")

        # --- Info del terminal (sysver + appinfo) ---
        info_card = Card("Info del terminal")
        sysver_btn = icon_button("tools", ctx.palette.text, "Ver versiones (sysver)")
        sysver_btn.clicked.connect(self._sysver)
        appinfo_btn = icon_button("download", ctx.palette.text, "Descargar appinfo.bin…")
        appinfo_btn.clicked.connect(self._get_appinfo)
        info_card.add(_hrow(sysver_btn, appinfo_btn))
        info_card.add(
            hint(
                "sysver: versiones de firmware (androidver/apbootver/spver). "
                "appinfo: descarga /data/resource/public/appinfo.bin."
            )
        )
        root.addWidget(info_card)

        # --- consola ---
        self._out = QPlainTextEdit()
        self._out.setObjectName("Console")
        self._out.setReadOnly(True)
        self._out.setPlaceholderText("La salida de systool/puk/sysver/appinfo aparecerá aquí…")
        root.addWidget(self._out, 1)

    # ------------------------------------------------------------------
    def _apply_preset(self, index: int) -> None:
        value = self._preset.itemData(index)
        if value:
            self._args.setText(value)
            self._args.setFocus()
        self._preset.setCurrentIndex(0)

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Fichero para systool", "", "Todos (*)")
        if path:
            self._file.setText(path)

    def _log(self, res: CommandResult) -> None:
        text = (res.text or "(sin salida)").rstrip()
        self._out.appendPlainText(text)
        if not res.ok:
            self._out.appendPlainText(f"[exit {res.returncode}]")
        self._out.appendPlainText("")

    def _run_systool(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        raw = self._args.text().strip()
        if not raw:
            self.ctx.notify("Escribe un subcomando de systool.", "warn")
            return
        try:
            tokens = shlex.split(raw)
        except ValueError as exc:
            self.ctx.notify(f"Argumentos inválidos: {exc}", "error")
            return

        file_path = self._file.text().strip()
        sub = tokens[0] if tokens else ""
        if sub in _FILE_BASED and not file_path:
            self.ctx.notify(
                f"El subcomando '{sub}' necesita un fichero (usa «Examinar…»).", "warn"
            )
            return

        args = ["systool"] + tokens
        if file_path:
            args.append(file_path)
        self._out.appendPlainText("$ pax_adb " + " ".join(args))
        self.ctx.adb.run(args, self._log, merge_stderr=True)

    def _get_appinfo(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar appinfo.bin", "appinfo.bin", "Binario (*.bin);;Todos (*)"
        )
        if not path:
            return
        self._out.appendPlainText(f"$ pax_adb getappinfo {path}")

        def after(res: CommandResult) -> None:
            self._log(res)
            self.ctx.notify(
                f"appinfo.bin descargado → {path}" if res.ok else "Fallo al descargar appinfo.bin",
                "ok" if res.ok else "error",
            )

        self.ctx.adb.run(["getappinfo", path], after)

    # ---- PUK (puktools) ----
    def _on_puk_sub(self, sub: str) -> None:
        """Ajusta el campo de argumento según el subcomando de puk."""
        placeholders = {
            "list": "(sin argumento)",
            "install": "fichero .puk (usa «Examinar…»)…",
            "uninstall": "nombre del paquete PUK…",
        }
        self._puk_arg.setPlaceholderText(placeholders.get(sub, ""))
        self._puk_arg.setEnabled(sub != "list")
        self._puk_browse.setEnabled(sub == "install")
        if sub == "list":
            self._puk_arg.clear()

    def _browse_puk(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Fichero PUK", "", "PUK (*.puk);;Todos (*)")
        if path:
            self._puk_arg.setText(path)

    def _run_puk(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        sub = self._puk_sub.currentText()
        arg = self._puk_arg.text().strip()
        if sub in ("install", "uninstall") and not arg:
            need = "un fichero .puk" if sub == "install" else "un nombre de paquete"
            self.ctx.notify(f"'{sub}' necesita {need}.", "warn")
            return
        args = ["puk", sub] + ([arg] if arg else [])
        self._out.appendPlainText("$ pax_adb " + " ".join(args))
        self.ctx.adb.run(args, self._log, merge_stderr=True)

    # ---- sysver ----
    def _sysver(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        self._out.appendPlainText("$ pax_adb sysver")
        self.ctx.adb.run(["sysver"], self._log, merge_stderr=True)
