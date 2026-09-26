#!/usr/bin/env python3
"""Avança (fast-forward) o branch `stable` até uma tag de lançamento, ou verifica se ele já aponta para lá."""
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "stable"


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def remote_head(root, remote):
    line = git(root, "ls-remote", "--heads", remote, "refs/heads/" + BRANCH)
    return line.split()[0] if line else None


def plan(root, tag, remote="origin"):
    """Retorna (ação, commit de lançamento); `stable` nunca se move para trás ou para o lado."""
    commit = git(root, "rev-parse", tag + "^{commit}")
    current = remote_head(root, remote)
    if current is None:
        return "create", commit
    if current == commit:
        return "current", commit
    git(root, "fetch", "--quiet", remote, "refs/heads/" + BRANCH)
    code = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", current, commit]).returncode
    if code not in (0, 1):
        raise RuntimeError("cannot compare {} with {}".format(BRANCH, tag))
    return ("advance" if code == 0 else "refuse"), commit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", nargs="?", help="usa v<VERSION> como padrão")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--check", action="store_true", help="nunca faz push; falha a menos que stable esteja na tag")
    args = parser.parse_args(argv)
    args.tag = args.tag or "v" + (ROOT / "VERSION").read_text().strip()
    action, commit = plan(ROOT, args.tag, args.remote)
    if action == "current":
        print("{} já está em {} ({})".format(BRANCH, args.tag, commit))
        return 0
    if action == "refuse":
        print("{} não é um ancestral de {}; recusando movê-lo".format(BRANCH, args.tag))
        return 1
    if args.check:
        print("{} está desatualizado: {} está em {} e o branch precisa {}".format(BRANCH, args.tag, commit, action))
        return 1
    try:
        git(ROOT, "push", args.remote, commit + ":refs/heads/" + BRANCH)
    except subprocess.CalledProcessError:
        # A anotação é o único rastro quando o job do workflow tem permissão para falhar.
        print("::warning::{} não foi movido para {}; rode scripts/advance_stable.py a partir de um checkout".format(BRANCH, args.tag))
        return 1
    print("{} agora em {} ({})".format(BRANCH, args.tag, commit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
