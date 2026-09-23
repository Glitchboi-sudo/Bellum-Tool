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
    """Descarga cada `(remoto, local)`.

    Primero intenta un `pull` directo (funciona cuando el servicio sync puede leer
    la ruta, p. ej. muchos /data/...). Si falla o baja 0 bytes, reintenta copiando
    antes a `stage` con shell `cp` (para unidades donde sync no lee /data/app pero
    el shell sí). Llama `on_done(fallos)` al terminar.
    """
    def _ok(local: str, res: CommandResult) -> bool:
        return res.ok and os.path.exists(local) and os.path.getsize(local) > 0

    def _next(i: int, stats: dict) -> None:
        if i >= len(jobs):
            adb.shell(f"rm -rf {stage}", None)  # limpia el tránsito
            on_done(stats["fail"])
            return
        remote, local = jobs[i]

        def after_direct(res: CommandResult) -> None:
            if _ok(local, res):
                _next(i + 1, stats)
                return
            # Reserva: copiar a un sitio legible por sync y volver a tirar.
            staged = f"{stage}/{posixpath.basename(local)}"
            copy = f'cp "{remote}" "{staged}" 2>/dev/null || cat "{remote}" > "{staged}"'

            def after_stage(_r: CommandResult) -> None:
                def after_pull(res2: CommandResult) -> None:
                    if not _ok(local, res2):
                        stats["fail"] += 1
                    _next(i + 1, stats)

                adb.run(["pull", staged, local], after_pull)

            adb.shell(copy, after_stage)

        adb.run(["pull", remote, local], after_direct)

    adb.shell(f"rm -rf {stage}; mkdir -p {stage}", lambda _r: _next(0, {"fail": 0}))
