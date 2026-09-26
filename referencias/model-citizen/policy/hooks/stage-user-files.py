#!/usr/bin/env python3
"""Hook de PreToolUse: copia para dentro cada arquivo que `SendUserFile` nomeia de fora do
diretório de trabalho da sessão, para que um cliente Remote Control consiga abrir o arquivo.

Numa sessão de Remote Control a ferramenta não envia upload de nada. O app guarda o caminho e
pede o arquivo à sessão quando você o abre, e o Claude Code o serve só quando o caminho real do
arquivo está sob o diretório em que a sessão começou ou um diretório adicionado a ele. Agentes
escrevem relatórios, renderizações e capturas de tela em diretórios temporários, diretórios de
scratch e outras worktrees, então sem isso o app recusa a maior parte do que enviam com "Couldn't
load this file".

Um arquivo cujo caminho real está fora do diretório de trabalho do hook, que o Claude Code mantém
dentro dos diretórios de trabalho da sessão, é copiado para
`.agent-harness/outbox/<digest>/<name>` ali, e o caminho é reescrito para a cópia. O digest cobre
o caminho real, tamanho e horários de modificação e alteração da fonte, então enviar um arquivo
inalterado de novo reutiliza sua cópia e qualquer reescrita, mesmo uma que restaure o horário de
modificação, recebe uma nova. O outbox traz um `.gitignore` que ignora tudo dentro dele, então
num repositório uma cópia nunca aparece no `git status`, num commit ou no lint. Diretórios
intocados por KEEP_DAYS são removidos quando algo novo é preparado, e `harness task` deixa o
outbox fora da sua fingerprint.

Um arquivo já dentro, um caminho ausente e um diretório são deixados em paz; a ferramenta reporta
seu próprio erro para um caminho que não consegue enviar. Um arquivo além do orçamento de bytes
ou tempo da chamada, ou um que não pode ser copiado, é deixado em paz com um aviso. Este hook
nunca nega: em qualquer falha a chamada roda inalterada.

Teste: echo '{"tool_name":"SendUserFile","cwd":"'"$PWD"'","tool_input":{"files":["/etc/hosts"]}}' | python3 stage-user-files.py
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

OUTBOX = Path(".agent-harness") / "outbox"
# O que uma chamada pode copiar, em bytes e em segundos, contra o orçamento de dez segundos de
# PreToolUse do coordenador. O tempo é checado entre arquivos, então uma fonte lenta ainda pode
# ultrapassá-lo; o hook então é parado e a chamada segue inalterada.
MAX_BYTES = 64 * 1024 * 1024
DEADLINE_SECONDS = 4
KEEP_DAYS = 14
DIGEST = re.compile(r"[0-9a-f]{16}")


def real(path):
    return Path(os.path.realpath(str(path)))


def outbox(root):
    """O outbox sob `root`, criado no primeiro uso; None quando qualquer parte dele é um link."""
    box = root / OUTBOX
    ignore = box / ".gitignore"
    if any(p.is_symlink() for p in (root / OUTBOX.parent, box, ignore)):
        return None
    box.mkdir(parents=True, exist_ok=True)
    if not real(box).is_relative_to(real(root)):
        return None
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
    return box


def stage(source, info, box):
    key = "%s\0%d\0%d\0%d" % (source, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    folder = box / hashlib.sha256(key.encode("utf-8", "surrogateescape")).hexdigest()[:16]
    target = folder / source.name
    if folder.is_symlink() or target.is_symlink():
        raise OSError("outbox entry is a link: " + folder.name)
    if target.is_file() and target.stat().st_size == info.st_size:
        os.utime(str(folder))
        return target
    folder.mkdir(exist_ok=True)
    handle, partial = tempfile.mkstemp(dir=str(folder), prefix=".", suffix=".part")
    os.close(handle)
    try:
        shutil.copyfile(str(source), partial)
        os.replace(partial, str(target))
    except BaseException:
        try:
            os.unlink(partial)
        except OSError:
            pass
        raise
    return target


def prune(box, now):
    cutoff = now - KEEP_DAYS * 86400
    for entry in box.iterdir():
        try:
            if (DIGEST.fullmatch(entry.name) and not entry.is_symlink() and entry.is_dir()
                    and entry.stat().st_mtime < cutoff):
                shutil.rmtree(str(entry), ignore_errors=True)
        except OSError:
            continue


def decide(payload):
    """A saída do hook para um payload de PreToolUse, ou None para deixar a chamada como está."""
    if not isinstance(payload, dict) or payload.get("tool_name") != "SendUserFile":
        return None
    inputs = payload.get("tool_input")
    cwd = payload.get("cwd")
    if not isinstance(inputs, dict) or not isinstance(cwd, str) or not os.path.isabs(cwd):
        return None
    files = inputs.get("files")
    if not isinstance(files, list) or not os.path.isdir(cwd):
        return None
    root, inside = Path(cwd), real(cwd)
    deadline, budget = time.monotonic() + DEADLINE_SECONDS, MAX_BYTES
    box, sent, staged, kept = None, [], 0, []
    for entry in files:
        sent.append(entry)
        if not isinstance(entry, str) or not entry.strip():
            continue
        try:
            path = Path(os.path.expanduser(entry))
            source = real(path if path.is_absolute() else root / path)
            if source.is_relative_to(inside) or not source.is_file():
                continue
            info = source.stat()
            if info.st_size > budget or time.monotonic() > deadline:
                kept.append(source.name)
                continue
            box = box or outbox(root)
            if box is None:
                kept.append(source.name)
                continue
            sent[-1] = str(stage(source, info, box))
            budget -= info.st_size
            staged += 1
        except (OSError, ValueError):
            kept.append(os.path.basename(entry.rstrip("/")) or entry)
    if staged:
        try:
            prune(box, time.time())
        except OSError:
            pass
    notes = []
    if staged:
        notes.append("copied %d file(s) from outside the session's working directory into %s/, "
                     "so Remote Control can open them" % (staged, OUTBOX.as_posix()))
    if kept:
        notes.append("could not copy %s into the working directory, so Remote Control may not open it"
                     % ", ".join(kept))
    if not notes:
        return None
    result = {"systemMessage": "stage-user-files: " + "; ".join(notes) + "."}
    if staged:
        result["hookSpecificOutput"] = {"hookEventName": "PreToolUse",
                                        "updatedInput": dict(inputs, files=sent)}
    return result


def main():
    try:
        result = decide(json.load(sys.stdin))
    except Exception:
        return
    if result:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
