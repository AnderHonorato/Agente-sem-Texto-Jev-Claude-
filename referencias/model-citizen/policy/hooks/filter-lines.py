#!/usr/bin/env python3
"""Lê uma execução de teste, build ou log no stdin e imprime só as linhas que carregam
informação: falhas, tracebacks e o que os segue, linhas de resumo, e o final da execução.

Invocado por `filter-output.py`, que reescreve um comando Bash correspondente para passar
por ele via pipe. Sempre sai com 0, para que o pipeline `pipefail` reporte o status do
comando sendo filtrado.
"""
import re
import sys

KEEP = re.compile(
    r"FAILED|FAIL:|ERROR|error\[|error:|panicked|Traceback|AssertionError|assert |✗|✘|not ok|warning: unused"
)
CONTEXT_AFTER = re.compile(r"Traceback|panicked")
SUMMARY = [
    re.compile(r"^=+ .* =+$"),
    re.compile(r"^Ran \d+ tests"),
    re.compile(r"^test result:"),
    re.compile(r"^Tests:"),
    re.compile(r"^ok\b|^FAILED\b"),
]
COUNTED = re.compile(r"passed|failed")
DIGIT = re.compile(r"\d")

CONTEXT_LINES = 3
TAIL_LINES = 20
MIN_KEPT = 5
CAP = 200


def is_summary(line):
    if any(p.search(line) for p in SUMMARY):
        return True
    return bool(COUNTED.search(line) and DIGIT.search(line))


def select(lines):
    keep = set()
    for i, line in enumerate(lines):
        if KEEP.search(line) or is_summary(line):
            keep.add(i)
        if CONTEXT_AFTER.search(line):
            keep.update(range(i + 1, min(i + 1 + CONTEXT_LINES, len(lines))))
    keep.update(range(max(0, len(lines) - TAIL_LINES), len(lines)))
    return [lines[i] for i in sorted(keep)]


def filter_text(text):
    lines = text.splitlines()
    kept = select(lines)
    if len(kept) < MIN_KEPT:
        kept = lines
    if len(kept) > CAP:
        half = CAP // 2
        kept = kept[:half] + ["[filter-lines: %d lines omitted]" % (len(kept) - CAP)] + kept[-half:]
    return "\n".join(kept)


def main():
    try:
        try:
            sys.stdin.reconfigure(errors="replace")
        except Exception:
            pass
        out = filter_text(sys.stdin.read())
        if out:
            sys.stdout.write(out + "\n")
    except Exception:
        return


if __name__ == "__main__":
    main()
