#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hook de Stop: roda o próprio portão do repositório e recusa terminar enquanto está vermelho.

Opt-in por repositório — o portão é o bloco cercado sob o cabeçalho `## Gate` do `AGENTS.md` do
repositório, executado junto num único shell. Um repositório sem esse bloco fica intocado. Só
pastas confiáveis: o bloco é texto próprio de um repositório, então só roda onde o diálogo de
confiança de pasta do Claude Code foi aceito (a flag `hasTrustDialogAccepted` que ele registra
por projeto), o mesmo consentimento que restringe os hooks do `.claude/settings.json` de um
repositório, ou onde a raiz está listada em ~/.config/agent-harness/trusted.txt por
`harness trust`. Limitado: depois de MAX_BLOCKS bloqueios consecutivos o turno é liberado, para
que um portão que nunca consegue passar não consiga prender uma sessão. A contagem é mantida por
sessão, então duas sessões parando no mesmo checkout nunca resetam a contagem uma da outra; uma
sessão silenciosa por STALE_SECONDS é esquecida. Um timeout libera o turno como não verificado;
erros inesperados bloqueiam. Nenhum dos dois registra sucesso.
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MAX_BLOCKS = 8
STALE_SECONDS = 24 * 3600
BUDGET_SECONDS = 240
TAIL_LINES = 30
GATE_FILES = ("AGENTS.md", "CLAUDE.md")
STATE = Path.home() / ".local" / "state" / "agent-harness" / "stop-gate"
TRUSTED = Path.home() / ".config" / "agent-harness" / "trusted.txt"


_LOG = []


def decisions():
    """O log de decisão irmão, ou None. Um log que não carrega custa nada além das suas próprias linhas."""
    if not _LOG:
        module = None
        try:
            path = Path(__file__).resolve().parent / "decisions.py"
            spec = importlib.util.spec_from_file_location("harness_decisions", str(path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            module = None
        _LOG.append(module)
    return _LOG[0]


def log_gate(payload, root, commands, answer, outcome):
    """Registra com o que este evento Stop foi respondido, e como o portão se desenrolou.

    Ambos os registros são escritos aqui porque ambos os fatos são conhecidos aqui: o hook roda o
    portão em si, então o resultado não espera por um evento posterior. A entrada julgada é o
    próprio bloco de portão do repositório — o texto que este hook decidiu rodar — e nunca a
    mensagem final do turno.

    A alegação em que o turno terminou é a do transcript, não a do payload: um evento Stop não
    carrega texto de assistente, então o log lê um final limitado do arquivo que o evento nomeia.
    Essa leitura só acontece sob `telemetry.completion_claim`, que está desligado, porque é o
    único campo no log que guarda prosa do modelo. Os nomes de ambos os runtimes para o arquivo
    são aceitos.
    """
    module = decisions()
    if module is None:
        return
    payload = payload if isinstance(payload, dict) else {}
    text = str(root) + "\n" + "\n".join(commands)
    transcript = (payload.get("transcript_path") or payload.get("rollout_path")
                  or payload.get("session_path") or "")
    identity = module.record("stop-gate", answer, text, payload, transcript=transcript)
    if identity and outcome is not None:
        module.observe(identity, outcome, "stop-gate", payload.get("session_id") or "")


def git(root, *args):
    try:
        out = subprocess.run(["git", "-C", root, *args],
                             capture_output=True, text=True, timeout=10)
    except Exception:
        return ""
    return out.stdout if out.returncode == 0 else ""


def git_root(cwd):
    root = git(cwd, "rev-parse", "--show-toplevel").strip()
    return root or None


def claude_config():
    """O arquivo de estado por usuário do Claude Code, honrando CLAUDE_CONFIG_DIR."""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(config_dir) if config_dir else Path.home()) / ".claude.json"


def listed_roots():
    """Raízes registradas por `harness trust`, como escritas e resolvidas."""
    try:
        lines = TRUSTED.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    roots = set()
    for ln in lines:
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            roots.update((ln, str(Path(ln).resolve())))
    return roots


def trusted(root, cwd):
    """True quando o diálogo de confiança de pasta foi aceito para o diretório de trabalho, a
    raiz do repositório, ou um diretório entre eles, ou quando `harness trust` listou a raiz."""
    if os.environ.get("HARNESS_RUNTIME") == "codex":
        return bool(listed_roots() & {str(Path(root)), str(Path(root).resolve())})
    try:
        projects = json.loads(claude_config().read_text(encoding="utf-8")).get("projects") or {}
    except Exception:
        projects = {}
    if not isinstance(projects, dict):
        projects = {}
    top = Path(root).resolve()
    if listed_roots() & {str(Path(root)), str(top)}:
        return True
    keys = {str(Path(root)), str(top)}
    path = Path(cwd)
    while path.resolve() == top or top in path.resolve().parents:
        keys.update((str(path), str(path.resolve())))  # diretórios temp com symlink registram qualquer uma das formas
        if path.resolve() == top:
            break
        path = path.parent
    return any(isinstance(projects.get(k), dict) and projects[k].get("hasTrustDialogAccepted") is True
               for k in keys)


def gate_file(root):
    for name in GATE_FILES:
        path = Path(root) / name
        if path.is_file():
            return path
    return None


def gate_commands(root):
    path = gate_file(root)
    if path is None:
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    start = None
    for i, raw in enumerate(lines):
        if raw.strip().lower() == "## gate":
            start = i + 1
            break
    if start is None:
        return []
    commands = []
    fenced = False
    for raw in lines[start:]:
        text = raw.strip()
        if text.startswith("```"):
            if fenced:
                break
            fenced = True
        elif not fenced:
            if text.startswith("#"):  # o próximo cabeçalho, sem bloco algum entre eles
                break
        elif text and not text.startswith("#"):
            commands.append(text)
    return commands


def tree_hash(root):
    digest = hashlib.sha256()
    digest.update(("gate-v2:" + str(Path(root).resolve())).encode())
    def checked(*args):
        return subprocess.run(["git", "-C", root, *args], capture_output=True,
                              check=True, timeout=10).stdout
    for args in (("rev-parse", "HEAD"), ("status", "--porcelain", "-z"),
                 ("diff", "--binary"), ("diff", "--cached", "--binary")):
        digest.update(hashlib.sha256(checked(*args)).digest())
    for name in checked("ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
        if not name:
            continue
        path = Path(root) / os.fsdecode(name)
        digest.update(name + b"\0")
        if path.is_symlink():
            digest.update(os.fsencode(os.readlink(path)))
        elif path.is_file():
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
    digest.update("\n".join(gate_commands(root)).encode())
    digest.update(str(BUDGET_SECONDS).encode())
    return digest.hexdigest()


def state_path(root):
    return STATE / (hashlib.sha256(root.encode("utf-8")).hexdigest() + ".json")


def read_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_state(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".gate-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run_gate(root, commands):
    """O primeiro comando vermelho como (command, exit code, output), ou None quando todos passam."""
    cmd = "\n".join(commands)
    out = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", cmd], cwd=root,
                         capture_output=True, text=True, timeout=BUDGET_SECONDS)
    if out.returncode != 0:
        return cmd, out.returncode, (out.stdout or "") + (out.stderr or "")
    return None


def reason(path, cmd, code, output):
    tail = "\n".join(output.splitlines()[-TAIL_LINES:]).strip()
    return (
        f"The gate in {path.name} is red: `{cmd}` exited {code}.\n\n"
        f"{tail}\n\n"
        "That command is the check block this repository defines under `## Gate`, run at the end "
        "of a turn once files have changed. Fix it and finish, or say why it cannot pass."
    )


def live_sessions(state, now):
    """As contagens de bloqueio por sessão em `state`, sem entradas silenciosas por STALE_SECONDS."""
    sessions = state.get("sessions")
    if not isinstance(sessions, dict):
        return {}
    kept = {}
    for session, entry in sessions.items():
        try:
            blocks, seen = int(entry["blocks"]), float(entry["seen"])
        except (KeyError, TypeError, ValueError):
            continue
        if now - seen < STALE_SECONDS:
            kept[session] = {"blocks": blocks, "seen": seen}
    return kept


def release(path, session, note):
    # Relê: o portão pode rodar por minutos, e outra sessão pode ter registrado bloqueios nesse meio tempo.
    sessions = live_sessions(read_state(path), time.time())
    sessions.pop(session, None)
    write_state(path, {"green_hash": None, "status": "unverified", "reason": note,
                       "sessions": sessions})
    sys.stderr.write("stop-gate: " + note + "\n")


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    cwd = payload.get("cwd") or os.getcwd()
    root = git_root(cwd)
    if not root:
        return
    commands = gate_commands(root)
    if not commands:
        return
    if not trusted(root, cwd):
        sys.stderr.write("stop-gate: folder not trusted in Claude Code and not listed by "
                         "`citizen trust`; gate skipped. Run `citizen trust .` in this folder to "
                         "let it run the repository's own checks.\n")
        log_gate(payload, root, commands, "skipped", "untrusted")
        return

    current = tree_hash(root)
    path = state_path(root)
    state = read_state(path)
    if state.get("green_hash") == current:
        log_gate(payload, root, commands, "skipped", "passed")
        return

    session = payload.get("session_id") or ""
    try:
        failure = run_gate(root, commands)
    except subprocess.TimeoutExpired:
        release(path, session, f"gate ran past {BUDGET_SECONDS}s; letting the turn end")
        log_gate(payload, root, commands, "released", "timeout")
        return
    if failure is None:
        if tree_hash(root) != current:
            release(path, session, "working tree changed during the gate; result unverified")
            log_gate(payload, root, commands, "released", "unverified")
            return
        write_state(path, {"green_hash": current, "status": "passed", "sessions": {}})
        log_gate(payload, root, commands, "released", "passed")
        return

    now = time.time()
    sessions = live_sessions(read_state(path), now)
    blocks = sessions.get(session, {}).get("blocks", 0) + 1
    if blocks >= MAX_BLOCKS:
        release(path, session, f"released after {MAX_BLOCKS} blocks; gate still red")
        log_gate(payload, root, commands, "released", "failed")
        return
    sessions[session] = {"blocks": blocks, "seen": now}
    write_state(path, {"green_hash": None, "status": "failed", "sessions": sessions})
    log_gate(payload, root, commands, "blocked", "failed")
    cmd, code, output = failure
    print(json.dumps({"decision": "block", "reason": reason(gate_file(root), cmd, code, output)}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"decision": "block", "reason": "Gate is unverified: " + str(exc)}))
