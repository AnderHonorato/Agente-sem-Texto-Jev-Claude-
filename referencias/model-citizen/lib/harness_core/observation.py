"""Registro do ponto de entrada de observação, e a instalação do braço nu que carrega só ele (AD-23).

O registrador em si é `harness_core.observer`. Seu registro lê quais eventos cada runtime dispara
a partir de `lifecycle.EVENTS`, a mesma declaração da qual `hook.py` também é registrado, então os
dois pontos de entrada não podem discordar sobre eventos. Nada aqui roteia através do dispatcher.
"""
import json
import shlex
import shutil
from pathlib import Path

from harness_core import lifecycle, observer

MARKER = "# harness:observe-"
TIMEOUT = 5
# O arquivo de runtime no qual cada instalação nua escreve seu registro.
SETTINGS_FILE = {"claude-code": "settings.json", "codex": "hooks.json"}
ENTRY = "observe.py"


def events(runtime):
    return lifecycle.EVENTS.get(runtime, lifecycle.BASE_EVENTS)


def hooks_for(command, runtime):
    return {event: [{"hooks": [{"type": "command", "command": command + " " + MARKER + event.lower(),
                                "timeout": TIMEOUT}]}]
            for event in events(runtime)}


def registration(root, runtime):
    """O bloco de hooks que registra `adapters/<runtime>/observe.py` para cada evento que dispara."""
    if runtime not in SETTINGS_FILE:
        raise ValueError("unknown runtime")
    script = Path(root) / "adapters" / runtime / "observe.py"
    return {"hooks": hooks_for("python3 " + shlex.quote(str(script)), runtime)}


def bare_install(dest, runtime="claude-code"):
    """Escreve toda a pegada do harness do braço nu em `dest` e retorna o caminho das settings.

    A pegada é o registrador, copiado sozinho como `observe.py`, e o arquivo de hook do runtime
    registrando-o com `--profile bare`. Nada mais do harness está presente: nenhum dispatcher,
    nenhuma política, regra, stance ou skill.
    """
    if runtime not in SETTINGS_FILE:
        raise ValueError("unknown runtime")
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    entry = dest / ENTRY
    shutil.copyfile(observer.__file__, str(entry))
    command = " ".join(["python3", shlex.quote(str(entry)), "--runtime", runtime, "--profile", "bare"])
    settings = dest / SETTINGS_FILE[runtime]
    settings.write_text(json.dumps({"hooks": hooks_for(command, runtime)}, indent=2, sort_keys=True) + "\n")
    return settings


def install_files(dest):
    """Todo arquivo sob `dest`, relativo a ele, ordenado."""
    dest = Path(dest)
    return sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())
