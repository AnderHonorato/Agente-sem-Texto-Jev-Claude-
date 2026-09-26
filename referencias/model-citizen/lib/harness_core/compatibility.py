"""Alegações de compatibilidade precisam carregar evidência nativa versionada."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

STATES = {"qualified", "unqualified", "planned", "unsupported"}
TIER_RESTRICTIONS = {"enforced", "advisory", "none"}
SOURCE_PATHS = ("VERSION", "bin", "lib", "adapters", "primitives", "policy", "templates",
                "config.example.json")
FREEZE_STATES = {"open", "frozen"}
SCOPE_VERSION = 1


def qualification_source(data):
    """Retorna a identidade de fonte que a evidência de um catálogo qualifica."""
    if data.get("release_state") != "released":
        return "HEAD"
    commit = data.get("qualification_source_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise ValueError("released compatibility catalog requires a full qualification source commit")
    return commit


def source_drift(root, data):
    """Uma alegação lançada continua legível, mas fonte alterada precisa de nova qualificação."""
    target = qualification_source(data)
    if target == "HEAD":
        return False
    ancestry = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", target, "HEAD"],
                              capture_output=True)
    unchanged = subprocess.run(["git", "-C", str(root), "diff", "--quiet", target, "HEAD", "--",
                                *SOURCE_PATHS], capture_output=True)
    return bool(ancestry.returncode or unchanged.returncode)


def git_output(root, *args):
    """Roda um comando git somente leitura em `root`, recusando-se a adivinhar quando falha."""
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if done.returncode:
        detail = (done.stderr.strip().splitlines() or [""])[0]
        raise ValueError("git " + args[0] + " failed: " + detail)
    return done.stdout


def freeze_record(root):
    """Lê o registro de congelamento do branch de lançamento; um arquivo ausente significa nenhum branch congelado.

    Uma rodada de qualificação roda no branch `release/vX.Y.Z` cortado neste commit, então merges
    dentro de `main` não podem invalidar a evidência da rodada. Veja docs/releasing.md.
    """
    path = root / "compatibility" / "freeze.json"
    if not path.is_file():
        return {"schema_version": 1, "state": "open"}
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("unsupported freeze schema")
    if data.get("state") not in FREEZE_STATES:
        raise ValueError("freeze state must be one of: " + ", ".join(sorted(FREEZE_STATES)))
    if data["state"] == "frozen":
        if not isinstance(data.get("branch"), str) or not data["branch"].strip():
            raise ValueError("a frozen release branch requires its branch name")
        commit = data.get("commit")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            raise ValueError("a frozen release branch requires a full commit identity")
    return data


def freeze_drift(root, data, ref="origin/main"):
    """Reporta desvio de fonte de runtime entre o commit congelado e `ref`.

    Este é o check que uma passagem de bastão de lançamento de outra forma registraria à mão; um
    `paths` vazio significa que a evidência da rodada ainda descreve `ref` tão bem quanto descreve
    o commit congelado.
    """
    result = {"state": data.get("state", "open"), "branch": data.get("branch"),
              "commit": data.get("commit"), "ref": ref, "paths": [], "stat": ""}
    if result["state"] != "frozen":
        return result
    numstat = git_output(root, "diff", "--numstat", "--no-renames", result["commit"], ref,
                         "--", *SOURCE_PATHS)
    result["paths"] = sorted({line.split("\t")[-1] for line in numstat.splitlines() if line.strip()})
    result["stat"] = git_output(root, "diff", "--stat", "--no-renames", result["commit"], ref,
                                "--", *SOURCE_PATHS).strip()
    return result


def merge_refusal(root, data, ref):
    """Recusa um merge para dentro de um branch de lançamento congelado que muda fonte de runtime qualificada."""
    if data.get("state") != "frozen":
        return []
    result = freeze_drift(root, data, ref)
    if not result["paths"]:
        return []
    return [data["branch"] + " is frozen at " + data["commit"][:12] + "; " + ref
            + " changes qualified runtime source: " + ", ".join(result["paths"])]


def invalidation_declaration(data):
    """O escopo de invalidação por alvo do catálogo, validado, ou `{}` quando nenhum é declarado.

    Três alegações são declaradas em vez de inferidas, porque um revisor precisa poder lê-las:
    qual diretório cada runtime possui, quais arquivos dentro de tal diretório o código
    compartilhado lê para qualquer runtime, e quais arquivos são carregados apenas para o runtime
    cuja sessão está rodando. As duas primeiras são impostas por
    tests/test_adapter_directory_isolation.py; a terceira é uma alegação de um mantenedor sobre
    pontos de chamada, e docs/compatibility.md o afirma.
    """
    declared = data.get("evidence_invalidation")
    if not declared:
        return {}
    if not isinstance(declared, dict) or declared.get("version") != SCOPE_VERSION:
        raise ValueError("unsupported evidence invalidation scope version")
    scopes, known = declared.get("runtime_paths"), {row.get("runtime") for row in data.get("clients") or []}
    if not isinstance(scopes, dict) or len(scopes) < 2:
        raise ValueError("evidence invalidation scope requires two or more runtime paths")
    for runtime in sorted(scopes, key=str):
        if not isinstance(runtime, str) or runtime not in known:
            raise ValueError("evidence invalidation scope names a runtime no client runs: "
                             + str(runtime))
        if scopes[runtime] != "adapters/" + runtime:
            raise ValueError("evidence invalidation scope must name each runtime's own adapter "
                             "directory: " + runtime)
    shared, private = declared.get("shared_files"), declared.get("runtime_files")
    for names, label in ((shared, "shared_files"), (private, "runtime_files")):
        if not isinstance(names, list) or not all(isinstance(name, str) and name and "/" not in name
                                                  and name not in (".", "..") for name in names):
            raise ValueError("evidence invalidation " + label + " must be plain file names")
    if not shared:
        raise ValueError("evidence invalidation scope requires the shared file names, because a "
                         "narrowed scope that names none fails open")
    if set(shared) & set(private):
        raise ValueError("an adapter file is either shared or per-runtime, never both")
    return {"runtime_paths": dict(scopes), "shared_files": sorted(shared),
            "runtime_files": sorted(private)}


def runtime_scopes(data):
    """O diretório de adaptador que cada runtime possui, conforme o catálogo declara."""
    return invalidation_declaration(data).get("runtime_paths", {})


def evidence_scope(data, client):
    """O conjunto de paths cuja mudança invalida a evidência de um cliente.

    Fonte compartilhada sempre conta, assim como os arquivos sob o diretório de adaptador de outro
    runtime que o código compartilhado lê independentemente do runtime. O resto do diretório de
    outro runtime não conta. Um runtime que o catálogo não mapeia não fica excluído de nada, então
    um alvo não mapeado ou não declarado mantém a regra de fonte inteira e o escopo falha fechado.
    """
    declared = invalidation_declaration(data)
    scopes = declared.get("runtime_paths", {})
    excluded, shared = [], []
    if client.get("runtime") in scopes:
        excluded = sorted(path for name, path in scopes.items() if name != client["runtime"])
        shared = sorted(path + "/" + name for path in excluded for name in declared["shared_files"])
    return {"version": SCOPE_VERSION, "paths": list(SOURCE_PATHS), "excluded": excluded,
            "shared": shared}


def scope_pathspec(scope):
    """O pathspec git para a fonte contra a qual a evidência de um alvo é checada.

    A mágica `literal` é o que impede uma exclusão de se alargar: um diretório declarado é
    comparado exatamente pelo path que é, nunca como um glob.
    """
    return list(scope["paths"]) + [":(exclude,literal)" + path for path in scope["excluded"]]


def same_scope(declared, scope):
    """Se um registro de evidência alega exatamente o escopo que o catálogo concede ao seu cliente.

    Um registro é entrada não confiável, então uma alegação malformada é apenas mais um escopo que
    o catálogo não concede, em vez de um traceback.
    """
    if not isinstance(declared, dict) or declared.get("version") != scope["version"]:
        return False
    for key in ("paths", "excluded", "shared"):
        names = declared.get(key)
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            return False
        if sorted(names) != sorted(scope[key]):
            return False
    return True


def case_path_map(data):
    """O mapa de caso-para-path validado do catálogo, ou `{}` quando nenhum é declarado.

    Todo caso obrigatório é uma chave, então adicionar um caso força uma alegação sobre ele. A
    lista de um caso nomeia os paths de fonte mapeados cuja mudança pode alterar o que esse caso
    observa; uma lista vazia alega que o caso não depende de nenhum deles. Um arquivo alterado sob
    o path de nenhum caso invalida todos os casos, então o mapa falha fechado. A regra e o
    argumento para cada entrada estão em docs/compatibility.md.
    """
    block = data.get("evidence_invalidation") or {}
    if "case_paths" not in block:
        return {}
    # Presente mas vazio ou malformado é recusado, não lido como ausente, para que uma declaração
    # quebrada não consiga desligar silenciosamente o escopo por caso.
    declared = block["case_paths"]
    version = declared.get("version") if isinstance(declared, dict) else None
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError("the case-to-path map requires a positive integer version")
    cases, required = declared.get("cases"), data.get("required_cases") or []
    if not isinstance(cases, dict) or set(cases) != set(required):
        raise ValueError("the case-to-path map must name every required case and no other")
    for case in sorted(cases):
        paths = cases[case]
        if not isinstance(paths, list) or len(set(map(str, paths))) != len(paths) \
                or not all(mapped_path(path) for path in paths):
            raise ValueError("the case-to-path map gives " + case + " a path that is not a "
                             "literal file or directory under the runtime source")
    return {"version": version, "cases": {case: sorted(cases[case]) for case in cases}}


def mapped_path(path):
    """Se `path` é um path literal de repositório sob um dos paths de fonte de runtime."""
    if not isinstance(path, str) or not path or any(mark in path for mark in "*?[]\\"):
        return False
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    return parts[0] in SOURCE_PATHS


def case_map_identity(data):
    """O que um novo registro de evidência declara sobre o mapa que assumiu, ou None sem mapa.

    O digest é o que mantém a versão honesta: um mapa editado sem incrementar a versão não bate
    mais com o digest que um registro mais antigo carrega, então esse registro recai para o alvo inteiro.
    """
    declared = case_path_map(data)
    if not declared:
        return None
    text = json.dumps(declared["cases"], sort_keys=True, separators=(",", ":"))
    return {"version": declared["version"], "sha256": hashlib.sha256(text.encode()).hexdigest()}


def under(changed, path):
    return changed == path or changed.startswith(path + "/")


def stale_cases(data, record, changed):
    """Os casos que os arquivos alterados de um registro invalidam, como `{case: [files]}`, ou None para todos.

    None significa que o registro inteiro está obsoleto: ele não declara mapa, declara um mapa
    diferente do catálogo, ou um arquivo alterado não está sob o path de nenhum caso.
    """
    identity = case_map_identity(data)
    if identity is None or record.get("case_map") != identity:
        return None
    cases = case_path_map(data)["cases"]
    stale = {}
    for name in changed:
        owners = [case for case, paths in cases.items() if any(under(name, path) for path in paths)]
        if not owners:
            return None
        for case in owners:
            stale.setdefault(case, []).append(name)
    return {case: sorted(names) for case, names in stale.items()}


def changed_files(root, commit, target, paths, carved):
    """Os arquivos sob `paths`, e sob o `carved` recortado de volta, que diferem entre os dois
    commits, ou None quando o git não consegue dizer, o que o chamador trata como todos eles."""
    names = set()
    for spec in (paths, carved):
        if not spec:
            continue
        done = subprocess.run(["git", "-C", str(root), "diff", "--name-only", "--no-renames",
                               commit, target, "--", *spec], capture_output=True, text=True)
        if done.returncode:
            return None
        names.update(line for line in (done.stdout or "").splitlines() if line.strip())
    return sorted(names)


def catalog(root):
    data = json.loads((root / "compatibility" / "catalog.json").read_text())
    if data.get("schema_version") != 1:
        raise ValueError("unsupported compatibility schema")
    if data.get("harness_version") != (root / "VERSION").read_text().strip():
        raise ValueError("compatibility catalog does not match VERSION")
    identifiers = [row["id"] for row in data["clients"]]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate compatibility client")
    runtime_scopes(data)
    case_path_map(data)
    target = qualification_source(data)
    if target != "HEAD":
        available = subprocess.run(["git", "-C", str(root), "cat-file", "-e", target + "^{commit}"],
                                   capture_output=True)
        if available.returncode:
            raise ValueError("released qualification source commit is unavailable")
    for row in data["clients"]:
        if row.get("status") not in STATES:
            raise ValueError("invalid compatibility status")
        # Uma string verdadeira aqui alegaria silenciosamente imposição para uma superfície sem hooks.
        if not isinstance(row.get("installs_hooks", True), bool):
            raise ValueError(row["id"] + ": installs_hooks must be true or false")
        if row["status"] == "qualified":
            errors = evidence_errors(root, data, row)
            if errors:
                raise ValueError(row["id"] + ": " + "; ".join(errors))
    return data


def evidence_errors(root, data, client):
    errors, passed, outdated = [], set(), {}
    target = qualification_source(data)
    scope = evidence_scope(data, client)
    if not client.get("runtime_version") or not client.get("client_version"):
        errors.append("native runtime and client versions are required")
    for item in client.get("evidence", []):
        path = (root / item.get("path", "")).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            errors.append("missing or external evidence artifact")
            continue
        try:
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != item.get("sha256"):
                errors.append("evidence digest mismatch")
                continue
            record = json.loads(content)
        except (ValueError, OSError):
            errors.append("unreadable evidence record")
            continue
        if not isinstance(record, dict):
            errors.append("evidence record must be an object")
            continue
        if record.get("client") != client["id"] or record.get("harness_version") != data["harness_version"]:
            errors.append("evidence version or client mismatch")
            continue
        if any(not client.get(key) or record.get(key) != client[key]
               for key in ("runtime_version", "client_version", "platform")):
            errors.append("evidence runtime, client version or platform mismatch")
            continue
        if record.get("kind") != "native" or not record.get("observations") or not record.get("source_commit"):
            errors.append("native observations and source commit are required")
            continue
        commit = record["source_commit"]
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            errors.append("native evidence requires a full source commit identity")
            continue
        declared = record.get("invalidation_scope")
        if declared is not None and not same_scope(declared, scope):
            errors.append("evidence claims an invalidation scope the catalog does not grant")
            continue
        paths = scope_pathspec(scope) if declared is not None else list(SOURCE_PATHS)
        # O recorte não pode viajar no mesmo pathspec: uma exclusão git vence sobre todo padrão
        # positivo, então os arquivos compartilhados dentro de um diretório excluído precisam do
        # próprio diff.
        carved = scope["shared"] if declared is not None else []
        ancestry = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", commit, target], capture_output=True)
        changed = None if ancestry.returncode else changed_files(root, commit, target, paths, carved)
        # O escopo por caso restringe apenas dentro do conjunto de paths do alvo, e apenas para um
        # registro que declara o mapa atual do catálogo; qualquer outra coisa mantém a regra de
        # alvo inteiro.
        stale = {} if changed == [] else (stale_cases(data, record, changed) if changed else None)
        if stale is None:
            errors.append("runtime source changed or evidence commit is unavailable")
            continue
        cases = record.get("cases")
        if not isinstance(cases, dict) or not cases:
            errors.append("native evidence requires acceptance cases")
            continue
        for case, result in cases.items():
            if case not in data["required_cases"] or result not in ("passed", "failed", "unverified"):
                errors.append("unknown acceptance case or result")
            elif case in stale:
                # O resultado descreve fonte que mudou desde então sob os paths deste caso, então
                # nem passa nem bloqueia; um rerun ligado ao lado responde pelo caso.
                outdated.setdefault(case, set()).update(stale[case])
            elif result != "passed":
                # Todo registro ligado faz parte da alegação; uma outra passagem não pode esconder uma falha.
                errors.append(case + " is " + result + " in linked evidence")
            else:
                passed.add(case)
    missing = set(data["required_cases"]) - passed
    for case in sorted(missing & set(outdated)):
        errors.append(case + " is stale in linked evidence: source changed under "
                      + ", ".join(sorted(outdated[case])))
    missing -= set(outdated)
    if missing:
        errors.append("missing acceptance cases: " + ", ".join(sorted(missing)))
    return errors


def release_errors(root):
    data = catalog(root)
    errors = [row["id"] + " is " + row["status"] for row in data["clients"]
              if row.get("required_for_release") and row["status"] != "qualified"]
    errors += reconciliation_errors(root, data)
    if source_drift(root, data):
        errors.append("current runtime source differs from the released qualification source")
    return errors


def coverage(root, choices):
    result = {}
    for runtime in ("claude-code", "codex"):
        bindings = json.loads((root / "adapters" / runtime / "capabilities.json").read_text())
        result[runtime] = {name: bindings["stances"].get(name, bindings["custom_stance_default"]) for name in choices}
    return result


def capability_entries(root, runtime):
    """As declarações de capacidade de um adaptador: suas dimensões de stance e sua execução de papel.

    Um adaptador ausente significa que o runtime não declara capacidade nenhuma, o que é como um
    cliente `planned` chega a este código sem inventar uma.
    """
    path = root / "adapters" / runtime / "capabilities.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text())
    entries = dict(data.get("stances", {}))
    if "role_execution" in data:
        entries["role_execution"] = data["role_execution"]
    return entries


def tier_restriction(root, client):
    """Se o teto de tier de modelo vincula a superfície de um cliente, e o que faz vinculá-lo.

    Imposição é um hook reescrevendo um disparo, então uma superfície que não instala hooks resolve
    para a entrada `without_hooks` do adaptador: a mesma prosa, nenhuma da recusa. Um runtime sem
    adaptador, ou nenhum declarando a chave, não restringe nada.
    """
    runtime = str(client.get("runtime"))
    path = root / "adapters" / runtime / "capabilities.json"
    entry = json.loads(path.read_text()).get("tier_restriction") if path.is_file() else None
    if not isinstance(entry, dict):
        return {"state": "none", "mechanism": None}
    # Ambos os ramos são validados independentemente de qual este cliente segue, então um erro de
    # digitação no fallback não é descoberto apenas pela única superfície que o lê.
    resolved = entry
    for candidate in (entry, entry.get("without_hooks")):
        if candidate is None:
            continue
        if not isinstance(candidate, dict) or candidate.get("state") not in TIER_RESTRICTIONS:
            raise ValueError(runtime + " declares an unknown tier restriction: "
                             + json.dumps(candidate))
        if candidate is not entry and client.get("installs_hooks", True) is False:
            resolved = candidate
    return {"state": resolved["state"], "mechanism": resolved.get("mechanism")}


def capability_states(root, data, client):
    """Qualificação por capacidade para um cliente, derivada do adaptador daquele runtime.

    Uma capacidade só é qualificada quando o cliente é qualificado e um caso de aceitação
    obrigatório que o adaptador nomeia como exercitando-a passou para aquele cliente; ela não
    herda nada do próprio status do cliente. A regra e a chave opcional `acceptance_cases` estão
    em docs/compatibility.md.
    """
    # `catalog` recusa um cliente qualificado cuja evidência não cobre um caso obrigatório, então
    # um cliente qualificado tem evidência nativa aprovada para todos eles e nenhum outro cliente
    # tem nenhuma.
    passed = set(data["required_cases"]) if client.get("status") == "qualified" else set()
    result = {}
    for name, entry in sorted(capability_entries(root, client["runtime"]).items()):
        cases = sorted(set(entry.get("acceptance_cases") or ()) & passed)
        state = entry.get("qualification", "unqualified")
        derived = "unqualified" if state == "qualified" and not cases else state
        result[name] = {"state": derived, "declared": state,
                        "mode": entry.get("mode"), "cases": cases}
    return result


def reconciliation_errors(root, data=None):
    """Reporta onde os casos de aceitação do catálogo e os estados de capacidade dos adaptadores discordam.

    O catálogo é a única autoridade: uma capacidade só pode alegar `qualified` contra um caso que
    o catálogo exige, num runtime que algum cliente qualificou nativamente.
    """
    data = catalog(root) if data is None else data
    required, errors = set(data["required_cases"]), []
    for runtime in sorted({row["runtime"] for row in data["clients"]}):
        qualified = [row["id"] for row in data["clients"]
                     if row["runtime"] == runtime and row["status"] == "qualified"]
        for name, entry in sorted(capability_entries(root, runtime).items()):
            label = runtime + " " + name
            state, cases = entry.get("qualification"), entry.get("acceptance_cases") or []
            if state not in STATES:
                errors.append(label + " declares no valid qualification state")
                continue
            if not isinstance(cases, list) or not all(isinstance(case, str) for case in cases):
                errors.append(label + " lists acceptance cases that are not strings")
                continue
            unknown = sorted(set(cases) - required)
            if unknown:
                errors.append(label + " names acceptance cases the catalog does not require: "
                              + ", ".join(unknown))
            if state == "qualified" and not cases:
                errors.append(label + " is qualified with no acceptance case covering it")
            if state == "qualified" and not qualified:
                errors.append(label + " is qualified while no " + runtime + " client is")
            if state != "qualified" and cases:
                errors.append(label + " is " + state + " yet acceptance cases cover it: "
                              + ", ".join(sorted(cases)))
    return errors
