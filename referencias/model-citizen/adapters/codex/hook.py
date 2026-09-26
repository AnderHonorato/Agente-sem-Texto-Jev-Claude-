#!/usr/bin/env python3
"""Ponto de entrada nativo do ciclo de vida; a política compartilhada mora em harness_core.lifecycle."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from harness_core.lifecycle import main
if __name__ == "__main__":
    main("codex")
