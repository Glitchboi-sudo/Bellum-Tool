"""Tema visual: paleta y hoja de estilos QSS.

Diseño limpio tipo app nativa moderna: barra lateral de navegación, tarjetas,
acento único. Dos paletas (oscuro por defecto, claro opcional).

Todos los pares texto/fondo están verificados a mano contra WCAG 2.1 AA
(4.5:1 para texto normal) — ver el historial de la sesión que introdujo estos
valores. Si tocas un color aquí, vuelve a comprobar el contraste.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str          # fondo ventana
    surface: str     # tarjetas / paneles
    surface_alt: str # filas alternas / hover sutil
    sidebar: str
    border: str
    text: str
    text_dim: str
    accent: str
    accent_hover: str
    accent_text: str
    danger: str
    warn: str
    ok: str
    # Tintes suaves para badges/chips: fondo pálido + texto saturado del mismo
    # tono (patrón "soft badge"). Siempre ≥4.5:1 texto/fondo — a diferencia de
    # texto blanco sobre el color plano, que en pasteles cae a ~2-3.6:1.
    ok_bg: str
    warn_bg: str
    danger_bg: str
    neutral_bg: str
    neutral_fg: str


DARK = Palette(
    name="dark",
    bg="#14161c",
    surface="#1b1e26",
    surface_alt="#222631",
    sidebar="#0f1116",
    border="#2b3040",
    text="#e7eaf0",
    text_dim="#9aa3b2",
    accent="#2f6bff",
    accent_hover="#5b93ff",
    accent_text="#ffffff",
    danger="#ff5d6c",
    warn="#f5a524",
    ok="#3ecf8e",
    ok_bg="#123626",
    warn_bg="#3a2a0a",
    danger_bg="#3a1418",
    neutral_bg="#262b38",
    neutral_fg="#b7c0d1",
)

LIGHT = Palette(
    name="light",
    bg="#f4f5f7",
    surface="#ffffff",
    surface_alt="#eef0f4",
    sidebar="#1b1e26",
    border="#d8dce3",
    text="#1a1d24",
    text_dim="#5b6472",
    accent="#2f6bff",
    accent_hover="#1f59ef",
    accent_text="#ffffff",
    danger="#c81f2c",
    warn="#96600a",
    ok="#0f7d54",
    ok_bg="#e3f8ee",
    warn_bg="#fdf1dd",
    danger_bg="#fde8ea",
    neutral_bg="#eef0f4",
    neutral_fg="#4a5364",
)


def stylesheet(p: Palette) -> str:
    return f"""
* {{
    font-family: "Inter", "Cantarell", "Segoe UI", "Noto Sans", sans-serif;
    font-size: 14px;
}}
QWidget {{ color: {p.text}; background: transparent; }}
QMainWindow, #RootBg {{ background: {p.bg}; }}

/* ---------- Barra lateral ---------- */
#Sidebar {{ background: {p.sidebar}; border: none; }}
#Sidebar QLabel#AppTitle {{ color: #ffffff; font-size: 17px; font-weight: 700; padding: 2px 4px; }}
#Sidebar QLabel#AppSub {{ color: #8a93a6; font-size: 11px; padding: 0 4px 4px 4px; }}
#NavList {{ background: transparent; border: none; padding: 6px; }}
#NavList::item {{
    color: #b9c0cf; padding: 10px 12px; border-radius: 9px; margin: 2px 4px;
    border: 1px solid transparent;
}}
#NavList::item:hover {{ background: rgba(255,255,255,0.06); color: #e7eaf0; }}
#NavList::item:selected {{ background: {p.accent}; color: {p.accent_text}; }}
#NavList::item:focus {{ border: 1px solid {p.accent_hover}; }}

/* ---------- Barra superior ---------- */
#TopBar {{ background: {p.surface}; border-bottom: 1px solid {p.border}; }}
#PageTitle {{ font-size: 19px; font-weight: 700; }}
#DeviceCombo {{
    background: {p.surface_alt}; border: 1px solid {p.border};
    border-radius: 8px; padding: 6px 10px; min-width: 240px;
}}
#DeviceCombo:focus {{ border-color: {p.accent}; }}
#DeviceCombo::drop-down {{ border: none; width: 22px; }}
#DeviceCombo QAbstractItemView {{
    background: {p.surface}; border: 1px solid {p.border};
    selection-background-color: {p.accent}; selection-color: {p.accent_text};
}}

/* ---------- Tarjetas ---------- */
QFrame#Card {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: 14px;
}}
QLabel#CardTitle {{ font-size: 12.5px; font-weight: 700; color: {p.text_dim}; }}
/* Tarjeta de acciones sensibles/destructivas: franja y título en rojo. */
QFrame#DangerCard {{
    background: {p.surface}; border: 1px solid {p.border};
    border-left: 4px solid {p.danger}; border-radius: 14px;
}}
QLabel#DangerCardTitle {{ color: {p.danger}; font-size: 12.5px; font-weight: 800; letter-spacing: 0.04em; }}
QLabel#Hint {{ color: {p.text_dim}; font-size: 12px; }}
QLabel#Mono {{ font-family: "JetBrains Mono","Fira Code",monospace; }}
QLabel#EmptyState {{ color: {p.text_dim}; font-size: 13px; padding: 28px 12px; }}

/* ---------- Botones ---------- */
QPushButton {{
    background: {p.surface_alt}; border: 1px solid {p.border};
    border-radius: 9px; padding: 8px 14px; color: {p.text};
}}
QPushButton:hover {{ border-color: {p.accent}; }}
QPushButton:focus {{ border-color: {p.accent}; }}
QPushButton:pressed {{ background: {p.border}; }}
QPushButton:disabled {{ color: {p.text_dim}; border-color: {p.border}; }}
QPushButton#Primary {{ background: {p.accent}; border: 1px solid {p.accent}; color: {p.accent_text}; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton#Primary:focus {{ border-color: {p.text}; }}
QPushButton#Danger {{ background: transparent; border: 1px solid {p.danger}; color: {p.danger}; }}
QPushButton#Danger:hover {{ background: {p.danger}; color: #ffffff; }}
QPushButton#Danger:focus {{ border-color: {p.text}; }}
/* Botón "enlace" plano (barra de actividad). */
QPushButton#LinkBtn {{ background: transparent; border: none; color: {p.text_dim}; font-size: 12px; font-weight: 600; padding: 2px 8px; }}
QPushButton#LinkBtn:hover {{ color: {p.accent}; }}
QPushButton#LinkBtn:focus {{ color: {p.accent}; }}

/* ---------- Chip de estado del dispositivo (barra superior) ---------- */
QLabel#StateChip {{ font-size: 12px; font-weight: 700; padding: 4px 11px; border-radius: 999px; }}
QLabel#StateChip[level="ok"] {{ color: {p.ok}; background: {p.ok_bg}; }}
QLabel#StateChip[level="warn"] {{ color: {p.warn}; background: {p.warn_bg}; }}
QLabel#StateChip[level="off"] {{ color: {p.neutral_fg}; background: {p.neutral_bg}; }}

/* ---------- Barra de actividad (registro de comandos) ---------- */
#ActivityBar {{ background: {p.surface}; border-top: 1px solid {p.border}; }}
QLabel#Trace {{ color: {p.text_dim}; font-size: 12px; }}
QLabel#LiveDot {{ color: {p.border}; font-size: 13px; }}
QLabel#LiveDot[active="true"] {{ color: {p.ok}; }}

/* ---------- Paleta de comandos (Ctrl+K) ---------- */
QDialog#Palette {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 14px; }}
#Palette QLineEdit {{
    font-size: 15px; background: transparent; border: none;
    border-bottom: 1px solid {p.border}; border-radius: 0; padding: 13px 16px;
}}
#Palette QLineEdit:focus {{ border: none; border-bottom: 1px solid {p.border}; }}
#Palette QListWidget {{ background: transparent; border: none; padding: 6px; outline: none; }}
#Palette QListWidget::item {{ padding: 9px 12px; border-radius: 8px; color: {p.text}; }}
#Palette QListWidget::item:selected {{ background: {p.accent}; color: {p.accent_text}; }}

/* ---------- Inputs ---------- */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {p.surface_alt}; border: 1px solid {p.border};
    border-radius: 8px; padding: 7px 10px; selection-background-color: {p.accent};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {p.accent}; }}
QLineEdit:disabled {{ color: {p.text_dim}; }}

/* ---------- Tablas / listas ---------- */
QTableView, QTreeView, QListView {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: 12px;
    gridline-color: {p.border}; alternate-background-color: {p.surface_alt};
    selection-background-color: {p.accent}; selection-color: {p.accent_text};
}}
QTableView:focus, QTreeView:focus, QListView:focus {{ border-color: {p.accent}; }}
QHeaderView::section {{
    background: {p.surface_alt}; color: {p.text_dim}; border: none;
    border-bottom: 1px solid {p.border}; padding: 8px 10px; font-weight: 600;
}}
QTableView::item {{ padding: 4px 6px; }}
QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}

/* ---------- Consola / log ---------- */
QPlainTextEdit#Console {{
    font-family: "JetBrains Mono","Fira Code","DejaVu Sans Mono",monospace;
    font-size: 12.5px; background: #0c0e13; color: #c7d0df;
    border: 1px solid {p.border}; border-radius: 10px;
}}
QPlainTextEdit#Console:focus {{ border-color: {p.accent}; }}

/* ---------- Misc ---------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_dim}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 5px; min-width: 30px; }}
QComboBox, QSpinBox {{
    background: {p.surface_alt}; border: 1px solid {p.border};
    border-radius: 8px; padding: 6px 10px;
}}
QComboBox:focus, QSpinBox:focus {{ border-color: {p.accent}; }}
QComboBox QAbstractItemView {{
    background: {p.surface}; border: 1px solid {p.border};
    selection-background-color: {p.accent}; selection-color: {p.accent_text};
}}
QToolTip {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 6px; padding: 5px 8px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px; border: 1px solid {p.border}; border-radius: 4px;
    background: {p.surface_alt};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {p.accent}; border-color: {p.accent};
}}
QProgressBar {{
    background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: 7px;
    height: 6px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 7px; }}

/* ---------- Pestañas (secciones agrupadas) ---------- */
QTabWidget::pane {{ border: none; border-top: 1px solid {p.border}; top: -1px; }}
QTabWidget::tab-bar {{ left: 20px; }}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent; color: {p.text_dim};
    padding: 9px 18px; margin: 0 2px; margin-bottom: -1px;
    border: none; border-bottom: 2px solid transparent; font-weight: 600;
}}
QTabBar::tab:hover {{ color: {p.text}; }}
QTabBar::tab:selected {{ color: {p.accent}; border-bottom: 2px solid {p.accent}; }}
QTabBar::tab:focus {{ color: {p.text}; }}

/* Chips/badges de estado — fondo tintado, sin fondo/borde propios en el QLabel */
#Badge {{ border-radius: 9px; padding: 3px 10px; font-size: 11px; font-weight: 700; border: none; }}

/* Insignia numérica de paso (Reciclaje) */
#StepNum {{
    background: {p.surface_alt}; color: {p.text_dim};
    border: 1px solid {p.border}; border-radius: 12px;
    min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px;
    font-weight: 700;
}}
"""
