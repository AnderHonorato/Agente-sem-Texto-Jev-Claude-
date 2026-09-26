#!/usr/bin/env python3
"""Hook de PreToolUse: passa execuções verbosas de teste, build e checagem de tipos por pipe
através de `filter-lines.py`, para que só falhas, o resumo e o final de uma execução entrem no
transcript.

Por que um hook e não uma instrução: no momento em que o modelo poderia decidir ler a saída de
forma restrita, a execução inteira já está no contexto e todo turno posterior paga por isso.
Reduzi-la é um trabalho computacional.

Comportamento:
  - Reescreve um comando que roda um dos MATCHES, depois que atribuições de ambiente
    iniciais e prefixos `cd ... &&` são removidos.
  - Deixa o comando intacto quando já está filtrado, já faz pipe para um
    pager, redireciona para um arquivo, ou observa (watch).
  - Emite só `updatedInput`. Nunca retorna uma decisão de permissão, então o
    fluxo de permissão normal e qualquer outro hook de PreToolUse em Bash ficam intocados.
  - `set -o pipefail` mantém o status de saída original; o filtro sempre sai com 0.

Teste: echo '{"tool_name":"Bash","tool_input":{"command":"pytest -q"}}' | python3 filter-output.py
"""
import json
import re
import shlex
import sys
from pathlib import Path

MATCHES = [
    "pytest", "python -m pytest", "python3 -m pytest", "python -m unittest",
    "python3 -m unittest", "uv run pytest", "cargo test", "cargo check",
    "cargo clippy", "cargo build", "npm test", "npm run test", "pnpm test",
    "yarn test", "go test", "npx tsc", "tsc", "npx vitest run", "npx jest",
]
MATCH_PATTERNS = [
    re.compile(r"(?<![\w./-])" + r"\s+".join(re.escape(w) for w in m.split()) + r"(?![\w./-])")
    for m in MATCHES
]
ENV_PREFIX = re.compile(r"""^\s*[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|[^\s;&|]*)\s+""")
CD_PREFIX = re.compile(r"""^\s*cd\s+(?:"[^"]*"|'[^']*'|[^\s;&|]+)\s*&&\s*""")
PAGED = re.compile(r"\|\s*(?:head|tail|grep|less|wc)\b")
REDIRECT_TO_FILE = re.compile(r">>?\s*(?!&)\S")
WATCH = re.compile(r"(?<![\w-])--watch(?![\w-])")
MAX_COMMAND = 10000


def strip_prefixes(cmd):
    prev = None
    while prev != cmd:
        prev = cmd
        cmd = CD_PREFIX.sub("", ENV_PREFIX.sub("", cmd))
    return cmd


def should_filter(cmd):
    if not cmd or len(cmd) > MAX_COMMAND:
        return False
    if "filter-lines.py" in cmd:
        return False
    if PAGED.search(cmd) or WATCH.search(cmd) or REDIRECT_TO_FILE.search(cmd):
        return False
    stripped = strip_prefixes(cmd)
    return any(p.search(stripped) for p in MATCH_PATTERNS)


def rewrite(cmd):
    filt = Path(__file__).resolve().parent / "filter-lines.py"
    return "set -o pipefail; ( %s ) 2>&1 | python3 %s" % (cmd, shlex.quote(str(filt)))


def main():
    try:
        payload = json.load(sys.stdin)
        if payload.get("tool_name") != "Bash":
            return
        tool_input = payload.get("tool_input") or {}
        cmd = tool_input.get("command")
        if not isinstance(cmd, str) or not should_filter(cmd):
            return
        updated = dict(tool_input)
        updated["command"] = rewrite(cmd)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "updatedInput": updated,
            }
        }))
    except Exception:
        return


if __name__ == "__main__":
    main()
