"""Roda papéis compartilhados restritos através de adaptadores de CLI nativos isolados."""
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from . import catalog, keychain, reconcile

LIMIT = 1024 * 1024
RUNTIMES = {"codex": "codex", "claude-code": "claude"}
# Caracteres por token, a aproximação sem tokenizador que `bin/harness` e `scripts/cost_bench.py`
# usam; os testes garantem que os três concordam. Bom para um orçamento e uma tendência, nunca
# para faturamento.
CHARS_PER_TOKEN = 4.0
# O que um worker pode receber antes de deixar de ser barato: a política que carrega mais todo
# byte montado ao lado dela. Registrado por execução em vez de imposto, porque o que um worker
# recebe é uma propriedade do seu contrato e dos próprios ponteiros da política, fixados antes de
# qualquer brief ser lido. Um papel de revisão resolve para cerca de 30.800 disso e o planejador,
# que pode ler qualquer skill, para 43.800 (#335).
CONTEXT_BUDGET_TOKENS = 50000


def harness_version(root):
    """A versão do checkout, a única string que `harness --version` imprime, ou None."""
    try:
        return (Path(root) / "VERSION").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def adapter(root, runtime):
    if runtime not in RUNTIMES:
        raise ValueError("unsupported worker runtime")
    spec = importlib.util.spec_from_file_location("harness_worker_" + runtime,
                                               root / "adapters" / runtime / "worker.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def posture_record(root, runtime, fields, table, row, binding, overrides, model):
    """O que a variante de custo selecionada fez a este worker, para `status.json`.

    De onde cada metade veio, nunca como foi redigida: um registro de status não carrega texto
    de prompt algum. `"role"` é o próprio contrato do papel e a entrada do adaptador, `"cost-row"`
    a linha da variante para ele, `"role-binding"` os `role_bindings` do usuário, `"cli"` um
    `--model` explícito.
    """
    effort_key = "model_reasoning_effort" if runtime == "codex" else "effort"
    classed = bool(table.get("class_applies")) and (row or {}).get("class") in catalog.TIER_CLASSES
    return {"cost_variant": table.get("cost_variant"),
            "class": row["class"] if classed else fields["tier"],
            "class_source": "cost-row" if classed else "role",
            "model_source": ("cli" if model else "role-binding" if "model" in binding
                             else "cost-row" if classed and "model" in overrides else "role"),
            "effort_source": ("role-binding" if effort_key in binding
                              else "cost-row" if effort_key in overrides else "role")}


def resolution(root, config, runtime, name, model=None, prompt=None):
    """Tudo que uma execução resolve antes de lançar: contrato, binding, instruções, postura.

    A variante de custo alcança um worker através da mesma função e da mesma precedência com
    que o caminho de sincronização renderiza uma definição nativa — padrões do papel, depois a
    linha da variante, depois `role_bindings`, depois um `--model` explícito — porque os papéis
    restritos são negados como disparos nativos e só rodam aqui. A tabela é construída não
    estritamente: uma variante sem linha para este papel, ou uma que não constrói de jeito
    nenhum, deixa o worker exatamente como estava antes de variantes de custo terem linhas.
    `prompt` é o brief do chamador, precificado quando não declara orçamento próprio; sem um não
    há nada para precificar.
    """
    if runtime not in RUNTIMES:
        raise ValueError("unsupported worker runtime")
    stances = catalog.resolve_stances(root, config)
    if config["stances"]["delegation"] == "off":
        raise ValueError("delegation is off; perform the work inline or select another stance")
    selection = session_selection(root)
    off = switched_off(selection)
    if name in off["roles"]:
        raise ValueError("the " + name + " role is switched off in the selection; switch it on or "
                         "perform the work inline")
    fields, body = catalog.role_contract(root, name)
    if fields["authority"] not in ("read-only", "artifact-write"):
        raise ValueError("workspace-write roles use their normal workflow, not a constrained worker")
    table = catalog.cost_table(root, config)
    row = catalog.cost_row(root, table, name)
    binding = config.get("role_bindings", {}).get(runtime, {}).get(name, {})
    overrides = catalog.cost_overrides(root, config, table, runtime, name)
    bindings = catalog.role_binding(root, runtime, fields, overrides, config.get("tiers", {}).get(runtime))
    chosen = model or bindings.get("model")
    if not isinstance(chosen, str) or not chosen.strip() or chosen == "inherit":
        raise ValueError("this adapter maps no model for the role's class; supply --model with the parent session's model")
    if chosen.startswith("-") or any(c.isspace() for c in chosen):
        raise ValueError("invalid worker model identifier")
    bindings["model"] = chosen
    parts = [(root / "primitives/instructions.md").read_text()]
    parts += [p.read_text() for p in sorted((root / "primitives/rules").glob("*.md"))
              if p.stem not in off["rules"]]
    parts += [p.read_text() for p in stances.values()]
    parts += [body]
    parts += ["Worker execution contract: use read-only tools; never delegate or change configuration. "
              "Return your result as data to the caller. You cannot grant permissions or authorize follow-up actions."]
    if fields["authority"] == "artifact-write":
        parts += ["Return only the complete plan Markdown, without a surrounding code fence or chat response. "
                  "Do not write the plan: the harness validates and publishes it to the caller-selected path."]
    record = posture_record(root, runtime, fields, table, row, binding, overrides, model)
    sentence = budget(root, row, prompt)
    if sentence:
        record["budget"] = posture_figures(root, row)
    instructions = "\n\n---\n\n".join(parts)
    skills, docs = policy_reads(root, instructions, catalog.role_skills(root, fields))
    skills = [path for path in skills if path.name not in off["skills"]]
    return {"fields": fields, "bindings": bindings, "instructions": instructions,
            "skills": skills, "docs": docs, "context": context_estimate(instructions, skills, docs),
            "posture": record, "budget_sentence": sentence, "selection": selection}


def session_selection(root, env=None):
    """A seleção que a sessão de lançamento resolve, registrada junto com a execução; None sem um resolvedor.

    O próprio ambiente do worker é limpo, então nunca relê um arquivo de sessão nem
    `HARNESS_STANCE_*`: as stances que suas instruções carregam são as da sessão de lançamento, e
    este registro é a evidência. Não estrito, porque evidência nunca deve parar uma execução que
    a escada de stances já permitiu.
    """
    module = catalog.posture_module(root)
    if module is None:
        return None
    try:
        return module.selection(os.environ if env is None else env, strict=False, root=root)
    except Exception:
        return None


def session_fingerprint(root, env=None):
    """A fingerprint de perfil da sessão de lançamento, carimbada na linha de ledger da execução; None sem uma.

    Tirada do mesmo ambiente que `session_selection` e pela mesma razão: o worker roda o perfil
    da sessão de lançamento. Nunca levanta exceção, já que um carimbo ausente é uma linha não
    atribuída e nunca motivo para recusar uma execução.
    """
    module = catalog.posture_module(root)
    try:
        return module.fingerprint(os.environ if env is None else env, root=root) if module else None
    except Exception:
        return None


def switched_off(selection):
    """`{kind: unidades desligadas}` para as regras, skills e papéis dos quais uma execução de worker é construída.

    Um worker é uma projeção como qualquer outra, então uma unidade que a sessão de lançamento
    desliga fica ausente dela; uma seleção que ninguém conseguiu resolver não desliga nada.
    """
    selection = selection if isinstance(selection, dict) else {}
    return {kind: {unit for unit, value in (selection.get(kind) or {}).items() if value == "off"}
            for kind in ("rules", "skills", "roles")}


POLICY_DOC = re.compile(r"docs/[a-z0-9][a-z0-9.-]*\.md")


def policy_reads(root, instructions, declared):
    """As skills e documentos que a política resolvida diz a este worker para abrir, como `(skills, docs)`.

    Toda regra e stance nesse texto aponta para algum lugar — "a skill `licensing-review`",
    "Listas: `docs/preferences.md`" — e um worker que não consegue seguir o ponteiro está sendo
    instruído a obedecer uma política que não consegue ler. Então o conjunto é derivado do
    próprio texto em vez de mantido à mão: uma stance que para de citar uma skill para de pagar
    por ela na próxima execução. `declared` é a própria linha `skills:` do papel, que adiciona o
    que seu corpo assume mas o texto compartilhado nunca nomeia.
    """
    available = sorted(p for p in (root / "primitives" / "skills").iterdir() if (p / "SKILL.md").is_file())
    cited = [p for p in available if re.search(r"\b" + re.escape(p.name) + r"\b", instructions)]
    skills = sorted(set(cited) | set(declared))
    docs = sorted({root / name for name in POLICY_DOC.findall(instructions) if (root / name).is_file()})
    return skills, docs


def est_tokens(chars):
    """Caracteres para tokens, a aproximação sem tokenizador. Veja CHARS_PER_TOKEN."""
    return int(round(chars / CHARS_PER_TOKEN))


def text_size(paths):
    """Caracteres de todo arquivo de texto legível nesses caminhos ou abaixo deles."""
    total = 0
    for path in paths:
        for item in [path] + (sorted(path.rglob("*")) if path.is_dir() else []):
            if item.is_file():
                try:
                    total += len(item.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    continue
    return total


def context_estimate(instructions, skills, docs):
    """O que este worker recebe, em tokens estimados: a política mais todo byte montado com ela.

    Isto conta o que é montado, não o que uma execução lê: um worker abre o que seu brief
    precisa. Nem o workspace nem o brief também, já que esses são do chamador e variam por
    execução. É o custo fixo que o próprio contrato do papel determina, que é o que uma rodada
    de revisão paga quatro vezes.
    """
    reference = text_size(skills) + text_size(docs)
    return {"policy_tokens": est_tokens(len(instructions)), "reference_tokens": est_tokens(reference),
            "total_tokens": est_tokens(len(instructions) + reference),
            "budget_tokens": CONTEXT_BUDGET_TOKENS}


def posture_figures(root, row):
    """As cifras de orçamento que a frase declara, como o resolvedor compartilhado as conta."""
    module = catalog.posture_module(root)
    return module.budget_figures(row) if hasattr(module, "budget_figures") else {}


def budget(root, row, prompt):
    """A frase de orçamento leve que este brief está sem, ou None; a mesma que um brief nativo recebe.

    A redação e o teste de "já precificado" são de `policy/hooks/posture.py`, carregado por
    arquivo do jeito que `lifecycle.py` carrega uma política, para que o brief de um worker de
    papel e o de um disparo nativo não possam declarar um gasto de duas formas diferentes. Um
    resolvedor que este checkout não carrega não acrescenta nada.
    """
    module = catalog.posture_module(root)
    if prompt is None or not hasattr(module, "budget_sentence"):
        return None
    return None if module.budget_stated(prompt) else module.budget_sentence(row)


def resolve(root, config, runtime, name, model=None):
    """O contrato, o binding nativo e as instruções compartilhadas de um worker de papel."""
    ready = resolution(root, config, runtime, name, model)
    return ready["fields"], ready["bindings"], ready["instructions"]


def passthrough(original):
    """As variáveis do chamador que um worker mantém: autenticação, locale, proxies e certificados.

    Personalização e overrides de loader são descartados. `environment` constrói sobre isto, e o
    `refusal` de um adaptador checa o mesmo conjunto, então a pré-checagem enxerga exatamente as
    credenciais que o worker recebe.
    """
    exact = {"PATH", "LANG", "LC_ALL", "TERM", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR",
             "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS", "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY"}
    auth_prefixes = ("OPENAI_", "ANTHROPIC_", "AWS_", "GOOGLE_", "AZURE_")
    env = {k: v for k, v in original.items() if k in exact or k.startswith(auth_prefixes)}
    for name in ("CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"):
        if name in original:
            env[name] = original[name]
    return env


def environment(original, work):
    env = passthrough(original)
    env.update(HOME=str(work / "home"), XDG_CONFIG_HOME=str(work / "home/.config"),
               XDG_STATE_HOME=str(work / "home/.local/state"), XDG_CACHE_HOME=str(work / "home/.cache"))
    Path(env["HOME"]).mkdir(mode=0o700)
    try:
        keychain.provision(env["HOME"])
    except OSError as exc:
        raise ValueError(str(exc))
    return env


@contextlib.contextmanager
def artifact_slot(workspace, filename):
    """Ancora o diretório de saída aprovado com descritores no-follow; nunca substitui um artefato."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.md", filename or ""):
        raise ValueError("--artifact must be a Markdown filename, not a path")
    fds = []
    try:
        fd = os.open(str(workspace), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fds.append(fd)
        for component in (".agent-harness", "plans"):
            try:
                os.mkdir(component, mode=0o700, dir_fd=fd)
            except FileExistsError:
                pass
            fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            fds.append(fd)
        try:
            os.stat(filename, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("artifact already exists; choose a new filename")
        yield fd, filename
    finally:
        for fd in reversed(fds):
            os.close(fd)


def publish(slot, content):
    fd, filename = slot
    temporary = ".worker-" + uuid.uuid4().hex
    try:
        handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # link() é atômico e recusa um destino criado enquanto o worker estava rodando.
        os.link(temporary, filename, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
        os.fsync(fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:
            pass


def validate_artifact(root, content, work):
    if not content.strip() or len(content.encode()) > LIMIT or content.lstrip().startswith("```"):
        raise ValueError("worker returned empty, oversized or fenced plan content")
    path = work / ".agent-harness/plans/check.md"
    path.parent.mkdir(parents=True)
    path.write_text(content)
    from . import lifecycle
    result = lifecycle.invoke("validate-plan-card", {"tool_input": {"file_path": str(path)}})
    if result:
        raise ValueError("worker plan failed the Review Card validator")


def execute(command, prompt, env, cwd, run_dir, timeout):
    with (run_dir / "stdout.log").open("w") as out, (run_dir / "stderr.log").open("w") as err:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                text=True, env=env, cwd=str(cwd), start_new_session=True)
        try:
            proc.communicate(prompt, timeout=timeout)
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()
            raise
        return proc.returncode


def policy_reference(work, docs):
    """Copia os documentos que a política cita para o próprio diretório do worker, e o retorna.

    Uma raiz de leitura é um diretório, e o diretório onde estes vivem é a árvore `docs/` de
    237.000 tokens; copiar os arquivos citados é como um worker segue `docs/preferences.md` sem
    receber tudo o mais ao lado.
    """
    reference = Path(work) / "policy-reference"
    reference.mkdir(exist_ok=True)
    for path in docs:
        shutil.copyfile(str(path), str(reference / path.name))
    return reference


def temporary_roots():
    """Os diretórios temporários compartilhados desta máquina, resolvidos: o scratch de toda execução cai aqui."""
    candidates = ["/tmp", "/var/tmp", tempfile.gettempdir(), os.environ.get("TMPDIR") or "/tmp"]
    return {Path(path).resolve() for path in candidates}


def broad_read_root(path):
    """Por que `path` é amplo demais para conceder a um worker, ou None quando é estreito o bastante.

    Uma raiz de leitura é tudo que um worker pode abrir, então uma raiz compartilhada entrega a
    ele os arquivos de toda outra execução: uma revisão cega recebendo `/tmp` poderia ler o
    relatório anterior nomeando seus defeitos plantados (issue #772). São recusados `/`, o
    diretório home, cada raiz temporária do sistema, e qualquer diretório acima de um deles; um
    subdiretório dedicado de qualquer um destes é aceito.
    """
    path = Path(path)
    home = Path.home().resolve()
    roots = [(Path("/"), "the filesystem root")]
    roots += [(temp, "a system temporary root") for temp in sorted(temporary_roots())]
    roots.append((home, "the home directory"))
    for root, what in roots:
        if path == root:
            return what
        if path in root.parents:
            return "above " + what + " " + str(root)
    return None


def granted_roots(read_dirs):
    """Os valores de `--read-dir` do chamador resolvidos, recusando qualquer um que não seja um diretório estreito."""
    roots = [Path(path).resolve(strict=True) for path in read_dirs]
    for path in roots:
        if not path.is_dir():
            raise ValueError("--read-dir must name an existing directory")
        reason = broad_read_root(path)
        if reason:
            raise ValueError("--read-dir " + str(path) + " is " + reason + ", which would let the worker "
                             "read every other run's files; put the inputs in a dedicated directory, such "
                             "as one made by `mktemp -d /tmp/harness-inputs.XXXXXX`, and grant that instead")
    return roots


def run(root, config, runtime, name, workspace, prompt, state_root, model=None, artifact=None, timeout=300, read_dirs=()):
    if os.name != "posix" or not 1 <= timeout <= 3600:
        raise ValueError("workers require POSIX and a timeout between 1 and 3600 seconds")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > LIMIT:
        raise ValueError("worker prompt must be nonempty and at most 1 MiB")
    workspace = Path(workspace).resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("worker workspace must be a directory")
    read_roots = granted_roots(read_dirs)
    ready = resolution(root, config, runtime, name, model, prompt)
    fields, bindings, instructions = ready["fields"], ready["bindings"], ready["instructions"]
    skills, docs = ready["skills"], ready["docs"]
    if ready["budget_sentence"]:
        prompt = prompt.rstrip() + ready["budget_sentence"]
    if bool(artifact) != (fields["authority"] == "artifact-write"):
        raise ValueError("only artifact-write roles require --artifact")
    native = adapter(root, runtime)
    executable = shutil.which(RUNTIMES[runtime])
    if not executable:
        raise ValueError("native CLI is not installed: " + RUNTIMES[runtime])
    version = subprocess.check_output([executable, "--version"], text=True, timeout=15).strip()
    # Um cliente que não consegue autenticar é recusado aqui, antes que qualquer registro ou
    # diretório exista, em vez de lançado para falhar no próprio prompt de login do runtime (issue #759).
    refusal = getattr(native, "refusal", None)
    reason = None
    if refusal:
        with tempfile.TemporaryDirectory(prefix="harness-worker-auth-", dir="/tmp") as empty:
            reason = refusal(executable, dict(os.environ), passthrough(os.environ), empty)
    if reason:
        raise ValueError(reason)
    state_root = Path(state_root)
    if state_root.is_symlink():
        raise ValueError("worker state directory cannot be a symlink")
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_dir = state_root / uuid.uuid4().hex
    run_dir.mkdir(mode=0o700)
    record = {"schema_version": 1, "id": run_dir.name, "role": name, "runtime": runtime,
              "runtime_version": version,
              # O harness que lançou esta execução, carimbado agora: a varredura de uso que
              # transforma o arquivo de status numa linha de ledger pode rodar muito depois que
              # esta versão foi substituída.
              "harness_version": harness_version(root),
              "profile_fingerprint": session_fingerprint(root),
              "model": bindings["model"], "workspace": str(workspace),
              "effort": bindings.get("model_reasoning_effort", bindings.get("effort")),
              # Os documentos que a política cita são montados como cópias, então as raízes
              # registradas aqui são as que sobrevivem à execução: o workspace, as skills e as do chamador.
              "read_roots": [str(workspace)] + [str(p) for p in skills] + list(map(str, read_roots)),
              "context": ready["context"],
              "mode": "isolated-cli", "status": "starting", "started_at": time.time(),
              # O executor supervisionando este worker, para que um leitor consiga distinguir uma
              # execução viva de uma cujo processo morreu no meio; `orphaned()` decide, e nunca sem o token de início.
              "pid": os.getpid(), "pid_start": process_start(os.getpid()),
              "stances": config["stances"], "selection": ready["selection"], "posture": ready["posture"],
              "policy_sha256": hashlib.sha256(instructions.encode()).hexdigest(),
              "qualification": "unqualified", "authority": "result data only; no transferred approvals"}
    status_path = run_dir / "status.json"
    reconcile.atomic_text(status_path, json.dumps(record, indent=2) + "\n")
    try:
        slot_context = artifact_slot(workspace, artifact) if artifact else contextlib.nullcontext(None)
        with slot_context as slot, tempfile.TemporaryDirectory(prefix="harness-worker-", dir="/tmp") as temporary:
            work = Path(temporary)
            original = dict(os.environ)
            env = environment(original, work)
            cwd = work / "cwd"
            cwd.mkdir()
            reference = policy_reference(work, docs)
            instructions += "\n\nProject to inspect (read-only): " + str(workspace)
            # As skills e documentos que a política acima cita, e nenhum outro caminho para
            # dentro do checkout: um worker precisa poder seguir os próprios ponteiros da sua
            # política, e não pode gastar uma camada de revisão no corpus sobre o qual ninguém perguntou (issue #335).
            if skills:
                instructions += ("\nSkill authority (read-only), the skills this role may read: "
                                 + ", ".join(str(p) for p in skills))
            else:
                instructions += "\nThis role reads no skill authority: the policy above is complete."
            if docs:
                instructions += ("\nDocuments the policy above cites, as copies under "
                                 + str(reference) + ": " + ", ".join(p.name for p in docs))
            instructions += "\nAdditional read-only inputs: " + ", ".join(map(str, read_roots))
            command = native.prepare(executable, work, root, workspace,
                                     list(skills) + ([reference] if docs else []) + read_roots,
                                     instructions, bindings, original, env)
            record["status"] = "running"
            reconcile.atomic_text(status_path, json.dumps(record, indent=2) + "\n")
            code = execute(command, prompt, env, cwd, run_dir, timeout)
            if code:
                raise ValueError("native worker exited with status " + str(code) + "; inspect its private logs")
            content = native.result(work, run_dir)
            if not isinstance(content, str) or not content.strip() or len(content.encode()) > LIMIT:
                raise ValueError("native worker returned an empty or oversized result")
            if slot:
                validate_artifact(root, content, work)
                publish(slot, content)
                record["artifact"] = str(workspace / ".agent-harness/plans" / artifact)
            reconcile.atomic_text(run_dir / "result.md", content)
            record["result_path"] = str(run_dir / "result.md")
            # O que a execução custou, como o próprio runtime reportou, para que `usage --by role`
            # conte um worker ao lado de um subagente. Um adaptador que não reporta nada deixa a
            # chave ausente em vez de um zero, que um relatório leria como uma execução medida que não gastou nada.
            try:
                counts = getattr(native, "usage", lambda *_: {})(work, run_dir)
            except Exception:
                counts = {}
            if isinstance(counts, dict) and counts:
                record["usage"] = counts
        record["status"] = "completed"
    except subprocess.TimeoutExpired:
        record.update(status="timed-out", error="native worker exceeded its timeout")
    except KeyboardInterrupt:
        record.update(status="cancelled", error="worker interrupted")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        record.update(status="failed", error=str(exc))
    finally:
        record["finished_at"] = time.time()
        reconcile.atomic_text(status_path, json.dumps(record, indent=2) + "\n")
    return record


LIVE = ("starting", "running")
ORPHANED = "the worker process ended without reporting a result"


def process_start(pid):
    """Um token nomeando a encarnação deste pid, ou None quando a plataforma não consegue dizer.

    Registrado ao lado do pid para que um pid reciclado não seja confundido com o processo
    original: um número reutilizado carrega um horário de início diferente. O Linux lê o campo 22
    de `/proc/<pid>/stat`, contado após o parêntese de fechamento do campo comm, que pode em si
    conter espaços; toda outra plataforma POSIX pergunta ao `ps`, cujo timestamp de resolução de
    segundo é suficiente para separar dois processos que por acaso receberam o mesmo número.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    try:
        stat = Path("/proc/" + str(pid) + "/stat")
        if stat.exists():
            return stat.read_text().rsplit(")", 1)[1].split()[19]
        # Um locale fixo, para que um leitor sob configurações LC_TIME diferentes imprima o mesmo token.
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True, timeout=10,
                             env=dict(os.environ, LC_ALL="C"))
    except (OSError, IndexError, ValueError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def running(pid, token):
    """True if the recorded process still runs, False if it is gone, None if it cannot be told.

    None is every case the harness cannot decide — a record from a release that stored no pid, a
    platform that reports no start time, a stat call refused — and the caller must read it as the
    status already on file rather than as a terminal state.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    except OSError:
        return None
    current = process_start(pid)
    if token is None or current is None:
        return True
    return current == token


def orphaned(record, run_dir):
    """Report a run whose supervising process died without a result as the terminal `orphaned`.

    Only the live statuses are reclassified, and only when nothing was reported: a result on disk
    means the run spoke for itself even if the process died before its final write. The new state
    is persisted into `status.json` alone, every other key and every other file left as they are,
    and a state directory that cannot be written still reports honestly to this caller.
    """
    if record.get("status") not in LIVE:
        return record
    if record.get("result_path") or (run_dir / "result.md").exists():
        return record
    if running(record.get("pid"), record.get("pid_start")) is not False:
        return record
    updated = dict(record, status="orphaned", error=ORPHANED)
    with contextlib.suppress(OSError):
        reconcile.atomic_text(run_dir / "status.json", json.dumps(updated, indent=2) + "\n")
    return updated


def status(state_root, worker_id=None):
    if worker_id and not re.fullmatch(r"[a-f0-9]{32}", worker_id):
        raise ValueError("invalid worker id")
    paths = [Path(state_root) / worker_id / "status.json"] if worker_id else sorted(Path(state_root).glob("*/status.json"))
    return [orphaned(json.loads(path.read_text()), path.parent) for path in paths]
