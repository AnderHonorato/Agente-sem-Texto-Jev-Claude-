#!/usr/bin/env python3
"""
Progresso de execuções de Workflow em segundo plano, reconstruído a partir do diário da execução.

`/workflows` é uma visão apenas de terminal; isto lê os mesmos dados subjacentes, então funciona
em qualquer lugar (VS Code, web, um shell encanado). Deliberadamente nunca lê uma transcrição
completa de agente — elas rotineiramente chegam a megabytes — apenas o diário mais a primeira
linha da transcrição de cada agente, que carrega seu prompt e é suficiente para nomeá-lo.

Uso:
    status.py                 # execução mais recente
    status.py --all           # toda execução encontrada, mais nova primeiro
    status.py --run wf_abc123 # uma execução específica
    status.py --limit 5       # limita quantas execuções são mostradas
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"
SCRIPTS_GLOB = "workflows/scripts/*.js"


def find_runs() -> list[Path]:
    """Todo diretório de execução de workflow nesta máquina, mais novo primeiro."""
    runs = [p for p in PROJECTS.glob("*/*/subagents/workflows/wf_*") if p.is_dir()]
    return sorted(runs, key=lambda p: p.stat().st_mtime, reverse=True)


def read_journal(run: Path) -> tuple[list[str], dict[str, int]]:
    """Retorna (chaves iniciadas em ordem, {chave: tamanho do resultado})."""
    journal = run / "journal.jsonl"
    if not journal.exists():
        return [], {}

    started: list[str] = []
    results: dict[str, int] = {}
    for line in journal.read_text(errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        key = entry.get("key")
        if not key:
            continue
        if entry.get("type") == "started":
            if key not in started:
                started.append(key)
        elif entry.get("type") == "result":
            payload = entry.get("result")
            results[key] = len(payload) if isinstance(payload, str) else 0
    return started, results


def agent_identity(path: Path) -> str:
    """
    Um rótulo curto e legível para um agente, tirado da primeira linha de sua transcrição.

    A opção `label` do workflow não é persistida, então o prompt é a melhor identidade
    disponível. Primeiro procuramos por um marcador explícito, depois recorremos às
    palavras de abertura.
    """
    try:
        with path.open(errors="replace") as handle:
            first = handle.readline()
        message = json.loads(first).get("message", {})
        content = message.get("content")
        if isinstance(content, list):
            text = " ".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        else:
            text = str(content or "")
    except Exception:
        return "(unreadable)"

    text = text.strip()
    # A identidade vem APENAS DA ABERTURA do prompt. Fases posteriores recebem a saída de fases
    # anteriores anexada por completo, então buscar no corpo inteiro rotularia todo agente
    # posterior com qualquer marcador que por acaso liderasse o resumo que lhe foi passado.
    head = re.sub(r"\s+", " ", text[:400]).strip()

    marker = re.match(r"=====\s*[A-Z]+:\s*([\w-]+)", head)
    if marker:
        return marker.group(1)
    lead = re.match(r"(?:Deep web research:\s*)?(.{0,88})", head)
    snippet = (lead.group(1) if lead else head[:88]).strip()
    return snippet or "(empty prompt)"


def phases_from_script(run_id: str) -> list[str]:
    """Títulos de fase declarados no script persistido da execução, quando pode ser encontrado."""
    for script in PROJECTS.glob(f"*/*/{SCRIPTS_GLOB}"):
        if run_id in script.name:
            text = script.read_text(errors="replace")
            return re.findall(r"title:\s*'([^']+)'", text)
    return []


def human_age(seconds: float) -> str:
    if seconds < 90:
        return f"{int(seconds)}s"
    if seconds < 5400:
        return f"{seconds / 60:.0f}m"
    return f"{seconds / 3600:.1f}h"


def report(run: Path) -> None:
    run_id = run.name
    started, results = read_journal(run)
    agents = sorted(run.glob("agent-*.jsonl"), key=lambda p: p.stat().st_mtime)

    now = time.time()
    began = min((p.stat().st_ctime for p in agents), default=run.stat().st_ctime)
    last = max((p.stat().st_mtime for p in agents), default=run.stat().st_mtime)
    idle = now - last

    done = len(results)
    total = max(len(started), len(agents))
    chars = sum(results.values())
    state = "COMPLETE" if done and done == total and idle > 60 else "RUNNING"

    print(f"\n\033[1m{run_id}\033[0m  —  {state}")
    print(f"  started {human_age(now - began)} ago · last activity {human_age(idle)} ago")
    print(f"  agents: {done}/{total} returned · {chars:,} chars of output")

    phases = phases_from_script(run_id)
    if phases:
        print(f"  phases: {' → '.join(phases)}")

    print()
    for path in agents:
        size = path.stat().st_size
        age = now - path.stat().st_mtime
        # Um agente cuja transcrição está quieta há um tempo quase certamente já retornou.
        finished = age > 45
        mark = "\033[32m✓\033[0m" if finished else "\033[33m•\033[0m"
        status = "done" if finished else f"active {human_age(age)} ago"
        print(f"  {mark} {agent_identity(path)[:74]:<74} {size / 1024:>7.0f}KB  {status}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="mostra toda execução")
    parser.add_argument("--run", help="um id de execução específico (wf_...)")
    parser.add_argument("--limit", type=int, default=1, help="quantas execuções mostrar")
    args = parser.parse_args()

    runs = find_runs()
    if not runs:
        print("Nenhuma execução de workflow encontrada sob ~/.claude/projects/*/*/subagents/workflows/")
        return 1

    if args.run:
        runs = [r for r in runs if args.run in r.name]
        if not runs:
            print(f"Nenhuma execução correspondendo a {args.run!r}.")
            return 1
    elif not args.all:
        runs = runs[: max(1, args.limit)]

    for run in runs:
        report(run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
