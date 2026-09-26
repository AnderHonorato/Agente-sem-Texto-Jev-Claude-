"""O catálogo de autoria compartilhado; os arquivos de runtime são projeções reproduzíveis."""
import hashlib
import importlib.util
import json
import re
from pathlib import Path

IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]*$")
# Todo tipo de primitiva: seu diretório sob uma raiz de primitivas, os arquivos que são suas
# unidades, o valor que uma seleção lhe atribui e o que a sincronização projeta a partir dela.
# Tipos `variant` escolhem um arquivo nomeado por dimensão; tipos `switch` são `on` ou `off`,
# padrão `on`; um tipo sem valor não é selecionável. `policy/hooks/posture.py` lê este mapa para
# resolver uma seleção, então um tipo novo é uma entrada aqui. `hooks` não tem diretório: suas
# unidades são os módulos de ciclo de vida que `HOOK_IDS` nomeia.
# Todo módulo de política que responde a um evento de ciclo de vida, pelo seu nome-base sob
# `policy/hooks/`. Os adaptadores das duas runtimes despacham através de `lifecycle.py`, então
# esta única lista é o id de hook de cada runtime; um módulo que os outros arquivos de
# `policy/hooks/` carregam como biblioteca não tem id nem switch.
HOOK_IDS = ("allow-plan-webfetch", "allow-readonly-bash", "approvals", "brief-guard", "filter-output",
            "grade-bash", "harness-session", "neutralize-tool-output", "stage-user-files", "stop-gate",
            "tier-agent-spawns", "usage-feed", "usage-log", "validate-plan-card")
# Os hooks que impõem em vez de apenas auxiliar: `off` só com `core_switches_acknowledged` true.
CORE_HOOKS = ("brief-guard", "grade-bash", "neutralize-tool-output", "stop-gate")
HOOKS_DIRECTORY = "policy/hooks"
KINDS = {
    "rules": {"directory": "rules", "pattern": "*.md", "value": "switch", "projection": "rule link"},
    "stances": {"directory": "stances", "pattern": "*/*.md", "value": "variant",
                "projection": "stance link and generated instructions"},
    "skills": {"directory": "skills", "pattern": "*/SKILL.md", "value": "switch", "projection": "skill link"},
    "roles": {"directory": "roles", "pattern": "*.md", "value": "switch", "projection": "agent definition"},
    "workflows": {"directory": "workflows", "pattern": "*.md", "value": "switch",
                  "projection": "command and generated skill"},
    "hooks": {"directory": None, "pattern": None, "units": HOOK_IDS, "value": "switch",
              "projection": "settings hook"},
    "presentation": {"directory": "presentation", "pattern": "*.md", "value": None, "projection": "output style"},
}
# Classes de capacidade, da mais forte para a mais fraca. Um papel compartilhado nomeia a classe
# que seu trabalho exige; o bindings.json de cada adaptador mapeia as classes que qualificou para
# seus próprios modelos nativos.
TIER_CLASSES = ("frontier", "strong", "standard", "light")
EFFORTS = ("low", "medium", "high")
# O que um `constraints.json` de regra pode conter. `excludes_roles` é a única condição que lê
# algo além da seleção: o frontmatter de um contrato de papel, com `allow` nomeando os papéis que
# uma skill isenta. Contrato de autoria: docs/primitive-authoring.md.
CONSTRAINT_KEYS = {"when", "requires", "excludes", "excludes_roles", "reason"}
# O que uma entrada `roles.<name>` de um adaptador pode conter, além do `model` que um override
# pode adicionar. `tools` é opcional: um papel que o omite herda todas as ferramentas que a sessão
# possui, o que é a única forma de um disparo redirecionado manter as ferramentas MCP que um
# disparo `general-purpose` teria tido, e `disallowed_tools` é então como ele devolve a única
# ferramenta que não deve possuir.
BINDING_KEYS = {"claude-code": ("tools", "disallowed_tools", "effort"),
                "codex": ("model_reasoning_effort",)}
# A grafia que cada chave assume no arquivo nativo; qualquer coisa ausente aqui já é nativa.
NATIVE_KEYS = {"disallowed_tools": "disallowedTools"}


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("primitive identifiers use lowercase letters, digits and hyphens")
    return value


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter: " + str(path))
    _, header, body = text.split("---", 2)
    fields = {}
    for line in header.strip().splitlines():
        key, sep, value = line.partition(":")
        if not sep or key in fields:
            raise ValueError("invalid or duplicate frontmatter field: " + str(path))
        fields[key] = value.strip()
    return fields, body.lstrip("\n")


def stance_roots(root, config):
    """O diretório de stances embutido e o de cada raiz de primitivas configurada, na ordem de carga."""
    roots = [root / "primitives" / "stances"]
    for entry in config.get("primitive_roots", []):
        custom = Path(entry).expanduser()
        if not custom.is_absolute():
            raise ValueError("primitive_roots must be absolute directories")
        roots.append(custom / "stances")
    return roots


def stance_constraints(root, config):
    """Cada constraint que uma raiz configurada traz, como pares (arquivo, regra), validados no caminho.

    Uma regra declara uma seleção `when` não vazia, um `reason`, e pelo menos um entre `requires`,
    `excludes` e `excludes_roles`; qualquer outra coisa nela é um erro de autoria em vez de uma
    chave que uma versão futura poderia significar, então é rejeitada aqui em vez de ser ignorada.
    """
    rules = []
    for source in stance_roots(root, config):
        path = source.parent / "constraints.json"
        if not path.exists():
            continue
        for rule in json.loads(path.read_text()).get("stances", []):
            unknown = set(rule) - CONSTRAINT_KEYS
            if unknown:
                raise ValueError("unknown stance constraint field(s): " + ", ".join(sorted(unknown)))
            if not isinstance(rule.get("when"), dict) or not rule["when"]:
                raise ValueError("stance constraints require a nonempty when selection")
            if not str(rule.get("reason", "")).strip():
                raise ValueError("a stance constraint states its reason: " + json.dumps(rule["when"]))
            if not any(rule.get(key) for key in ("requires", "excludes", "excludes_roles")):
                raise ValueError("a stance constraint rules something out: " + json.dumps(rule["when"]))
            rules.append((path, rule))
    return rules


def excluded_roles(root, condition):
    """Papéis embutidos cujo frontmatter combina com `condition`, menos os que ela permite por nome.

    A camada de stance escolhe variantes, mas o texto de uma variante também pode contradizer um
    contrato de papel: `delegation/tiered` recusa a classe frontier enquanto dois papéis de design
    a declaram. `allow` é como uma constraint carrega a exceção em nível de skill em vez de
    deixá-la apenas em prosa.
    """
    if not condition:
        return []
    allowed = set(condition.get("allow", []))
    fields = {k: v for k, v in condition.items() if k != "allow"}
    if not fields:
        raise ValueError("excludes_roles names at least one frontmatter field")
    hits = []
    for path in sorted((root / "primitives" / "roles").glob("*.md")):
        if path.stem in allowed:
            continue
        header, _ = frontmatter(path)
        if all(header.get(key) == value for key, value in fields.items()):
            hits.append(path.stem)
    return hits


def stance_conflicts(root, config):
    """Uma mensagem por constraint que a seleção viola, cada uma terminando na razão da regra.

    Um conflito é um achado antes de ser qualquer outra coisa — `harness stances` e `harness lint`
    imprimem estes — e `resolve_stances` é o único chamador que transforma o primeiro deles no
    erro fatal que uma sincronização sempre levantou, então nenhuma projeção é escrita a partir de
    uma contradição.
    """
    selected = config.get("stances", {})
    if not isinstance(selected, dict):
        raise ValueError("stances must be an object")
    findings = []
    for _, rule in stance_constraints(root, config):
        if not all(selected.get(key) == value for key, value in rule["when"].items()):
            continue
        when = ", ".join(k + ": " + v for k, v in sorted(rule["when"].items()))
        for key, value in sorted(rule.get("requires", {}).items()):
            if selected.get(key) != value:
                findings.append(when + " requires " + key + ": " + value + " — " + rule["reason"])
        for key, value in sorted(rule.get("excludes", {}).items()):
            if selected.get(key) == value:
                findings.append(when + " excludes " + key + ": " + value + " — " + rule["reason"])
        for name in excluded_roles(root, rule.get("excludes_roles")):
            findings.append(when + " excludes the role " + name + " — " + rule["reason"])
    return findings


def resolve_stances(root, config, strict=True):
    """Resolve escolhas embutidas e definidas pelo usuário sem aceitar path traversal."""
    roots = stance_roots(root, config)
    available = {}
    for index, source in enumerate(roots):
        if not source.is_dir():
            # Uma raiz customizada pode trazer apenas regras e skills — `harness import` escreve
            # uma assim — então uma raiz sem `stances/` não contribui com nada em vez de quebrar
            # toda sincronização.
            if index:
                continue
            raise ValueError("missing stance source: " + str(source))
        for dimension in sorted(source.iterdir()):
            if dimension.is_dir():
                identifier(dimension.name)
                variants = available.setdefault(dimension.name, {})
                for path in sorted(dimension.glob("*.md")):
                    identifier(path.stem)
                    if path.stem in variants:
                        raise ValueError("duplicate stance authority: " + dimension.name + "/" + path.stem)
                    variants[path.stem] = path
    selected = config.get("stances", {})
    if not isinstance(selected, dict):
        raise ValueError("stances must be an object")
    result = {}
    for name, variant in selected.items():
        identifier(name)
        identifier(variant)
        if name not in available or variant not in available[name]:
            raise ValueError("stance '" + name + "' has no variant '" + variant +
                             "'; options: " + ", ".join(sorted(available.get(name, {}))))
        result[name] = available[name][variant]
    # Uma dimensão customizada é opcional até ser selecionada; os padrões embutidos não são.
    defaults = json.loads((root / "config.example.json").read_text())["stances"]
    for name in defaults:
        if name not in result:
            raise ValueError("config has no variant for stance '" + name + "'")
    conflicts = stance_conflicts(root, config)
    if strict and conflicts:
        raise ValueError("stance conflict: " + conflicts[0])
    return result


def catalog(root):
    entries = []
    for kind, entry in KINDS.items():
        if not entry["directory"]:
            continue
        source = root / "primitives" / entry["directory"]
        for path in sorted(source.glob(entry["pattern"])):
            ident = str(path.relative_to(source).with_suffix(""))
            if kind == "skills":
                ident = path.parent.name
            entries.append({"id": ident, "kind": kind, "source": str(path.relative_to(root)),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    for ident in HOOK_IDS:
        path = root / HOOKS_DIRECTORY / (ident + ".py")
        if path.is_file():
            entries.append({"id": ident, "kind": "hooks", "source": str(path.relative_to(root)),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "core": ident in CORE_HOOKS})
    return {"schema_version": 1, "version": (root / "VERSION").read_text().strip(),
            "primitives": entries}


def role_contract(root, name):
    identifier(name)
    path = root / "primitives" / "roles" / (name + ".md")
    if not path.is_file():
        raise ValueError("unknown harness role: " + name)
    fields, body = frontmatter(path)
    if fields.get("name") != name or fields.get("authority") not in ("read-only", "artifact-write", "workspace-write"):
        raise ValueError("invalid shared role name or authority: " + name)
    if fields.get("context") != "fresh" or fields.get("delegation") != "none":
        raise ValueError("unsupported role context or delegation contract: " + name)
    if fields.get("tier") not in TIER_CLASSES:
        raise ValueError("shared role tier must be one of " + ", ".join(TIER_CLASSES) + ": " + name)
    # `posture: fixed` é a recusa do papel a uma classe e esforço de variante de custo; seus
    # orçamentos ainda se aplicam. Ausente significa que a variante decide, o que é o padrão para
    # todo outro papel.
    if fields.get("posture", "fixed") != "fixed":
        raise ValueError("shared role posture, when present, must be 'fixed': " + name)
    role_skills(root, fields)
    return fields, body


def role_skills(root, fields):
    """Os diretórios de skill que um papel declara além dos que a política compartilhada cita, como paths.

    Cada nome deve resolver para uma skill embutida, porque um erro de digitação removeria
    silenciosamente autoridade que o corpo do papel assume. `all` é o caso do planejador: seu
    corpo o instrui a ler as skills que o plano vai nomear, e quais são essas não é conhecido até
    o brief ser lido.
    """
    shipped = root / "primitives" / "skills"
    declared = [part.strip() for part in str(fields.get("skills", "")).split(",") if part.strip()]
    if declared == ["all"]:
        return sorted(p for p in shipped.iterdir() if (p / "SKILL.md").is_file())
    paths = []
    for skill in declared:
        path = shipped / identifier(skill)
        if not (path / "SKILL.md").is_file():
            raise ValueError("role declares an unknown skill: " + skill)
        paths.append(path)
    return paths


def native_model(tiers, tier):
    """O modelo do adaptador para uma classe, ou a classe mais forte mapeada mais próxima; None se nenhuma.

    Uma classe não mapeada nunca resolve para baixo: um modelo mais fraco do que o papel pediu é
    uma falha silenciosa, enquanto None faz o chamador herdar o modelo da sessão e dizê-lo.
    """
    for name in reversed(TIER_CLASSES[:TIER_CLASSES.index(tier) + 1]):
        if name in tiers:
            return tiers[name]
    return None


def adapter_tiers(root, runtime, tiers=None):
    """A tabela de classes do adaptador com as entradas `tiers.<runtime>` do usuário sobrepostas."""
    data = json.loads((root / "adapters" / runtime / "bindings.json").read_text())
    merged = dict(data.get("tiers", {}), **(tiers or {}))
    if set(merged) - set(TIER_CLASSES) or not all(
            isinstance(v, str) and v.strip() and not v.startswith("-") and not any(c.isspace() for c in v)
            for v in merged.values()):
        raise ValueError("adapter tiers map " + ", ".join(TIER_CLASSES) + " to native model identifiers")
    return data, merged


def tier_findings(tiers, models):
    """O que o catálogo de modelos de um provedor diz estar errado com uma tabela de classes, como (classe, modelo, problema).

    `models` é a lista própria do provedor: `slug`, `priority` (menor é mais forte) e `upgrade`, o
    sucessor que ela nomeia assim que um modelo é substituído. Um id versionado continua
    resolvendo depois que seu sucessor é lançado, então sem isso a tabela envelhece
    silenciosamente.
    """
    known = {m.get("slug"): m for m in models if isinstance(m, dict)}
    findings, last = [], None
    for name in TIER_CLASSES:
        model = tiers.get(name)
        if model is None:
            continue
        entry = known.get(model)
        if entry is None:
            findings.append((name, model, "not in the provider's catalog"))
            continue
        successor = entry.get("upgrade")
        successor = successor.get("model") or successor.get("slug") if isinstance(successor, dict) else successor
        if successor:
            findings.append((name, model, "superseded by " + str(successor)))
        priority = entry.get("priority")
        if isinstance(priority, int):
            if last is not None and priority < last:
                findings.append((name, model, "the catalog ranks it above the class before it"))
            last = priority
    return findings


def role_overrides(root, runtime, row=None, class_applies=True, tiers=None, binding=None):
    """Os overrides de binding de um papel: a linha de custo ativa, depois o binding explícito do usuário.

    Precedência, da mais fraca à mais forte: o `tier` próprio do papel e o esforço do adaptador,
    que não são overrides de forma alguma e chegam a `role_binding` por conta própria; depois a
    linha de custo resolvida; depois `role_bindings.<runtime>.<role>`, que sempre vence porque o
    usuário a nomeou explicitamente. Uma linha carrega uma classe de capacidade e nunca um modelo,
    então a tabela do adaptador continua sendo o único lugar onde um modelo nativo é escrito; um
    papel `posture: fixed` chega sem classe e sem esforço, porque o resolvedor já os removeu.
    """
    effort_key = "model_reasoning_effort" if runtime == "codex" else "effort"
    out = {}
    if row:
        if class_applies and row.get("class") in TIER_CLASSES:
            model = native_model(adapter_tiers(root, runtime, tiers)[1], row["class"])
            if model:
                out["model"] = model
        if row.get("effort") in EFFORTS:
            out[effort_key] = row["effort"]
    out.update(binding or {})
    return out


_POSTURE_MODULES = {}


def posture_module(root):
    """O resolvedor de stance e custo que os hooks de política executam, carregado por arquivo, ou None se ausente.

    Carregar o mesmo arquivo que os hooks carregam é o que mantém uma única resposta para "o que
    esta variante diz": uma sincronização, um lint e um worker de papel isolado leem o resolvedor,
    nunca uma segunda cópia dele. Carregado uma vez por raiz, porque uma sincronização faz a ele
    uma pergunta por papel por runtime.
    """
    key = str(root)
    if key in _POSTURE_MODULES:
        return _POSTURE_MODULES[key]
    # Um arquivo com dois nomes: `claude/hooks` é um symlink para `policy/hooks`. O segundo nome é
    # como uma árvore que carrega apenas o lado projetado ainda resolve suas próprias variantes.
    path = next((p for p in (Path(root) / "policy" / "hooks" / "posture.py",
                             Path(root) / "claude" / "hooks" / "posture.py") if p.is_file()), None)
    if path is None:
        return None
    try:
        spec = importlib.util.spec_from_file_location("harness_posture", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        return None
    _POSTURE_MODULES[key] = module
    return module


def cost_table(root, config):
    """A tabela resolvida da variante de custo configurada; nunca um motivo para o trabalho em mãos falhar.

    Construída a partir da configuração que o chamador já resolveu, então toda a escada de stances
    já percorrida — arquivo do usuário, arquivo do projeto, variáveis de sessão — chega até as
    linhas. Um resolvedor que este checkout não carrega, ou um sidecar que não consegue usar,
    produz uma tabela vazia: tudo então resolve exatamente como resolvia antes de variantes de
    custo terem linhas.
    """
    module = posture_module(root)
    if module is None:
        return {"rows": {}, "class_applies": False,
                "warnings": ["no posture resolver in this checkout; rendering without cost rows"]}
    try:
        return module.table_for(dict(config.get("stances", {})), config, strict=False, root=root)
    except Exception as exc:
        return {"rows": {}, "class_applies": False,
                "warnings": ["cost table unusable, rendering without cost rows: " + str(exc)]}


def cost_row(root, table, role):
    """A linha de custo que governa um papel, incluindo linhas de banda; o resolvedor decide qual.

    Uma única consulta para cada chamador, então um worker de banda é precificado a partir da
    linha para a qual o hook de disparo o redireciona. Um checkout sem resolvedor recai para a
    própria linha do papel.
    """
    module = posture_module(root)
    if module is None or not hasattr(module, "row_for"):
        return (table.get("rows") or {}).get(role)
    return module.row_for(table, role)


def cost_overrides(root, config, table, runtime, role):
    """Os overrides com os quais um papel é vinculado sob `table`, para qualquer uma das runtimes.

    O caminho de sincronização renderiza uma definição de agente nativa com estes, e
    `workers.resolve` vincula um worker isolado com eles, então um papel não pode rodar numa
    classe como definição e noutra como worker.
    """
    return role_overrides(root, runtime, cost_row(root, table, role),
                          class_applies=bool(table.get("class_applies")),
                          tiers=config.get("tiers", {}).get(runtime),
                          binding=config.get("role_bindings", {}).get(runtime, {}).get(role, {}))


def role_binding(root, runtime, fields, overrides=None, tiers=None):
    """O binding nativo de um papel: a entrada do adaptador, sua classe resolvida para um modelo, depois os overrides."""
    data, tiers = adapter_tiers(root, runtime, tiers)
    effort_key = "model_reasoning_effort" if runtime == "codex" else "effort"
    if set(overrides or {}) - {"model", effort_key}:
        raise ValueError("role bindings may change model and effort only")
    binding = dict(data["roles"][fields["name"]], **(overrides or {}))
    unknown = set(binding) - set(BINDING_KEYS.get(runtime, ())) - {"model"}
    if unknown or not all(isinstance(v, str) and v.strip() for v in binding.values()):
        raise ValueError("an adapter role entry holds " + ", ".join(BINDING_KEYS.get(runtime, ()))
                         + " as non-empty strings: " + fields["name"])
    if binding.get(effort_key, EFFORTS[0]) not in EFFORTS:
        raise ValueError("role effort must be one of " + ", ".join(EFFORTS) + ": " + fields["name"])
    model = binding.pop("model", None) or native_model(tiers, fields["tier"])
    # Um override `inherit` é o caminho de volta ao modelo da sessão, para um provedor sem esses ids.
    binding = {NATIVE_KEYS.get(key, key): value for key, value in binding.items()}
    return dict({"model": model} if model and model != "inherit" else {}, **binding)


def role_projection(root, runtime, path, overrides=None, tiers=None):
    fields, body = role_contract(root, path.stem)
    binding = role_binding(root, runtime, fields, overrides, tiers)
    if runtime == "claude-code":
        values = {k: fields[k] for k in ("name", "description")}
        values.update(dict({"model": "inherit"}, **binding))
        return "---\n" + "".join(k + ": " + v + "\n" for k, v in values.items()) + "---\n\n" + body
    if runtime != "codex":
        raise ValueError("unsupported runtime: " + runtime)
    values = {k: fields[k] for k in ("name", "description")}
    values["developer_instructions"] = body
    values["sandbox_mode"] = "workspace-write" if fields["authority"] == "workspace-write" else "read-only"
    values.update(binding)
    # Strings/arrays JSON são válidos para este conjunto de valores TOML restrito.
    return "# Generated from primitives/roles; edit the shared source.\n" + "".join(
        k + " = " + json.dumps(v, ensure_ascii=False) + "\n" for k, v in values.items())


def projections(root):
    files = {}
    for role in sorted((root / "primitives" / "roles").glob("*.md")):
        files["claude/agents/" + role.name] = role_projection(root, "claude-code", role)
    for workflow in sorted((root / "primitives" / "workflows").glob("*.md")):
        files["claude/commands/" + workflow.name] = workflow.read_text().replace("{{arguments}}", "$ARGUMENTS")
    files["claude/CLAUDE.md"] = (root / "primitives" / "instructions.md").read_text() + "\n@~/.claude/CLAUDE.personal.md\n"
    files["claude/CLAUDE.personal.template.md"] = (root / "primitives" / "personal.template.md").read_text()
    from . import compatibility
    for name in ("README.md", "docs/compatibility.md"):
        path = root / name
        if not path.exists() or "<!-- harness:compatibility:start -->" not in path.read_text():
            continue
        data = compatibility.catalog(root)
        lines = []
        for status in ("qualified", "unqualified", "planned", "unsupported"):
            clients = [row["id"] for row in data["clients"] if row["status"] == status]
            if clients:
                lines.append("**" + status.capitalize() + ":** " + ", ".join("`" + name + "`" for name in clients) + ".")
        lines.extend(compatibility_capability_table(root, data))
        block = "<!-- harness:compatibility:start -->\n" + "\n\n".join(lines) + "\n<!-- harness:compatibility:end -->"
        files[name] = re.sub(r"<!-- harness:compatibility:start -->.*?<!-- harness:compatibility:end -->", block, path.read_text(), flags=re.S)
    return files


def compatibility_capability_table(root, data):
    """As linhas de capacidade por cliente renderizadas ao lado dos status dos clientes.

    O estado de uma capacidade é derivado no momento da geração a partir do adaptador do runtime,
    nunca escrito aqui nem no catálogo à mão. O layout segue a matriz de capacidades gerada em
    `docs/harnesses.md` do wshobson/agents.
    """
    from . import compatibility
    states = {row["id"]: compatibility.capability_states(root, data, row) for row in data["clients"]}
    columns = [row["id"] for row in data["clients"] if states[row["id"]]]
    names = sorted({name for row in columns for name in states[row]})
    if not columns or not names:
        return []
    rows = ["| Capability | " + " | ".join("`" + name + "`" for name in columns) + " |",
            "|---|" + "---|" * len(columns)]
    for name in names:
        rows.append("| `" + name + "` | "
                    + " | ".join(states[client][name]["state"] for client in columns) + " |")
    restrictions = {row["id"]: compatibility.tier_restriction(root, row) for row in data["clients"]}
    rows.append("| tier restriction | "
                + " | ".join(restrictions[client]["state"] for client in columns) + " |")
    carried = {}
    for client in columns:
        if restrictions[client]["mechanism"]:
            carried.setdefault(restrictions[client]["state"], set()).add(restrictions[client]["mechanism"])
    mechanisms = [state + " by " + ", ".join("`" + name + "`" for name in sorted(carried[state]))
                  for state in sorted(carried)]
    note = ("The last row is not a qualification state. It says whether the delegation stance's "
            "model-tier ceiling is **enforced** (a hook rewrites or refuses the spawn), "
            "**advisory** (prompt text only) or **none**"
            + (", carried " + "; ".join(mechanisms) if mechanisms else "")
            + ". `enforced` is narrower than it sounds. It never reaches the session's own model: "
            "the `model` settings key is one this harness never writes "
            "(`docs/settings-ownership.md`). Within a session it rewrites a spawn only while the "
            "selected `delegation` variant is `tiered`. `off` stops the spawn instead, any other "
            "variant leaves it alone, and it acts only while the adapter's class table maps at "
            "least two models, since one class is no ladder to move a spawn down. Under every "
            "other condition the ceiling is prose, exactly as `advisory` is everywhere.")
    return ["A client's status is not a capability's status. Each cell is derived from that "
            "runtime's `adapters/<runtime>/capabilities.json` at generation time:", "\n".join(rows),
            note]


def projection_drift(root):
    return [name for name, content in projections(root).items()
            if not (root / name).is_file() or (root / name).read_text() != content]
