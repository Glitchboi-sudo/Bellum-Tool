"""Permite lanzar la app con `python -m bellum` (usado por los paquetes)."""

from bellum.app import main

if __name__ == "__main__":
    raise SystemExit(main())
