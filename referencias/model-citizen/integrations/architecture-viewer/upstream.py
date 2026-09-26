#!/usr/bin/env python3
"""Invoca o visualizador autônomo instalado por meio de sua interface pública."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from harness_core.upstream_viewer import main

if __name__ == "__main__":
    raise SystemExit(main())
