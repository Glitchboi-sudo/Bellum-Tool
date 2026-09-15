<p align="center">
  <pre>
██████╗ ███████╗██╗     ██╗     ██╗   ██╗███╗   ███╗
██╔══██╗██╔════╝██║     ██║     ██║   ██║████╗ ████║
██████╔╝█████╗  ██║     ██║     ██║   ██║██╔████╔██║
██╔══██╗██╔══╝  ██║     ██║     ██║   ██║██║╚██╔╝██║
██████╔╝███████╗███████╗███████╗╚██████╔╝██║ ╚═╝ ██║
╚═════╝ ╚══════╝╚══════╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝
              P A X   P A Y D R O I D   T O O L
  </pre>
</p>

<p align="center">
  <strong>Feito por Glitchboi</strong><br>
  Controlo nativo de Linux para terminais PAX PayDroid
</p>

<p align="center">
  <img src="https://img.shields.io/badge/estado-BETA-orange" alt="Estado" />
  <img src="https://img.shields.io/badge/licença-GNU_GPLv3-blue" alt="Licença" />
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python" />
  <img src="https://img.shields.io/badge/GUI-Qt6%20%2F%20PySide6-41CD52" alt="Qt6 / PySide6" />
  <img src="https://img.shields.io/badge/plataforma-Linux-333" alt="Plataforma" />
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.es.md">Español</a> ·
  <strong>Português</strong>
</p>

---

## O que é o Bellum Tool?

O Bellum Tool é um **aplicativo de desktop nativo para Linux** (Qt6 / PySide6) para
gerir terminais de ponto de venda **PAX PayDroid** (A910 / A920 / A930, série D…) por
ADB. É um front-end limpo e moderno sobre
[`pax_adb`](https://github.com/Glitchboi-sudo/pax_linux) e sobre `fastboot` /
`paydroidboot`. Cumpre o mesmo papel que a *PayDroid Tool* do Windows, mas como
aplicativo de desktop nativo.

O menu lateral tem **5 seções** que agrupam **9 páginas de ferramentas**:

- **Resumo** — deteção, estado online/não autorizado/offline, ficha `getprop`,
  estado do sistema (bateria, `/data`, resolução, uptime), exportar relatório,
  reinício para sistema/bootloader e ADB sem fios.
- **Aplicativos** — gestor de pacotes completo: listar/filtrar com versão,
  instalar APK ou pasta, extrair/backup, desinstalar, ativar/desativar, limpar
  dados, iniciar / forçar paragem e permissões por app (conceder/revogar).
- **Ficheiros** — explorador remoto com push/pull e eliminação (`unlink`).
- **Diagnóstico** — *Registos* (`logcat` ou `syslog` da PAX), *Consola*
  (`adb shell`), *Captura* (`screencap`), *Ferramentas* (`screenrecord`,
  `bugreport`, `dumpsys`).
- **Manutenção** — *Flash* (front-end do `fastboot` com receitas em lote
  guardáveis), *Reciclagem* (wipe padrão), *Sistema PAX* (os comandos proprietários).

---

## Download (Linux)

Os pacotes são publicados em
**[Releases](https://github.com/Glitchboi-sudo/Bellum-Tool/releases)** e construídos
automaticamente a cada push.

O **AppImage** inclui Python + Qt + toda a aplicação — sem instalar nada:

```bash
chmod +x Bellum_Tool-*-x86_64.AppImage
./Bellum_Tool-*-x86_64.AppImage
```

Ou baixe o pacote nativo da sua distro:

| Família de distro | Pacote | Instalar |
|---|---|---|
| Debian · Ubuntu · Mint · Pop!_OS | `.deb` | `sudo apt install ./bellum-tool_*.deb` |
| Fedora · RHEL · CentOS | `.rpm` | `sudo dnf install ./bellum-tool-*.rpm` |
| openSUSE | `.rpm` | `sudo zypper install ./bellum-tool-*.rpm` |
| Arch · Manjaro · EndeavourOS | `.pkg.tar.zst` | `sudo pacman -U ./bellum-tool-*.pkg.tar.zst` |
| Qualquer outra | `.AppImage` | `chmod +x *.AppImage && ./*.AppImage` |

O Bellum é um **front-end** — algumas coisas devem existir no sistema alvo (não são
empacotadas):

| Você precisa de… | Para quê | Instalar no alvo |
|---|---|---|
| Binário **`pax_adb`** | o transporte até ao terminal (detetado automaticamente) | [`Glitchboi-sudo/pax_linux`](https://github.com/Glitchboi-sudo/pax_linux) |
| **`fastboot`** *(opcional)* | apenas para o módulo de flash | `android-tools` (ou `paydroidboot`) |

---

## Instalação a partir do código

Requer **Python 3.10+**.

```bash
git clone https://github.com/Glitchboi-sudo/Bellum-Tool.git
cd Bellum-Tool

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh
```

`run.sh` usa `.venv` automaticamente e recorre ao `python3` do sistema. No Arch pode
também `sudo pacman -S pyside6` e executar `python3 main.py` sem venv.

---

## Utilização

```bash
./run.sh                      # inicia a GUI
PAX_ADB=/caminho/pax_adb ./run.sh   # aponta para um binário pax_adb específico
```

O `pax_adb` é descoberto via a variável `PAX_ADB` → `PATH` → caminhos conhecidos, e
o caminho resolvido é guardado nas definições. Se nada for encontrado, configure-o em
**Definições** (há um botão **Deteção automática**). Todos os detalhes na
**[Wiki → Configuration](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki/Configuration)**.

---

## Documentação

O manual completo está na
**[Wiki do projeto](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki)**:
instalação, configuração, o guia de utilização completo, os comandos proprietários
da PAX, os fluxos de flash e reciclagem, arquitetura, empacotamento, resolução de
problemas e como contribuir.

---

## Arquitetura

O núcleo é **leve em Qt** (serviços + parsers puros); a UI fica à parte; cada comando
de dispositivo é executado de forma **assíncrona** por `QProcess`, por isso a
interface nunca bloqueia.

```
bellum/
├── core/     sem Qt exceto QProcess — núcleo reutilizável
│   ├── adb.py        AdbService — descoberta + execução assíncrona
│   ├── fastboot.py   FastbootService
│   └── models.py     Device, Package (+ parsers puros)
├── ui/
│   ├── theme.py      paletas + QSS (escuro/claro), verificado WCAG AA
│   ├── icons.py      ícones do tema do sistema, recoloridos ao voo
│   ├── widgets.py    Card, badges, EmptyState, Page, TabPage
│   ├── main_window.py barra lateral (5 seções), seletor, banner
│   └── pages/        as 9 páginas de ferramentas
└── app.py    arranque do QApplication
```

`TabPage` agrupa as 9 páginas independentes em 5 entradas do menu e reencaminha os
hooks de ciclo de vida. Mais na
**[Wiki → Architecture](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki/Architecture)**.

---

## Escopo e uso responsável

O Bellum Tool é um front-end de gestão para terminais **de sua propriedade ou que
está autorizado a manter**. Deliberadamente **não** inclui nada que contorne a
segurança de pagamento ou a proteção anti-tamper da PAX. Pacotes como
`com.pax.ipp.neptune` e `com.pax.daemon` são realçados a vermelho e exigem
confirmação reforçada antes de qualquer ação. Use-o de forma legal e apenas no seu
próprio equipamento. Veja
**[Wiki → Scope & Responsible Use](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki/Scope-and-Responsible-Use)**.

---

## Créditos

Feito por **[Glitchboi](https://github.com/Glitchboi-sudo)** — *Security from Mexico,
for everyone*.

Construído sobre `PySide6` / Qt6 e o ecossistema Python. Comunica com os terminais
PAX através de `pax_adb` e `fastboot` / `paydroidboot`.

---

## Licença

Copyright © 2026 **Glitchboi**. Distribuído sob a **[Licença Pública Geral GNU v3.0
ou posterior](LICENSE)** (GPL-3.0-or-later).
