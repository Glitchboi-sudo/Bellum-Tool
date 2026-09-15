"""Iconos: tema de iconos del sistema (FreeDesktop), recoloreados al vuelo.

Usar `QIcon.fromTheme()` en vez de emoji/glifos unicode nos da iconos
realmente nativos: en GNOME salen con trazo Adwaita, en KDE con Breeze, etc.
Si el compositor no expone un tema activo (p. ej. Hyprland sin shell propio,
Qt cae a "hicolor", que está casi vacío), forzamos Adwaita como *fallback*
— nunca si el usuario ya tiene un tema configurado.

Cada concepto tiene una lista de nombres candidatos (spec FreeDesktop +
variantes de temas distintos); se usa el primero que exista. Si ninguno
existe, se devuelve un QIcon nulo y el llamador debe conservar su texto — la
app nunca depende de que un icono concreto esté presente.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

_CANDIDATES: dict[str, tuple[str, ...]] = {
    "dashboard": ("computer-symbolic", "computer"),
    "apps": ("view-grid-symbolic", "view-app-grid-symbolic", "applications-all-symbolic"),
    "folder": ("folder-symbolic", "folder"),
    "camera": ("camera-photo-symbolic", "camera-photo"),
    "logs": ("view-list-symbolic", "text-x-generic-symbolic"),
    "terminal": ("utilities-terminal-symbolic", "utilities-terminal"),
    "flash": ("media-flash-symbolic", "battery-caution-symbolic"),
    "recycle": ("user-trash-symbolic", "edit-clear-all-symbolic"),
    "refresh": ("view-refresh-symbolic", "view-refresh"),
    "settings": ("preferences-system-symbolic", "applications-system-symbolic"),
    "moon": ("weather-clear-night-symbolic",),
    "sun": ("weather-clear-symbolic",),
    "save": ("document-save-symbolic",),
    "open": ("document-open-symbolic", "folder-open-symbolic"),
    "add": ("list-add-symbolic",),
    "remove": ("list-remove-symbolic",),
    "up": ("go-up-symbolic",),
    "down": ("go-down-symbolic",),
    "warning": ("dialog-warning-symbolic",),
    "play": ("media-playback-start-symbolic",),
    "stop": ("media-playback-stop-symbolic",),
    "reboot": ("system-reboot-symbolic", "view-refresh-symbolic"),
    "jump": ("go-jump-symbolic", "go-next-symbolic"),
    "close": ("window-close-symbolic",),
    "ok": ("object-select-symbolic",),
    "device": ("phone-symbolic", "smartphone-symbolic", "computer-symbolic"),
    "tools": ("applications-engineering-symbolic", "applications-utilities-symbolic", "system-run-symbolic"),
    "download": ("folder-download-symbolic", "document-save-symbolic"),
    "run": ("system-run-symbolic", "media-playback-start-symbolic"),
}

_ensured_fallback = False


def _ensure_theme() -> None:
    """Si el DE no expone un tema de iconos, usa Adwaita como fallback."""
    global _ensured_fallback
    if _ensured_fallback:
        return
    _ensured_fallback = True
    name = QIcon.themeName()
    if not name or name.lower() == "hicolor":
        QIcon.setThemeName("Adwaita")


def _recolor(pixmap: QPixmap, color: str) -> QPixmap:
    """Tiñe un pixmap monocromo preservando su canal alfa (SourceIn)."""
    out = QPixmap(pixmap.size())
    out.setDevicePixelRatio(pixmap.devicePixelRatio())
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.drawPixmap(0, 0, pixmap)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(QRect(0, 0, pixmap.width(), pixmap.height()), QColor(color))
    p.end()
    return out


def icon(concept: str, color: str, size: int = 18) -> QIcon:
    """Icono nativo del tema del sistema para `concept`, teñido de `color`.

    Devuelve un QIcon vacío (isNull()) si el tema no tiene ninguno de los
    nombres candidatos — el llamador debe seguir mostrando su texto en ese
    caso, nunca depender solo del icono.
    """
    _ensure_theme()
    for name in _CANDIDATES.get(concept, ()):
        src = QIcon.fromTheme(name)
        if not src.isNull():
            pm = src.pixmap(size, size)
            if not pm.isNull():
                return QIcon(_recolor(pm, color))
    return QIcon()
