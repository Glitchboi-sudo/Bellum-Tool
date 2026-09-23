"""Personalización de arranque: generar splash.img y empujar bootanimation.

Dos utilidades cosméticas, sin exploit ni bypass:

* **BootLogo Maker** — reimplementación del `mkblsp` original con Qt puro
  (`QImage` + `gzip` de la stdlib, sin Pillow): toma una imagen del usuario, la
  redimensiona a 720×1280, la guarda como BMP, la comprime con gzip y produce un
  `splash.img` (≤1024 KB) listo para flashear. Es solo generación de fichero
  local; no toca el terminal.
* **Bootanimation** — empuja un `bootanimation.zip` que aporta el usuario a la
  ruta de medios del cliente (`/cache/customer/media/`, editable). Es una copia
  de fichero (equivalente al `btchge` original), no escribe particiones.
"""

from __future__ import annotations

import gzip
import os
import posixpath

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from ...core import apk
from ...core.adb import CommandResult
from ..widgets import Card, DangerCard, Page, flow_row, hint, icon_button

# Parámetros del splash del PAX A910/A920, fieles al mkblsp original.
_SPLASH_W, _SPLASH_H = 720, 1280
_SPLASH_MAX_KB = 1024
# Ruta de medios de personalización del cliente (destino del bootanimation.zip).
_BOOTANIM_DIR = "/cache/customer/media/"
# Nombre por defecto del helper on-device (PaySh); editable en la UI.
_PAYSH_PKG = "com.pax.paysh"
# PayDroid Tool: agente on-device del tool oficial de PAX. Identidad observada en
# el logcat de un A910 (paquete, ruta del APK y actividad principal). Se instala el
# APK que aporte el usuario; la extracción usa la ruta conocida (pull directo, sin
# depender del shell) para redeplegarlo en otro terminal.
_PAYDROID_PKG = "com.pax.tsclear"
_PAYDROID_APK = "/cache/customer/priv-app/paydroidtool/base.apk"
_PAYDROID_ACTIVITY = "com.paxsz.paydroidtool.Activities.MainActivity"
# Partición cruda del logo de arranque (A910/A920 Unisoc); editable en la UI.
_LOGO_PART = "/dev/block/platform/sdio_emmc/by-name/logo"


class PersonalizePage(Page):
    title = "Personalización"
    icon_concept = "camera"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self._splash_out: str = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)

        root.addWidget(
            hint(
                "Personalización cosmética del arranque. Es un cambio de imagen/animación "
                "sobre equipo de tu propiedad — no habilita ADB ni modifica la seguridad del "
                "terminal (eso presupone que ya tienes acceso al shell)."
            )
        )

        # --- BootLogo Maker (generación local de splash.img) ---------------
        maker = Card("BootLogo Maker · genera splash.img")
        maker.add(
            hint(
                f"Convierte una imagen ({_SPLASH_W}×{_SPLASH_H}, BMP comprimido con gzip) en un "
                f"splash.img listo para flashear. Límite {_SPLASH_MAX_KB} KB: si se pasa, usa una "
                "imagen más ligera. Formatos: PNG, JPG, BMP, TIFF."
            )
        )
        self._src = QLineEdit()
        self._src.setPlaceholderText("Imagen de origen…")
        pick = icon_button("open", ctx.palette.text, "Elegir imagen…")
        pick.clicked.connect(self._pick_source)
        make_btn = icon_button(
            "save", ctx.palette.accent_text, "Generar splash.img", object_name="Primary"
        )
        make_btn.clicked.connect(self._make_splash)
        maker.add(flow_row(QLabel("Origen:"), self._src, pick, make_btn))
        root.addWidget(maker)

        # --- Bootanimation (push del zip al terminal) ----------------------
        anim = Card("Bootanimation · empuja al terminal")
        anim.add(
            hint(
                "Copia un bootanimation.zip a la carpeta de medios del cliente. Requiere un "
                "dispositivo adb seleccionado con shell disponible."
            )
        )
        self._anim = QLineEdit()
        self._anim.setPlaceholderText("bootanimation.zip…")
        anim_pick = icon_button("open", ctx.palette.text, "Elegir zip…")
        anim_pick.clicked.connect(self._pick_anim)
        self._anim_dst = QLineEdit(_BOOTANIM_DIR)
        push_btn = icon_button(
            "run", ctx.palette.accent_text, "Empujar al terminal", object_name="Primary"
        )
        push_btn.clicked.connect(self._push_anim)
        anim.add(flow_row(QLabel("Archivo:"), self._anim, anim_pick))
        anim.add(flow_row(QLabel("Destino:"), self._anim_dst, push_btn))
        root.addWidget(anim)

        # --- Herramienta on-device (PaySh) ---------------------------------
        # Reimplementa el «instalar PayDroid Tool en el terminal» del tool
        # original. No se distribuye ningún APK propietario: se instala el que
        # aporte el usuario, o se extrae de un terminal que ya lo tenga para
        # reinstalarlo en otro (usa el mismo tránsito que la extracción de APKs).
        helper = Card("Herramienta on-device (PaySh) · instalar / extraer")
        helper.add(
            hint(
                "Instala en el terminal el APK del helper (equivalente a «instalar PayDroid Tool» "
                "del tool original) o extrae el que ya tenga un terminal para reinstalarlo en otro. "
                "Aporta tú el APK: no se incluye software propietario."
            )
        )
        self._helper_apk = QLineEdit()
        self._helper_apk.setPlaceholderText("APK del helper…")
        helper_pick = icon_button("open", ctx.palette.text, "Elegir APK…")
        helper_pick.clicked.connect(self._pick_helper)
        install_btn = icon_button(
            "run", ctx.palette.accent_text, "Instalar en el terminal", object_name="Primary"
        )
        install_btn.clicked.connect(self._install_helper)
        helper.add(flow_row(QLabel("APK:"), self._helper_apk, helper_pick, install_btn))

        self._paysh_pkg = QLineEdit(_PAYSH_PKG)
        extract_btn = icon_button("save", ctx.palette.text, "Extraer del terminal…")
        extract_btn.clicked.connect(self._extract_helper)
        helper.add(flow_row(QLabel("Paquete:"), self._paysh_pkg, extract_btn))
        root.addWidget(helper)

        # --- PayDroid Tool (acción rápida) --------------------------------
        # Instala/extrae/lanza el agente on-device del PayDroid Tool oficial con
        # su identidad ya conocida (no hay que teclear rutas ni paquetes). No se
        # incluye el APK: para instalar, aporta el que extraigas de un terminal.
        pdt = Card("PayDroid Tool · instalar · extraer · abrir")
        pdt.add(
            hint(
                f"Agente on-device del tool oficial ({_PAYDROID_PKG}). Instalar y abrir van por "
                "systool (canal propietario, sin depender del shell); extraer usa la ruta "
                f"conocida ({_PAYDROID_APK}) por «sync». «Instalar» aquí necesita un APK suelto: "
                "el oficial viene CIFRADO dentro del customer-res (.ac) — para ese usa la tarjeta "
                "de abajo."
            )
        )
        self._pdt_apk = QLineEdit()
        self._pdt_apk.setPlaceholderText("APK de PayDroid Tool…")
        pdt_pick = icon_button("open", ctx.palette.text, "Elegir APK…")
        pdt_pick.clicked.connect(self._pick_paydroid)
        pdt_install = icon_button(
            "run", ctx.palette.accent_text, "Instalar en el terminal", object_name="Primary"
        )
        pdt_install.clicked.connect(self._install_paydroid)
        pdt.add(flow_row(QLabel("APK:"), self._pdt_apk, pdt_pick, pdt_install))
        pdt_extract = icon_button("save", ctx.palette.text, "Extraer del terminal…")
        pdt_extract.clicked.connect(self._extract_paydroid)
        pdt_launch = icon_button("play", ctx.palette.text, "Abrir en el terminal")
        pdt_launch.clicked.connect(self._launch_paydroid)
        pdt.add(flow_row(pdt_extract, pdt_launch))
        root.addWidget(pdt)

        # --- PayDroid Tool: aplicar customer-res (.ac) — vía real del tool ----
        # El tool oficial no hace `install` de un APK suelto: aplica un paquete
        # de recurso de cliente CIFRADO (.ac) que el daemon de PAX descifra y
        # desempaqueta en el terminal (instalar = *_paydroidtool.ac; desinstalar
        # = *_empty.ac, que reemplaza el recurso por uno vacío). Bellum trata el
        # .ac como blob opaco: NO lo descifra ni lo abre. Es categoría `update`
        # → riesgo de brick, por eso va en DangerCard con confirmación.
        pdt_res = DangerCard("PayDroid Tool · aplicar customer-res (.ac) — ⚠ experimental")
        pdt_res.add(
            hint(
                "Vía fiel del tool oficial: sube y aplica el paquete de recurso de cliente "
                "cifrado por «systool update resource». Instalar = …_customer_res_paydroidtool.zip.ac; "
                "desinstalar = …_customer_res_empty.zip.ac. El terminal puede reiniciarse al "
                "terminar. ⚠ Es categoría update: un fichero incorrecto puede inutilizar recursos "
                "del terminal. Bellum no descifra el .ac; solo lo entrega al daemon."
            )
        )
        self._pdt_res = QLineEdit()
        self._pdt_res.setPlaceholderText("customer_res *.ac (paydroidtool = instalar · empty = desinstalar)…")
        pdt_res_pick = icon_button("open", ctx.palette.text, "Elegir .ac…")
        pdt_res_pick.clicked.connect(self._pick_pdt_res)
        pdt_res_apply = icon_button("flash", ctx.palette.text, "Aplicar customer-res ⚠")
        pdt_res_apply.setObjectName("Danger")
        pdt_res_apply.clicked.connect(self._apply_pdt_res)
        pdt_res.add(flow_row(QLabel("Recurso:"), self._pdt_res, pdt_res_pick, pdt_res_apply))
        root.addWidget(pdt_res)

        # --- Flashear splash.img al logo (equivalente a `spchge`) ----------
        flash = DangerCard("Flashear splash.img al logo — ⚠ escribe partición")
        flash.add(
            hint(
                "Escribe una splash.img sobre la partición cruda del logo (push → dd → rm). "
                "Completa el flujo del BootLogo Maker. Una imagen de tamaño/formato incorrecto "
                "puede dejar el logo inservible; requiere shell con acceso a /dev/block. "
                "Haz antes un volcado de la partición «logo» por si necesitas revertir."
            )
        )
        self._flash_img = QLineEdit()
        self._flash_img.setPlaceholderText("splash.img (por defecto, el recién generado)…")
        flash_pick = icon_button("open", ctx.palette.text, "Elegir .img…")
        flash_pick.clicked.connect(self._pick_flash_img)
        self._logo_part = QLineEdit(_LOGO_PART)
        flash_btn = icon_button("flash", ctx.palette.text, "Flashear al logo ⚠")
        flash_btn.setObjectName("Danger")
        flash_btn.clicked.connect(self._flash_logo)
        flash.add(flow_row(QLabel("Imagen:"), self._flash_img, flash_pick))
        flash.add(flow_row(QLabel("Partición:"), self._logo_part, flash_btn))
        root.addWidget(flash)

        self._out = QPlainTextEdit()
        self._out.setObjectName("Console")
        self._out.setReadOnly(True)
        self._out.setPlaceholderText("La salida aparecerá aquí…")
        root.addWidget(self._out, 1)

    # ------------------------------------------------------------------
    def _log(self, res: CommandResult) -> None:
        self._out.appendPlainText((res.text or "(sin salida)").rstrip())
        self._out.appendPlainText("")

    # ---- BootLogo Maker ----------------------------------------------
    def _pick_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Imagen de origen", "", "Imágenes (*.png *.jpg *.jpeg *.bmp *.tiff);;Todos (*)"
        )
        if path:
            self._src.setText(path)

    def _make_splash(self) -> None:
        src = self._src.text().strip()
        if not src:
            self.ctx.notify("Elige una imagen de origen.", "warn")
            return
        img = QImage(src)
        if img.isNull():
            self.ctx.notify("No se pudo leer la imagen (formato no soportado).", "error")
            return

        out, _ = QFileDialog.getSaveFileName(
            self, "Guardar splash.img", self._splash_out or "splash.img", "Imagen (*.img)"
        )
        if not out:
            return

        # Redimensiona (estirado exacto a la resolución del panel, como mkblsp)
        # y serializa a BMP en memoria; luego comprime con gzip.
        scaled = img.scaled(
            _SPLASH_W,
            _SPLASH_H,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Fuerza BMP de 24 bits sin canal alfa (RGB888), como el splash.img
        # original de mkblsp. Sin esto, una imagen con alfa se guardaría como BMP
        # de 32 bits BGRA y el bootloader mostraría el logo corrupto o lo rechazaría.
        scaled = scaled.convertToFormat(QImage.Format.Format_RGB888)
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.ReadWrite)
        if not scaled.save(buf, "BMP"):
            self.ctx.notify("No se pudo codificar el BMP.", "error")
            return
        compressed = gzip.compress(bytes(buf.data()))

        size_kb = len(compressed) / 1024
        if size_kb > _SPLASH_MAX_KB:
            self.ctx.notify(
                f"splash.img supera {_SPLASH_MAX_KB} KB ({int(size_kb)} KB). "
                "Prueba con una imagen más ligera.",
                "error",
            )
            return
        try:
            with open(out, "wb") as fh:
                fh.write(compressed)
        except OSError as exc:
            self.ctx.notify(f"No se pudo guardar: {exc}", "error")
            return

        self._splash_out = out
        self._out.appendPlainText(
            f"✓ Generado {out} ({int(size_kb)} KB, {_SPLASH_W}×{_SPLASH_H} BMP+gzip)\n"
        )
        self.ctx.notify("splash.img listo para flashear.", "ok")

    # ---- Bootanimation -----------------------------------------------
    def _pick_anim(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "bootanimation.zip", "", "Archivos ZIP (*.zip);;Todos (*)"
        )
        if path:
            self._anim.setText(path)

    def _push_anim(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        src = self._anim.text().strip()
        dst = self._anim_dst.text().strip() or _BOOTANIM_DIR
        if not src:
            self.ctx.notify("Elige un bootanimation.zip.", "warn")
            return
        if not os.path.isfile(src):
            self.ctx.notify(f"No existe el archivo: {src}", "error")
            return
        self._out.appendPlainText(f"$ adb push {src} {dst}")
        self.ctx.adb.run(["push", src, dst], self._log)

    # ---- Herramienta on-device (PaySh) -------------------------------
    def _pick_helper(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "APK del helper", "", "Android Package (*.apk);;Todos (*)"
        )
        if path:
            self._helper_apk.setText(path)

    def _install_helper(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        path = self._helper_apk.text().strip()
        if not path:
            self.ctx.notify("Elige el APK del helper.", "warn")
            return
        if not os.path.isfile(path):
            self.ctx.notify(f"No existe el archivo: {path}", "error")
            return
        self._out.appendPlainText(f"$ adb install -r -g {path}")

        def after(res: CommandResult) -> None:
            self._log(res)
            ok = res.ok and "Success" in (res.text or "")
            self.ctx.notify(
                "Helper instalado en el terminal." if ok else "No se pudo instalar el helper.",
                "ok" if ok else "error",
            )

        # -r reinstala conservando datos; -g concede permisos de runtime.
        self.ctx.adb.run(["install", "-r", "-g", path], after, merge_stderr=True)

    def _extract_helper(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        pkg = self._paysh_pkg.text().strip()
        if not pkg:
            self.ctx.notify("Indica el nombre del paquete a extraer.", "warn")
            return
        dest = QFileDialog.getExistingDirectory(self, "Guardar APK en…")
        if not dest:
            return
        self._out.appendPlainText(f"$ adb shell pm path {pkg} → pull")

        def on_paths(paths: dict[str, list[str]]) -> None:
            remotes = paths.get(pkg, [])
            if not remotes:
                self.ctx.notify(f"El terminal no tiene instalado {pkg}.", "warn")
                return
            jobs = []
            for remote in remotes:
                base = posixpath.basename(remote)
                local = os.path.join(dest, f"{pkg}.apk" if len(remotes) == 1 else f"{pkg}-{base}")
                jobs.append((remote, local))
            total = len(jobs)
            apk.stage_pull(
                self.ctx.adb,
                jobs,
                lambda fail: self.ctx.notify(
                    f"Extraer {pkg}: {total - fail}/{total} OK → {dest}", "ok" if not fail else "warn"
                ),
            )

        apk.resolve_paths(self.ctx.adb, [pkg], on_paths)

    # ---- PayDroid Tool (acción rápida) -------------------------------
    def _pick_paydroid(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "APK de PayDroid Tool", "", "Android Package (*.apk);;Todos (*)"
        )
        if path:
            self._pdt_apk.setText(path)

    def _install_paydroid(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        path = self._pdt_apk.text().strip()
        if not path:
            self.ctx.notify("Elige el APK de PayDroid Tool.", "warn")
            return
        if not os.path.isfile(path):
            self.ctx.notify(f"No existe el archivo: {path}", "error")
            return
        # Vía systool (no el shell): pax_adb sube el APK al terminal y el daemon
        # de PAX lo instala. Es la ruta nativa en terminales bloqueados, donde el
        # shell (y a veces `adb install`) no responde.
        self._out.appendPlainText(f"$ pax_adb systool install app {path}")

        def after(res: CommandResult) -> None:
            self._log(res)
            txt = res.text or ""
            ok = res.ok and "SYSTOOL:-" not in txt and "Failure" not in txt
            self.ctx.notify(
                "PayDroid Tool instalado en el terminal." if ok
                else "No se pudo instalar PayDroid Tool.",
                "ok" if ok else "error",
            )

        self.ctx.adb.run(["systool", "install", "app", path], after, merge_stderr=True)

    def _extract_paydroid(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        dest = QFileDialog.getExistingDirectory(self, "Guardar PayDroid Tool.apk en…")
        if not dest:
            return
        # Ruta conocida → pull directo (stage_pull la intenta primero; funciona
        # aunque el shell esté bloqueado, si el servicio sync puede leer /cache).
        local = os.path.join(dest, "paydroidtool.apk")
        self._out.appendPlainText(f"$ adb pull {_PAYDROID_APK} {local}")
        apk.stage_pull(
            self.ctx.adb,
            [(_PAYDROID_APK, local)],
            lambda fail: self.ctx.notify(
                f"PayDroid Tool extraído → {local}" if not fail
                else "No se pudo extraer PayDroid Tool (¿sync sin acceso a /cache?).",
                "ok" if not fail else "warn",
            ),
        )

    def _launch_paydroid(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        # `systool startproc Activity <pkg> <activity>` lanza la app por el canal
        # propietario de PAX, sin pasar por el shell (inestable en estos terminales).
        args = ["systool", "startproc", "Activity", _PAYDROID_PKG, _PAYDROID_ACTIVITY]
        self._out.appendPlainText("$ pax_adb " + " ".join(args))

        def after(res: CommandResult) -> None:
            self._log(res)
            ok = res.ok and "SYSTOOL:-" not in (res.text or "")
            self.ctx.notify(
                "Abriendo PayDroid Tool en el terminal." if ok
                else "No se pudo abrir PayDroid Tool.",
                "ok" if ok else "warn",
            )

        self.ctx.adb.run(args, after, merge_stderr=True)

    def _pick_pdt_res(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Paquete customer-res (.ac)", "",
            "Recurso PAX (*.ac *.zip);;Todos (*)",
        )
        if path:
            self._pdt_res.setText(path)

    def _apply_pdt_res(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        path = self._pdt_res.text().strip()
        if not path:
            self.ctx.notify("Elige el paquete customer-res (.ac).", "warn")
            return
        if not os.path.isfile(path):
            self.ctx.notify(f"No existe el archivo: {path}", "error")
            return
        name = os.path.basename(path)
        accion = "DESINSTALAR" if "empty" in name.lower() else "INSTALAR"
        if not self._confirm(
            "Aplicar customer-res — ⚠ experimental",
            f"Se aplicará por «systool update resource» (acción prevista: {accion}):\n\n"
            f"  {name}\n\n"
            "Es categoría update: el daemon de PAX descifra y reescribe recursos del "
            "terminal, que puede reiniciarse. Un fichero equivocado puede dejar recursos "
            "inservibles. Úsalo solo con el .ac oficial y en equipo de tu propiedad. ¿Continuar?",
        ):
            return
        # pax_adb sube el .ac (último arg de un subcomando 'update') y el daemon
        # lo aplica; Bellum no toca su cifrado.
        self._out.appendPlainText(f"$ pax_adb systool update resource {path}")

        def after(res: CommandResult) -> None:
            self._log(res)
            ok = res.ok and "SYSTOOL:-" not in (res.text or "")
            self.ctx.notify(
                f"customer-res aplicado ({accion.lower()}). El terminal puede reiniciarse." if ok
                else "No se pudo aplicar el customer-res.",
                "ok" if ok else "error",
            )

        self.ctx.adb.run(["systool", "update", "resource", path], after, merge_stderr=True)

    # ---- Flashear splash.img al logo (spchge) ------------------------
    def _confirm(self, title: str, body: str) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _pick_flash_img(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "splash.img", "", "Imagen (*.img);;Todos (*)"
        )
        if path:
            self._flash_img.setText(path)

    def _flash_logo(self) -> None:
        if not self.ctx.adb.serial:
            self.ctx.notify("Sin dispositivo adb seleccionado.", "warn")
            return
        img = self._flash_img.text().strip() or self._splash_out
        if not img or not os.path.isfile(img):
            self.ctx.notify("Genera o elige una splash.img primero.", "warn")
            return
        part = self._logo_part.text().strip() or _LOGO_PART
        if not self._confirm(
            "Flashear logo",
            f"Se escribirá:\n\n  {os.path.basename(img)}\n  → {part}\n\n"
            "Modifica una partición del sistema en crudo (dd). Una imagen incorrecta puede "
            "dejar el logo inservible. ¿Continuar?",
        ):
            return
        remote = "/data/local/tmp/bellum_splash.img"
        self._out.appendPlainText(f"$ adb push {img} {remote}")

        def after_push(res: CommandResult) -> None:
            self._log(res)
            if not res.ok:
                self.ctx.notify("No se pudo subir la imagen al terminal.", "error")
                return
            cmd = f"dd if={remote} of={part}"
            self._out.appendPlainText(f"$ adb shell {cmd}")
            self.ctx.adb.shell(cmd, after_dd)

        def after_dd(res: CommandResult) -> None:
            self._log(res)
            self.ctx.adb.shell(f"rm -f {remote}", None)
            if res.ok:
                self._out.appendPlainText("✓ Logo flasheado. Se verá en el próximo arranque.\n")
                self.ctx.notify("Logo flasheado en el terminal.", "ok")
            else:
                self.ctx.notify("Falló el flasheo del logo (¿shell sin acceso a /dev/block?).", "error")

        self.ctx.adb.run(["push", img, remote], after_push)
