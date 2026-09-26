#!/usr/bin/env python3
"""Ponto de entrada de observação, ao lado de hook.py e fora de seu dispatcher; veja harness_core.observer."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from harness_core.observer import main
if __name__ == "__main__":
    main("claude-code")
