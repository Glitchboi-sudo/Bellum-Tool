"""Descubrimiento del binario `pax_adb` y ejecución asíncrona de comandos.

Toda ejecución pasa por QProcess para integrarse con el bucle de eventos de Qt
y nunca bloquear el hilo de UI. Los comandos de un solo disparo usan `run()`
(con callback), y los de streaming (p.ej. logcat) usan `start()` que devuelve el
QProcess para que el llamador gestione su ciclo de vida.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QProcess, Signal

# Rutas candidatas donde puede estar el binario, en orden de preferencia.
_CANDIDATE_PATHS = (
    "/home/glitchboi/pax_adb_linux/pax_adb",
    "/usr/local/bin/pax_adb",
    "/usr/bin/pax_adb",
)


def is_executable(path: str | None) -> bool:
    """True si `path` es un fichero ejecutable existente (ruta configurada válida)."""
    return bool(path) and Path(path).is_file() and os.access(path, os.X_OK)


def find_pax_adb() -> str | None:
    """Localiza el binario pax_adb.

    Orden: variable de entorno PAX_ADB → PATH → rutas conocidas.
    Devuelve la ruta absoluta o None si no se encuentra.
    """
    env = os.environ.get("PAX_ADB")
    if is_executable(env):
        return str(Path(env).resolve())

    found = shutil.which("pax_adb")
    if found:
        return str(Path(found).resolve())

    for cand in _CANDIDATE_PATHS:
        if is_executable(cand):
            return str(Path(cand).resolve())
    return None


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def text(self) -> str:
        """stdout, o stderr si stdout está vacío (adb escribe errores en stderr)."""
        return self.stdout if self.stdout.strip() else self.stderr

    def __str__(self) -> str:
        return self.text


class AdbService(QObject):
    """Fachada de ejecución de pax_adb con dispositivo objetivo seleccionable."""

    binary_changed = Signal(str)
    serial_changed = Signal(str)  # "" si no hay dispositivo seleccionado
    # Registro de cada invocación, para una consola de log en la UI.
    command_logged = Signal(str)

    def __init__(self, binary: str | None = None, parent: QObject | None = None):
        super().__init__(parent)
        # Si la ruta configurada ya no es válida (binario movido/borrado),
        # se ignora y se auto-detecta.
        self._binary = binary if is_executable(binary) else find_pax_adb()
        self._serial: str = ""
        self._jobs: set[QProcess] = set()
        self._shutting = False

    # ---- configuración ------------------------------------------------
    @property
    def binary(self) -> str | None:
        return self._binary

    @binary.setter
    def binary(self, value: str | None) -> None:
        self._binary = str(Path(value).resolve()) if value else None
        self.binary_changed.emit(self._binary or "")

    @property
    def available(self) -> bool:
        return bool(self._binary)

    @property
    def serial(self) -> str:
        return self._serial

    @serial.setter
    def serial(self, value: str) -> None:
        value = value or ""
        if value != self._serial:
            self._serial = value
            self.serial_changed.emit(value)

    # ---- construcción de argumentos -----------------------------------
    def _full_args(self, args: list[str], targeted: bool) -> list[str]:
        prefix: list[str] = []
        if targeted and self._serial:
            prefix = ["-s", self._serial]
        return prefix + args

    # ---- streaming (logcat, etc.) -------------------------------------
    def start(self, args: list[str], *, targeted: bool = True) -> QProcess | None:
        """Lanza un proceso y devuelve el QProcess (el llamador gestiona señales)."""
        if not self._binary:
            return None
        full = self._full_args(args, targeted)
        proc = QProcess(self)
        proc.setProgram(self._binary)
        proc.setArguments(full)
        self.command_logged.emit("pax_adb " + " ".join(full))
        proc.start()
        return proc

    # ---- un solo disparo con callback ---------------------------------
    def run(
        self,
        args: list[str],
        on_finished: Callable[[CommandResult], None] | None = None,
        *,
        targeted: bool = True,
        merge_stderr: bool = False,
    ) -> None:
        """Ejecuta un comando y llama a `on_finished(CommandResult)` al terminar."""
        if not self._binary:
            if on_finished:
                on_finished(
                    CommandResult(
                        args=args,
                        returncode=-1,
                        stderr="No se encontró el binario pax_adb. Configúralo en Ajustes.",
                    )
                )
            return

        full = self._full_args(args, targeted)
        proc = QProcess(self)
        if merge_stderr:
            proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setProgram(self._binary)
        proc.setArguments(full)
        self._jobs.add(proc)
        self.command_logged.emit("pax_adb " + " ".join(full))

        def _done(code: int, _status) -> None:
            # Guarda contra doble despacho y contra señales entregadas durante el
            # teardown (el objeto C++ puede estar ya destruido → RuntimeError).
            if self._shutting or proc not in self._jobs:
                return
            self._jobs.discard(proc)
            try:
                out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
                # Con canales fusionados, stderr va en stdout: no lo leas (Qt avisa).
                err = (
                    ""
                    if merge_stderr
                    else bytes(proc.readAllStandardError()).decode("utf-8", "replace")
                )
            except RuntimeError:
                return
            proc.deleteLater()
            if on_finished:
                on_finished(CommandResult(args=full, returncode=code, stdout=out, stderr=err))

        def _err(_error) -> None:
            # errorOccurred: fallo al lanzar (p.ej. binario ilegible).
            if self._shutting or proc not in self._jobs:
                return
            self._jobs.discard(proc)
            try:
                msg = proc.errorString()
            except RuntimeError:
                return
            proc.deleteLater()
            if on_finished:
                on_finished(CommandResult(args=full, returncode=-1, stderr=msg))

        proc.finished.connect(_done)
        proc.errorOccurred.connect(_err)
        proc.start()

    def shutdown(self) -> None:
        """Detiene todos los procesos en curso y silencia sus señales.

        Debe llamarse al cerrar la ventana, antes de destruir los objetos Qt,
        para evitar callbacks sobre QProcess ya eliminados.
        """
        self._shutting = True
        for proc in list(self._jobs):
            try:
                proc.blockSignals(True)
                proc.kill()
                proc.waitForFinished(300)
            except RuntimeError:
                pass
        self._jobs.clear()

    # ---- conexión por red ---------------------------------------------
    def connect(self, host: str, on_finished: Callable[[CommandResult], None]) -> None:
        # connect/disconnect no llevan -s (no van dirigidos a un dispositivo).
        self.run(["connect", host], on_finished, targeted=False, merge_stderr=True)

    def disconnect(self, host: str, on_finished: Callable[[CommandResult], None]) -> None:
        self.run(["disconnect", host], on_finished, targeted=False, merge_stderr=True)

    def tcpip(self, port: int, on_finished: Callable[[CommandResult], None]) -> None:
        # tcpip sí va dirigido: le dice al dispositivo USB actual que escuche
        # ADB por TCP en <port>. Requiere un dispositivo seleccionado.
        self.run(["tcpip", str(port)], on_finished, merge_stderr=True)

    # ---- helpers de alto nivel ----------------------------------------
    def list_devices(self, on_finished: Callable[[CommandResult], None]) -> None:
        self.run(["devices", "-l"], on_finished, targeted=False)

    def getprops(self, on_finished: Callable[[dict[str, str]], None]) -> None:
        """Ejecuta `shell getprop` y parsea a dict."""

        def _parse(res: CommandResult) -> None:
            props: dict[str, str] = {}
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("[") and "]: [" in line:
                    key, _, rest = line[1:].partition("]: [")
                    props[key] = rest.rstrip("]")
            on_finished(props)

        self.run(["shell", "getprop"], _parse)

    def shell(
        self, command: str, on_finished: Callable[[CommandResult], None] | None = None
    ) -> None:
        # adb une los argumentos con espacios; pasar el comando como un único
        # token preserva comillas y pipes tal cual los escribe el usuario.
        self.run(["shell", command], on_finished, merge_stderr=True)

    # ---- streaming binario a fichero (volcados grandes) ----------------
    def stream_to_file(
        self,
        args: list[str],
        local_path: str,
        on_finished: Callable[[CommandResult], None] | None = None,
        *,
        targeted: bool = True,
    ) -> QProcess | None:
        """Ejecuta un comando y vuelca su STDOUT crudo (binario) a `local_path`.

        Para volcados grandes (p. ej. `exec-out dd if=/dev/block/mmcblk0`): el
        stdout va directo al fichero, sin pasar por memoria ni decodificarse como
        texto (que corrompería los bytes). Devuelve el QProcess (para cancelar).
        """
        if not self._binary:
            if on_finished:
                on_finished(CommandResult(args=args, returncode=-1,
                                          stderr="No se encontró el binario pax_adb."))
            return None
        full = self._full_args(args, targeted)
        proc = QProcess(self)
        proc.setStandardOutputFile(local_path)  # stdout binario → fichero
        proc.setProgram(self._binary)
        proc.setArguments(full)
        self._jobs.add(proc)
        self.command_logged.emit("pax_adb " + " ".join(full) + f"  > {local_path}")

        def _done(code: int, _status) -> None:
            if self._shutting or proc not in self._jobs:
                return
            self._jobs.discard(proc)
            try:
                err = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
            except RuntimeError:
                return
            proc.deleteLater()
            if on_finished:
                on_finished(CommandResult(args=full, returncode=code, stderr=err))

        def _err(_error) -> None:
            if self._shutting or proc not in self._jobs:
                return
            self._jobs.discard(proc)
            try:
                msg = proc.errorString()
            except RuntimeError:
                return
            proc.deleteLater()
            if on_finished:
                on_finished(CommandResult(args=full, returncode=-1, stderr=msg))

        proc.finished.connect(_done)
        proc.errorOccurred.connect(_err)
        proc.start()
        return proc
