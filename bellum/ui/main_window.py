"""Ventana principal: barra lateral, selector de dispositivo y páginas."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.adb import AdbService, CommandResult
from ..core.fastboot import FastbootService
from ..core.models import Device
from . import icons, theme
from .pages.apps import AppsPage
from .pages.dashboard import DashboardPage
from .pages.diagtools import DiagToolsPage
from .pages.dump import DumpPage
from .pages.files import FilesPage
from .pages.flash import FlashPage
from .pages.logcat import LogcatPage
from .pages.personalize import PersonalizePage
from .pages.recycle import RecyclePage
from .pages.screenshot import ScreenshotPage
from .pages.serialcon import SerialConsolePage
from .pages.shell import ShellPage
from .pages.systool import SystoolPage
from .settings_dialog import SettingsDialog
from .widgets import AppContext, TabPage, scroll_wrap

# Color de los iconos de la barra lateral: fija, porque el fondo de la
# barra lateral también es fijo (siempre oscuro, en ambos temas — ver
# Palette.sidebar). Un solo tono claro lee bien tanto sobre el fondo oscuro
# en reposo como sobre el acento azul del ítem seleccionado.
_NAV_ICON_COLOR = "#dde1ea"

# nivel -> (fondo, texto, icono) usando los tokens de tinte suave de Palette
_NOTIFY_STYLE = {
    "info": ("neutral_bg", "neutral_fg", None),
    "ok": ("ok_bg", "ok", "ok"),
    "warn": ("warn_bg", "warn", "warning"),
    "error": ("danger_bg", "danger", "warning"),
}


def _app_icon(accent: str) -> QIcon:
    """Icono de app sintetizado: cuadrado redondeado + rayo, sin ficheros externos."""
    size = 64
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(accent))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(2, 2, size - 4, size - 4), 16, 16)
    p.setBrush(QColor("#ffffff"))
    bolt = [
        (34, 10), (18, 36), (29, 36), (26, 54), (46, 26), (34, 26),
    ]
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPolygonF

    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in bolt]))
    p.end()
    return QIcon(pm)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bellum Tool")
        self.resize(1180, 760)
        # Mínimo pequeño: el contenido de cada página va dentro de un QScrollArea
        # y las filas reflujan (FlowLayout), así que la ventana puede encogerse
        # mucho (incluso a ~1/4 de pantalla o en HiDPI) sin recortar contenido.
        self.setMinimumSize(360, 480)
        # Estado del sidebar responsivo (se colapsa a solo iconos si la ventana
        # es muy estrecha). None = aún sin aplicar; lo fija _apply_responsive.
        self._compact: bool | None = None

        self._settings = QSettings("bellum", "bellum_tool")
        self._migrate_settings()
        self._palette = theme.DARK if self._settings.value("theme", "dark") == "dark" else theme.LIGHT
        self.setWindowIcon(_app_icon(self._palette.accent))

        self._adb = AdbService(self._settings.value("adb_path", None) or None)
        self._fastboot = FastbootService(self._settings.value("fastboot_path", None) or None)
        # Auto-configura: guarda en los ajustes la ruta que se haya resuelto
        # (la configurada si es válida, o la autodetectada). Así queda
        # "configurado" y visible en Ajustes sin intervención. Si no se detectó
        # nada, el ajuste se deja como estaba para configurarlo a mano.
        self._persist_binary("adb_path", self._adb.binary)
        self._persist_binary("fastboot_path", self._fastboot.binary)

        self._ctx = AppContext(
            adb=self._adb,
            fastboot=self._fastboot,
            palette=self._palette,
            notify=self.notify,
        )

        self._build_ui()
        self._apply_theme()

        self._adb.command_logged.connect(lambda c: self._trace.setText(f"↳ {c}"))

        # Carga inicial + sondeo periódico de dispositivos.
        self._poll = QTimer(self)
        self._poll.setInterval(4000)
        self._poll.timeout.connect(self._refresh_devices)
        self._poll.start()
        QTimer.singleShot(0, self._initial_check)

    # ------------------------------------------------------------------
    def _migrate_settings(self) -> None:
        """Trae la config del nombre anterior (tpv_toolkit/pax_toolkit) una vez.

        Evita que renombrar a Bellum Tool pierda el `adb_path`/`theme` que el
        usuario ya tenía configurados. Solo copia si el ajuste nuevo aún no
        existe; no pisa cambios posteriores.
        """
        old = QSettings("tpv_toolkit", "pax_toolkit")
        for key in ("adb_path", "fastboot_path", "theme"):
            if self._settings.value(key) is None and old.value(key) is not None:
                self._settings.setValue(key, old.value(key))

    def _persist_binary(self, key: str, value: str | None) -> None:
        """Guarda `value` en los ajustes si es una ruta nueva (auto-config)."""
        if value and self._settings.value(key, "") != value:
            self._settings.setValue(key, value)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("RootBg")
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_sidebar())
        outer.addWidget(self._build_main(), 1)
        self.setCentralWidget(root)

    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("Sidebar")
        self._side = side
        side.setFixedWidth(224)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(12, 18, 12, 14)
        lay.setSpacing(4)

        self._side_title = QLabel("Bellum Tool")
        self._side_title.setObjectName("AppTitle")
        self._side_sub = QLabel("Gestión de terminales PAX")
        self._side_sub.setObjectName("AppSub")
        lay.addWidget(self._side_title)
        lay.addWidget(self._side_sub)
        lay.addSpacing(10)

        self._nav = QListWidget()
        self._nav.setObjectName("NavList")
        self._nav.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._nav.currentRowChanged.connect(self._on_nav)
        lay.addWidget(self._nav, 1)

        self._theme_btn = QPushButton()
        self._theme_btn.clicked.connect(self._toggle_theme)
        self._settings_btn = QPushButton("  Ajustes")
        settings_ic = icons.icon("settings", self._palette.text)
        if not settings_ic.isNull():
            self._settings_btn.setIcon(settings_ic)
        self._settings_btn.clicked.connect(self._open_settings)
        lay.addWidget(self._theme_btn)
        lay.addWidget(self._settings_btn)
        return side

    # ---- sidebar responsivo -------------------------------------------
    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._apply_responsive(self.width())

    def _apply_responsive(self, width: int) -> None:
        """Colapsa el sidebar a solo iconos en ventanas estrechas, para dejar el
        máximo espacio al contenido (sin él, con 224px fijos, el contenido se
        recortaba por debajo de ~600px de ancho)."""
        compact = width < 640
        if compact == self._compact:
            return
        self._compact = compact
        self._side.setFixedWidth(64 if compact else 224)
        self._side_title.setVisible(not compact)
        self._side_sub.setVisible(not compact)
        for i, page in enumerate(self._pages):
            item = self._nav.item(i)
            if item is not None:
                item.setText("" if compact else f"  {page.title}")
                item.setToolTip(page.title if compact else "")
        self._settings_btn.setText("" if compact else "  Ajustes")
        self._settings_btn.setToolTip("Ajustes" if compact else "")
        self._update_theme_button()

    def _build_main(self) -> QWidget:
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # barra superior
        top = QWidget()
        top.setObjectName("TopBar")
        top.setFixedHeight(64)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(22, 10, 22, 10)
        self._page_title = QLabel("Resumen")
        self._page_title.setObjectName("PageTitle")
        tl.addWidget(self._page_title)
        tl.addStretch(1)

        self._device_combo = QComboBox()
        self._device_combo.setObjectName("DeviceCombo")
        # Encogible: en ventanas estrechas el combo se recorta con elipsis en
        # vez de forzar el ancho de la barra superior.
        self._device_combo.setMinimumWidth(80)
        self._device_combo.setMaximumWidth(260)
        self._device_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._device_combo.currentIndexChanged.connect(self._on_device_selected)
        self._refresh_btn = QPushButton()
        ic = icons.icon("refresh", self._palette.text)
        if not ic.isNull():
            self._refresh_btn.setIcon(ic)
        else:
            self._refresh_btn.setText("⟲")
        self._refresh_btn.setToolTip("Actualizar lista de dispositivos")
        self._refresh_btn.setAccessibleName("Actualizar lista de dispositivos")
        self._refresh_btn.setFixedWidth(40)
        self._refresh_btn.clicked.connect(self._refresh_devices)
        self._wifi_btn = QPushButton("Wi-Fi…")
        self._wifi_btn.setToolTip("Conectar a un terminal por red (ADB inalámbrico)")
        self._wifi_btn.clicked.connect(self._open_wireless)
        tl.addWidget(QLabel("Dispositivo:"))
        tl.addWidget(self._device_combo)
        tl.addWidget(self._refresh_btn)
        tl.addWidget(self._wifi_btn)
        lay.addWidget(top)

        # banner de notificación (oculto salvo cuando hay algo que decir)
        self._banner = QWidget()
        self._banner.setFixedHeight(0)
        self._banner.setVisible(False)
        bl = QHBoxLayout(self._banner)
        bl.setContentsMargins(22, 8, 16, 8)
        bl.setSpacing(8)
        self._banner_icon = QLabel()
        self._banner_icon.setFixedWidth(16)
        bl.addWidget(self._banner_icon)
        self._banner_label = QLabel("")
        self._banner_label.setWordWrap(True)
        bl.addWidget(self._banner_label, 1)
        banner_close = QPushButton("✕")
        banner_close.setFlat(True)
        banner_close.setFixedWidth(28)
        banner_close.setToolTip("Cerrar aviso")
        banner_close.clicked.connect(self._hide_banner)
        bl.addWidget(banner_close)
        lay.addWidget(self._banner)
        self._banner_timer = QTimer(self)
        self._banner_timer.setSingleShot(True)
        self._banner_timer.timeout.connect(self._hide_banner)

        # páginas
        self._stack = QStackedWidget()
        lay.addWidget(self._stack, 1)

        # 5 secciones de nivel superior. Las relacionadas se agrupan en pestañas
        # (TabPage) para acortar el menú sin perder ninguna herramienta.
        self._pages: list = [
            DashboardPage(self._ctx),
            AppsPage(self._ctx),
            FilesPage(self._ctx),
            TabPage(
                self._ctx,
                "Diagnóstico",
                "logs",
                [
                    LogcatPage(self._ctx),
                    ShellPage(self._ctx),
                    ScreenshotPage(self._ctx),
                    SerialConsolePage(self._ctx),
                    DiagToolsPage(self._ctx),
                ],
            ),
            TabPage(
                self._ctx,
                "Mantenimiento",
                "tools",
                [
                    FlashPage(self._ctx),
                    PersonalizePage(self._ctx),
                    DumpPage(self._ctx),
                    RecyclePage(self._ctx),
                    SystoolPage(self._ctx),
                ],
            ),
        ]
        for page in self._pages:
            # Cada página va envuelta en un área desplazable: si no cabe a lo
            # alto/ancho, aparece scroll en vez de recortarse.
            self._stack.addWidget(scroll_wrap(page))
            item = QListWidgetItem(f"  {page.title}")
            nav_icon = icons.icon(page.icon_concept, _NAV_ICON_COLOR, size=18)
            if not nav_icon.isNull():
                item.setIcon(nav_icon)
            self._nav.addItem(item)

        # traza de comandos (siempre visible, informativa, no de alerta)
        self._trace = QLabel("Listo.")
        self._trace.setContentsMargins(22, 6, 22, 6)
        self._trace.setStyleSheet(f"color:{self._palette.text_dim}; font-size:12px;")
        lay.addWidget(self._trace)

        self._nav.setCurrentRow(0)
        self._update_theme_button()
        return container

    # ------------------------------------------------------------------
    def _apply_theme(self) -> None:
        self.setStyleSheet(theme.stylesheet(self._palette))
        self._trace.setStyleSheet(f"color:{self._palette.text_dim}; font-size:12px;")
        self.setWindowIcon(_app_icon(self._palette.accent))

    def _update_theme_button(self) -> None:
        going_light = self._palette.name == "dark"
        concept = "sun" if going_light else "moon"
        full = "  Tema claro" if going_light else "  Tema oscuro"
        self._theme_btn.setText("" if self._compact else full)
        self._theme_btn.setToolTip(full.strip() if self._compact else "")
        ic = icons.icon(concept, self._palette.text)
        if not ic.isNull():
            self._theme_btn.setIcon(ic)

    def _toggle_theme(self) -> None:
        self._palette = theme.LIGHT if self._palette.name == "dark" else theme.DARK
        self._ctx.palette = self._palette
        self._settings.setValue("theme", self._palette.name)
        self._apply_theme()
        self._update_theme_button()
        self.notify(f"Tema {self._palette.name.replace('dark', 'oscuro').replace('light', 'claro')} activado.", "info")

    def _on_nav(self, row: int) -> None:
        if row < 0 or row >= len(self._pages):
            return
        self._stack.setCurrentIndex(row)
        page = self._pages[row]
        self._page_title.setText(page.title)
        page.on_shown()

    def _current_page(self):
        idx = self._stack.currentIndex()
        return self._pages[idx] if 0 <= idx < len(self._pages) else None

    # ---- dispositivos -------------------------------------------------
    def _initial_check(self) -> None:
        if not self._adb.available:
            self.notify(
                "No se encontró el binario pax_adb. Configúralo en Ajustes.", "error"
            )
        self._refresh_devices()

    def _refresh_devices(self) -> None:
        if not self._adb.available:
            return
        self._adb.list_devices(self._on_devices)

    def _on_devices(self, res: CommandResult) -> None:
        devices = Device.parse_devices(res.stdout)
        prev = self._adb.serial

        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        if not devices:
            self._device_combo.addItem("— sin dispositivos —", "")
        else:
            for d in devices:
                suffix = "" if d.online else f"  [{d.state}]"
                self._device_combo.addItem(d.label + suffix, d.serial)

        # restaura selección previa si sigue presente
        target_index = 0
        if prev:
            idx = self._device_combo.findData(prev)
            if idx >= 0:
                target_index = idx
        self._device_combo.setCurrentIndex(target_index)
        self._device_combo.blockSignals(False)

        new_serial = self._device_combo.currentData() or ""
        if new_serial != prev:
            self._adb.serial = new_serial
            self._broadcast_device_change()

    def _on_device_selected(self, _index: int) -> None:
        serial = self._device_combo.currentData() or ""
        if serial != self._adb.serial:
            self._adb.serial = serial
            self._broadcast_device_change()

    def _broadcast_device_change(self) -> None:
        for page in self._pages:
            page.on_device_changed()

    # ---- ajustes ------------------------------------------------------
    def _open_wireless(self) -> None:
        from .wireless_dialog import WirelessDialog

        WirelessDialog(self._ctx, self._refresh_devices, self).exec()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._adb.binary or "", self._fastboot.binary or "", self)
        if dlg.exec():
            self._adb.binary = dlg.adb_path or None
            self._fastboot.binary = dlg.fastboot_path or None
            self._settings.setValue("adb_path", dlg.adb_path)
            self._settings.setValue("fastboot_path", dlg.fastboot_path)
            self.notify("Ajustes guardados.", "ok")
            self._refresh_devices()
            page = self._current_page()
            if page:
                page.refresh()

    # ---- notificaciones ----------------------------------------------
    def notify(self, message: str, level: str = "info") -> None:
        """Banner transitorio bajo la barra superior + traza de estado."""
        bg_attr, fg_attr, icon_concept = _NOTIFY_STYLE.get(level, _NOTIFY_STYLE["info"])
        bg = getattr(self._palette, bg_attr)
        fg = getattr(self._palette, fg_attr)
        self._banner.setStyleSheet(f"background:{bg};")
        self._banner_label.setStyleSheet(f"color:{fg}; font-size:12.5px; font-weight:600;")
        self._banner_icon.clear()
        if icon_concept:
            ic = icons.icon(icon_concept, fg, size=15)
            if not ic.isNull():
                self._banner_icon.setPixmap(ic.pixmap(15, 15))
        self._banner_label.setText(message)
        self._banner.setVisible(True)
        self._banner.setFixedHeight(38)
        self._banner_timer.start(5000)

    def _hide_banner(self) -> None:
        self._banner.setVisible(False)
        self._banner.setFixedHeight(0)
        self._banner_timer.stop()

    def closeEvent(self, event):  # noqa: N802
        self._poll.stop()
        for page in self._pages:
            if hasattr(page, "shutdown"):
                page.shutdown()
        self._adb.shutdown()
        self._fastboot.shutdown()
        super().closeEvent(event)
