# SPDX-License-Identifier: MIT
"""Lança agentes que mantêm um servidor Claude Code Remote Control rodando por pasta configurada.

Um servidor serve uma pasta, então a lista `remote_control.folders` na configuração do usuário
vira um agente launchd para cada uma. O harness nunca aceita o diálogo de confiança de workspace
de uma pasta em nome do usuário: uma pasta não confiável é reportada e pulada, porque o servidor
a recusa e o launchd reiniciaria a recusa para sempre.
"""
import hashlib
import json
import plistlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

LABEL_PREFIX = "com.agent-harness.remote-control."
SPAWN_MODES = ("same-dir", "worktree", "session")
PERMISSION_MODES = ("acceptEdits", "auto", "bypassPermissions", "default", "dontAsk", "plan")
DEFAULTS = {"folders": [], "spawn": "worktree", "permission_mode": "default", "keep_awake": False}
# Uma entrada de `folders` é um caminho, ou um objeto nomeando um caminho mais o que difere para
# aquele host específico.
FOLDER_KEYS = ("path", "spawn", "env")
SYSTEM_PATH = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
# As sessões de todo host herdam isto. Sem isso, o Claude Code 2.1.280 dá a uma sessão que um
# host inicia nenhuma rota de upload, então um arquivo que o agente envia com SendUserFile chega
# ao app como "not delivered" e não pode ser aberto lá; com isso definido, o arquivo é enviado
# com a conta logada. A variável não é documentada. O próprio `env` de uma pasta vence, então ""
# a desliga ali.
HOST_ENV = {"CLAUDE_CODE_BRIEF_UPLOAD": "1"}
# Um servidor que não consegue se registrar (pasta servida de um terminal, sem rede) sai na hora;
# o padrão de dez segundos do launchd bombardearia o endpoint de registro.
THROTTLE_SECONDS = 60


def settings(cfg):
    """O bloco `remote_control` sobre seus padrões, validado; pastas resolvidas e sem duplicatas."""
    block = cfg.get("remote_control") or {}
    if not isinstance(block, dict):
        raise ValueError("remote_control must be an object")
    unknown = set(block) - set(DEFAULTS)
    if unknown:
        raise ValueError("unknown remote_control key(s): " + ", ".join(sorted(unknown)))
    out = dict(DEFAULTS, **block)
    if out["spawn"] not in SPAWN_MODES:
        raise ValueError("remote_control.spawn must be one of " + ", ".join(SPAWN_MODES))
    if out["permission_mode"] not in PERMISSION_MODES:
        raise ValueError("remote_control.permission_mode must be one of " + ", ".join(PERMISSION_MODES))
    if not isinstance(out["folders"], list):
        raise ValueError("remote_control.folders must be a list of paths or folder objects")
    folders, options = [], {}
    for index, raw in enumerate(out["folders"]):
        folder, extra = folder_entry(raw, index)
        if folder in options and options[folder] != extra:
            raise ValueError(f"remote_control.folders lists {folder} twice with different options")
        if folder not in folders:
            folders.append(folder)
            options[folder] = extra
    out["folders"] = folders
    out["folder_options"] = options
    out["keep_awake"] = bool(out["keep_awake"])
    return out


def folder_entry(raw, index):
    """Uma entrada de `folders` como `(caminho resolvido, {"spawn"?: mode, "env": {name: value}})`."""
    where = f"remote_control.folders[{index}]"
    if isinstance(raw, str):
        raw = {"path": raw}
    if not isinstance(raw, dict):
        raise ValueError(f"{where} must be a path or an object with a `path`")
    unknown = set(raw) - set(FOLDER_KEYS)
    if unknown:
        raise ValueError(f"unknown {where} key(s): " + ", ".join(sorted(unknown)))
    path = raw.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError(f"{where}.path must be a non-empty path")
    extra = {}
    if "spawn" in raw:
        if raw["spawn"] not in SPAWN_MODES:
            raise ValueError(f"{where}.spawn must be one of " + ", ".join(SPAWN_MODES))
        extra["spawn"] = raw["spawn"]
    env = raw.get("env", {})
    if not isinstance(env, dict) or not all(
            isinstance(k, str) and k and isinstance(v, str) for k, v in env.items()):
        raise ValueError(f"{where}.env must be an object of string names to string values")
    extra["env"] = dict(env)
    return Path(path).expanduser().resolve(), extra


def folder_options(folder, opts):
    """As opções do bloco com o próprio `spawn` e `env` de uma pasta sobrepostos."""
    extra = (opts.get("folder_options") or {}).get(Path(folder), {})
    return {"spawn": extra.get("spawn", opts["spawn"]), "env": dict(extra.get("env") or {})}


def label(folder):
    """Rótulo launchd estável: um slug legível mais um hash de caminho, para que duas pastas `api` nunca colidam."""
    slug = re.sub(r"[^a-z0-9]+", "-", Path(folder).name.lower()).strip("-") or "folder"
    digest = hashlib.sha256(str(folder).encode("utf-8")).hexdigest()[:8]
    return f"{LABEL_PREFIX}{slug}-{digest}"


def command(folder, opts, claude_bin):
    # Sem `--no-create-session-in-dir`: o Claude Code 2.1.280 lê o ponteiro de ponte, e por isso
    # reutiliza o ambiente num relançamento, só enquanto createSessionInDir está ligado. A sessão
    # que ele pré-cria é reutilizada entre reinícios enquanto o ponteiro se mantiver fresco.
    argv = [str(claude_bin), "remote-control", "--name", Path(folder).name,
            "--spawn", folder_options(folder, opts)["spawn"],
            "--permission-mode", opts["permission_mode"]]
    if opts["keep_awake"]:
        # -i segura o sono ocioso, -s segura o sono do sistema na energia AC; nenhum sobrevive a
        # uma tampa fechada.
        argv = ["/usr/bin/caffeinate", "-is"] + argv
    return argv


def plist(folder, opts, claude_bin, home, log_dir):
    name = label(folder)
    path = [str(Path(claude_bin).parent)] + [p for p in SYSTEM_PATH if p != str(Path(claude_bin).parent)]
    env = dict({"HOME": str(home), "PATH": ":".join(path)}, **HOST_ENV)
    env.update(folder_options(folder, opts)["env"])
    return {
        "Label": name,
        "ProgramArguments": command(folder, opts, claude_bin),
        "WorkingDirectory": str(folder),
        "EnvironmentVariables": env,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": THROTTLE_SECONDS,
        "ProcessType": "Background",
        "StandardOutPath": str(Path(log_dir) / (name + ".log")),
        "StandardErrorPath": str(Path(log_dir) / (name + ".log")),
    }


def render(folder, opts, claude_bin, home, log_dir):
    return plistlib.dumps(plist(folder, opts, claude_bin, home, log_dir), sort_keys=True)


def trusted(folder, claude_json):
    """Se o diálogo de confiança de workspace do Claude Code foi aceito para esta pasta exata.

    Um pai confiável não confia num filho: o Claude Code chaveia a confiança pelo diretório em
    que foi iniciado, então um host num filho não confiável sai no prompt e o launchd reinicia
    essa recusa a cada minuto para sempre.
    """
    try:
        projects = json.loads(Path(claude_json).read_text(encoding="utf-8")).get("projects", {})
    except (OSError, ValueError):
        return False
    if not isinstance(projects, dict):
        return False
    entry = projects.get(str(Path(folder)))
    return isinstance(entry, dict) and entry.get("hasTrustDialogAccepted") is True


def trust_hint(folder):
    """A única linha que conserta uma pasta não confiável, nomeada em `install` e em `status`."""
    return f"workspace trust not accepted; run `bin/harness trust {folder}` then `claude` there once"


def installed(agents_dir):
    """Rótulo -> caminho de plist para cada agente que este módulo possui."""
    agents_dir = Path(agents_dir)
    if not agents_dir.is_dir():
        return {}
    return {p.stem: p for p in sorted(agents_dir.glob(LABEL_PREFIX + "*.plist"))}


def plan(opts, agents_dir, claude_json):
    """Divide as pastas configuradas entre as que servir e as que pular, e encontra agentes obsoletos.

    Retorna (serve, skipped, stale): pastas; pares (folder, reason); rótulos que nenhuma pasta reivindica.
    """
    serve, skipped = [], []
    for folder in opts["folders"]:
        if not folder.is_dir():
            skipped.append((folder, "not a directory"))
        elif not trusted(folder, claude_json):
            skipped.append((folder, trust_hint(folder)))
        else:
            serve.append(folder)
    wanted = {label(f) for f in serve}
    stale = [name for name in installed(agents_dir) if name not in wanted]
    return serve, skipped, stale


# --------------------------------------------------------------------------- ponteiro de ponte

HEAL_LABEL = "com.agent-harness.remote-control-heal"
HEAL_INTERVAL_SECONDS = 60
POINTER_NAME = "bridge-pointer.json"
# O Claude Code 2.1.278 reutiliza o ambiente num ponteiro só enquanto o mtime do arquivo está
# dentro de BRIDGE_POINTER_TTL_MS, então um ponteiro que ninguém reescreve expira e o próximo
# host se registra do zero.
POINTER_TTL_SECONDS = 4 * 60 * 60
# O schema do leitor é fechado: uma chave desconhecida falha a validação e o arquivo é apagado.
POINTER_KEYS = ("sessionId", "environmentId", "source", "pid", "procStart",
                "activeSessionIds", "activeSessionIdsPersistedAt",
                "projectThreadSessionIds", "projectThreadSessionIdsPersistedAt",
                # Adicionado pela 2.1.280.
                "parkedProjectThreadSessionIds", "parkedProjectThreadSessionIdsPersistedAt")
CARRIED_KEYS = POINTER_KEYS[5:]
ENV_ID = re.compile(r"env_01[A-Za-z0-9]+")
# O host imprime sua própria idade de orçamento de erro, então ela é lida em vez de recalculada a
# partir do relógio: `[01:46:00] Connection error, retrying in 2m (541s elapsed): fetch failed`.
RETRY_LINE = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\][^\n]*Connection error, retrying")
RETRY_ELAPSED = re.compile(r"Connection error, retrying[^\n]*?\((\d+)s elapsed\)")
# `[bridge:work] Detected system sleep (312s gap), resetting error budget` — o host reinicia o
# orçamento ao acordar, então o supervisor precisa também ou pararia um host que não está falhando.
SLEEP_RESET = re.compile(r"Detected system sleep \((\d+)s gap\), resetting error budget")
RECONNECTED = re.compile(r"Reconnected after (\d+)s")
GAVE_UP = re.compile(r"Persistent errors for \d+ minutes?, giving up\.")
SHUTTING_DOWN = re.compile(r"Shutting down (\d+) active session\(s\)")
REMOVED_WORKTREE = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]\s*removed worktree (\S.*?)\s*$")
# `connGiveUpMs` é fixo em dez minutos e seu caminho arquiva toda sessão e cancela o registro do
# ambiente; nove minutos deixa um minuto para parar o host enquanto um reinício ainda pode retomar.
GIVE_UP_SECONDS = 600
STOP_AT_SECONDS = 540


def project_slug(folder):
    """A chave por diretório do Claude Code sob `~/.claude/projects`: todo outro caractere vira um traço."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(folder))


def pointer_path(projects_root, folder):
    return Path(projects_root) / project_slug(folder) / POINTER_NAME


def read_pointer(path):
    """O ponteiro como um dict, ou None quando está ausente, ilegível ou não é um objeto."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def pointer_payload(environment_id, pid, proc_start, previous=None):
    """O que o próprio host escreve, com os ids de sessão carregados do arquivo anterior mantidos.

    Só sobrevivem as chaves que o leitor valida: ele rejeita o arquivo inteiro numa desconhecida.
    Ids de um ambiente diferente são descartados, como o cliente os descarta — um id de sessão só
    tem significado para o ambiente em que foi criado, e `bridge/reconnect` recusa o resto.

    Um `pid` de None não escreve `pid` nem `procStart`: o ponteiro que `install` deixa para um
    host que está prestes a substituir, que o próximo host lê como pertencente a nenhum processo vivo.
    """
    previous = previous if isinstance(previous, dict) else {}
    if previous.get("environmentId") != environment_id:
        previous = {}
    out = {"sessionId": previous.get("sessionId") if isinstance(previous.get("sessionId"), str) else "",
           "environmentId": environment_id,
           "source": "standalone"}
    if pid is not None:
        out["pid"] = int(pid)
        out["procStart"] = str(proc_start)
    for key in CARRIED_KEYS:
        if key in previous:
            out[key] = previous[key]
    return out


def install_step(loaded, unchanged, pid, environment):
    """O que `install` faz com o agente de uma pasta: `unchanged`, `adopt` ou `load`.

    Um agente inalterado e carregado é deixado em paz: recarregá-lo cortaria suas sessões. Um
    alterado cujo host está rodando num ambiente conhecido é adotado — o ponteiro é escrito para
    aquele ambiente e o host recebe SIGKILL antes da recarga, porque um host que não reutilizou um
    ambiente no início arquiva suas sessões e cancela o registro no SIGTERM, e
    `launchctl bootout` envia exatamente isso. Qualquer outro caso é um load simples.
    """
    if loaded and unchanged:
        return "unchanged"
    if pid is not None and environment:
        return "adopt"
    return "load"


def environment_id(log_text):
    """O ambiente que o host mais recentemente registrou: o último que seu log nomeia."""
    found = ENV_ID.findall(log_text or "")
    return found[-1] if found else None


def unreachable_seconds(log_text):
    """Há quanto tempo o host está falhando ao alcançar o servidor, a partir da sequência final de
    linhas `Connection error, retrying`.

    A cifra `(Ns elapsed)` é o próprio orçamento de erro do host e vence; um log sem uma recai
    para o intervalo `[HH:MM:SS]`, que lê uma sequência que cruza a meia-noite como uma volta em
    vez de uma lacuna negativa. Qualquer outra linha encerra a sequência, então uma reconexão e o
    reset de sono do sistema zeram o orçamento de volta — como fazem dentro do host.
    """
    elapsed, stamps = 0, []
    for line in (log_text or "").splitlines():
        if not line.strip():
            continue
        found = RETRY_LINE.search(line)
        if not found:
            elapsed, stamps = 0, []
            continue
        stamps.append(tuple(int(part) for part in found.groups()))
        counted = RETRY_ELAPSED.search(line)
        if counted:
            elapsed = int(counted.group(1))
    span = 0
    if len(stamps) >= 2:
        first, last = stamps[0], stamps[-1]
        start = timedelta(hours=first[0], minutes=first[1], seconds=first[2])
        end = timedelta(hours=last[0], minutes=last[1], seconds=last[2])
        if end < start:
            end += timedelta(days=1)
        span = int((end - start).total_seconds())
    return max(elapsed, span)


def removed_worktrees(log_text):
    """`(stamp, path)` para cada worktree de sessão que a limpeza de desistência apagou.

    Uma linha `kept worktree … · uncommitted changes` não é uma dessas: aquele checkout ainda existe.
    """
    out = []
    for line in (log_text or "").splitlines():
        found = REMOVED_WORKTREE.search(line)
        if found:
            out.append((found.group(1), found.group(2)))
    return out


def gave_up(log_text):
    """Se a última desistência do log é mais recente que seu último registro."""
    return bool(GAVE_UP.search(log_text or ""))


def pointer_is_current(existing, wanted, path, now=None):
    """Se o arquivo já diz o que esta execução escreveria, e é novo o bastante para ser lido.

    A frescor é o mtime do arquivo, não um campo, então um ponteiro inalterado mas expirando
    ainda precisa ser reescrito.
    """
    if existing != wanted:
        return False
    try:
        age = (now or datetime.now().timestamp()) - Path(path).stat().st_mtime
    except OSError:
        return False
    return age < POINTER_TTL_SECONDS / 2


def heal_plist(harness_bin, home, log_dir, claude_bin=None):
    """Um agente launchd que roda `harness remote-control heal --once` num intervalo."""
    path = [str(Path(claude_bin).parent)] if claude_bin else []
    path += [p for p in SYSTEM_PATH if p not in path]
    return {
        "Label": HEAL_LABEL,
        "ProgramArguments": [str(harness_bin), "remote-control", "heal", "--once"],
        "EnvironmentVariables": {"HOME": str(home), "PATH": ":".join(path)},
        "RunAtLoad": True,
        "StartInterval": HEAL_INTERVAL_SECONDS,
        "ProcessType": "Background",
        "StandardOutPath": str(Path(log_dir) / (HEAL_LABEL + ".log")),
        "StandardErrorPath": str(Path(log_dir) / (HEAL_LABEL + ".log")),
    }


def render_heal(harness_bin, home, log_dir, claude_bin=None):
    return plistlib.dumps(heal_plist(harness_bin, home, log_dir, claude_bin), sort_keys=True)


# --------------------------------------------------------------------------- estado do supervisor

STATE_NAME = "supervisor-state.json"


def read_state(path):
    """O que o supervisor já fez:
    `{"stopped": {label: pid}, "recreated": [key], "reconnected": {session: epoch}}`.

    Um arquivo ausente ou ilegível é um estado vazio, então o pior que um arquivo perdido custa é
    um SIGTERM repetido para um host que já está falhando de qualquer forma.
    """
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = None
    value = value if isinstance(value, dict) else {}
    stopped = value.get("stopped")
    recreated = value.get("recreated")
    reconnected = value.get("reconnected")
    return {"stopped": stopped if isinstance(stopped, dict) else {},
            "recreated": recreated if isinstance(recreated, list) else [],
            "reconnected": reconnected if isinstance(reconnected, dict) else {}}


def stop_is_due(elapsed, label, pid, state):
    """Se este host deve ser parado agora, e ainda não foi parado.

    A proteção é o pid: o relançamento do launchd é um processo novo, então a próxima
    interrupção para o novo host uma vez e esse nunca duas.
    """
    return elapsed >= STOP_AT_SECONDS and state["stopped"].get(label) != pid


def record_stop(state, label, pid):
    state["stopped"][str(label)] = int(pid)
    return state


def worktree_key(stamp, path):
    return f"{stamp} {path}"


def unseen_worktrees(removed, state):
    """As linhas `removed worktree` sobre as quais esta execução ainda não agiu, mais antigas primeiro."""
    seen = set(state["recreated"])
    return [(stamp, path) for stamp, path in removed if worktree_key(stamp, path) not in seen]


def record_worktree(state, stamp, path):
    state["recreated"].append(worktree_key(stamp, path))
    # Chaves de uma interrupção só é o que importa; o log em si gira muito mais devagar.
    state["recreated"] = state["recreated"][-256:]
    return state


def reconnect_is_due(session_id, state, now):
    """Se heal pode recolocar esta sessão na fila agora: no máximo uma vez por `RECONNECT_EVERY_SECONDS`."""
    last = state.get("reconnected", {}).get(str(session_id))
    return not isinstance(last, (int, float)) or now - last >= RECONNECT_EVERY_SECONDS


def record_reconnect(state, session_id, now):
    """Carimba uma tentativa, e esquece as antigas o bastante para não segurarem mais nada."""
    kept = {sid: when for sid, when in state.get("reconnected", {}).items()
            if isinstance(when, (int, float)) and now - when < RECONNECT_EVERY_SECONDS}
    kept[str(session_id)] = int(now)
    state["reconnected"] = kept
    return state


def worktree_branch(path):
    """O nome de branch que o Claude Code dá à worktree de uma sessão disparada: `worktree-<dirname>`."""
    return "worktree-" + Path(path).name


def worktree_add_argv(root, path, branch, base, branch_exists):
    """`git worktree add`, anexando o branch da sessão quando sobreviveu à limpeza.

    O host apaga o checkout mas nem sempre o branch, e recriar um branch que existe falha,
    então os dois casos assumem formas de argumento diferentes.
    """
    argv = ["git", "-C", str(root), "worktree", "add"]
    return argv + ([str(path), branch] if branch_exists else [str(path), "-b", branch, str(base)])


# --------------------------------------------------------------------------- lost sessions

# The cap is a budget, so the page has to be spent on the newest sessions: a lost session is
# recovered within minutes or not at all. The endpoint takes no sort parameter — `sort` and
# `order` were measured on 2026-09-22 to return the identical page — so the order is checked on
# arrival by `descending_by_event` and never requested.
PAGE_LIMIT = 50
SESSIONS_URL = "https://api.anthropic.com/v1/code/sessions?limit=%d" % PAGE_LIMIT
KEYCHAIN_SERVICE = "Claude Code-credentials"
API_HEADERS = {"anthropic-version": "2023-06-01", "anthropic-beta": "oauth-2025-04-20"}
# Heal re-queues these through `bridge/reconnect`. A `--session-id` reattach host registers the
# lost environment a second time, as a single-session environment that then takes new chats from
# the client, so that command is printed for the sessions heal cannot reconnect and never run.
REATTACH_WARNING = ("heal reconnects these automatically each minute; the command below is for a "
                    "session it cannot reconnect. Reattaching registers a second environment for "
                    "this Mac and new chats may land on it; stop the host as soon as the session "
                    "has answered")
RECONNECT_URL = "https://api.anthropic.com/v1/environments/%s/bridge/reconnect"
ENVIRONMENTS_BETA = "environments-2025-11-01"
RECONNECT_EVERY_SECONDS = 600


def oauth_token(keychain_payload):
    """The claude.ai access token out of the keychain item's JSON. Never logged or stored."""
    try:
        value = json.loads(keychain_payload or "")
    except ValueError:
        return None
    token = (value.get("claudeAiOauth") or {}).get("accessToken") if isinstance(value, dict) else None
    return token if isinstance(token, str) and token else None


def sessions_request(token):
    return Request(SESSIONS_URL, headers=dict(API_HEADERS, Authorization="Bearer " + token))


def reconnect_request(token, environment, session_id):
    """`POST bridge/reconnect`, which puts a disconnected session back in its environment's queue."""
    headers = dict(API_HEADERS, Authorization="Bearer " + token)
    headers["anthropic-beta"] = ",".join([API_HEADERS["anthropic-beta"], ENVIRONMENTS_BETA])
    headers["Content-Type"] = "application/json"
    body = json.dumps({"session_id": str(session_id)}).encode("utf-8")
    return Request(RECONNECT_URL % environment, data=body, headers=headers, method="POST")


def reconnect(token, environment, session_id, opener=None):
    """Re-queue one session; the HTTP status as text, or `failed: <reason>`. Never raises."""
    try:
        with (opener or urlopen)(reconnect_request(token, environment, session_id),
                                 timeout=20) as response:
            return str(getattr(response, "status", None) or response.getcode())
    except HTTPError as exc:
        return str(exc.code)
    except Exception as exc:  # noqa: BLE001 - a network failure is a log line, not a crash
        return "failed: " + (type(exc).__name__ + (f" {exc}" if str(exc) else ""))


def owned_environments(host_ids, pointers):
    """Every environment this Mac's hosts hold: those their logs name plus those their pointers name."""
    out = []
    for env in list(host_ids or []) + [p.get("environmentId") for p in pointers or []
                                       if isinstance(p, dict)]:
        if isinstance(env, str) and env and env not in out:
            out.append(env)
    return out


def session_rows(payload):
    """The rows of one sessions page, or None when the payload is not a page of session objects.

    An entry that is not an object refuses the whole page rather than being dropped: what is left
    would pass the order check trivially, and a page this malformed says nothing about the rest.
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        return None
    return data


def event_time(row):
    """One row's `last_event_at` as a datetime, or None when it carries no readable one.

    The field is ISO-8601 with microseconds and a `Z`, which 3.9's parser does not take.
    """
    stamp = row.get("last_event_at")
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp[:-1] + "+00:00" if stamp.endswith("Z") else stamp)
    except ValueError:
        return None


def descending_by_event(rows):
    """Whether a page is newest-first by `last_event_at`, the field the server orders by.

    Measured against a live account on 2026-09-22: a 50-row page is descending by `last_event_at`
    with no violations, while `updated_at` goes backwards seven times within it and `created_at`
    twenty-two, so `last_event_at` is the only field the cap can be read under.

    A page of more than one row holding a row with no readable timestamp is not descending: its
    order cannot be read, and under a cap an order that cannot be read is refused rather than
    assumed.
    """
    times = [event_time(row) for row in rows]
    if len(times) < 2:
        return True
    if any(when is None for when in times):
        return False
    return all(a >= b for a, b in zip(times, times[1:]))


class SessionPage(object):
    """One capped read of the sessions endpoint: what came back, or why nothing did.

    The three statuses are kept apart because a caller must never print one as another — a
    refused page is not an account with no lost sessions. `truncated` is whether the account
    holds more sessions than this page, which is as far as a capped read can honestly speak.
    """

    FAILED, REFUSED, OK = "failed", "refused", "ok"

    def __init__(self, status, rows=(), truncated=False):
        self.status = status
        self.rows = list(rows)
        self.truncated = truncated

    @property
    def ok(self):
        return self.status == self.OK

    def with_rows(self, rows):
        return SessionPage(self.status, rows, self.truncated)

    def scope(self):
        """What the count on this page may claim: the account, or only the newest `PAGE_LIMIT`."""
        return " in the newest %d" % PAGE_LIMIT if self.truncated else ""


def fetch_sessions(token, opener=None):
    """One page of the account's recent Remote Control sessions, newest first.

    A page that did not arrive newest-first is refused rather than read, because under a cap the
    rows such a page dropped are unknown rather than merely old.

    A failure here is a report line, never an exit code: the supervisor's other work does not
    depend on the network.
    """
    try:
        with (opener or urlopen)(sessions_request(token), timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - any network or parse failure reads the same to the caller
        return SessionPage(SessionPage.FAILED)
    rows = session_rows(payload)
    if rows is None:
        return SessionPage(SessionPage.FAILED)
    if not descending_by_event(rows):
        return SessionPage(SessionPage.REFUSED)
    return SessionPage(SessionPage.OK, rows, bool(payload.get("next_cursor")))


def disconnected_sessions(rows, environment_ids):
    """Sessions still `active` whose bridge is `disconnected`, on an environment this Mac ran.

    An archived session is past recovery and one on another device's environment is not ours,
    so both are left out. The page's own order is kept: it has already been checked newest-first
    by `last_event_at`, and re-sorting on `updated_at` would scramble it.
    """
    wanted = {str(e) for e in (environment_ids or [])}
    out = []
    for row in rows or []:
        if row.get("status") != "active" or row.get("connection_status") != "disconnected":
            continue
        if row.get("environment_id") not in wanted:
            continue
        out.append(row)
    return out


def reattach_command(session, permission_mode="default"):
    """The manual recovery line for one lost session. Printed for the user to run, not run."""
    return (f"claude remote-control --session-id {session.get('id')} "
            f"--permission-mode {permission_mode}")


def is_host_process(command):
    """Whether a `ps -o command=` line is the `claude` host itself, not its caffeinate wrapper.

    `keep_awake` makes the launchd job pid caffeinate's, and signalling that leaves the host
    running, so the signal has to find the child.
    """
    parts = (command or "").split()
    return bool(parts) and Path(parts[0]).name != "caffeinate" and "remote-control" in parts
