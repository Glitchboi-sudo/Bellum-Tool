"""Diálogo de ajustes: rutas de los binarios pax_adb y fastboot."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.adb import find_pax_adb
from ..core.fastboot import find_fastboot


class SettingsDialog(QDialog):
    def __init__(self, adb_path: str, fastboot_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustes")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._adb = QLineEdit(adb_path)
        self._fb = QLineEdit(fastboot_path)
        form.addRow("Binario pax_adb:", self._with_browse(self._adb))
        form.addRow("Binario fastboot:", self._with_browse(self._fb))
        layout.addLayout(form)

        self._detect_status = QLabel("")
        self._detect_status.setObjectName("Hint")
        self._detect_status.setWordWrap(True)
        layout.addWidget(self._detect_status)

        detect_row = QHBoxLayout()
        detect_btn = QPushButton("Auto-detectar")
        detect_btn.setToolTip("Buscar pax_adb y fastboot en el PATH y rutas conocidas")
        detect_btn.clicked.connect(self._auto_detect)
        detect_row.addWidget(detect_btn)
        detect_row.addStretch(1)
        layout.addLayout(detect_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _auto_detect(self) -> None:
        adb = find_pax_adb()
        fb = find_fastboot()
        if adb:
            self._adb.setText(adb)
        if fb:
            self._fb.setText(fb)
        msgs = [
            f"pax_adb: {adb}" if adb else "pax_adb: no encontrado",
            f"fastboot: {fb}" if fb else "fastboot: no encontrado",
        ]
        self._detect_status.setText("Detectado —  " + "  ·  ".join(msgs)
                                    + "\nPulsa «Guardar» para aplicarlo.")

    def _with_browse(self, line: QLineEdit) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton("Examinar…")

        def pick():
            path, _ = QFileDialog.getOpenFileName(self, "Seleccionar binario", line.text() or "/")
            if path:
                line.setText(path)

        btn.clicked.connect(pick)
        lay.addWidget(line, 1)
        lay.addWidget(btn)
        return w

    @property
    def adb_path(self) -> str:
        return self._adb.text().strip()

    @property
    def fastboot_path(self) -> str:
        return self._fb.text().strip()
