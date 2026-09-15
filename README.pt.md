<!-- Seletor de idioma -->
[English](README.md) · [Español](README.es.md) · **Português**

# Bellum Tool

Aplicativo de desktop nativo para Linux (Qt6 / PySide6) para gerir terminais de
ponto de venda **PAX PayDroid** (A910 / A920 / A930, série D…) por ADB. É um
front-end limpo e moderno sobre o [`pax_adb`](https://github.com/Glitchboi-sudo) —o
`adb` do AOSP com o handshake `A_HDSK` da PAX e os seus seis comandos proprietários
(`syslog`, `systool`, `puk`, `sysver`, `unlink`, `getappinfo`)— e sobre `fastboot` /
`paydroidboot`. Cumpre o mesmo papel que a *PayDroid Tool* do Windows, mas como
aplicativo de desktop nativo.

> **Gestão neutra de dispositivos em equipamento de sua propriedade.** O Bellum não
> inclui firmware, nem APKs empacotadas, nem macros de "remover tamper" ou de
> contornar a segurança de pagamento. Os pacotes críticos de segurança/pagamento da
> PAX são destacados e exigem confirmação reforçada. Veja
> [Escopo e uso responsável](#escopo-e-uso-responsável).

📖 **A documentação completa está na [Wiki](https://github.com/Glitchboi-sudo/Bellum-Tool/wiki).**

## Funcionalidades

O menu lateral tem **5 seções**; as ferramentas relacionadas são agrupadas em abas.

- **Resumo** — deteção de terminais, estado online/não autorizado/offline, ficha de
  propriedades (`getprop`), estado do sistema (bateria, armazenamento `/data`,
  resolução, uptime), exportar relatório (`.json` / `.txt`), reinício normal / para
  o bootloader e ADB sem fios (Wi-Fi `tcpip` + `connect`).
- **Aplicativos** — gestor de pacotes genérico: listar (todos/utilizador/sistema/
  desativados) com versão, filtrar, instalar APK (ou pasta), extrair/backup de APK,
  desinstalar, ativar/desativar, limpar dados, iniciar / forçar paragem e detalhe por
  app (info + permissões com conceder/revogar).
- **Ficheiros** — explorador remoto com transferência push/pull e eliminação (`unlink`).
- **Diagnóstico** — abas *Registos* (`logcat` do Android ou `syslog` da PAX),
  *Consola* (executor de `adb shell` com histórico), *Captura* (visualizador de
  `screencap`) e *Ferramentas* (`screenrecord`, `bugreport`, explorador `dumpsys`).
- **Manutenção** — abas *Flash* (front-end do `fastboot` com receitas em lote
  guardáveis — **você fornece as suas imagens**), *Reciclagem* (wipe padrão:
  `userdata` / `cache` / reinício) e *Sistema PAX* (comandos proprietários `systool`,
  `puk`, `sysver`, `getappinfo`).

## Requisitos

- Python 3.10+
- `PySide6` (`pip install -r requirements.txt`)
- O binário **`pax_adb`** (detetado automaticamente; ver a Wiki)
- Opcional para flash: `fastboot` (`android-tools`) ou `paydroidboot`

## Instalação

### Pacotes (recomendado)

Baixe o pacote da sua distro na página de
[Releases](https://github.com/Glitchboi-sudo/Bellum-Tool/releases):

| Família de distro | Pacote |
|---|---|
| Debian / Ubuntu / Mint / Pop!_OS | `.deb` |
| Fedora / RHEL / openSUSE | `.rpm` |
| Arch / Manjaro / EndeavourOS | `.pkg.tar.zst` (ou o `packaging/PKGBUILD`) |
| Qualquer outra | `.AppImage` (autocontido) |

### A partir do código

```sh
git clone https://github.com/Glitchboi-sudo/Bellum-Tool.git
cd Bellum-Tool
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh
```

`run.sh` usa `.venv` automaticamente e recorre ao `python3` do sistema se não existir.

## Escopo e uso responsável

O Bellum Tool é um front-end de gestão para terminais **de sua propriedade ou que
está autorizado a manter**. Deliberadamente **não** inclui nada que contorne a
segurança de pagamento ou a proteção anti-tamper da PAX. Pacotes como
`com.pax.ipp.neptune` e `com.pax.daemon` são realçados a vermelho e exigem
confirmação reforçada antes de qualquer ação. Use-o de forma legal e apenas no seu
próprio equipamento.

## Licença

Publicado sob a **[Licença Pública Geral GNU v3.0 ou posterior](LICENSE)** (GPL-3.0-or-later).
