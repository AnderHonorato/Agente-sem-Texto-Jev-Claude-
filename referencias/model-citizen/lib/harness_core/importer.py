"""Lê um CLAUDE.md, AGENTS.md ou `.cursorrules` existente para dentro de primitivas.

Adotar o harness não deveria significar descartar as instruções que um repositório já carrega,
então o arquivo é dividido em vez de substituído: cada seção `##` de nível superior vira uma
regra, a prosa acima da primeira seção vira uma regra de preâmbulo, um `@`-import de CLAUDE.md é
seguido um nível e vira uma regra própria, e o front matter de `.cursor/rules/*.mdc` é carregado
inalterado. Nada é descartado. Qualquer coisa que o divisor não consiga posicionar — um
cabeçalho que não produz identificador, uma segunda seção reivindicando um nome já usado, uma
linha de front matter que não é um campo — cai numa única regra `-unsorted` com uma nota
dizendo isso, porque uma omissão silenciosa de um arquivo de instruções é o único resultado que
uma importação nunca deve produzir.

O divisor é deliberadamente conservador sobre o que conta como um cabeçalho: um `##` dentro de um
bloco de código cercado é texto, não estrutura.
"""
import hashlib
import json
import re
from datetime import date
from pathlib import Path

# As chaves de front matter que uma regra `.mdc` do Cursor carrega. Elas decidem quando uma
# regra se aplica, então sobrevivem à divisão literalmente em vez de serem re-derivadas do corpo.
MDC_KEYS = ("description", "globs", "alwaysApply")
HEADING = re.compile(r"^##(?!#)\s*(.*?)\s*$")
IMPORT = re.compile(r"^\s*@(\S+)\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
UNSORTED_NOTE = ("Imported content the splitter could not place under a heading of its own. "
                 "Nothing here was dropped; sort it into rules by hand.")


def kind_of(path):
    """Que tipo de arquivo de instrução é este, a partir do nome e do sufixo."""
    path = Path(path)
    if path.name == "CLAUDE.md":
        return "claude"
    if path.name == "AGENTS.md":
        return "agents"
    if path.name == ".cursorrules":
        return "cursorrules"
    if path.suffix == ".mdc":
        return "mdc"
    raise ValueError("import reads CLAUDE.md, AGENTS.md, .cursorrules or a .cursor/rules/*.mdc "
                     "file; got " + path.name)


def slug(text):
    """Um identificador de primitiva para um cabeçalho, ou uma string vazia quando não produz nenhum."""
    flattened = "".join(c.lower() if (c.isascii() and c.isalnum()) else "-" for c in text)
    parts = [part for part in flattened.split("-") if part]
    name = "-".join(parts)
    return ("rule-" + name) if name[:1].isdigit() else name


def default_name(path, kind):
    """O nome da importação: o próprio stem do arquivo `.mdc`, senão o diretório em que foi encontrado."""
    path = Path(path)
    candidates = [path.stem] if kind == "mdc" else [path.parent.name, path.stem]
    for candidate in candidates:
        found = slug(candidate)
        if found:
            return found
    return "imported"


def frontmatter(text):
    """`(fields, unparsed lines, body)` para um bloco `---` inicial; campos vazios quando não há nenhum."""
    if not text.startswith("---\n"):
        return {}, [], text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, [], text
    header, body = text[4:end], text[end + 4:].lstrip("\n")
    fields, extra = {}, []
    for line in header.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() and key.strip() == key.strip().split()[0] and key not in fields:
            fields[key.strip()] = value.strip()
        elif line.strip():
            extra.append(line)
    return fields, extra, body


def _sections(body):
    """`(linhas de preâmbulo, [(cabeçalho, linhas)])`, com blocos cercados deixados intactos."""
    preamble, sections, fence, current = [], [], None, None
    for line in body.splitlines():
        marker = FENCE.match(line)
        if marker:
            token = marker.group(1)
            fence = token if fence is None else (None if fence == token else fence)
        heading = None if fence else HEADING.match(line)
        if heading:
            current = (heading.group(1), [line])
            sections.append(current)
            continue
        (current[1] if current else preamble).append(line)
    return preamble, sections


def _imports(body):
    """Imports `@path` de linha inteira fora de blocos cercados, em ordem e sem duplicatas."""
    found, fence = [], None
    for line in body.splitlines():
        marker = FENCE.match(line)
        if marker:
            token = marker.group(1)
            fence = token if fence is None else (None if fence == token else fence)
            continue
        match = None if fence else IMPORT.match(line)
        if match and match.group(1) not in found:
            found.append(match.group(1))
    return found


def _render(fields, lines):
    body = "\n".join(lines).strip("\n")
    header = "".join(key + ": " + value + "\n" for key, value in fields.items())
    return "---\n" + header + "---\n\n" + body + "\n"


def _heading_of(text):
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def plan(path, name=None, today=None):
    """`(files, notices)`: cada regra que a importação escreveria, e o que não conseguiu resolver.

    Um arquivo é `{"path": "rules/<slug>.md", "text": ...}` relativo à raiz de primitivas que o
    chamador escolheu. Nada é escrito aqui; o chamador decide se este plano é impresso ou aplicado.
    """
    path = Path(path).expanduser()
    kind = kind_of(path)
    source = str(path.resolve())
    stamp = today or date.today().isoformat()
    text = path.read_text(encoding="utf-8")
    fields, extra, body = frontmatter(text)
    name = slug(name) if name else default_name(path, kind)
    if not name:
        raise ValueError("--name must be a primitive identifier: lowercase letters, digits, hyphens")
    carried = {key: fields[key] for key in MDC_KEYS if key in fields}

    def base(**more):
        return dict({"source": source, "imported": stamp}, **dict(carried, **more))

    files, notices, unsorted, taken = [], [], [], set()
    if extra:
        unsorted.append("Front-matter lines that are not fields:")
        unsorted.extend(extra)
    preamble, sections = _sections(body)
    if "\n".join(preamble).strip():
        files.append({"path": "rules/" + name + "-preamble.md",
                      "text": _render(base(), preamble)})
        taken.add(name + "-preamble")
    for heading, lines in sections:
        identifier = slug(heading)
        if not identifier or identifier in taken:
            unsorted.extend(lines if identifier else [""] + lines)
            if identifier:
                notices.append("second section named '" + heading + "'; kept in " + name + "-unsorted")
            else:
                notices.append("heading '" + heading + "' yields no identifier; kept in " + name + "-unsorted")
            continue
        taken.add(identifier)
        files.append({"path": "rules/" + identifier + ".md",
                      "text": _render(base(heading=heading), lines)})
    for reference in _imports(body) if kind in ("claude", "agents") else []:
        target = Path(reference).expanduser()
        if not target.is_absolute():
            target = path.parent / target
        if not target.is_file():
            notices.append("@" + reference + " does not resolve to a readable file; its line was kept")
            continue
        imported = target.read_text(encoding="utf-8")
        identifier = slug(target.stem) or (name + "-import")
        while identifier in taken:
            identifier += "-import"
        taken.add(identifier)
        files.append({"path": "rules/" + identifier + ".md",
                      "text": _render({"source": str(target.resolve()), "imported": stamp,
                                       "heading": _heading_of(imported) or target.stem},
                                      imported.splitlines())})
    if "\n".join(unsorted).strip():
        files.append({"path": "rules/" + name + "-unsorted.md",
                      "text": _render(base(), [UNSORTED_NOTE, ""] + unsorted)})
    return files, notices


def digest(root, files):
    """Uma impressão digital estável de um plano, para que uma segunda execução reconheça o plano que imprimiu."""
    payload = json.dumps([str(root)] + [[item["path"], item["text"]] for item in files],
                         sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
