#!/usr/bin/env python3
"""Mantém o painel About do GitHub igual ao texto de vitrine (landing copy) em `product.json`.

`--check` nomeia todo campo que difere e sai com código diferente de zero; `--apply` escreve os
metadados públicos do repositório através de `gh repo edit`, então precisa da aprovação do dono a
cada execução. Os topics são comparados como um conjunto, porque o GitHub os retorna em sua
própria ordem.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GH_TIMEOUT_SECONDS = 30
VIEW_ARGS = ("repo", "view", "--json", "description,repositoryTopics,homepageUrl")


class GhError(RuntimeError):
    """`gh` estava ausente, recusou, ou retornou saída que não pôde ser lida."""


def gh(args, root=ROOT):
    """Roda `gh` e retorna seu stdout, levantando `GhError` para todo modo de falha."""
    try:
        result = subprocess.run(["gh", *args], cwd=str(root), text=True,
                                capture_output=True, timeout=GH_TIMEOUT_SECONDS)
    except OSError as error:
        raise GhError("gh não está disponível: {}".format(error))
    except subprocess.TimeoutExpired:
        raise GhError("gh expirou após {} segundos".format(GH_TIMEOUT_SECONDS))
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise GhError(message or "gh saiu com código {}".format(result.returncode))
    return result.stdout


def authenticated(runner=gh):
    try:
        runner(["auth", "status"])
    except GhError:
        return False
    return True


def product(root=ROOT):
    """O About como `product.json` o declara.

    `homepage` é opcional: quando os dados não nomeiam nenhuma, a homepage ao vivo é deixada
    em paz em vez de comparada contra um valor que o repositório não possui.
    """
    data = json.loads((root / "product.json").read_text())
    about = {"description": data["github_description"], "topics": sorted(data["topics"])}
    homepage = data.get("homepage")
    if homepage:
        about["homepage"] = homepage
    return about


def published(runner=gh):
    data = json.loads(runner(list(VIEW_ARGS)))
    return {
        "description": data.get("description") or "",
        "topics": sorted(topic["name"] for topic in data.get("repositoryTopics") or []),
        "homepage": data.get("homepageUrl") or "",
    }


def differences(wanted, live):
    """Nomes de campo cujo valor ao vivo difere de `product.json`, em ordem estável."""
    return [field for field in ("description", "topics", "homepage")
            if field in wanted and live[field] != wanted[field]]


def shown(value):
    return ", ".join(value) if isinstance(value, list) else value


def edit_args(wanted, live):
    """Os argumentos de `gh repo edit` que fariam o GitHub combinar com `product.json`."""
    args = ["repo", "edit"]
    if live["description"] != wanted["description"]:
        args += ["--description", wanted["description"]]
    if "homepage" in wanted and live["homepage"] != wanted["homepage"]:
        args += ["--homepage", wanted["homepage"]]
    for topic in sorted(set(wanted["topics"]) - set(live["topics"])):
        args += ["--add-topic", topic]
    for topic in sorted(set(live["topics"]) - set(wanted["topics"])):
        args += ["--remove-topic", topic]
    return args


def report(fields, wanted, live, out=print):
    for field in fields:
        out("About drift: " + field)
        out("  product.json: " + shown(wanted[field]))
        out("  github:       " + shown(live[field]))


def main(argv=None, root=ROOT, runner=gh):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="relata o desvio e sai com código diferente de zero quando o About difere")
    group.add_argument("--apply", action="store_true",
                       help="escreve descrição, topics e homepage no GitHub")
    args = parser.parse_args(argv)
    wanted = product(root)
    try:
        live = published(runner)
        fields = differences(wanted, live)
        if not fields:
            print("About matches product.json: " + ", ".join(sorted(wanted)))
            return 0
        report(fields, wanted, live)
        if args.check:
            return 1
        runner(edit_args(wanted, live))
    except GhError as error:
        print("About check failed: " + str(error))
        return 1
    print("About updated from product.json: " + ", ".join(fields))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
