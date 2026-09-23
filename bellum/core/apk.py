"""Ayudas para extraer APKs del terminal, compartidas entre páginas.

Hay dos escenarios de terminal, y `stage_pull` los distingue con un sondeo:

- **Shell utilizable** (unidades menos bloqueadas): el `adb pull` directo sobre
  `/data/app/...` puede fallar (SELinux no deja al servicio `sync` leer esa ruta
  aunque el shell sí). Se copia antes a una carpeta legible por sync
  (`/data/local/tmp`) con `cp`/`cat` y se descarga desde ahí.
- **Shell muerto** (PayDroid muy bloqueado, p. ej. A910 de campo): cualquier
  comando de shell devuelve `error: closed`. Ahí la copia intermedia es imposible,
  así que sólo se intenta el `pull` directo (funciona con las rutas que el servicio
  sync tiene en lista blanca, típicamente parte de `/data`; `/system` no).

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


# Marca única para comprobar si el shell responde de verdad (no `error: closed`).
_PROBE_TOKEN = "BELLUM_SHELL_OK"


def stage_pull(
    adb: AdbService,
    jobs: list[tuple[str, str]],
    on_done: Callable[[int], None],
    stage: str = STAGE_DIR,
) -> None:
    """Descarga cada `(remoto, local)`. Llama `on_done(fallos)` al terminar.

    Sondea el shell una sola vez (un `echo` con marca). Según el resultado:

    - Shell vivo: `pull` directo y, si falla o baja 0 bytes, copia a `stage` con
      `cp`/`cat` y vuelve a tirar (rodea el bloqueo de sync sobre `/data/app`).
    - Shell muerto (`error: closed`): sólo `pull` directo, sin copias intermedias
      (que sólo generarían ruido de `error: closed`). Ahorra comandos en unidades
      muy bloqueadas y descarga lo que el servicio sync tenga en lista blanca.
    """
    def _ok(local: str, res: CommandResult) -> bool:
        return res.ok and os.path.exists(local) and os.path.getsize(local) > 0

    def _run(shell_ok: bool) -> None:
        def _next(i: int, stats: dict) -> None:
            if i >= len(jobs):
                if shell_ok:
                    adb.shell(f"rm -rf {stage}", None)  # limpia el tránsito
                on_done(stats["fail"])
                return
            remote, local = jobs[i]

            def after_direct(res: CommandResult) -> None:
                if _ok(local, res):
                    _next(i + 1, stats)
                    return
                if not shell_ok:
                    # Sin shell no hay copia intermedia posible: el pull directo era
                    # la única vía y ha fallado (p. ej. rutas de /system restringidas).
                    stats["fail"] += 1
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

        if shell_ok:
            adb.shell(f"rm -rf {stage}; mkdir -p {stage}", lambda _r: _next(0, {"fail": 0}))
        else:
            _next(0, {"fail": 0})

    def _probe(res: CommandResult) -> None:
        _run(_PROBE_TOKEN in (res.text or ""))

    adb.shell(f"echo {_PROBE_TOKEN}", _probe)
