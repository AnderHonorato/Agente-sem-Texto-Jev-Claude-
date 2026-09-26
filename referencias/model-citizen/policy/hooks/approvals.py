#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hook de UserPromptSubmit, e a biblioteca por trás dele: aprovações de uso único que o usuário digita no chat.

Por quê: no modo `auto` o `ask` de um hook é ignorado, então `grade-bash` precisa negar, e o
classificador do modo auto recusa qualquer comando que o agente prefixe com o marcador de
confirmação como uma tentativa de contornar um hook de segurança. O único canal que o agente não
consegue produzir é o próprio prompt do usuário, então o usuário aprova um comando recusado
respondendo `approve <code>`, e nada mais pode criar uma aprovação.

- `code_for(session_id, command)` são os primeiros seis caracteres base32 de
  `sha256(session_id + "\\n" + command)`, sobre o texto bruto do comando. O mesmo comando na mesma
  sessão sempre recebe o mesmo código, então não há armazenamento pendente a proteger: conhecer um
  código não vale nada sem uma aprovação registrada a partir de um prompt.
- `record(session_id, prompt)` guarda as aprovações do prompt em
  `~/.local/state/agent-harness/approvals/<session_id>.json` com seu horário, mas só quando o
  prompt inteiro é composto de tokens `approve <code>` (sem diferenciar maiúsculas/minúsculas,
  vários permitidos, separados por espaço ou vírgula). Qualquer outro texto não registra nada:
  UserPromptSubmit também dispara em turnos que o usuário nunca digitou, como notificações de
  tarefa, passagens de bastão de subagente e mensagens entre sessões, e esses carregam texto
  controlado pelo agente que de outra forma poderia contrabandear uma aprovação.
- `consume(session_id, code)` marca uma aprovação viva de `code` mais nova que `TTL` segundos como
  usada e diz se encontrou uma. Uma aprovação confirma uma execução de um comando numa sessão.
- O armazenamento é só do usuário: `grade-bash` avalia uma escrita Bash nele em 3, e o dispatcher
  nega uma escrita de ferramenta de arquivo nele (`file_write_deny`).

Cada `record` e `consume` segura um `flock` exclusivo em `<session_id>.lock` ao lado do arquivo
por toda a sua leitura-modificação-escrita, então dois consumidores não podem usar a mesma
aprovação e um consume não pode descartar uma aprovação que um record acabou de adicionar. Um
lock que não pode ser obtido falha fechado.

Toda leitura e escrita é envolvida, então um armazenamento que não pode ser lido não tem aprovação
nenhuma e um armazenamento que não pode ser escrito não registra nada; nenhum dos dois jamais
levanta exceção para o hook que o chamou.

Teste: echo '{"hook_event_name":"UserPromptSubmit","session_id":"s1","prompt":"approve ABC234"}' | python3 approvals.py
"""
import base64
import contextlib
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # nenhum lock consultivo aqui, então o armazenamento nem registra nem consome
    fcntl = None

CODE_LENGTH = 6
TTL = 30 * 60
SESSION_ID_MAX = 128
# Limitado para que uma sessão longa não faça seu arquivo crescer sem limite; as aprovações mais antigas saem primeiro.
KEEP = 64
TOKEN = r"approve\s+([A-Za-z2-7]{%d})" % CODE_LENGTH
APPROVE_RE = re.compile(TOKEN, re.I)
# O prompt inteiro, aparado: um ou mais tokens e nada mais.
ONLY_TOKENS_RE = re.compile(r"(?:%s)(?:[\s,]+%s)*" % (TOKEN, TOKEN), re.I)
# Um comando Bash que nomeia o armazenamento em qualquer uma dessas grafias é tratado como uma
# escrita nele assim que for qualquer coisa além de somente leitura; veja `mentions_store`.
STORE_RE = re.compile(r"agent-harness[/\\]+approvals(?=$|[/\\\s\"'`;|&)<>])|\.local[/\\]+state[/\\]+agent-harness"
                      r"(?=[\s\S]*approvals)")
FILE_DENY = ("The approvals store is written only from the user's own prompt, so no tool may write "
             "to it. Ask the user to reply with the approval the refusal named.")


def home():
    return Path(os.environ.get("HARNESS_HOME") or os.environ.get("HOME") or Path.home())


def store_dir():
    return home() / ".local" / "state" / "agent-harness" / "approvals"


def _session_ok(value):
    """Um id de sessão seguro para virar um nome de arquivo: sem separador, sem travessia, limitado."""
    return (isinstance(value, str) and value.isascii() and 0 < len(value) <= SESSION_ID_MAX
            and value[0].isalnum() and all(c.isalnum() or c in "._-" for c in value))


def store_path(session_id):
    return store_dir() / (session_id + ".json") if _session_ok(session_id) else None


def code_for(session_id, command):
    digest = hashlib.sha256((session_id + "\n" + command).encode("utf-8")).digest()
    return base64.b32encode(digest).decode("ascii")[:CODE_LENGTH]


def codes_in(prompt):
    """Os códigos que um prompt aprova, em maiúsculas, em ordem, sem repetições; nenhum a menos
    que o prompt aparado seja só tokens `approve <code>`."""
    seen = []
    text = prompt.strip() if isinstance(prompt, str) else ""
    if not ONLY_TOKENS_RE.fullmatch(text):
        return seen
    for match in APPROVE_RE.finditer(text):
        code = match.group(1).upper()
        if code not in seen:
            seen.append(code)
    return seen


def _read(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = data.get("approvals") if isinstance(data, dict) else None
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def _write(path, entries):
    temp = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(str(path.parent), 0o700)
        with os.fdopen(os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
                       "w", encoding="utf-8") as handle:
            json.dump({"approvals": entries[-KEEP:]}, handle)
        os.replace(str(temp), str(path))
        return True
    except OSError:
        try:
            os.unlink(str(temp))
        except OSError:
            pass
        return False


@contextlib.contextmanager
def _locked(path):
    """Segura um lock exclusivo para a sessão de `path`; produz False quando nenhum pôde ser obtido."""
    fd = None
    try:
        if fcntl is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(str(path.parent), 0o700)
            fd = os.open(str(path.with_suffix(".lock")), os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
    except OSError:
        if fd is not None:
            os.close(fd)
        fd = None
    try:
        yield fd is not None
    finally:
        if fd is not None:
            os.close(fd)  # fechar o descritor libera o lock


def _live(entry, now):
    created = entry.get("created")
    # Um horário de criação um pouco além de `now` é um registro que obteve o lock depois que
    # esta chamada leu o relógio, não uma falsificação: só um prompt do usuário escreve o armazenamento.
    return isinstance(created, (int, float)) and not entry.get("used") and now - created <= TTL


def record(session_id, prompt, now=None):
    """Registra os tokens `approve <code>` do prompt para esta sessão; os códigos registrados."""
    path = store_path(session_id)
    codes = codes_in(prompt)
    if path is None or not codes:
        return []
    now = time.time() if now is None else now
    with _locked(path) as held:
        if not held:
            return []
        entries = [e for e in _read(path) if _live(e, now)]
        entries.extend({"code": code, "created": now, "used": False} for code in codes)
        return codes if _write(path, entries) else []


def consume(session_id, code, now=None):
    """Usa uma aprovação viva de `code` nesta sessão; True quando havia uma para usar."""
    path = store_path(session_id)
    if path is None or not isinstance(code, str):
        return False
    if not path.exists():
        return False  # nada jamais foi registrado: nenhum arquivo de lock para uma sessão sem aprovações
    now = time.time() if now is None else now
    with _locked(path) as held:
        if not held:
            return False
        entries = _read(path)
        for entry in entries:
            if entry.get("code") == code.upper() and _live(entry, now):
                entry["used"] = True
                entry["used_at"] = now
                return _write(path, entries)
        return False


def mentions_store(text):
    return isinstance(text, str) and bool(STORE_RE.search(text))


def under_store(path):
    """Se um caminho de arquivo, resolvido, é o armazenamento ou está dentro dele."""
    try:
        target = os.path.realpath(os.path.expanduser(str(path)))
        root = os.path.realpath(str(store_dir()))
    except (OSError, ValueError):
        return False
    return target == root or target.startswith(root + os.sep)


def file_write_deny(paths):
    """A negação para uma escrita de ferramenta de arquivo cujos caminhos alcançam o armazenamento, ou None."""
    if any(under_store(p) for p in paths):
        return {"hookSpecificOutput": {"permissionDecision": "deny",
                                       "permissionDecisionReason": FILE_DENY}}
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict) or payload.get("hook_event_name") != "UserPromptSubmit":
        return
    record(payload.get("session_id"), payload.get("prompt"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # uma falha do registrador custa uma aprovação, nunca o prompt do usuário
