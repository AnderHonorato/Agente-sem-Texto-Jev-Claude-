# SPDX-License-Identifier: MIT
"""Se este host consegue iniciar cada alvo de qualificação sobre o qual é perguntado, respondido antes de uma rodada.

Um alvo roda aqui mesmo, quando sua plataforma é a deste host, ou no container Linux que o
runbook de qualificação constrói, quando é um alvo Linux e este host não é Linux. O que precisa
existir difere por caso, e cada peça ausente de outra forma aparece no meio de uma rodada paga:

- um alvo que roda aqui precisa do seu cliente no `PATH`, e uma credencial que o cliente possa
  usar — para o Codex, um login de sessão ChatGPT na sua home de configuração ou
  `OPENAI_API_KEY`, para o Claude Code a resposta que `credentials.reachable` dá;
- um alvo Linux num host que não é Linux precisa de `docker` no `PATH` e um daemon que responda;
  seu cliente e login são checados por essa mesma sondagem rodando dentro do container;
- um alvo macOS não consegue rodar em lugar nenhum além de um Mac. Nomeado explicitamente fora de
  um Mac, é uma falha; deixado para a lista padrão, é pulado com esse motivo, então o padrão nunca
  reprova um host por um alvo que não conseguiria rodar.

Nenhum valor é lido ou impresso. A pergunta sobre o Docker é o único subprocesso, limitado por um
timeout, e é feita uma vez, não importa quantos alvos precisem dela. O contrato de provisionamento
que essas checagens seguem está em docs/compatibility.md e os comandos estão em
docs/qualification-runbook.md.
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from harness_core import credentials

RUNTIMES = {"claude-code-cli-": ("claude-code", "claude"), "codex-cli-": ("codex", "codex")}
# Os alvos de CLI do executor de aceitação, o padrão quando nenhum alvo é nomeado. Um teste
# mantém isso alinhado com a própria tabela do executor, que este módulo não pode importar de `scripts/`.
DEFAULT_TARGETS = ("claude-code-cli-linux", "claude-code-cli-macos", "codex-cli-linux",
                   "codex-cli-macos")
PLATFORMS = {"Darwin": "macos", "Linux": "linux"}
CODEX_LOGIN = "auth.json"
DOCKER_TIMEOUT = 15


class Unready(Exception):
    """Um alvo que este host foi solicitado a rodar não consegue iniciar aqui."""


def describe(target):
    """``(runtime, command, platform)`` para um id de alvo de CLI como ``codex-cli-linux``.

    Só as superfícies de CLI rodam sem interface; uma superfície de editor, desktop ou marketplace é recusada.
    """
    for prefix, (runtime, command) in RUNTIMES.items():
        if target.startswith(prefix) and target[len(prefix):] in PLATFORMS.values():
            return runtime, command, target[len(prefix):]
    raise Unready("%s is not a target this probe knows how to check" % target)


def codex_login(env, home):
    """Levanta `Unready` a menos que um cliente Codex lançado a partir de `env` tenha um login para usar."""
    if env.get("OPENAI_API_KEY"):
        return
    folder = env.get("CODEX_HOME") or str(Path(home) / ".codex")
    if credentials.points_at_a_file(Path(folder) / CODEX_LOGIN):
        return
    raise Unready("no Codex login: neither a ChatGPT session login in the Codex home nor "
                  "OPENAI_API_KEY; run `codex login` before the round")


def docker_daemon(which=shutil.which, run=subprocess.run):
    """Levanta `Unready` a menos que um daemon Docker responda dentro de `DOCKER_TIMEOUT` segundos."""
    if not which("docker"):
        raise Unready("`docker` is not on PATH; a Linux target runs in a container on this host")
    try:
        result = run(["docker", "info", "--format", "{{.ServerVersion}}"],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, timeout=DOCKER_TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        raise Unready("the Docker daemon did not answer within %ss" % DOCKER_TIMEOUT)
    except OSError:
        raise Unready("`docker info` could not be started")
    if result.returncode:
        raise Unready("the Docker daemon is not running; start it before the round")


def runnable(target, host):
    """Se `host` consegue rodar `target` de algum jeito: aqui mesmo, ou num container quando é um alvo Linux."""
    where = describe(target)[2]
    return where == PLATFORMS.get(host) or where == "linux"


def by_default(host):
    """Os alvos padrão divididos entre os que este host consegue rodar e os pulados, com o motivo."""
    run, skipped = [], []
    for target in DEFAULT_TARGETS:
        if runnable(target, host):
            run.append(target)
        else:
            skipped.append((target, "runs only on a %s host" % describe(target)[2]))
    return run, skipped


def problems(targets, env, home, host, which=None, run=None):
    """Cada alvo que não consegue iniciar neste host, com o motivo, na ordem perguntada."""
    which = which or shutil.which
    run = run or subprocess.run
    found = []
    daemon = None
    for target in targets:
        try:
            runtime, command, where = describe(target)
            if where != PLATFORMS.get(host):
                if where != "linux":
                    raise Unready("a %s target runs only on a %s host" % (where, where))
                if daemon is None:
                    try:
                        docker_daemon(which, run)
                        daemon = ""
                    except Unready as error:
                        daemon = str(error)
                if daemon:
                    raise Unready(daemon)
                continue
            if not which(command, path=env.get("PATH")):
                raise Unready("`%s` is not on PATH" % command)
            if runtime == "codex":
                codex_login(env, home)
            else:
                try:
                    credentials.reachable(env, home)
                except credentials.Unreachable as error:
                    raise Unready(str(error))
        except Unready as error:
            found.append((target, str(error)))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--targets",
                        help="comma-separated target ids, for example codex-cli-linux; default "
                             "every CLI target this host can run")
    args = parser.parse_args(argv)
    host = platform.system()
    skipped = []
    if args.targets is None:
        targets, skipped = by_default(host)
    else:
        targets = [name.strip() for name in args.targets.split(",") if name.strip()]
        if not targets:
            raise SystemExit("--targets names no target")
    for target, reason in skipped:
        print("preconditions: %s: skipped, %s" % (target, reason))
    found = problems(targets, dict(os.environ), os.path.expanduser("~"), host)
    for target, reason in found:
        print("preconditions: %s: %s" % (target, reason), file=sys.stderr)
    if found:
        return 1
    print("preconditions: every target can start on this host")
    return 0


if __name__ == "__main__":
    sys.exit(main())
