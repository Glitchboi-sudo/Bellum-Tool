"""Paquetes «customer-res» de PAX (.ac): descifrado y extracción del recurso.

Reimplementa de forma **nativa en Linux** el transporte que el PayDroid Tool
oficial (MobileTool) hace con `bpa.exe` (binario de Windows). El flujo real,
obtenido de PayDroid Tool.exe (PCLoader.MobileToolForm / DESFileClass), es:

  .ac  →  descifrar  →  .zip  →  extraer el .zip firmado interior  →
  aplicar en el terminal con `pax_adb systool update resource <SIG.zip>`.

Este módulo cubre solo el descifrado + extracción; la aplicación la lanza la UI
por `AdbService` (systool). El `.ac` es un **recurso de cliente** (APKs + ficheros
de /cache/customer), no material criptográfico de pago: se trata como blob que el
operador ya controla, y el .zip interior va firmado (no se re-firma nada).

Formato del contenedor `.ac` (DESFileClass, pese al nombre usa Rijndael/AES):
  [IV 16 bytes][salt 16 bytes][ AES-256-CBC(cabecera 16 bytes + zip) ]
  - clave: PasswordDeriveBytes(password, salt, "SHA256", 1000) → 32 bytes
    (PBKDF1: SHA-256 de password+salt y luego 999 rehashes; total 1000).
  - cabecera descifrada: [int64 LE longitud del zip][8 bytes reservados].

Sin dependencias nuevas: la derivación de clave usa `hashlib`, el descomprimido
`zipfile` (stdlib) y el AES el binario `openssl` del sistema (como `pax_adb`).
"""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
import zipfile
from typing import Callable

from PySide6.QtCore import QObject, QProcess

# Clave del customer-res de PayDroid Tool, hallada en PayDroid Tool.exe
# (PCLoader.MobileToolForm pasa esta cadena a DESFileClass.DecryptFile).
PAYDROID_KEY = "PayDroidTool&MobileTool&20181225"


def derive_key(password: str, salt: bytes, iterations: int = 1000) -> bytes:
    """Deriva la clave AES-256 como el `PasswordDeriveBytes` de .NET (PBKDF1).

    base = SHA256(password_utf8 + salt); luego (iterations-1) rehashes de SHA256.
    Para 32 bytes con SHA-256 basta el valor base (un bloque de hash).
    """
    h = hashlib.sha256(password.encode("utf-8") + salt).digest()
    for _ in range(iterations - 1):
        h = hashlib.sha256(h).digest()
    return h  # 32 bytes → AES-256


def extract_inner_sig(plaintext: bytes) -> bytes | None:
    """Del texto en claro (cabecera + zip) devuelve el .zip firmado interior.

    El zip exterior contiene una única entrada: el `resource-*_SIG.zip` que el
    terminal aplica. Devuelve sus bytes, o None si el formato no cuadra.
    """
    if len(plaintext) < 16:
        return None
    length = int.from_bytes(plaintext[0:8], "little")
    blob = plaintext[16:16 + length]
    try:
        outer = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        return None
    names = outer.namelist()
    if not names:
        return None
    try:
        return outer.read(names[0])
    except (KeyError, zipfile.BadZipFile):
        return None


def decrypt_ac(
    parent: QObject,
    ac_path: str,
    out_sig_path: str,
    on_done: Callable[[bool, str], None],
    *,
    password: str = PAYDROID_KEY,
) -> None:
    """Descifra `ac_path` y escribe el .zip firmado interior en `out_sig_path`.

    No bloquea el hilo de UI: el AES lo hace `openssl` por QProcess (parentado a
    `parent` para su ciclo de vida). Llama `on_done(ok, mensaje)` al terminar
    (`mensaje` es `out_sig_path` si ok, o el texto de error si falla).
    """
    try:
        with open(ac_path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        on_done(False, f"No se pudo leer el .ac: {exc}")
        return
    if len(data) < 48:
        on_done(False, "El fichero .ac es demasiado pequeño o no es válido.")
        return

    iv, salt, ct = data[0:16], data[16:32], data[32:]
    if len(ct) % 16 != 0:
        on_done(False, "El .ac no tiene un tamaño de bloque AES válido.")
        return
    key = derive_key(password, salt)

    tmpdir = tempfile.mkdtemp(prefix="bellum-custres-")
    ct_path = os.path.join(tmpdir, "ct.bin")
    pt_path = os.path.join(tmpdir, "pt.bin")
    try:
        with open(ct_path, "wb") as fh:
            fh.write(ct)
    except OSError as exc:
        on_done(False, f"No se pudo preparar el descifrado: {exc}")
        return

    proc = QProcess(parent)
    proc.setProgram("openssl")
    # -nopad: el relleno lo gestionamos nosotros troceando por la cabecera de
    # longitud (el bloque lleva PKCS7 pero también una cola de hash que no toca).
    proc.setArguments([
        "enc", "-d", "-aes-256-cbc",
        "-K", key.hex(), "-iv", iv.hex(),
        "-nopad", "-in", ct_path, "-out", pt_path,
    ])

    def _cleanup() -> None:
        for p in (ct_path, pt_path):
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass

    def _finished(code: int, _status) -> None:
        try:
            if code != 0:
                err = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
                on_done(False, f"openssl falló al descifrar ({code}): {err.strip()}")
                return
            try:
                with open(pt_path, "rb") as fh:
                    pt = fh.read()
            except OSError as exc:
                on_done(False, f"No se pudo leer el texto descifrado: {exc}")
                return
            sig = extract_inner_sig(pt)
            if sig is None:
                on_done(False, "Descifrado incorrecto o formato inesperado "
                               "(¿clave o fichero equivocado?).")
                return
            try:
                with open(out_sig_path, "wb") as fh:
                    fh.write(sig)
            except OSError as exc:
                on_done(False, f"No se pudo guardar el recurso: {exc}")
                return
            on_done(True, out_sig_path)
        finally:
            _cleanup()
            proc.deleteLater()

    def _error(_err) -> None:
        msg = proc.errorString()
        _cleanup()
        proc.deleteLater()
        on_done(False, f"No se pudo ejecutar openssl: {msg} "
                       "(instala 'openssl' o revísalo en el PATH).")

    proc.finished.connect(_finished)
    proc.errorOccurred.connect(_error)
    proc.start()
