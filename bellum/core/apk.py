"""Ayudas para extraer APKs del terminal, compartidas entre páginas.

El `adb pull` directo sobre `/data/app/...` falla en muchos PayDroid (el servicio
`sync` no puede leer esa ruta aunque shell sí, por SELinux). Por eso se copia
antes a una carpeta que sync sí lee (`/data/local/tmp`) y se descarga desde ahí.

Agnóstico de UI: recibe un `AdbService` y callbacks.
"""

from __future__ import annotations

import os
import posixpath
from typing import Callable

from .adb import AdbService, CommandResult

# Carpeta de tránsito en el dispositivo (accesible por el servicio sync).
STAGE_DIR = "/data/local/tmp/bellum_apk"


def resolve_paths(
    adb: AdbService,
    packages: list[str],
    on_done: Callable[[dict[str, list[str]]], None],
) -> None:
    """Resuelve las rutas remotas (`pm path`) de cada paquete → `on_done({pkg: [rutas]})`.

    Encadenado (uno tras otro) para no disparar varios shell en ráfaga.
    """
    paths: dict[str, list[str]] = {}

    def step(i: int) -> None:
        if i >= len(packages):
            on_done(paths)
            return
        pkg = packages[i]

        def after(res: CommandResult) -> None:
            paths[pkg] = [
                ln[len("package:"):].strip()
                for ln in res.stdout.splitlines()
                if ln.startswith("package:")
            ]
            step(i + 1)

        adb.shell(f"pm path {pkg}", after)

    step(0)


def stage_pull(
    adb: AdbService,
    jobs: list[tuple[str, str]],
    on_done: Callable[[int], None],
    stage: str = STAGE_DIR,
) -> None:
    """Descarga cada `(remoto, local)` copiándolo antes a `stage`.

    Llama `on_done(fallos)` al terminar (nº de descargas fallidas).
    """
    def start(_res: CommandResult) -> None:
        _next(0, {"fail": 0})

    def _next(i: int, stats: dict) -> None:
        if i >= len(jobs):
            adb.shell(f"rm -rf {stage}", None)  # limpia el tránsito
            on_done(stats["fail"])
            return
        remote, local = jobs[i]
        staged = f"{stage}/{posixpath.basename(local)}"
        # `cp` (toybox); si no existe, `cat` de reserva. Comillas por si hay espacios.
        copy = f'cp "{remote}" "{staged}" 2>/dev/null || cat "{remote}" > "{staged}"'

        def after_stage(_r: CommandResult) -> None:
            def after_pull(res: CommandResult) -> None:
                # pull "ok" pero 0 bytes = la copia falló (ruta sin permiso).
                if not res.ok or not os.path.exists(local) or os.path.getsize(local) == 0:
                    stats["fail"] += 1
                _next(i + 1, stats)

            adb.run(["pull", staged, local], after_pull)

        adb.shell(copy, after_stage)

    adb.shell(f"rm -rf {stage}; mkdir -p {stage}", start)
