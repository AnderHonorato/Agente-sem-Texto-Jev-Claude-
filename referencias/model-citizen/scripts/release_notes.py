#!/usr/bin/env python3
"""Renderiza as notas de lançamento a partir das mesmas autoridades de produto e compatibilidade do site.

Com `--changelog VERSION`, monta os fragmentos de `changelog.d/` no CHANGELOG.md em vez disso; o
formato e a ordenação dos fragmentos são de `harness_core.changelog`.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from harness_core import changelog, compatibility


def notes(root=ROOT):
    product = json.loads((root / "product.json").read_text())
    data = compatibility.catalog(root)
    migration = json.loads((root / "compatibility" / "migration.json").read_text())
    version = (root / "VERSION").read_text().strip()
    if (migration.get("schema_version") != 1 or migration.get("harness_version") != version or
            not isinstance(migration.get("summary"), str) or not migration["summary"] or
            not isinstance(migration.get("actions"), list) or not migration["actions"] or
            any(not isinstance(item, str) or not item for item in migration["actions"]) or
            not isinstance(migration.get("recovery"), list) or not migration["recovery"] or
            any(not isinstance(item, str) or not item for item in migration["recovery"])):
        raise ValueError("os metadados de migração precisam combinar com VERSION e conter actions e recovery")
    policy = "https://github.com/JakeSelby/agent-harness/blob/v%s/docs/compatibility-policy.md" % version
    lines = ["# " + product["headline"], "", product["description"], "", product["stances"], "", "## Compatibility", ""]
    lines += ["- " + row["id"] + ": " + row["status"] for row in data["clients"]]
    lines += ["", "Native restrictions remain authoritative. See the versioned compatibility catalog for evidence and gaps.",
              "", "## Compatibility policy", "",
              "Stable interfaces, preview boundaries, deprecation, migration and failed-release recovery are defined in the [versioned compatibility policy](%s)." % policy,
              "", "## Migration", "", migration["summary"], ""]
    lines += ["- " + item for item in migration["actions"]]
    lines += ["", "### Recovery", ""] + ["- " + item for item in migration["recovery"]]
    return "\n".join(lines) + "\n"


def write_changelog(version, date, root=ROOT, dry_run=False):
    """Dobra cada fragmento no CHANGELOG.md sob `version` e apaga os fragmentos."""
    entries = changelog.fragments(root)
    path = root / "CHANGELOG.md"
    text = changelog.assemble(path.read_text(encoding="utf-8"), version, date, entries)
    if dry_run:
        return text
    path.write_text(text, encoding="utf-8")
    for item in sorted((root / changelog.DIRECTORY).iterdir()):
        if item.is_file() and changelog.is_candidate(item.name):
            item.unlink()
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--changelog", metavar="VERSION",
                        help="monta os fragmentos de changelog.d/ no CHANGELOG.md sob VERSION")
    parser.add_argument("--date", default=datetime.date.today().isoformat(),
                        help="com --changelog, a data do lançamento (padrão hoje)")
    parser.add_argument("--dry-run", action="store_true",
                        help="com --changelog, imprime o resultado e não muda nada")
    args = parser.parse_args(argv)
    if not args.changelog:
        print(notes(), end="")
        return 0
    try:
        text = write_changelog(args.changelog, args.date, dry_run=args.dry_run)
    except ValueError as error:
        print("notas de lançamento: %s" % error, file=sys.stderr)
        return 1
    if args.dry_run:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
