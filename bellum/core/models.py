"""Modelos de datos del dominio (sin dependencias de Qt)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Device:
    """Un terminal visto por `pax_adb devices -l`."""

    serial: str
    state: str  # device | unauthorized | offline | bootloader | recovery ...
    qualifiers: dict[str, str] = field(default_factory=dict)

    @property
    def online(self) -> bool:
        return self.state == "device"

    @property
    def model(self) -> str:
        return (
            self.qualifiers.get("model")
            or self.qualifiers.get("device")
            or self.qualifiers.get("product")
            or self.serial
        )

    @property
    def label(self) -> str:
        model = self.qualifiers.get("model", "")
        model = model.replace("_", " ").strip()
        if model and model.lower() != self.serial.lower():
            return f"{model} · {self.serial}"
        return self.serial

    @staticmethod
    def parse_devices(output: str) -> list["Device"]:
        """Parsea la salida de `adb devices -l`.

        Formato por línea:  <serial>\t<state>            (devices)
                     o:      <serial> <state> key:val key:val ... (devices -l)
        """
        devices: list[Device] = []
        for raw in output.splitlines():
            line = raw.strip()
            if not line or line.startswith("List of devices"):
                continue
            if line.startswith("*") or line.startswith("adb "):
                continue  # mensajes del daemon ("* daemon started successfully")
            parts = line.split()
            if len(parts) < 2:
                continue
            serial, state = parts[0], parts[1]
            quals: dict[str, str] = {}
            for token in parts[2:]:
                if ":" in token:
                    k, _, v = token.partition(":")
                    quals[k] = v
            devices.append(Device(serial=serial, state=state, qualifiers=quals))
        return devices


@dataclass(frozen=True)
class Package:
    """Un paquete instalado (`pm list packages`)."""

    name: str
    apk_path: str = ""
    system: bool = False
    enabled: bool = True
    installer: str = ""

    @property
    def third_party(self) -> bool:
        return not self.system


# Paquetes PAX conocidos, solo para *etiquetar/advertir* en la UI. El toolkit
# NO trae ninguna macro que los elimine automáticamente: es información para que
# el usuario sepa qué está tocando antes de actuar sobre su propio equipo.
KNOWN_PAX_PACKAGES: dict[str, str] = {
    "com.pax.ipp.neptune": "PAX Neptune — núcleo de pago seguro (crítico)",
    "com.pax.daemon": "PAX daemon del sistema (crítico)",
    "com.pax.otaupdate": "Actualizaciones OTA de PAX",
    "com.pax.appstore": "PAX App Store",
    "com.pax.market.android.pax": "PAXSTORE cliente",
    "com.pax.settings": "Ajustes PAX",
    "com.pax.launcher": "Lanzador PAX",
}
