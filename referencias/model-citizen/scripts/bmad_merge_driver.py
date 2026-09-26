#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Drivers de merge do git para o mapa de issues do BMad e o status de sprint derivado dele.

Dois branches que cada um reserva um ID do BMad ambos anexam a `items` e incrementam `next_ids`,
então o segundo a mesclar costumava entrar em conflito textual. `map` mescla as três versões item
por item: o mapa do lado principal, mais as entradas que o outro lado adicionou, com o maior
`next_ids` por tipo. Quando os dois lados mapearam a mesma issue do GitHub sob IDs diferentes, a
entrada do lado principal vence. O lado principal é o que está entrando (incoming) num merge, já
que agentes mesclam main dentro do próprio branch, e é o upstream num rebase.

`sprint-status` não consegue mesclar o arquivo derivado a partir de suas próprias três versões, e
qualquer coisa que escreve na árvore de trabalho nunca alcança o commit de merge. Ele reconstrói o
mapa mesclado e os arquivos de história mesclados a partir dos dois commits sendo mesclados,
renderiza-os, e retorna essa renderização como o resultado do merge, então o commit de merge
carrega uma regeneração fresca. Ele suporta `git merge` e `git pull`, que nomeiam o commit
entrando; em qualquer outro lugar ele relata um conflito e deixa o arquivo do seu lado, e você o
regenera com `python3 scripts/bmad_issue_sync.py sprint-status`.

Os dois saem com 1 em qualquer coisa que não conseguem mesclar exatamente, o que o git relata
como um conflito. Uma duplicata genuína, um ID reivindicado por duas issues diferentes, mantém as
duas entradas para que a auditoria ainda falhe nela. Registre-as com `citizen worktree create`,
ou com os comandos em docs/bmad-governance.md.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmad_issue_sync as sync  # noqa: E402


HEX_OID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
EMPTY_MAP = {"items": [], "next_ids": {}}


class Unmergeable(Exception):
    """Um merge que o driver não consegue resolver exatamente; o git o relata como um conflito."""


def serialize(manifest):
    """O formato de bytes que `bmad_issue_sync.write_manifest` escreve."""
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


def parse_map(text, side):
    try:
        manifest = json.loads(text) if text.strip() else dict(EMPTY_MAP)
    except ValueError:
        raise Unmergeable("the {} issue map is not valid JSON".format(side))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("items", []), list):
        raise Unmergeable("the {} issue map has no item list".format(side))
    counters = manifest.get("next_ids", {})
    if not isinstance(counters, dict):
        raise Unmergeable("the {} issue map's next_ids is not an object".format(side))
    for kind, value in counters.items():
        # `type` em vez de isinstance, já que JSON true é um bool do Python e bool é um int.
        if type(value) is not int:
            raise Unmergeable("the {} issue map's next {} ID is not an integer".format(side, kind))
    return manifest


def merge_value(key, base, main, branch, conflicts):
    if main == branch or branch == base:
        return main
    if main == base:
        return branch
    conflicts.append(key)
    return main


def merge_item(base, main, branch, conflicts):
    merged = {}
    for key in list(main) + [key for key in branch if key not in main]:
        value = merge_value(
            "{} {}".format(main.get("bmad_id") or branch.get("bmad_id"), key),
            base.get(key, sync.MISSING), main.get(key, sync.MISSING), branch.get(key, sync.MISSING), conflicts,
        )
        if value is not sync.MISSING:
            merged[key] = value
    return merged


def items_by_id(manifest):
    return {item.get("bmad_id"): item for item in manifest.get("items", [])}


def merge_maps(base, ours, theirs, main_is_ours=False):
    """Merge de três vias de mapas já analisados; retorna (mesclado, conflitos, avisos)."""
    main, branch = (ours, theirs) if main_is_ours else (theirs, ours)
    conflicts, notices = [], []
    base_items, main_items, branch_items = (items_by_id(manifest) for manifest in (base, main, branch))
    items = []
    for bmad_id, item in main_items.items():
        other = branch_items.get(bmad_id)
        before = base_items.get(bmad_id)
        if other is None:
            if before is None:
                items.append(item)
            elif before != item:
                conflicts.append("{} was removed on one side and changed on the other".format(bmad_id))
                items.append(item)
            continue
        if before is None and other != item:
            # Os dois lados usaram um ID para trabalhos diferentes: uma duplicata genuína que a auditoria precisa ver.
            conflicts.append("{} was reserved on both sides".format(bmad_id))
            items.extend([item, other])
            continue
        items.append(merge_item(before or {}, item, other, conflicts))
    main_issues = {item.get("github_number") for item in main.get("items", [])}
    for bmad_id, item in branch_items.items():
        if bmad_id in main_items:
            continue
        before = base_items.get(bmad_id)
        if before is not None:
            if before != item:
                conflicts.append("{} was removed on one side and changed on the other".format(bmad_id))
                items.append(item)
            continue
        if item.get("github_number") in main_issues:
            notices.append("{} dropped: main maps issue #{} under another ID".format(
                bmad_id, item.get("github_number")
            ))
            continue
        items.append(item)
    merged = {}
    for key in list(main) + [key for key in branch if key not in main]:
        if key == "items":
            merged[key] = sorted(items, key=lambda value: value.get("github_number") or 0)
        elif key == "next_ids":
            counters = dict(main.get(key) or {})
            for kind, value in (branch.get(key) or {}).items():
                current = counters.get(kind)
                if current is None or value > current:
                    counters[kind] = value
            merged[key] = counters
        else:
            value = merge_value(key, base.get(key, sync.MISSING), main.get(key, sync.MISSING),
                                branch.get(key, sync.MISSING), conflicts)
            if value is not sync.MISSING:
                merged[key] = value
    return merged, conflicts, notices


def git(*args, input_data=None):
    result = subprocess.run(
        ["git"] + list(args), input=input_data, capture_output=True, timeout=sync.GIT_TIMEOUT_SECONDS
    )
    if result.returncode != 0:
        raise Unmergeable("git {} failed: {}".format(args[0], result.stderr.decode("utf-8", "replace").strip()))
    return result.stdout


def rebasing():
    for name in ("rebase-merge", "rebase-apply"):
        if Path(git("rev-parse", "--git-path", name).decode().strip()).exists():
            return True
    return False


def incoming_commit():
    """O commit que `git merge` está mesclando, que ele nomeia numa variável GITHEAD_<oid>."""
    oids = [name[len("GITHEAD_"):] for name in os.environ if name.startswith("GITHEAD_")]
    oids = [oid for oid in oids if HEX_OID.match(oid)]
    if len(oids) != 1:
        raise Unmergeable("the incoming commit is not known outside a two-head git merge")
    return oids[0]


def tree_blobs(commit, directory):
    """{path: blob} para os arquivos sob `directory` em `commit`."""
    out = git("ls-tree", "-r", "-z", commit, "--", directory).decode("utf-8")
    blobs = {}
    for entry in filter(None, out.split("\0")):
        meta, path = entry.split("\t", 1)
        blobs[path] = meta.split()[2]
    return blobs


def read_blobs(oids):
    """{oid: bytes} através de um único `git cat-file --batch`."""
    oids = sorted(set(oids))
    if not oids:
        return {}
    out = git("cat-file", "--batch", input_data="".join(oid + "\n" for oid in oids).encode())
    contents, offset = {}, 0
    for oid in oids:
        header_end = out.index(b"\n", offset)
        header = out[offset:header_end].split()
        if len(header) != 3:
            raise Unmergeable("git cat-file could not read {}".format(oid))
        size = int(header[2])
        contents[oid] = out[header_end + 1:header_end + 1 + size]
        offset = header_end + 1 + size + 1
    return contents


def merge_story(path, base, ours, theirs, contents, scratch):
    """O conteúdo que o merge limpo do git dá a um arquivo de história, ou None quando o arquivo está ausente."""
    if ours == theirs or theirs == base:
        oid = ours
    elif ours == base:
        oid = theirs
    else:
        files = []
        for index, oid in enumerate((ours, base, theirs)):
            file = Path(scratch) / "story-{}".format(index)
            file.write_bytes(contents[oid] if oid else b"")
            files.append(str(file))
        result = subprocess.run(["git", "merge-file", "-p"] + files, capture_output=True,
                                timeout=sync.GIT_TIMEOUT_SECONDS)
        if result.returncode != 0:
            raise Unmergeable("{} conflicts, so the sprint status waits for its resolution".format(path))
        return result.stdout
    return contents[oid] if oid else None


def merged_sprint_status():
    """Renderiza o status de sprint a partir da árvore que o merge em andamento vai commitar."""
    if rebasing():
        raise Unmergeable("a rebase replays commits without naming them to the driver")
    theirs = incoming_commit()
    bases = git("merge-base", "--all", "HEAD", theirs).decode().split()
    if len(bases) != 1:
        raise Unmergeable("the merge has {} merge bases, not one".format(len(bases)))
    commits = (bases[0], "HEAD", theirs)
    directory = "_bmad-output/"
    trees = [tree_blobs(commit, directory) for commit in commits]
    contents = read_blobs(oid for tree in trees for oid in tree.values())
    maps = []
    for side, tree in zip(("base", "ours", "theirs"), trees):
        oid = tree.get(sync.MAP_RELATIVE_PATH)
        maps.append(parse_map(contents[oid].decode("utf-8") if oid else "", side))
    manifest, conflicts, _ = merge_maps(*maps)
    if conflicts:
        raise Unmergeable("the issue map conflicts: {}".format("; ".join(conflicts)))
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch) / "tree"
        for item in manifest["items"]:
            path = item["artifact_path"]
            text = merge_story(path, *(tree.get(path) for tree in trees), contents, scratch)
            if text is not None:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(text)
        saved = sync.ROOT
        sync.ROOT = root
        try:
            return sync.render_sprint_status(manifest)
        finally:
            sync.ROOT = saved


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 4 or argv[0] not in {"map", "sprint-status"}:
        print("usage: bmad_merge_driver.py map|sprint-status BASE OURS THEIRS", file=sys.stderr)
        return 2
    kind, base_path, ours_path, theirs_path = argv
    try:
        if kind == "map":
            texts = [Path(path).read_text(encoding="utf-8") for path in (base_path, ours_path, theirs_path)]
            maps = [parse_map(text, side) for text, side in zip(texts, ("base", "ours", "theirs"))]
            merged, conflicts, notices = merge_maps(*maps, main_is_ours=rebasing())
            for notice in notices:
                print("bmad merge driver: {}".format(notice), file=sys.stderr)
            Path(ours_path).write_bytes(serialize(merged).encode("utf-8"))
            if conflicts:
                raise Unmergeable("; ".join(conflicts))
            return 0
        rendered = merged_sprint_status()
        Path(ours_path).write_bytes(rendered.encode("utf-8"))
        return 0
    except (Unmergeable, OSError, UnicodeDecodeError, subprocess.SubprocessError) as error:
        print("bmad merge driver: {}; resolve by hand, then run {}".format(error, sync.SPRINT_STATUS_COMMAND),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
