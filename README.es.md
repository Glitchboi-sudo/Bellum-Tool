<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/assets/bellum-logo-type-light.svg">
    <img src=".github/assets/bellum-logo-type-dark.svg" alt="Bellum Tool" width="260">
  </picture>
</p>

<p align="center">
  <strong>Hecho por Glitchboi</strong><br>
  Control nativo de Linux para terminales PAX PayDroid
</p>

<p align="center">
  <img src="https://img.shields.io/badge/estado-BETA-orange" alt="Estado" />
  <img src="https://img.shields.io/badge/licencia-GNU_GPLv3-blue" alt="Licencia" />
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python" />
  <img src="https://img.shields.io/badge/GUI-Qt6%20%2F%20PySide6-41CD52" alt="Qt6 / PySide6" />
  <img src="https://img.shields.io/badge/plataforma-Linux-333" alt="Plataforma" />
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <strong>Español</strong> ·
  <a href="README.pt.md">Português</a>
</p>

<p align="center">
  <a href="https://buymeacoffee.com/glitchboi">
    <img src="https://img.shields.io/badge/%E2%98%95%20Buy%20Me%20a%20Coffee-Apoya%20el%20proyecto-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=black" alt="Buy Me a Coffee" height="42" />
  </a>
</p>

---

## ¿Qué es Bellum Tool?

Bellum Tool es una **app de escritorio nativa de Linux** (Qt6 / PySide6) para
gestionar terminales de punto de venta **PAX PayDroid** (A910 / A920 / A930, serie
D…) por ADB. Es un front-end limpio y moderno sobre
[`pax_adb`](https://github.com/Glitchboi-sudo/pax_linux) y sobre `fastboot` /
`paydroidboot`. Cumple el mismo rol que la *PayDroid Tool* de Windows, pero como app
de escritorio nativa.

El menú lateral tiene **5 secciones** que agrupan **13 páginas de herramientas**:

- **Resumen** — detección, estado online/no autorizado/offline, ficha `getprop`,
  estado del sistema (batería, `/data`, resolución, uptime), exportar informe,
  **volcar info** del terminal (`systool` device-info + `sysver` + sysprops, que
  funciona incluso con el shell bloqueado), reinicio a sistema/bootloader y ADB
  inalámbrico.
- **Aplicaciones** — gestor de paquetes completo: listar/filtrar con versión,
  instalar APK o carpeta, extraer/backup, desinstalar, activar/desactivar, limpiar
  datos, lanzar / forzar detención y permisos por app (conceder/revocar).
- **Ficheros** — explorador remoto con push/pull y borrado (`unlink`).
- **Diagnóstico** — *Registros* (`logcat` o `syslog` de PAX), *Consola*
  (`adb shell`), *Captura* (`screencap`), *Consola serie* (terminal COM/tty
  interactiva vía `QtSerialPort`), *Herramientas* (`screenrecord`, `bugreport`,
  `dumpsys`).
- **Mantenimiento** — *Flasheo* (front-end de `fastboot` con recetas por lotes
  guardables), *Personalización* (BootLogo Maker: imagen → `splash.img`, + push de
  un `bootanimation.zip`), *Volcado* (dump genérico de particiones — tú eliges),
  *Reciclaje* (wipe estándar), *Sistema PAX* (los comandos propietarios, con una
  barra de acciones rápidas de un clic).

---

## Descarga (Linux)

Los paquetes se publican en
**[Releases](https://github.com/Glitchboi-sudo/Bellum-Tool/releases)** y se
construyen automáticamente en cada push.

El **AppImage** incluye Python + Qt + toda la app — sin instalar nada:

```bash
chmod +x Bellum-*-x86_64.AppImage
./Bellum-*-x86_64.AppImage
```

O descarga el paquete nativo de tu distro:

| Familia de distro | Paquete | Instalar |
|---|---|---|
| Debian · Ubuntu · Mint · Pop!_OS | `.deb` | `sudo apt install ./bellum-tool_*.deb` |
| Fedora · RHEL · CentOS | `.rpm` | `sudo dnf install ./bellum-tool-*.rpm` |
| openSUSE | `.rpm` | `sudo zypper install ./bellum-tool-*.rpm` |
| Arch · Manjaro · EndeavourOS | `.pkg.tar.zst` | `sudo pacman -U ./bellum-tool-*.pkg.tar.zst` |
| Cualquier otra | `.AppImage` | `chmod +x *.AppImage && ./*.AppImage` |

Bellum es un **front-end** — un par de cosas deben existir en el equipo destino (no
van empaquetadas):

| Necesitas… | Para qué | Instalar en el destino |
|---|---|---|
| Binario **`pax_adb`** | el transporte al terminal (se autodetecta) | [`Glitchboi-sudo/pax_linux`](https://github.com/Glitchboi-sudo/pax_linux) |
| **`fastboot`** *(opcional)* | solo para el módulo de flasheo | `android-tools` (o `paydroidboot`) |

---

## Instalación desde el código

Requiere **Python 3.10+**.

```bash
git clone https://github.com/Glitchboi-sudo/Bellum-Tool.git
cd Bellum-Tool

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh
```

`run.sh` usa `.venv` automáticamente y cae a `python3` del sistema. En Arch también
puedes `sudo pacman -S pyside6` y ejecutar `python3 main.py` sin venv.

---

## Uso

```bash
./run.sh                      # lanza la GUI
PAX_ADB=/ruta/a/pax_adb ./run.sh    # apunta a un binario pax_adb concreto
```

`pax_adb` se descubre vía la variable `PAX_ADB` → `PATH` → rutas conocidas, y la
ruta resuelta se guarda en los ajustes. Si no se encuentra nada, configúralo en
**Ajustes** (hay un botón **Auto-detectar**). Todo el detalle en la
**[Wiki → Configuration](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki/Configuration)**.

---

## Documentación

El manual completo está en la
**[Wiki del proyecto](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki)**:
instalación, configuración, la guía de uso completa, los comandos propietarios de
PAX, los flujos de flasheo y reciclaje, arquitectura, empaquetado, resolución de
problemas y cómo contribuir.

---

## Arquitectura

El núcleo es **ligero en Qt** (servicios + parsers puros); la UI va aparte; cada
comando de dispositivo se ejecuta de forma **asíncrona** por `QProcess`, así la
interfaz nunca se bloquea.

```
bellum/
├── core/     sin Qt salvo QProcess — núcleo reutilizable
│   ├── adb.py        AdbService — descubrimiento + ejecución asíncrona
│   ├── fastboot.py   FastbootService
│   ├── inventory.py  volcado de info systool (compartido Resumen + Sistema PAX)
│   └── models.py     Device, Package (+ parsers puros)
├── ui/
│   ├── theme.py      paletas + QSS (oscuro/claro), verificado WCAG AA
│   ├── icons.py      iconos del tema del sistema, recoloreados al vuelo
│   ├── widgets.py    Card, badges, EmptyState, Page, TabPage
│   ├── main_window.py barra lateral (5 secciones), selector, banner
│   └── pages/        las 13 páginas de herramientas
└── app.py    arranque de QApplication
```

`TabPage` agrupa las 13 páginas independientes en 5 entradas del menú y reenvía los
hooks de ciclo de vida. Más en la
**[Wiki → Architecture](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki/Architecture)**.

---

## Alcance y uso responsable

Bellum Tool es un front-end de gestión para terminales **de tu propiedad o que estás
autorizado a mantener**. Deliberadamente **no** incluye nada que eluda la seguridad
de pago ni la protección anti-tamper de PAX. Paquetes como `com.pax.ipp.neptune` y
`com.pax.daemon` se resaltan en rojo y requieren confirmación reforzada antes de
cualquier acción. Úsalo de forma legal y solo sobre tu propio equipo. Ver
**[Wiki → Scope & Responsible Use](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki/Scope-and-Responsible-Use)**.

---

## Créditos

Hecho por **[Glitchboi](https://github.com/Glitchboi-sudo)** — *Security from Mexico,
for everyone*.

Construido sobre `PySide6` / Qt6 y el ecosistema Python. Habla con los terminales
PAX a través de `pax_adb` y `fastboot` / `paydroidboot`.

---

## Licencia

Copyright © 2026 **Glitchboi**. Distribuido bajo la **[Licencia Pública General GNU
v3.0 o posterior](LICENSE)** (GPL-3.0-or-later).
