#!/usr/bin/env python3
"""Roda as verificações determinísticas de pré-qualificação como um único nível: sem turno de modelo, sem cliente, sem custo.

Toda verificação aqui já existe neste repositório; o nível é o único comando que as roda
antes de uma rodada de qualificação ser paga — os autotestes do runner de aceitação contra
transcrições registradas, a verificação de links de documentação, a sonda de precondição de
credencial e host para cada alvo que a rodada vai rodar, e as verificações de sync de home
descartável, desvio de projeção e ciclo de vida.

Um nível verde nunca é qualificação de cliente nativo. Ele não observa nenhum comportamento de
cliente, não escreve nada sob `compatibility/evidence/` e não aparece em nenhum registro de
catálogo; a execução falha se qualquer um dos dois for tocado. O que um cliente precisa ser
observado fazendo, e o que a evidência precisa conter, está em docs/compatibility.md.

    python3 scripts/smoke_tier.py --list
    python3 scripts/smoke_tier.py
    python3 scripts/smoke_tier.py --only credentials,documentation-links
    python3 scripts/smoke_tier.py --targets claude-code-cli-macos,codex-cli-linux
"""
import argparse
import hashlib
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_acceptance import CLIENTS, redact

NOT_QUALIFICATION = ("smoke tier: deterministic pre-qualification checks, no model turn; "
                     "a green run is not native client qualification")
# O que nenhuma verificação pode tocar: um registro de evidência é uma alegação sobre um cliente
# observado, e este nível não observa nenhum.
GUARDED = (Path("compatibility") / "evidence", Path("compatibility") / "catalog.json")
TAIL = 600
GIT_TIMEOUT = 30


def unittest_argv(pattern):
    return [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern]


def steps(work, targets=None):
    """Cada verificação, na ordem em que uma que falhar é mais barata de ler: mais rápida e mais estreita primeiro.

    `credentials` verifica, para cada alvo, o que docs/qualification-runbook.md diz que precisa
    existir antes de começar: seu cliente e login aqui, ou um daemon Docker para um alvo Linux que
    este host roda em um container. Sem nenhum alvo nomeado, ela verifica todo alvo de CLI que
    este host consegue rodar e relata o resto como pulado.
    """
    return [
        {"name": "credentials",
         "how": "check each target's client, login or Docker daemon on this host",
         "argv": [sys.executable, "-m", "harness_core.target_preconditions"]
                 + (["--targets", ",".join(targets)] if targets else []),
         "env": {"PYTHONPATH": str(ROOT / "lib")}, "timeout": 30},
        {"name": "projection-drift",
         "how": "regenerate every native projection and compare it with the committed one",
         "argv": [sys.executable, str(ROOT / "bin" / "harness"), "generate", "--check"],
         "timeout": 120},
        {"name": "documentation-links",
         "how": "resolve every relative documentation link and heading anchor",
         "argv": unittest_argv("test_doc_links.py"), "timeout": 120},
        {"name": "runner-self-tests",
         "how": "read recorded transcripts with the acceptance runner's own readers",
         "argv": unittest_argv("test_native_acceptance*.py"), "timeout": 600},
        {"name": "disposable-home-lifecycle",
         "how": "install, sync, upgrade, roll back and uninstall in disposable homes",
         "argv": [sys.executable, str(ROOT / "scripts" / "lifecycle_acceptance.py"),
                  "--output", str(work / "lifecycle.json")],
         "timeout": 1800, "clean_tree": True},
    ]


def dirty(root=ROOT):
    """O que a árvore de trabalho mudou, ou `None` quando seu estado não pôde ser lido de forma alguma.

    Fora de um checkout git, `git status` sai com 128 e não imprime nada, o que é
    indistinguível de uma árvore limpa se só a saída padrão for lida; uma verificação que precisa
    de uma árvore limpa fica `unverified` nesse caso em vez de rodar contra uma desconhecida.
    """
    try:
        result = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                                capture_output=True, text=True, check=False, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    return result.stdout.strip()


def digest(root=ROOT):
    """Um único digest sobre tudo que este nível não pode escrever, para que uma escrita seja pega em vez de confiada."""
    sha = hashlib.sha256()
    for relative in GUARDED:
        path = root / relative
        for item in ([path] if path.is_file() else sorted(path.rglob("*")) if path.exists() else []):
            sha.update(str(item.relative_to(root)).encode())
            if item.is_file():
                sha.update(item.read_bytes())
    return sha.hexdigest()


def outcome(step, result, seconds, detail):
    return {"name": step["name"], "result": result, "seconds": seconds, "detail": detail}


def kill_group(process):
    """Mata a verificação e tudo que ela iniciou; um neto sobrevivente mantém a execução aberta."""
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except OSError:
        process.kill()


def tail(output, code):
    """O fim da saída de uma verificação que falhou, redigida inteira antes de ser cortada.

    Cortar primeiro pode deixar a segunda metade de um caminho de home ou um token isolada, então
    a redação roda sobre tudo que a verificação imprimiu e o corte é tirado do resultado.
    """
    return redact(output)[-TAIL:] or "exit %s with no output" % code


def run_step(step, root=ROOT):
    """Roda uma verificação sob um timeout limitado e a classifica, nunca inferindo uma aprovação."""
    started = time.time()
    if step.get("clean_tree"):
        state = dirty(root)
        if state is None:
            return outcome(step, "unverified", 0.0,
                           "the tree state could not be read, so this check was not run")
        if state:
            return outcome(step, "unverified", 0.0,
                           "the checkout is dirty and this check requires a clean one")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.update(step.get("env") or {})
    try:
        process = subprocess.Popen([str(item) for item in step["argv"]], cwd=str(root), env=env,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
    except OSError as error:
        return outcome(step, "unverified", 0.0, "the check could not be started: " + redact(error))
    try:
        out, err = process.communicate(timeout=step["timeout"])
    except subprocess.TimeoutExpired:
        # Uma verificação que nunca respondeu não observou nada, então ela é unverified em vez de
        # failed — e é morta com seus filhos, que é a travada que este nível existe para substituir.
        kill_group(process)
        process.communicate()
        return outcome(step, "unverified", float(step["timeout"]),
                       "no answer within %ss" % step["timeout"])
    except OSError as error:
        kill_group(process)
        return outcome(step, "unverified", round(time.time() - started, 1),
                       "the check could not be read: " + redact(error))
    seconds = round(time.time() - started, 1)
    if process.returncode == 0:
        return outcome(step, "passed", seconds, "")
    return outcome(step, "failed", seconds, tail((err or "") + (out or ""), process.returncode))


def names_in(names, plan):
    chosen = [name.strip() for name in (names or "").split(",") if name.strip()]
    unknown = [name for name in chosen if name not in {step["name"] for step in plan}]
    if unknown:
        raise SystemExit("unknown smoke check: " + ", ".join(unknown))
    return chosen


def selected(only, skip, plan):
    keep = names_in(only, plan) or [step["name"] for step in plan]
    dropped = names_in(skip, plan)
    return [step for step in plan if step["name"] in keep and step["name"] not in dropped]


def report(results, wrote):
    lines = [NOT_QUALIFICATION]
    for item in results:
        lines.append("  %-26s %-11s %ss" % (item["name"], item["result"], item["seconds"]))
        if item["detail"]:
            lines.append("      " + item["detail"])
    counted = [result for result in ("passed", "failed", "unverified")
               if any(item["result"] == result for item in results)]
    lines.append("smoke tier: " + ", ".join(
        "%s %s" % (sum(item["result"] == result for item in results), result)
        for result in counted or ["passed"]))
    if wrote:
        lines.append("smoke tier: a check wrote under %s; the tier writes no evidence"
                     % " or ".join(str(path) for path in GUARDED))
    return "\n".join(lines)


def tier(plan, root=ROOT, runner=run_step):
    before = digest(root)
    results = [runner(step, root) for step in plan]
    return results, digest(root) != before


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="subconjunto separado por vírgulas das verificações a rodar")
    parser.add_argument("--skip", help="verificações separadas por vírgulas a deixar fora desta execução")
    parser.add_argument("--targets",
                        help="alvos separados por vírgulas que a rodada vai rodar; por padrão todo "
                             "alvo de CLI que este host consegue rodar")
    parser.add_argument("--list", action="store_true", dest="listing",
                        help="imprime o que rodaria, sem rodar nada")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="harness-smoke-") as work:
        targets = [name.strip() for name in (args.targets or "").split(",") if name.strip()]
        unknown = [name for name in targets if name not in CLIENTS]
        if unknown:
            raise SystemExit("unknown target: " + ", ".join(unknown))
        plan = selected(args.only, args.skip, steps(Path(work), targets))
        if not plan:
            raise SystemExit("no smoke check selected; --list names them")
        if args.listing:
            print("\n".join([NOT_QUALIFICATION]
                            + ["  %-26s %s" % (step["name"], step["how"]) for step in plan]))
            return 0
        results, wrote = tier(plan)
    print(report(results, wrote))
    return 0 if not wrote and all(item["result"] == "passed" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
