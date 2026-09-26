"""Nomes duplicados de skill, agente e comando entre raízes de primitivas.

Um runtime resolve duas definições de um mesmo nome em silêncio, o primeiro vence, sem aviso: o
perdedor simplesmente nunca é carregado, e nada num transcript diz qual deles rodou. Duas
instalações irmãs projetando a mesma skill em `~/.claude/skills/` é a forma pela qual este
repositório já foi mordido (`docs/bmad.md`), então os nomes são coletados em cada raiz que uma
configuração registra e uma duplicata é recusada antes que a sincronização escreva qualquer coisa.

wshobson/agents traz `tools/check_agent_name_collisions.py` contra o mesmo problema; este
verificador é escrito para as próprias raízes e tipos do harness em vez de adaptado a partir dele.

Um `.claude/agents/*.md` ou `.claude/skills/<name>/` em nível de projeto não é uma colisão: uma
definição de projeto legitimamente tem precedência sobre uma em nível de usuário. É reportada como
uma sombra em vez disso, para que a precedência seja visível em vez de descoberta.
"""
from pathlib import Path

# O tipo que cada chamador enxerga, e o diretório de primitivas em que é escrito.
KINDS = (("skill", "skills"), ("agent", "roles"), ("command", "workflows"))


def roots(root, config):
    """As raízes de primitivas a pesquisar: a embutida, depois as configuradas, em ordem."""
    found = [Path(root) / "primitives"]
    entries = config.get("primitive_roots") if isinstance(config, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, str) and entry.strip():
            path = Path(entry).expanduser()
            if path.is_absolute():
                found.append(path)
    return found


def _display(path, root):
    """Um path como um leitor pode situá-lo: relativo dentro do checkout, absoluto fora dele."""
    try:
        return str(Path(path).relative_to(Path(root)))
    except ValueError:
        return str(path)


def _sources(directory, kind):
    """Cada definição de um tipo num diretório, como (nome, path), ordenada por nome."""
    if not directory.is_dir():
        return []
    if kind == "skill":
        return sorted((child.name, child / "SKILL.md") for child in directory.iterdir()
                      if child.is_dir() and (child / "SKILL.md").is_file())
    return sorted((path.stem, path) for path in directory.glob("*.md") if path.is_file())


def names(root, config):
    """Todo nome definido, como {tipo: {nome: [paths de exibição, na ordem das raízes]}}."""
    found = {kind: {} for kind, _ in KINDS}
    for source in roots(root, config):
        for kind, directory in KINDS:
            for name, path in _sources(source / directory, kind):
                found[kind].setdefault(name, []).append(_display(path, root))
    return found


def collisions(root, config):
    """Nomes definidos mais de uma vez, como (nome, tipo, [paths]), ordenados para um relatório estável."""
    found = names(root, config)
    return sorted(((name, kind, paths) for kind, _ in KINDS
                   for name, paths in found[kind].items() if len(paths) > 1),
                  key=lambda item: (item[1], item[0]))


def findings(root, config):
    """Uma linha por colisão, nomeando cada fonte, mais o que fazer a respeito."""
    lines = ["collision: " + kind + " '" + name + "' is defined in " + " and ".join(paths)
             for name, kind, paths in collisions(root, config)]
    if lines:
        lines.append("collision: a runtime resolves a duplicate name silently, first-wins; rename one "
                     "of them or unregister the primitive root that carries it")
    return lines


def shadows(root, config, project):
    """Definições de projeto que têm precedência sobre um nome em nível de usuário, uma linha de aviso cada.

    Não é uma falha: o próprio `.claude/` de um projeto é como um repositório sobrepõe o harness do
    usuário, e dizer qual nome ele assume é todo o remédio necessário.
    """
    if project is None:
        return []
    claude = Path(project) / ".claude"
    found = names(root, config)
    lines = []
    for kind, directory in (("skill", "skills"), ("agent", "agents")):
        for name, path in _sources(claude / directory, kind):
            if name in found[kind]:
                lines.append("shadowed: project " + kind + " '" + name + "' at " + str(path) +
                             " outranks the user-level definition in " + found[kind][name][0])
    return sorted(lines)
