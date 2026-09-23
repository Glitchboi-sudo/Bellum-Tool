"""Auditoría de postura de seguridad (solo lectura) para uso en evaluaciones
autorizadas sobre equipo propio.

Recoge un conjunto acotado de propiedades relevantes para seguridad vía
`systool get sysprop` (encadenadas, como en `inventory`, para funcionar aunque el
`adb shell` esté bloqueado) y las evalúa en hallazgos con severidad. Es
enumeración y documentación de postura — no realiza ningún bypass ni extracción
de material criptográfico.

Módulo agnóstico de UI: recibe un `AdbService` y callbacks.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Callable

from .adb import AdbService, CommandResult

# Niveles de severidad, ordenados de más a menos grave (para resumen/orden).
LEVELS = ("danger", "warn", "info", "ok", "na")

# Propiedades de sistema relevantes para seguridad (todas de solo lectura).
SECURITY_PROP_KEYS: tuple[str, ...] = (
    "ro.build.version.release", "ro.build.version.sdk", "ro.build.version.security_patch",
    "ro.build.tags", "ro.build.type", "ro.build.fingerprint",
    "ro.secure", "ro.debuggable", "ro.adb.secure",
    "ro.boot.flash.locked", "ro.boot.verifiedbootstate", "ro.boot.veritymode",
    "ro.crypto.state", "ro.boot.selinux",
    "sys.usb.config", "persist.sys.usb.config",
)


@dataclass
class Finding:
    label: str
    value: str
    level: str    # uno de LEVELS
    detail: str


# ----------------------------------------------------------------------
# Recogida (systool, encadenada)
# ----------------------------------------------------------------------
def _merge(text: str, props: dict[str, str]) -> None:
    """Añade a `props` las líneas `.<clave>=<valor>` de una salida de systool."""
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith(".") and "=" in line:
            key, _, val = line[1:].partition("=")
            key = key.strip()
            if key and key not in props:
                props[key] = val.strip()


def collect_security(adb: AdbService, on_done: Callable[[dict[str, str]], None],
                     on_progress: Callable[[str], None] | None = None) -> None:
    """Recoge device-info + sysprops de seguridad y llama `on_done(props)`."""
    probes: list[tuple[str, list[str]]] = [("device-info", ["systool", "get", "device-info"])]
    probes += [(k, ["systool", "get", "sysprop", k]) for k in SECURITY_PROP_KEYS]
    _run(adb, probes, 0, {}, on_done, on_progress)


def _run(adb, probes, i, props, on_done, on_progress) -> None:
    if i >= len(probes):
        on_done(props)
        return
    header, args = probes[i]

    def after(res: CommandResult) -> None:
        _merge(res.text or "", props)
        if on_progress is not None:
            on_progress(header)
        _run(adb, probes, i + 1, props, on_done, on_progress)

    adb.run(args, after, merge_stderr=True)


# ----------------------------------------------------------------------
# Evaluación
# ----------------------------------------------------------------------
def evaluate(props: dict[str, str]) -> list[Finding]:
    """Convierte las propiedades recogidas en hallazgos con severidad."""
    def g(k: str) -> str:
        return (props.get(k) or "").strip()

    year = datetime.date.today().year
    out: list[Finding] = []

    # --- Versión de Android / soporte ---
    sdk, rel = g("ro.build.version.sdk"), g("ro.build.version.release")
    val = f"{rel or '?'} (SDK {sdk or '?'})"
    try:
        n = int(sdk)
    except ValueError:
        n = None
    if n is None:
        lvl, det = "na", "No se pudo leer la versión de Android."
    elif n <= 23:
        lvl, det = "danger", "Android 6.0 o anterior: fuera de soporte, sin parches de seguridad desde hace años."
    elif n <= 27:
        lvl, det = "warn", "Android 7–8.1: soporte finalizado; faltan parches recientes."
    elif n <= 29:
        lvl, det = "warn", "Android 9–10: soporte muy limitado a estas alturas."
    else:
        lvl, det = "ok", "Versión de Android relativamente reciente."
    out.append(Finding("Versión de Android", val, lvl, det))

    # --- Nivel de parche de seguridad ---
    sp = g("ro.build.version.security_patch")
    if not sp:
        out.append(Finding("Parche de seguridad", "(no expuesto)", "warn",
                            "El terminal no informa nivel de parche de seguridad."))
    else:
        py = int(sp[:4]) if len(sp) >= 4 and sp[:4].isdigit() else None
        if py is None:
            lvl, det = "na", "Formato de parche no reconocido."
        elif py < year - 1:
            lvl, det = "danger", "Parche de seguridad con más de un año de antigüedad."
        elif py < year:
            lvl, det = "warn", "Parche de seguridad de hace casi un año."
        else:
            lvl, det = "ok", "Parche de seguridad reciente."
        out.append(Finding("Parche de seguridad", sp, lvl, det))

    # --- Claves de firma / tipo de build ---
    tags, btype, fp = g("ro.build.tags"), g("ro.build.type"), g("ro.build.fingerprint")
    blob = f"{tags} {fp}"
    if "test-keys" in blob:
        lvl, det, val = "danger", "Firmado con test-keys: build de desarrollo, no de producción.", "test-keys"
    elif "release-keys" in blob:
        lvl, det, val = "ok", "Firmado con release-keys (build de producción).", "release-keys"
    else:
        lvl, det, val = "na", "No se pudieron determinar las claves de firma.", tags or "(no expuesto)"
    if btype in ("userdebug", "eng"):
        lvl, val = "danger", f"{val} · {btype}"
        det = f"Tipo de build «{btype}» (depuración): acceso ampliado a shell/root."
    out.append(Finding("Claves de firma / build", val, lvl, det))

    # --- ro.secure ---
    v = g("ro.secure")
    out.append(_flag("adbd restringido (ro.secure)", v,
                     ok_when="1", ok="adbd restringido (ro.secure=1).",
                     bad="0", bad_lvl="danger", bad_det="adbd se ejecuta como root (ro.secure=0)."))
    # --- ro.debuggable ---
    v = g("ro.debuggable")
    out.append(_flag("Build depurable (ro.debuggable)", v,
                     ok_when="0", ok="No depurable (ro.debuggable=0).",
                     bad="1", bad_lvl="danger", bad_det="Build depurable: permite root vía adb (ro.debuggable=1)."))
    # --- ro.adb.secure ---
    v = g("ro.adb.secure")
    out.append(_flag("Autorización ADB (ro.adb.secure)", v,
                     ok_when="1", ok="ADB exige autorización por clave (ro.adb.secure=1).",
                     bad="0", bad_lvl="warn", bad_det="ADB sin autorización por clave (ro.adb.secure=0)."))

    # --- Bootloader / verified boot ---
    locked, vbs = g("ro.boot.flash.locked"), g("ro.boot.verifiedbootstate")
    val = locked or vbs or "(no expuesto)"
    if locked == "1" or vbs == "green":
        lvl, det = "ok", "Bootloader bloqueado / verified boot en verde."
    elif locked == "0" or vbs in ("orange", "yellow", "red"):
        lvl, det = "danger", f"Bootloader desbloqueado / verified boot {vbs or 'unlocked'}."
    else:
        lvl, det = "na", "No se expone el estado del bootloader (habitual vía systool)."
    out.append(Finding("Bootloader / verified boot", val, lvl, det))

    # --- Cifrado ---
    cs = g("ro.crypto.state")
    val = cs or "(no expuesto)"
    det_map = {"encrypted": ("ok", "Almacenamiento cifrado."),
               "unencrypted": ("danger", "Almacenamiento sin cifrar."),
               "unsupported": ("warn", "El dispositivo no soporta cifrado.")}
    lvl, det = det_map.get(cs, ("na", "No se expone el estado de cifrado."))
    out.append(Finding("Cifrado de datos", val, lvl, det))

    # --- SELinux ---
    se = g("ro.boot.selinux")
    val = se or "(no expuesto)"
    if se == "enforcing":
        lvl, det = "ok", "SELinux en modo enforcing."
    elif se == "permissive":
        lvl, det = "danger", "SELinux en modo permissive: sin aislamiento obligatorio."
    else:
        lvl, det = "na", "No se expone el modo de SELinux por esta vía."
    out.append(Finding("SELinux", val, lvl, det))

    # --- Config USB / ADB expuesto ---
    u = g("sys.usb.config") or g("persist.sys.usb.config")
    if not u:
        out.append(Finding("Config USB", "(no expuesto)", "na", "No se expone la configuración USB."))
    elif "adb" in u:
        out.append(Finding("Config USB", u, "info", "ADB habilitado en la configuración USB actual."))
    else:
        out.append(Finding("Config USB", u, "ok", "ADB no aparece en la configuración USB actual."))

    # --- Personalización (customer) ---
    c = g("customer")
    if not c:
        out.append(Finding("Personalización", "(no expuesto)", "na", "No se expone el estado de personalización."))
    elif c == "255":
        out.append(Finding("Personalización", "customer=255", "info",
                            "Sin personalizar (estado de fábrica): sin adquirente/comercio cargado."))
    else:
        out.append(Finding("Personalización", f"customer={c}", "info", "Terminal personalizado."))

    return out


def _flag(label: str, value: str, *, ok_when: str, ok: str,
          bad: str, bad_lvl: str, bad_det: str) -> Finding:
    """Hallazgo para una propiedad binaria (1/0)."""
    if value == ok_when:
        return Finding(label, value, "ok", ok)
    if value == bad:
        return Finding(label, value, bad_lvl, bad_det)
    return Finding(label, value or "(no expuesto)", "na", "El terminal no expone esta propiedad.")


def summarize(findings: list[Finding]) -> dict[str, int]:
    """Cuenta hallazgos por nivel."""
    counts = {lvl: 0 for lvl in LEVELS}
    for f in findings:
        counts[f.level] = counts.get(f.level, 0) + 1
    return counts
