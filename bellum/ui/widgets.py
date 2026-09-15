"""Widgets y helpers compartidos por las páginas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.adb import AdbService
from ..core.fastboot import FastbootService
from . import icons
from .theme import Palette


@dataclass
class AppContext:
    """Dependencias compartidas que se inyectan en cada página."""

    adb: AdbService
    fastboot: FastbootService
    palette: Palette
    notify: Callable[[str, str], None]  # (mensaje, nivel: info|ok|warn|error)


class Card(QFrame):
    """Panel con borde redondeado y título opcional."""

    def __init__(self, title: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(16, 14, 16, 16)
        self._outer.setSpacing(10)
        if title:
            lbl = QLabel(title.upper())
            lbl.setObjectName("CardTitle")
            self._outer.addWidget(lbl)

    def body(self) -> QVBoxLayout:
        return self._outer

    def add(self, w: QWidget) -> QWidget:
        self._outer.addWidget(w)
        return w


def badge(text: str, bg: str, fg: str) -> QLabel:
    """Chip de estado: fondo tintado + texto saturado del mismo tono.

    Este patrón ("soft badge") siempre pasa 4.5:1 de contraste con los
    tokens *_bg de Palette; texto blanco sobre un color plano pastel no lo
    hacía (bajaba a ~2-3.6:1 con los tonos ok/warn de esta paleta).
    """
    lbl = QLabel(text)
    lbl.setObjectName("Badge")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(f"#Badge {{ background: {bg}; color: {fg}; }}")
    lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
    return lbl


def state_badge(state: str, pal: Palette) -> QLabel:
    variants = {
        "device": (pal.ok_bg, pal.ok, "ONLINE"),
        "unauthorized": (pal.warn_bg, pal.warn, "NO AUTORIZADO"),
        "offline": (pal.neutral_bg, pal.neutral_fg, "OFFLINE"),
        "bootloader": (pal.neutral_bg, pal.accent, "BOOTLOADER"),
        "recovery": (pal.warn_bg, pal.warn, "RECOVERY"),
    }
    bg, fg, label = variants.get(state, (pal.neutral_bg, pal.neutral_fg, state.upper()))
    return badge(label, bg, fg)


def hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Hint")
    lbl.setWordWrap(True)
    return lbl


def hrow(*widgets: QWidget, spacing: int = 8) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for x in widgets:
        lay.addWidget(x)
    return w


def busy_bar() -> QProgressBar:
    """Barra de progreso indeterminada (min==max==0), fina, para "cargando…"."""
    bar = QProgressBar()
    bar.setRange(0, 0)
    bar.setFixedHeight(4)
    bar.setTextVisible(False)
    return bar


def icon_button(
    concept: str, color: str, text: str = "", tooltip: str = "", object_name: str = ""
) -> QPushButton:
    """Botón con icono del tema del sistema (o solo texto si no hay icono)."""
    btn = QPushButton(text)
    ic = icons.icon(concept, color)
    if not ic.isNull():
        btn.setIcon(ic)
    if object_name:
        btn.setObjectName(object_name)
    btn.setToolTip(tooltip or text)
    if not text:
        btn.setAccessibleName(tooltip)
    return btn


class EmptyState(QWidget):
    """Marcador de "aquí no hay nada": icono + mensaje + acción opcional.

    Se usa dentro de un QStackedWidget junto al contenido real (tabla, lista…)
    y se muestra en vez de dejar el área en blanco cuando no hay datos.
    """

    def __init__(
        self,
        message: str,
        pal: Palette,
        icon_concept: str = "warning",
        action_text: str = "",
        on_action: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(10)

        ic = icons.icon(icon_concept, pal.text_dim, size=32)
        if not ic.isNull():
            icon_lbl = QLabel()
            icon_lbl.setPixmap(ic.pixmap(32, 32))
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(icon_lbl)

        text_lbl = QLabel(message)
        text_lbl.setObjectName("EmptyState")
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_lbl.setWordWrap(True)
        lay.addWidget(text_lbl)

        if action_text and on_action:
            btn = QPushButton(action_text)
            btn.setObjectName("Primary")
            btn.clicked.connect(on_action)
            btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(btn)
            row.addStretch(1)
            lay.addLayout(row)


def stacked_with_empty(content: QWidget, empty: QWidget) -> QStackedWidget:
    """Empaqueta `content` y `empty` en un QStackedWidget (índice 0 / 1)."""
    stack = QStackedWidget()
    stack.addWidget(content)
    stack.addWidget(empty)
    return stack


class Page(QWidget):
    """Base de todas las páginas de navegación.

    Subclases implementan `refresh()` (datos) y opcionalmente reaccionan a
    `on_device_changed()`. `title` e `icon_concept` alimentan la navegación
    (`icon_concept` es una clave de `bellum.ui.icons._CANDIDATES`).
    """

    title: str = "Página"
    icon_concept: str = "dashboard"

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx

    # Hooks — las subclases sobrescriben lo que necesiten.
    def refresh(self) -> None:  # datos del dispositivo actual
        ...

    def on_device_changed(self) -> None:
        self.refresh()

    def on_shown(self) -> None:
        self.refresh()


class TabPage(Page):
    """Agrupa varias sub-páginas (Page) en un QTabWidget.

    Se comporta como una Page normal ante la ventana principal: expone
    `title`/`icon_concept` para la navegación lateral y reenvía los hooks del
    ciclo de vida a las sub-páginas (device change a todas; refresh/on_shown
    solo a la pestaña activa, de forma perezosa).
    """

    def __init__(
        self,
        ctx: AppContext,
        title: str,
        icon_concept: str,
        subpages: list[Page],
        parent: QWidget | None = None,
    ):
        super().__init__(ctx, parent)
        self.title = title
        self.icon_concept = icon_concept
        self._subpages = subpages

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        for sp in subpages:
            self._tabs.addTab(sp, sp.title)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

    def _on_tab_changed(self, index: int) -> None:
        w = self._tabs.widget(index)
        if isinstance(w, Page):
            w.on_shown()

    # --- ciclo de vida reenviado a las sub-páginas ---
    def refresh(self) -> None:
        w = self._tabs.currentWidget()
        if isinstance(w, Page):
            w.refresh()

    def on_shown(self) -> None:
        w = self._tabs.currentWidget()
        if isinstance(w, Page):
            w.on_shown()

    def on_device_changed(self) -> None:
        # A todas: p. ej. Registros debe cortar el streaming aunque no sea la
        # pestaña visible.
        for sp in self._subpages:
            sp.on_device_changed()

    def shutdown(self) -> None:
        for sp in self._subpages:
            if hasattr(sp, "shutdown"):
                sp.shutdown()
