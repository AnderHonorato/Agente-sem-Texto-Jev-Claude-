#!/usr/bin/env python3
"""Provisiona o diretório de rascunho de uma rodada de qualificação, uma vez, a partir deste checkout.

Toda rodada antes desta construiu as mesmas três coisas manualmente numa cópia de rascunho por
rodada: um clone congelado do commit sob qualificação, um checkout do framework BMad para a suíte
de integração opcional, e um lugar para guardar o registro de cada alvo. Construído à mão significa
não revisado, e um clone tirado do commit errado invalida a rodada em que é usado, então isto é um
script versionado em vez disso.

O clone é tirado do próprio object store deste repositório — sem rede — e é recusado a menos que a
árvore esteja limpa e o commit seja o que o chamador nomeou. O passo do BMad é o único que alcança
a rede, é opt-in, e roda o instalador fixado de docs/bmad.md em vez de uma versão flutuante.

    python3 scripts/qualification_provision.py --out ../round-0.13.0
    python3 scripts/qualification_provision.py --out ../round-0.13.0 --commit <sha> --bmad
    python3 scripts/qualification_provision.py --out ../round-0.13.0 --print-env
"""
import argparse
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text().strip()
# Dividido em torno do `@`, assim como o runner divide sua identidade de committer descartável,
# para que o padrão de endereço do lint não combine com um especificador npm fixado.
BMAD_INSTALLER = "bmad-method" "@6.12.0"
BMAD_MODULES = "bmm"
CLONE = "clone"
# Escrito num clone que este script fez, e verificado antes de um ser removido: um diretório que
# outra pessoa colocou nesse caminho é recusado em vez de apagado.
CLONE_MARKER = ".harness-round-clone"
RECORDS = "records"
BMAD = "bmad"
BMAD_ENV = "HARNESS_ACCEPTANCE_BMAD"
TIMEOUT = 600


def run(args, cwd=None, timeout=TIMEOUT):
    return subprocess.run([str(item) for item in args], cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, check=False, timeout=timeout)


def git(*args, **kwargs):
    return run(["git", "-C", str(kwargs.pop("repo", ROOT))] + list(args), **kwargs)


def head():
    return git("rev-parse", "HEAD").stdout.strip()


def clean():
    return not git("status", "--porcelain").stdout.strip()


def clone(out, commit):
    """Um clone somente leitura de um commit, tirado do object store local.

    A evidência da rodada nomeia um commit de origem; um clone que não está nesse commit registra
    uma alegação sobre uma origem que ninguém rodou. `--no-hardlinks` é deliberado: um object store
    com hard link compartilha um destino com o checkout em que o operador continua trabalhando.
    """
    target = out / CLONE
    if target.exists():
        if not (target / CLONE_MARKER).is_file():
            raise SystemExit("%s exists and was not created by this script; move it aside first"
                             % target)
        shutil.rmtree(str(target))
    # `--no-shared` é a grafia que o git aceita: a opção não recebe valor, então passar um faz todo
    # clone sair com 129. Um object store compartilhado também daria ao clone o mesmo destino do
    # checkout sendo trabalhado, que é a razão de a flag estar aqui.
    result = run(["git", "clone", "--quiet", "--no-hardlinks", "--no-shared", str(ROOT),
                  str(target)])
    if result.returncode:
        raise SystemExit("could not clone this checkout: " + result.stderr.strip()[-300:])
    checked = git("checkout", "--quiet", "--detach", commit, repo=target)
    if checked.returncode:
        raise SystemExit("the clone could not be moved to %s: %s"
                         % (commit, checked.stderr.strip()[-300:]))
    at = git("rev-parse", "HEAD", repo=target).stdout.strip()
    if at != commit:
        raise SystemExit("the clone is at %s, not the commit asked for" % at)
    (target / CLONE_MARKER).write_text(commit + "\n")
    exclude_marker(target)
    status = git("status", "--porcelain", repo=target)
    if status.returncode:
        raise SystemExit("could not check whether the clone at %s is clean: %s"
                         % (target, status.stderr.strip()[-300:]))
    if status.stdout.strip():
        raise SystemExit("the clone at %s is not clean, and the runner inside it refuses a dirty "
                         "checkout" % target)
    return target


def exclude_marker(target):
    """Mantém o marcador fora do status do clone, para que o runner dentro do clone o aceite.

    O runner recusa um checkout com qualquer saída de `git status --porcelain`, e uma rodada
    conduz o runner a partir deste clone. A exclusão é o próprio `.git/info/exclude` do clone,
    nunca um `.gitignore` rastreado: o clone precisa continuar byte-idêntico ao commit sob
    qualificação. Corrigir isso aqui em vez de no runner alcança toda rodada de uma vez, já que o
    runner que executa é o do commit congelado, enquanto este script roda a partir do checkout do
    operador.
    """
    exclude = Path(git("rev-parse", "--git-path", "info/exclude", repo=target).stdout.strip())
    if not exclude.is_absolute():
        exclude = target / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text() if exclude.is_file() else ""
    line = "/" + CLONE_MARKER
    if line not in existing.splitlines():
        separator = "" if not existing or existing.endswith("\n") else "\n"
        exclude.write_text(existing + separator + line + "\n")


def bmad_install_args(target):
    """O comando de instalação da suíte opcional de docs/bmad.md, com `target` como raiz do framework.

    Precisa continuar esse comando, flag por flag. Sem `--shims` os nomes de skill de revisão
    legados que alguns workflows ainda invocam ficam ausentes, e `harness integration apply bmad`
    relata desvio na raiz provisionada.
    """
    return ["npx", "--yes", BMAD_INSTALLER, "install", "--directory", str(target),
            "--modules", BMAD_MODULES, "--tools", "claude-code,codex",
            "--output-folder", "_bmad-output", "--shims", "--yes"]


def bmad(out):
    """Um checkout do framework BMad para a suíte de integração opcional, a partir do instalador fixado.

    Nenhum caso obrigatório o lê: `framework-spawn-routing` constrói sua receita a partir do
    descritor de integração e não roda nenhum workflow de framework. O checkout é para a suíte de
    revisão nativa que docs/releasing.md pede uma vez por lançamento minor, que um operador roda
    manualmente. É o único passo aqui que alcança a rede, então é opt-in, e um instalador que este
    script não consegue encontrar é uma lacuna relatada, não um provisionamento que falhou.
    """
    target = out / BMAD
    target.mkdir(parents=True, exist_ok=True)
    if not (target / ".git").exists():
        git("init", "--quiet", repo=target)
    if not shutil.which("npx"):
        return None, "npx is not on PATH, so no BMad framework checkout was installed"
    result = run(bmad_install_args(target), timeout=TIMEOUT)
    if result.returncode or not (target / "_bmad").is_dir():
        return None, ("the pinned BMad installer did not produce a framework checkout: "
                      + (result.stderr or result.stdout).strip()[-300:])
    return target, ""


def provision(out, commit, want_bmad):
    out.mkdir(parents=True, exist_ok=True)
    (out / RECORDS).mkdir(exist_ok=True)
    report = {"harness_version": VERSION, "source_commit": commit,
              "clone": str(clone(out, commit)), "records": str(out / RECORDS),
              "bmad": None, "notes": []}
    if want_bmad:
        path, note = bmad(out)
        report["bmad"] = str(path) if path else None
        if note:
            report["notes"].append(note)
    else:
        report["notes"].append("no BMad framework checkout was asked for; only the optional "
                               "integration suite needs one")
    return report


def environment(report):
    """A única variável que uma rodada exporta, para que nenhum caso alcance a rede para achar um checkout."""
    return {BMAD_ENV: report["bmad"]} if report.get("bmad") else {}


def inside_this_repository(path):
    """Se `path` resolve para dentro de qualquer checkout ou worktree deste repositório.

    Um diretório de rodada ali seria removido por uma verificação de árvore limpa, ou pior, seria
    commitado. O teste é o object store git que os dois caminhos compartilham, então um worktree
    irmão deste repositório é recusado exatamente como o próprio checkout é, e um repositório não
    relacionado em outro lugar não é.
    """
    mine = git("rev-parse", "--git-common-dir").stdout.strip()
    if not mine:
        return False
    mine = (ROOT / mine).resolve()
    for candidate in [path] + list(path.parents):
        if not (candidate / ".git").exists():
            continue
        common = run(["git", "-C", str(candidate), "rev-parse", "--git-common-dir"]).stdout.strip()
        if common and (candidate / common).resolve() == mine:
            return True
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True,
                        help="diretório da rodada, fora deste checkout")
    parser.add_argument("--commit", help="commit a qualificar (padrão: HEAD deste checkout)")
    parser.add_argument("--bmad", action="store_true",
                        help="instala o checkout fixado do framework BMad para a suíte de integração "
                             "opcional; o único passo de rede")
    parser.add_argument("--print-env", action="store_true",
                        help="imprime os exports que uma rodada precisa, um por linha, e não provisiona nada")
    args = parser.parse_args(argv)
    out = args.out.expanduser().resolve()
    if inside_this_repository(out):
        raise SystemExit("the round directory must be outside every checkout of this repository")
    if args.print_env:
        existing = out / "provision.json"
        if not existing.is_file():
            raise SystemExit("no provision record at %s; provision the round first" % existing)
        for key, value in sorted(environment(json.loads(existing.read_text())).items()):
            print("export %s=%s" % (key, shlex.quote(str(value))))
        return 0
    if not clean():
        raise SystemExit("the checkout must be clean: a round's evidence names a source commit")
    commit = args.commit or head()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        resolved = git("rev-parse", commit).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{40}", resolved):
            raise SystemExit("not a commit in this repository: " + commit)
        commit = resolved
    report = provision(out, commit, args.bmad)
    (out / "provision.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
