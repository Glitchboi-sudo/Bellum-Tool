"""Inventario del terminal vía systool (solo lectura).

Encadena `systool get device-info` + `pax_adb sysver` + un set de `sysprop`
uno tras otro (cada uno tras la respuesta del anterior). Ese espaciado natural
evita el `[SYSTOOL:-101]` intermitente que devuelve el daemon systool ante
llamadas en ráfaga, y funciona incluso en terminales con el shell de adbd
bloqueado (systool responde por su canal propietario).

La función es agnóstica de UI: recibe un `AdbService` y callbacks. La usan tanto
la página de Sistema PAX como el Dashboard.
"""

from __future__ import annotations

from typing import Callable

from .adb import AdbService, CommandResult

# Propiedades útiles para un inventario del terminal (todas de solo lectura).
DUMP_SYSPROPS: tuple[str, ...] = (
    "ro.serialno", "ro.product.model", "ro.product.name", "ro.product.device",
    "ro.product.manufacturer", "ro.hardware", "ro.build.version.release",
    "ro.build.version.sdk", "ro.build.display.id", "ro.build.fingerprint",
    "persist.sys.timezone", "gsm.version.baseband",
)


def _probes() -> list[tuple[str, list[str]]]:
    probes: list[tuple[str, list[str]]] = [
        ("systool get device-info", ["systool", "get", "device-info"]),
        ("pax_adb sysver", ["sysver"]),
    ]
    probes += [(f"sysprop {k}", ["systool", "get", "sysprop", k]) for k in DUMP_SYSPROPS]
    return probes


def collect_info(
    adb: AdbService,
    on_done: Callable[[str], None],
    on_progress: Callable[[str], None] | None = None,
) -> None:
    """Recoge el inventario y llama `on_done(texto)` con el volcado completo.

    `on_progress(encabezado)` se invoca (si se pasa) tras cada sonda, para
    reflejar el avance en la UI.
    """
    _run(adb, _probes(), 0, [], on_done, on_progress)


def _run(
    adb: AdbService,
    probes: list[tuple[str, list[str]]],
    i: int,
    acc: list[str],
    on_done: Callable[[str], None],
    on_progress: Callable[[str], None] | None,
) -> None:
    if i >= len(probes):
        on_done("\n".join(acc).strip() + "\n")
        return
    header, args = probes[i]

    def after(res: CommandResult) -> None:
        acc.append(f"# {header}\n{(res.text or '').strip()}")
        if on_progress is not None:
            on_progress(header)
        _run(adb, probes, i + 1, acc, on_done, on_progress)

    adb.run(args, after, merge_stderr=True)


def dump_to_file(
    adb: AdbService,
    path: str,
    notify: Callable[[str, str], None],
    on_progress: Callable[[str], None] | None = None,
    on_finish: Callable[[bool], None] | None = None,
) -> None:
    """Recoge el inventario y lo escribe en `path`.

    Notifica el resultado con `notify(mensaje, nivel)` (`ok`/`error`) y, si se
    pasa, invoca `on_finish(ok)` al terminar — para efectos de UI como ocultar un
    indicador de progreso o registrar una línea de éxito. Comparte la escritura y
    el manejo de errores entre el Dashboard y la página de Sistema PAX.
    """

    def done(text: str) -> None:
        ok = True
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            ok = False
            notify(f"No se pudo guardar: {exc}", "error")
        else:
            notify(f"Info del terminal → {path}", "ok")
        if on_finish is not None:
            on_finish(ok)

    collect_info(adb, done, on_progress)
