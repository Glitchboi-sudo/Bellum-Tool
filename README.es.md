<!-- Selector de idioma -->
[English](README.md) · **Español** · [Português](README.pt.md)

# Bellum Tool

Aplicación de escritorio nativa de Linux (Qt6 / PySide6) para gestionar terminales
de punto de venta **PAX PayDroid** (A910 / A920 / A930, serie D…) por ADB. Es un
front-end limpio y moderno sobre [`pax_adb`](https://github.com/Glitchboi-sudo) —el
`adb` de AOSP con el handshake `A_HDSK` de PAX y sus seis comandos propietarios
(`syslog`, `systool`, `puk`, `sysver`, `unlink`, `getappinfo`)— y sobre `fastboot` /
`paydroidboot`. Cumple el mismo rol que la *PayDroid Tool* de Windows, pero como
app de escritorio nativa.

> **Gestión neutra de dispositivos sobre equipo de tu propiedad.** Bellum no incluye
> firmware, ni APKs empaquetadas, ni macros de "quitar tamper" o de elusión de la
> seguridad de pago. Los paquetes críticos de seguridad/pago de PAX se marcan y
> requieren una confirmación reforzada. Ver [Alcance y uso responsable](#alcance-y-uso-responsable).

📖 **La documentación completa está en la [Wiki](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki).**

## Funciones

El menú lateral tiene **5 secciones**; las herramientas relacionadas se agrupan en
pestañas.

- **Resumen** — detección de terminales, estado online/no autorizado/offline, ficha
  de propiedades (`getprop`), estado del sistema (batería, almacenamiento `/data`,
  resolución, uptime), exportar informe (`.json` / `.txt`), reinicio normal / a
  bootloader y ADB inalámbrico (Wi-Fi `tcpip` + `connect`).
- **Aplicaciones** — gestor de paquetes genérico: listar (todos/usuario/sistema/
  desactivados) con versión, filtrar, instalar APK (o carpeta), extraer/backup de
  APK, desinstalar, activar/desactivar, limpiar datos, lanzar / forzar detención y
  detalle por app (info + permisos con conceder/revocar).
- **Ficheros** — explorador remoto con transferencia push/pull y borrado (`unlink`).
- **Diagnóstico** — pestañas *Registros* (`logcat` de Android o `syslog` de PAX),
  *Consola* (ejecutor de `adb shell` con historial), *Captura* (visor de `screencap`)
  y *Herramientas* (`screenrecord`, `bugreport`, explorador `dumpsys`).
- **Mantenimiento** — pestañas *Flasheo* (front-end de `fastboot` con recetas por
  lotes guardables — **tú aportas tus imágenes**), *Reciclaje* (wipe estándar:
  `userdata` / `cache` / reinicio) y *Sistema PAX* (comandos propietarios `systool`,
  `puk`, `sysver`, `getappinfo`).

## Requisitos

- Python 3.10+
- `PySide6` (`pip install -r requirements.txt`)
- El binario **`pax_adb`** (se autodetecta; ver la Wiki)
- Opcional para flasheo: `fastboot` (`android-tools`) o `paydroidboot`

## Instalación

### Paquetes (recomendado)

Descarga el paquete de tu distro desde la página de
[Releases](https://github.com/Glitchboi-sudo/Bellum-Tool/releases):

| Familia de distro | Paquete |
|---|---|
| Debian / Ubuntu / Mint / Pop!_OS | `.deb` |
| Fedora / RHEL / openSUSE | `.rpm` |
| Arch / Manjaro / EndeavourOS | `.pkg.tar.zst` (o el `packaging/PKGBUILD`) |
| Cualquier otra | `.AppImage` (autocontenido) |

### Desde el código

```sh
git clone https://github.com/Glitchboi-sudo/Bellum-Tool.git
cd Bellum-Tool
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh
```

`run.sh` usa `.venv` automáticamente y cae a `python3` del sistema si no existe.

## Alcance y uso responsable

Bellum Tool es un front-end de gestión para terminales **de tu propiedad o que estás
autorizado a mantener**. Deliberadamente **no** incluye nada que eluda la seguridad
de pago ni la protección anti-tamper de PAX. Paquetes como `com.pax.ipp.neptune` y
`com.pax.daemon` se resaltan en rojo y requieren confirmación reforzada antes de
cualquier acción. Úsalo de forma legal y solo sobre tu propio equipo.

## Licencia

Publicado bajo la **[Licencia Pública General GNU v3.0 o posterior](LICENSE)** (GPL-3.0-or-later).
