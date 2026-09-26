#!/usr/bin/env python3
"""O caminho de hook somente-observação: uma linha de ledger por evento de hook, e nada mais (AD-23).

A observação roda em todo braço de uma comparação, o nu incluído, então nunca deve mudar o que o
modelo ou o usuário veem. Este caminho, portanto, não imprime nada, não adiciona contexto, não
retorna decisão alguma e sai com 0 em toda entrada. Qualquer falha, incluindo um ledger que não
pode ser escrito, vai para um log de erro local ao lado do ledger, e uma falha ao escrever esse
log é descartada.

Uma linha carrega o nome do evento, o runtime, o id de sessão, o nome da ferramenta onde o evento
tem um, e a fingerprint do perfil. Nunca carrega um prompt, uma entrada de ferramenta, um
resultado de ferramenta ou qualquer outro corpo de mensagem.

O arquivo é só biblioteca padrão e não importa nada do harness, porque uma instalação de braço nu
o copia sozinho (`harness_core.observation.bare_install`). Rodado como script, recebe
`--runtime <name>` e `--profile <fingerprint>`; uma instalação nua passa `--profile bare`, que é
o nome que as linhas do braço nu carregam, já que ele não carrega perfil algum para resumir.
"""
import datetime
import importlib.util
import json
import os
import sys
from pathlib import Path

SCHEMA_KEY = "schema_version"
SCHEMA_VERSION = 1
FINGERPRINT_KEY = "profile_fingerprint"
LEDGER = "observation.jsonl"
ERRORS = "observation.errors.jsonl"


def state_dir(env=None):
    env = os.environ if env is None else env
    home = env.get("HARNESS_HOME") or env.get("HOME") or str(Path.home())
    return Path(home) / ".local" / "state" / "agent-harness"


def ledger_path(env=None):
    return state_dir(env) / LEDGER


def errors_path(env=None):
    return state_dir(env) / ERRORS


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def profile_fingerprint(profile=None):
    """O perfil nomeado, senão o digest do `posture.py` neste checkout, senão None.

    None é a resposta sempre que o resolvedor está ausente ou falha: uma fingerprint adivinhada
    atribuiria uma linha a um perfil que não a produziu.
    """
    if profile:
        return profile
    location = Path(os.path.realpath(__file__)).parents[2] / "policy" / "hooks" / "posture.py"
    try:
        spec = importlib.util.spec_from_file_location("harness_observer_posture", str(location))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.fingerprint()
    except Exception:
        return None


def row_for(payload, runtime, profile=None):
    """A linha de ledger para um evento: só identificadores, nunca um corpo."""
    row = {"ts": now(), "runtime": runtime,
           "event": payload.get("hook_event_name") if isinstance(payload, dict) else None,
           "session_id": payload.get("session_id") if isinstance(payload, dict) else None}
    tool = payload.get("tool_name") if isinstance(payload, dict) else None
    if tool:
        row["tool_name"] = tool
    row[SCHEMA_KEY] = SCHEMA_VERSION
    row[FINGERPRINT_KEY] = profile_fingerprint(profile)
    return row


def append(row, target):
    """Uma linha, um `write`, para um ledger que só seu dono consegue ler."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(target.parent), 0o700)
    except OSError:
        pass
    fd = os.open(str(target), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (json.dumps(row, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        os.close(fd)


def record(payload, runtime, profile=None):
    append(row_for(payload, runtime, profile), ledger_path())


def note_error(runtime, error):
    try:
        append({"ts": now(), "runtime": runtime, "error": type(error).__name__,
                "detail": str(error)[:500]}, errors_path())
    except Exception:
        pass


def parse_args(argv):
    runtime, profile, index = None, None, 0
    while index < len(argv):
        if argv[index] == "--runtime" and index + 1 < len(argv):
            runtime, index = argv[index + 1], index + 2
        elif argv[index] == "--profile" and index + 1 < len(argv):
            profile, index = argv[index + 1], index + 2
        else:
            index += 1
    return runtime, profile


def main(runtime=None, argv=None, stdin=None):
    """Registra o evento recebido no stdin. Retorna 0 em todo caminho, e nunca escreve em stdout ou stderr."""
    try:
        named, profile = parse_args(sys.argv[1:] if argv is None else argv)
        runtime = runtime or named or "unknown"
        raw = (sys.stdin if stdin is None else stdin).read()
        record(json.loads(raw), runtime, profile)
    except BaseException as error:  # noqa: BLE001 - a observação falha aberta e silenciosa, sempre.
        note_error(runtime or "unknown", error)
    return 0


if __name__ == "__main__":
    main()
