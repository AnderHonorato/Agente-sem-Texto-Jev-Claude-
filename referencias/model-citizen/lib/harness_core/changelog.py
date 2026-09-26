"""Fragmentos de changelog: um arquivo por mudança, montados em CHANGELOG.md no momento do lançamento.

Antes, todo branch acrescentava sua entrada ao mesmo bloco `## [Unreleased]`, então quaisquer dois
branches em andamento entravam em conflito ali; arquivos novos se mesclam sem conflito. A
nomenclatura, a isenção e a montagem estão descritas para colaboradores em `changelog.d/README.md`.
"""
import re
import subprocess
from pathlib import Path

DIRECTORY = "changelog.d"
# Mantém a ordem do Keep a Changelog; `none` é a isenção e nunca é renderizada.
KINDS = ("added", "changed", "removed", "fixed")
WAIVER = "none"
NAME = re.compile(r"^([1-9][0-9]*)\.([a-z]+)\.md$")
IGNORED = ("README.md",)
ROOTS = ("bin/", "lib/", "adapters/", "primitives/", "policy/", "docs/", "scripts/")
MINIMUM_REASON_WORDS = 3
BASE = "origin/main"
# O último lançamento cujas entradas são escritas à mão em `## [Unreleased]`. Até que o
# CHANGELOG.md do branch base carregue a seção desta versão, um branch que edita Unreleased fica
# isento da regra de fragmento; o pull request de lançamento que a dobra é, portanto, o corte.
LAST_HAND_WRITTEN = "0.13.0"


def parse_name(name):
    """(número, tipo) para o nome de um arquivo de fragmento, ou ValueError nomeando a forma esperada."""
    match = NAME.match(name)
    kinds = KINDS + (WAIVER,)
    if not match or match.group(2) not in kinds:
        raise ValueError("changelog fragment %s is not named <issue-or-pr>.<%s>.md"
                         % (name, "|".join(kinds)))
    return int(match.group(1)), match.group(2)


def is_candidate(name):
    """Se um arquivo no diretório é destinado a ser um fragmento: um `.md` visível diferente do README.

    Dotfiles, arquivos de swap/backup de editor e qualquer coisa que não termine em `.md` são
    ignorados; um `.md` que pretende ser um fragmento mas está mal nomeado é rejeitado, porque
    descartá-lo perderia uma entrada.
    """
    return name.endswith(".md") and not name.startswith(".") and name not in IGNORED


def fragments(root):
    """Cada fragmento como (número, tipo, texto), na ordem de renderização. Nomes malformados são rejeitados."""
    directory = Path(root) / DIRECTORY
    found = []
    if not directory.is_dir():
        return found
    for path in sorted(directory.iterdir()):
        if not path.is_file() or not is_candidate(path.name):
            continue
        number, kind = parse_name(path.name)
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError("changelog fragment %s is empty" % path.name)
        found.append((number, kind, text))
    order = {kind: index for index, kind in enumerate(KINDS + (WAIVER,))}
    return sorted(found, key=lambda item: (order[item[1]], item[0]))


def _entry(number, text):
    reference = "(#%d)" % number
    if reference not in text:
        text += " " + reference
    lines = text.splitlines()
    return "\n".join(["- " + lines[0]] + [("  " + line) if line.strip() else "" for line in lines[1:]])


def render(entries):
    """O corpo de uma seção de versão: um bloco `###` por tipo que tiver entradas."""
    blocks = []
    for kind in KINDS:
        items = [_entry(number, text) for number, found, text in entries if found == kind]
        if items:
            blocks.append("### %s\n\n%s" % (kind.capitalize(), "\n\n".join(items)))
    return "\n\n".join(blocks)


def assemble(changelog, version, date, entries):
    """Texto do CHANGELOG.md com uma seção `## [versão] — data` inserida sob um Unreleased vazio.

    Recusa em vez de adivinhar quando Unreleased ainda carrega entradas escritas à mão, quando a
    versão já tem uma seção, ou quando não há nada a montar.
    """
    body = render(entries)
    if not body:
        raise ValueError("no changelog fragments to assemble")
    if re.search(r"^## \[%s\]" % re.escape(version), changelog, re.MULTILINE):
        raise ValueError("CHANGELOG.md already has a section for %s" % version)
    heading = re.search(r"^## \[Unreleased\][^\n]*\n", changelog, re.MULTILINE)
    if heading is None:
        raise ValueError("CHANGELOG.md has no ## [Unreleased] heading")
    following = re.search(r"^## \[", changelog[heading.end():], re.MULTILINE)
    end = heading.end() + following.start() if following else len(changelog)
    if changelog[heading.end():end].strip():
        raise ValueError("## [Unreleased] still holds hand-written entries; fold them into a "
                         "version section or move them into fragments first")
    section = "## [%s] — %s\n\n%s\n" % (version, date, body)
    rest = changelog[end:]
    return changelog[:heading.end()] + "\n" + section + ("\n" + rest if rest else "")


class GitUnavailable(Exception):
    """git está ausente ou não respondeu a tempo; a regra é pulada, não falhada."""


def _git(root, *argv):
    try:
        out = subprocess.run(["git", "-C", str(root)] + list(argv), capture_output=True, text=True,
                             timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise GitUnavailable(str(error))
    return out.stdout if out.returncode == 0 else None


def _lines(text):
    return [line for line in (text or "").splitlines() if line]


def branch_changes(root, base=BASE):
    """(origem, alterados, adicionados) para este branch contra o ponto onde deixou `base`,
    incluindo trabalho não commitado; `added` guarda apenas arquivos que o branch cria.

    None quando não há `base` com que comparar ou o branch não tem commit próprio, então um
    checkout parado no tronco, um build de tag e um push para main nunca são julgados.
    """
    head = _git(root, "rev-parse", "HEAD")
    fork = _git(root, "merge-base", "HEAD", base)
    if not head or not fork or head.strip() == fork.strip():
        return None
    fork = fork.strip()
    diffed = _git(root, "diff", "--name-only", fork)
    created = _git(root, "diff", "--name-only", "--diff-filter=A", fork)
    untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    if diffed is None or created is None or untracked is None:
        return None
    changed = sorted(set(_lines(diffed) + _lines(untracked)))
    added = sorted(set(_lines(created) + _lines(untracked)))
    return fork, changed, added


def unreleased_span(text):
    """Números de linha 1-based (primeiro, último) do corpo da seção `## [Unreleased]`, ou None."""
    lines = (text or "").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("## [Unreleased]")), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## [")), len(lines))
    return start + 1, end


def _overlaps(span, first, count):
    if span is None:
        return False
    last = first + max(count, 1) - 1
    return first <= span[1] and last >= span[0]


def touches_unreleased(root, fork):
    """Se o diff do CHANGELOG.md do branch cai em Unreleased, em qualquer lado do diff,
    de modo que uma entrada adicionada ali e um lançamento que a dobra para fora contam ambos."""
    diff = _git(root, "diff", "-U0", fork, "--", "CHANGELOG.md")
    if not diff:
        return False
    before = unreleased_span(_git(root, "show", "%s:CHANGELOG.md" % fork))
    path = Path(root) / "CHANGELOG.md"
    after = unreleased_span(path.read_text(encoding="utf-8") if path.is_file() else "")
    for match in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", diff, re.MULTILINE):
        old_first, old_count, new_first, new_count = match.groups()
        if (_overlaps(before, int(old_first), int(old_count or 1)) or
                _overlaps(after, int(new_first), int(new_count or 1))):
            return True
    return False


def hand_written_release_open(root, fork):
    """True até que o CHANGELOG.md do branch base tenha uma seção para LAST_HAND_WRITTEN."""
    base = _git(root, "show", "%s:CHANGELOG.md" % fork) or ""
    return not re.search(r"^## \[%s\]" % re.escape(LAST_HAND_WRITTEN), base, re.MULTILINE)


VERSION_HEADING = re.compile(r"^## \[([0-9][^\]]*)\]", re.MULTILINE)


def assembles_release(root, fork):
    """Se o branch é um lançamento: seu CHANGELOG.md ganha uma seção `## [<versão>]` que a base
    não tem e ele apaga fragmentos que a base carregava, que é o que `release_notes.py --changelog`
    deixa para trás. Um branch assim consome fragmentos, então pedir a ele um seria abandonar uma isenção."""
    path = Path(root) / "CHANGELOG.md"
    after = set(VERSION_HEADING.findall(path.read_text(encoding="utf-8") if path.is_file() else ""))
    before = set(VERSION_HEADING.findall(_git(root, "show", "%s:CHANGELOG.md" % fork) or ""))
    if not after - before:
        return False
    deleted = _git(root, "diff", "--name-only", "--diff-filter=D", fork, "--", DIRECTORY + "/")
    return any(is_candidate(Path(name).name) and name.count("/") == 1 for name in _lines(deleted))


def reason_words(text):
    return [word for word in text.split() if re.search(r"[A-Za-z]", word)]


def findings(root, notes=None):
    """Achados do lint: um fragmento malformado ou mal colocado, uma isenção rasa, ou um branch que
    toca ROOTS sem adicionar um fragmento, a menos que monte um lançamento. Por que a regra foi
    pulada, se foi, vai para `notes`."""
    root = Path(root)
    hits = []
    try:
        fragments(root)
    except ValueError as error:
        hits.append("changelog: %s" % error)
    directory = root / DIRECTORY
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            if path.is_dir():
                hits.append("changelog: %s/%s/ is a subdirectory; fragments live directly in %s/"
                            % (DIRECTORY, path.name, DIRECTORY))
    try:
        found = branch_changes(root)
        if found is None:
            return hits
        fork, changed, added = found
        touched = [path for path in changed if path.startswith(ROOTS)]
        if not touched:
            return hits
        new = [path for path in added if path.startswith(DIRECTORY + "/")
               and path.count("/") == 1 and is_candidate(Path(path).name) and (root / path).is_file()]
        for path in new:
            try:
                kind = parse_name(Path(path).name)[1]
            except ValueError:
                continue
            words = reason_words((root / path).read_text(encoding="utf-8"))
            if kind == WAIVER and len(words) < MINIMUM_REASON_WORDS:
                hits.append("changelog: waiver %s must give a reason of at least %d words"
                            % (path, MINIMUM_REASON_WORDS))
        if new:
            return hits
        if hand_written_release_open(root, fork) and touches_unreleased(root, fork):
            return hits
        if assembles_release(root, fork):
            return hits
    except GitUnavailable as error:
        if notes is not None:
            notes.append("changelog: fragment rule skipped, git unavailable (%s)" % error)
        return hits
    hits.append("changelog: this branch changes %s but adds no fragment; add %s/<issue-or-pr>.<%s>.md, "
                "or %s/<issue-or-pr>.%s.md saying in at least %d words why no entry is needed"
                % (touched[0] + (" and %d more" % (len(touched) - 1) if len(touched) > 1 else ""),
                   DIRECTORY, "|".join(KINDS), DIRECTORY, WAIVER, MINIMUM_REASON_WORDS))
    return hits
