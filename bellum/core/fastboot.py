"""Wrapper genérico de fastboot para el flasheo de particiones.

El usuario aporta sus propias imágenes. No se incluye ninguna imagen de
firmware ni secuencia de flasheo prefabricada. En Linux el `fastboot` estándar
(paquete android-tools) cubre flash/erase/reboot; `paydroidboot` es el fork de
PAX con el mismo interfaz de línea de comandos.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QProcess, Signal

from .adb import CommandResult, is_executable

_CANDIDATE_PATHS = (
    "/usr/bin/fastboot",
    "/usr/local/bin/fastboot",
    "/home/glitchboi/pax_adb_linux/paydroidboot",
    "/usr/local/bin/paydroidboot",
)


def find_fastboot() -> str | None:
    env = os.environ.get("FASTBOOT")
    if is_executable(env):
        return str(Path(env).resolve())
    for name in ("fastboot", "paydroidboot"):
        found = shutil.which(name)
        if found:
            return str(Path(found).resolve())
    for cand in _CANDIDATE_PATHS:
        if is_executable(cand):
            return str(Path(cand).resolve())
    return None


class FastbootService(QObject):
    binary_changed = Signal(str)
    command_logged = Signal(str)

    def __init__(self, binary: str | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._binary = binary if is_executable(binary) else find_fastboot()
        self._jobs: set[QProcess] = set()
        self._shutting = False

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

    def run(
        self,
        args: list[str],
        on_finished: Callable[[CommandResult], None] | None = None,
    ) -> None:
        if not self._binary:
            if on_finished:
                on_finished(
                    CommandResult(
                        args=args,
                        returncode=-1,
                        stderr="No se encontró fastboot/paydroidboot. Instala android-tools "
                        "o configúralo en Ajustes.",
                    )
                )
            return

        proc = QProcess(self)
        proc.setProgram(self._binary)
        proc.setArguments(args)
        self._jobs.add(proc)
        self.command_logged.emit(f"{Path(self._binary).name} " + " ".join(args))

        def _done(code: int, _status) -> None:
            if self._shutting or proc not in self._jobs:
                return
            self._jobs.discard(proc)
            try:
                out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
                err = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
            except RuntimeError:
                return
            proc.deleteLater()
            if on_finished:
                on_finished(CommandResult(args=args, returncode=code, stdout=out, stderr=err))

        def _err(_e) -> None:
            if self._shutting or proc not in self._jobs:
                return
            self._jobs.discard(proc)
            try:
                msg = proc.errorString()
            except RuntimeError:
                return
            proc.deleteLater()
            if on_finished:
                on_finished(CommandResult(args=args, returncode=-1, stderr=msg))

        proc.finished.connect(_done)
        proc.errorOccurred.connect(_err)
        proc.start()

    def shutdown(self) -> None:
        self._shutting = True
        for proc in list(self._jobs):
            try:
                proc.blockSignals(True)
                proc.kill()
                proc.waitForFinished(300)
            except RuntimeError:
                pass
        self._jobs.clear()

    def list_devices(self, on_finished: Callable[[CommandResult], None]) -> None:
        self.run(["devices"], on_finished)
