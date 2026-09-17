"""Panel completo de `systool` (comandos propietarios de PAX) + PUK y appinfo.

`systool` actúa sobre el firmware del terminal. La página lo organiza por
categorías siguiendo la referencia de PAXDROID SYSTOOL v2.0:

  get       leer información (device-info, sysver, sysprop…)          — seguro
  set       configurar (time, timezone, language, customer, sysprop…) — persiste
  install   instalar apps (app / persist-app), sube el fichero local
  write     grabar blobs (puk, apn, whitelist, pubkey, licencia)
  update    actualizar imágenes (os, bootlogo, resource, bootanimation) — ⚠ brick
  remove    eliminar (datas, rki, package, persist-app, whitelist…)   — ⚠ destructivo
  startproc lanzar una actividad
  control   comandos internos por id (1..5)                           — ⚠ avanzado
  reboot    reiniciar la terminal                                     — ⚠

Los subcomandos con fichero (install/write/update, y puk/apn) toman un fichero
local como último argumento: el binario `pax_adb` lo sube a /data/local/tmp,
ejecuta systool contra él y lo borra. Todo eso es transparente aquí.
"""

from __future__ import annotations

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core.adb import CommandResult
from ..widgets import Card, Page, flow_row, hint, icon_button

# Categorías cuyo primer token hace que pax_adb suba el fichero (último arg).
_FILE_CATS = {"install", "write", "update"}

# control <id>: significado de cada id (referencia OsManagerService.doControl).
_CONTROL_INFO = {
    "1": "Refresca perfil de Customer y reinicia el Launcher (sin mensaje).",
    "2": "App Download finished — cierra colas de instalación automática.",
    "3": "Puk download completed — afecta el entorno seguro. Requiere reinicio.",
    "4": "System update completed — marca la OTA como terminada.",
    "5": "Finaliza provisión; intenta limpiar SIDs (credenciales lockscreen).",
}


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
                "Comandos propietarios de PAX (systool) que actúan sobre el firmware. "
                "Requieren un terminal con soporte de systool. Los marcados con ⚠ son "
                "destructivos o pueden inutilizar el terminal: pide confirmación."
            )
        )

        root.addWidget(self._build_get_card(ctx))
        root.addWidget(self._build_set_card(ctx))
        root.addWidget(self._build_files_card(ctx))
        root.addWidget(self._build_remove_card(ctx))
        root.addWidget(self._build_advanced_card(ctx))
        root.addWidget(self._build_puk_card(ctx))
        root.addWidget(self._build_info_card(ctx))

        # --- consola ---
        self._out = QPlainTextEdit()
        self._out.setObjectName("Console")
        self._out.setReadOnly(True)
        self._out.setPlaceholderText("La salida de systool/puk/sysver/appinfo aparecerá aquí…")
        root.addWidget(self._out, 1)

    # ==================================================================
    # Construcción de tarjetas
    # ==================================================================
    def _build_get_card(self, ctx) -> Card:
        card = Card("Leer (get) — seguro")
        row_btns = []
        for label, sub in (
            ("device-info", ["get", "device-info"]),
            ("sysver", ["get", "sysver"]),
            ("isNewScannerActive", ["get", "isNewScannerActive"]),
        ):
            b = icon_button("tools", ctx.palette.text, label)
            b.clicked.connect(lambda _=False, a=sub: self._exec(a))
            row_btns.append(b)
        card.add(flow_row(*row_btns))

        self._getprop = QLineEdit()
        self._getprop.setPlaceholderText("propiedad (p. ej. ro.serialno, ro.build.version.release)…")
        getprop_btn = icon_button("run", ctx.palette.accent_text, "Leer", object_name="Primary")

        def read_prop() -> None:
            key = self._getprop.text().strip()
            if not key:
                self.ctx.notify("Escribe una propiedad.", "warn")
                return
            self._exec(["get", "sysprop", key])

        getprop_btn.clicked.connect(read_prop)
        self._getprop.returnPressed.connect(read_prop)
        card.add(_hrow(QLabel("sysprop:"), self._getprop, getprop_btn, stretch_index=1))
        return card

    def _build_set_card(self, ctx) -> Card:
        card = Card("Configurar (set) — persiste tras reinicio")

        # time (con botón "Ahora")
        self._set_time = QLineEdit()
        self._set_time.setPlaceholderText("YYYY/MM/DD-HH:MM:SS")
        now_btn = icon_button("refresh", ctx.palette.text, "Ahora")
        now_btn.clicked.connect(
            lambda: self._set_time.setText(
                QDateTime.currentDateTime().toString("yyyy/MM/dd-HH:mm:ss")
            )
        )
        time_run = self._mk_run(lambda: ["set", "time", self._set_time.text().strip()],
                                need=self._set_time)
        card.add(_hrow(QLabel("time:"), self._set_time, now_btn, time_run, stretch_index=1))

        self._set_tz = self._simple_set_row(card, "timezone:", "America/Mazatlan", "timezone")
        self._set_lang = self._simple_set_row(card, "language:", "es-MX / en-US", "language")
        self._set_customer = self._simple_set_row(card, "customer:", "0xff", "customer")

        # sysprop set (key + value) — potencialmente peligroso
        self._sp_key = QLineEdit()
        self._sp_key.setPlaceholderText("clave")
        self._sp_val = QLineEdit()
        self._sp_val.setPlaceholderText("valor")
        sp_btn = icon_button("run", ctx.palette.accent_text, "Escribir", object_name="Primary")

        def set_prop() -> None:
            k = self._sp_key.text().strip()
            v = self._sp_val.text().strip()
            if not k:
                self.ctx.notify("Escribe la clave de la propiedad.", "warn")
                return
            self._exec(
                ["set", "sysprop", k, v],
                confirm=(
                    "set sysprop",
                    f"Vas a escribir la propiedad del sistema:\n\n  {k} = {v}\n\n"
                    "Cambiar propiedades del sistema puede alterar el comportamiento "
                    "del terminal. ¿Continuar?",
                ),
            )

        sp_btn.clicked.connect(set_prop)
        card.add(_hrow(QLabel("sysprop:"), self._sp_key, self._sp_val, sp_btn, stretch_index=1))

        # mtp on/off <token>
        self._mtp_mode = QComboBox()
        self._mtp_mode.addItems(["on", "off"])
        self._mtp_token = QLineEdit()
        self._mtp_token.setPlaceholderText("token")
        mtp_btn = self._mk_run(
            lambda: ["set", "mtp", self._mtp_mode.currentText(), self._mtp_token.text().strip()],
            need=self._mtp_token,
        )
        card.add(_hrow(QLabel("mtp:"), self._mtp_mode, self._mtp_token, mtp_btn, stretch_index=2))
        return card

    def _build_files_card(self, ctx) -> Card:
        card = Card("Ficheros: install / write / update")

        # install <app|persist-app> <apk>
        self._inst_sub = QComboBox()
        self._inst_sub.addItems(["app", "persist-app"])
        self._inst_file = QLineEdit()
        self._inst_file.setPlaceholderText("APK local…")
        inst_browse = icon_button("open", ctx.palette.text, "Examinar…")
        inst_browse.clicked.connect(lambda: self._pick(self._inst_file, "APK (*.apk);;Todos (*)"))
        inst_run = self._mk_run(
            lambda: ["install", self._inst_sub.currentText(), self._inst_file.text().strip()],
            need=self._inst_file,
        )
        card.add(_hrow(QLabel("install:"), self._inst_sub, self._inst_file, inst_browse, inst_run,
                       stretch_index=2))

        # write <sub> <file>
        self._wr_sub = QComboBox()
        self._wr_sub.addItems(
            ["puk", "apn", "uninstall_whitelist", "customer-pubkey", "scan-license"]
        )
        self._wr_file = QLineEdit()
        self._wr_file.setPlaceholderText("fichero local…")
        wr_browse = icon_button("open", ctx.palette.text, "Examinar…")
        wr_browse.clicked.connect(lambda: self._pick(self._wr_file, "Todos (*)"))
        wr_run = self._mk_run(
            lambda: ["write", self._wr_sub.currentText(), self._wr_file.text().strip()],
            need=self._wr_file,
        )
        card.add(_hrow(QLabel("write:"), self._wr_sub, self._wr_file, wr_browse, wr_run,
                       stretch_index=2))

        # update <sub> <file>  — ⚠ brick
        self._up_sub = QComboBox()
        self._up_sub.addItems(["os", "bootlogo", "resource", "bootanimation"])
        self._up_file = QLineEdit()
        self._up_file.setPlaceholderText("imagen local…")
        up_browse = icon_button("open", ctx.palette.text, "Examinar…")
        up_browse.clicked.connect(lambda: self._pick(self._up_file, "Todos (*)"))
        up_run = icon_button("run", ctx.palette.accent_text, "Actualizar ⚠", object_name="Primary")

        def do_update() -> None:
            f = self._up_file.text().strip()
            sub = self._up_sub.currentText()
            if not f:
                self.ctx.notify("Selecciona la imagen a aplicar.", "warn")
                return
            self._exec(
                ["update", sub, f],
                confirm=(
                    "update — riesgo de brick",
                    f"Vas a aplicar update {sub}:\n\n  {f}\n\n"
                    "⚠ Una imagen incorrecta o mal empaquetada puede INUTILIZAR (brick) "
                    "el terminal. Usa solo imágenes oficiales y con respaldo. ¿Continuar?",
                ),
            )

        up_run.clicked.connect(do_update)
        card.add(_hrow(QLabel("update:"), self._up_sub, self._up_file, up_browse, up_run,
                       stretch_index=2))
        card.add(
            hint(
                "install/write/update suben el fichero local al terminal y ejecutan systool "
                "contra él. update puede brickear: usa imágenes oficiales."
            )
        )
        return card

    def _build_remove_card(self, ctx) -> Card:
        card = Card("Eliminar (remove) — ⚠ destructivo")

        # Botones sin argumento (con confirmación)
        no_arg = [
            ("remove datas", ["remove", "datas"], "Borra datos (limpieza)."),
            ("remove rki", ["remove", "rki"], "Elimina RKI (Remote Key Injection)."),
            ("remove unsigned-apps", ["remove", "unsigned-apps"], "Limpia apps no firmadas."),
            ("remove uninstall_whitelist", ["remove", "uninstall_whitelist"], "Quita la whitelist."),
        ]
        btns = []
        for label, args, why in no_arg:
            b = icon_button("remove", ctx.palette.text, label)
            b.setObjectName("Danger")
            b.clicked.connect(
                lambda _=False, a=args, lbl=label, w=why: self._exec(
                    a, confirm=(lbl, f"{w}\n\nEsta acción es destructiva. ¿Continuar?")
                )
            )
            btns.append(b)
        card.add(flow_row(*btns))

        # remove package <name>
        self._rm_pkg = QLineEdit()
        self._rm_pkg.setPlaceholderText("nombre del paquete (com.ejemplo.app)…")
        rm_pkg_btn = icon_button("remove", ctx.palette.text, "Desinstalar")
        rm_pkg_btn.setObjectName("Danger")
        rm_pkg_btn.clicked.connect(
            lambda: self._exec_arg(
                self._rm_pkg, lambda v: ["remove", "package", v],
                confirm_title="remove package",
                confirm_body=lambda v: f"Vas a desinstalar el paquete:\n\n  {v}\n\n¿Continuar?",
            )
        )
        card.add(_hrow(QLabel("package:"), self._rm_pkg, rm_pkg_btn, stretch_index=1))

        # remove persist-app <path>
        self._rm_persist = QLineEdit()
        self._rm_persist.setPlaceholderText("ruta de la app persistente (/data/resource/app/…)…")
        rm_persist_btn = icon_button("remove", ctx.palette.text, "Eliminar")
        rm_persist_btn.setObjectName("Danger")
        rm_persist_btn.clicked.connect(
            lambda: self._exec_arg(
                self._rm_persist, lambda v: ["remove", "persist-app", v],
                confirm_title="remove persist-app",
                confirm_body=lambda v: f"Vas a eliminar la app persistente:\n\n  {v}\n\n¿Continuar?",
            )
        )
        card.add(_hrow(QLabel("persist-app:"), self._rm_persist, rm_persist_btn, stretch_index=1))
        return card

    def _build_advanced_card(self, ctx) -> Card:
        card = Card("Avanzado: startproc / control / reboot — ⚠")

        # startproc Activity <pkg> <activity>
        self._sp_pkg = QLineEdit()
        self._sp_pkg.setPlaceholderText("packageName")
        self._sp_act = QLineEdit()
        self._sp_act.setPlaceholderText("ActivityName")
        sp_run = icon_button("play", ctx.palette.text, "Lanzar")

        def start_proc() -> None:
            pkg = self._sp_pkg.text().strip()
            act = self._sp_act.text().strip()
            if not pkg or not act:
                self.ctx.notify("Indica packageName y ActivityName.", "warn")
                return
            self._exec(["startproc", "Activity", pkg, act])

        sp_run.clicked.connect(start_proc)
        card.add(_hrow(QLabel("startproc:"), self._sp_pkg, self._sp_act, sp_run, stretch_index=1))

        # control <id>
        self._ctrl_id = QComboBox()
        self._ctrl_id.addItems(list(_CONTROL_INFO.keys()))
        self._ctrl_id.currentTextChanged.connect(self._on_ctrl_id)
        ctrl_run = icon_button("run", ctx.palette.text, "Ejecutar control ⚠")
        ctrl_run.clicked.connect(self._run_control)
        card.add(_hrow(QLabel("control id:"), self._ctrl_id, ctrl_run))
        self._ctrl_hint = hint("")
        card.add(self._ctrl_hint)
        self._on_ctrl_id(self._ctrl_id.currentText())

        # reboot
        reboot_btn = icon_button("reboot", ctx.palette.text, "systool reboot ⚠")
        reboot_btn.setObjectName("Danger")
        reboot_btn.clicked.connect(
            lambda: self._exec(
                ["reboot"],
                confirm=("systool reboot", "Se reiniciará la terminal ahora. ¿Continuar?"),
            )
        )
        card.add(flow_row(reboot_btn))
        return card

    def _build_puk_card(self, ctx) -> Card:
        card = Card("PUK (paquetes puktools)")
        self._puk_sub = QComboBox()
        self._puk_sub.addItems(["list", "install", "uninstall"])
        self._puk_sub.currentTextChanged.connect(self._on_puk_sub)
        self._puk_arg = QLineEdit()
        self._puk_browse = icon_button("open", ctx.palette.text, "Examinar…")
        self._puk_browse.clicked.connect(self._browse_puk)
        puk_run = icon_button("run", ctx.palette.accent_text, "Ejecutar", object_name="Primary")
        puk_run.clicked.connect(self._run_puk)
        card.add(_hrow(QLabel("Acción:"), self._puk_sub, self._puk_arg, self._puk_browse, puk_run,
                       stretch_index=2))
        card.add(
            hint(
                "list: enumera los paquetes PUK · install: sube e instala un .puk · "
                "uninstall: elimina por nombre de paquete."
            )
        )
        self._on_puk_sub("list")
        return card

    def _build_info_card(self, ctx) -> Card:
        card = Card("Info del terminal")
        sysver_btn = icon_button("tools", ctx.palette.text, "Ver versiones (pax_adb sysver)")
        sysver_btn.clicked.connect(self._sysver)
        appinfo_btn = icon_button("download", ctx.palette.text, "Descargar appinfo.bin…")
        appinfo_btn.clicked.connect(self._get_appinfo)
        card.add(flow_row(sysver_btn, appinfo_btn))
        card.add(
            hint(
                "sysver: versiones de firmware (androidver/apbootver/spver). "
                "appinfo: descarga /data/resource/public/appinfo.bin."
            )
        )
        return card

    # ==================================================================
    # Helpers de construcción/ejecución
    # ==================================================================
    def _simple_set_row(self, card: Card, label: str, placeholder: str, key: str) -> QLineEdit:
        """Fila 'set <key> <valor>' con un solo campo."""
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        btn = self._mk_run(lambda: ["set", key, field.text().strip()], need=field)
        card.add(_hrow(QLabel(label), field, btn, stretch_index=1))
        return field

    def _mk_run(self, build_args, need: QLineEdit | None = None):
        """Crea un botón 'Ejecutar' que valida `need` y ejecuta build_args()."""
        btn = icon_button("run", self.ctx.palette.accent_text, "Ejecutar", object_name="Primary")

        def run() -> None:
            if need is not None and not need.text().strip():
                self.ctx.notify("Falta un valor.", "warn")
                return
            self._exec(build_args())

        btn.clicked.connect(run)
        if need is not None:
            need.returnPressed.connect(run)
        return btn

    def _exec_arg(self, field: QLineEdit, build_args, confirm_title=None, confirm_body=None) -> None:
        v = field.text().strip()
        if not v:
            self.ctx.notify("Falta un valor.", "warn")
            return
        confirm = None
        if confirm_title and confirm_body:
            confirm = (confirm_title, confirm_body(v))
        self._exec(build_args(v), confirm=confirm)

    def _exec(self, sub_args: list[str], confirm: tuple[str, str] | None = None) -> None:
        """Ejecuta `systool <sub_args…>`. Si `confirm` está, pide confirmación."""
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        # Ningún argumento vacío (p. ej. token/valor faltante en un 'set').
        if any(a == "" for a in sub_args):
            self.ctx.notify("Faltan argumentos para el comando.", "warn")
            return
        if confirm is not None and not self._confirm(*confirm):
            return
        args = ["systool"] + sub_args
        self._out.appendPlainText("$ pax_adb " + " ".join(args))
        self.ctx.adb.run(args, self._log, merge_stderr=True)

    def _confirm(self, title: str, body: str) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _pick(self, field: QLineEdit, file_filter: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar fichero", "", file_filter)
        if path:
            field.setText(path)

    def _log(self, res: CommandResult) -> None:
        text = (res.text or "(sin salida)").rstrip()
        self._out.appendPlainText(text)
        if not res.ok:
            self._out.appendPlainText(f"[exit {res.returncode}]")
        self._out.appendPlainText("")

    # ---- control ----
    def _on_ctrl_id(self, cid: str) -> None:
        self._ctrl_hint.setText(f"control {cid}: {_CONTROL_INFO.get(cid, '')}")

    def _run_control(self) -> None:
        cid = self._ctrl_id.currentText()
        self._exec(
            ["control", cid],
            confirm=(
                f"control {cid}",
                f"{_CONTROL_INFO.get(cid, '')}\n\n"
                "Son comandos internos del OsManager y pueden afectar el entorno "
                "seguro o la provisión. ¿Continuar?",
            ),
        )

    # ---- PUK (puktools) ----
    def _on_puk_sub(self, sub: str) -> None:
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

    # ---- sysver / appinfo ----
    def _sysver(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo seleccionado.", "warn")
            return
        self._out.appendPlainText("$ pax_adb sysver")
        self.ctx.adb.run(["sysver"], self._log, merge_stderr=True)

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
