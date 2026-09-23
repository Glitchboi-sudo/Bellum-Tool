"""Paleta de comandos (Ctrl+K): salto rápido a cualquiera de las herramientas.

Un diálogo ligero y sin estado: recibe una lista de `PaletteEntry` (etiqueta,
sección y una función que ejecuta la navegación) y deja filtrar por texto y
elegir con teclado. No conoce la ventana principal — esta le pasa las entradas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


@dataclass
class PaletteEntry:
    label: str          # nombre de la herramienta ("Volcado")
    section: str        # sección a la que pertenece ("Mantenimiento"), o ""
    activate: Callable[[], None]

    @property
    def haystack(self) -> str:
        return f"{self.label} {self.section}".lower()


class CommandPalette(QDialog):
    _ROLE = Qt.ItemDataRole.UserRole

    def __init__(self, entries: list[PaletteEntry], parent=None):
        super().__init__(parent)
        self._entries = entries
        self.setObjectName("Palette")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Ir a una herramienta…")
        self._search.textChanged.connect(self._filter)
        self._search.installEventFilter(self)
        lay.addWidget(self._search)

        self._list = QListWidget()
        self._list.setUniformItemSizes(True)
        self._list.itemActivated.connect(self._activate_item)
        self._list.itemClicked.connect(self._activate_item)
        lay.addWidget(self._list)

        self._filter("")
        self._search.setFocus()

    # ------------------------------------------------------------------
    def _filter(self, text: str) -> None:
        q = text.strip().lower()
        self._list.clear()
        for e in self._entries:
            if q and q not in e.haystack:
                continue
            label = e.label if not e.section else f"{e.label}   ·   {e.section}"
            item = QListWidgetItem(label)
            item.setData(self._ROLE, e)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        # La lista crece con el contenido, hasta un máximo.
        rows = min(self._list.count(), 8)
        self._list.setFixedHeight(max(rows, 1) * 38 + 8)

    def _move(self, delta: int) -> None:
        count = self._list.count()
        if not count:
            return
        row = (self._list.currentRow() + delta) % count
        self._list.setCurrentRow(row)

    def _activate_item(self, item: QListWidgetItem) -> None:
        entry: PaletteEntry = item.data(self._ROLE)
        self.accept()
        if entry is not None:
            entry.activate()

    def _activate_current(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            self._activate_item(item)

    # Flechas / Enter mientras el foco está en el buscador.
    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self._search and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                self._move(1)
                return True
            if key == Qt.Key.Key_Up:
                self._move(-1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._activate_current()
                return True
        return super().eventFilter(obj, event)
