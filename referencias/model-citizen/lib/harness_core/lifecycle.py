"""Normaliza eventos de ciclo de vida e compõe políticas compartilhadas antes da codificação nativa."""
import contextlib
import difflib
import fnmatch
import importlib.util
import io
import json
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICIES = ROOT / "policy" / "hooks"
ALIASES = {"exec_command": "Bash", "shell_command": "Bash", "shell": "Bash",
           "spawn_agent": "Agent", "write_file": "Write", "edit_file": "Edit"}
BASE_EVENTS = ("PreToolUse", "PostToolUse", "SessionStart", "Stop", "SessionEnd")
# Os próprios eventos do feed de uso. Só o Claude Code os carrega; `adapters/codex/capabilities.json`
# declara a lacuna em vez de registrar um evento que aquele runtime não dispara.
FEED_EVENTS = ("UserPromptSubmit", "SubagentStart", "SubagentStop")
EVENTS = {"claude-code": BASE_EVENTS + FEED_EVENTS, "codex": BASE_EVENTS}
# As ferramentas que escrevem um arquivo por caminho, depois de `ALIASES`; `apply_patch` nomeia
# seus caminhos dentro do patch.
FILE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch")
ROLE_NAME = re.compile(r"[a-z][a-z0-9-]*")
# Um brief pode declarar o papel ao qual pertence. A linha fica isolada para que a declaração não
# possa ser produzida por prosa que por acaso menciona um papel, e ela viaja com o texto: um
# brief colado num disparo sem nome ainda a carrega, que é todo o ponto disso.
ROLE_MARKER = re.compile(r"^[ \t]*harness-role:[ \t]*([a-z][a-z0-9-]*)[ \t]*$", re.M)
# O que uma sessão lembra sobre um disparo que recusou, e como um disparo posterior é comparado
# contra ele. Limitado em ambos os eixos: 32 entradas de 2.000 caracteres normalizados está muito
# além de qualquer fan-out real, e um registro de sessão não é lugar para acumular transcript.
DENIED_KEY = "denied_spawns"
NOTICED_KEY = "session_notices"
DENIED_MAX = 32
FINGERPRINT_MAX = 2000
PREFIX_MATCH = 400
SIMILARITY = 0.85


def load(name):
    spec = importlib.util.spec_from_file_location("harness_" + name.replace("-", "_"), POLICIES / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_DECISIONS = []


def decisions():
    """O log de decisão, ou None quando não pode ser carregado. Carregado uma vez por processo.

    Todo chamador trata None como "esta decisão não é registrada" e continua: o log registra o
    que o harness decidiu e nunca pode ser capaz de mudar isso.
    """
    if not _DECISIONS:
        try:
            _DECISIONS.append(load("decisions"))
        except Exception:
            _DECISIONS.append(None)
    return _DECISIONS[0]


def normalize(payload):
    event = dict(payload)
    name = str(event.get("tool_name", "")).rsplit(".", 1)[-1]
    event["tool_name"] = ALIASES.get(name, name)
    inputs = event.get("tool_input") or {}
    if not isinstance(inputs, dict):
        raise ValueError("tool_input must be an object")
    inputs = dict(inputs)
    if event["tool_name"] == "Bash":
        command = inputs.get("command", inputs.get("cmd"))
        if isinstance(command, list):
            command = shlex.join(command)
        if not isinstance(command, str):
            raise ValueError("shell command is missing")
        inputs["command"] = command
    if event["tool_name"] == "Agent":
        inputs["prompt"] = inputs.get("prompt", inputs.get("message", ""))
        inputs["subagent_type"] = inputs.get("subagent_type", inputs.get("agent_type"))
    event["tool_input"] = inputs
    return event


# A seleção de hooks para o despacho em andamento, para que um evento resolva a escada uma única vez.
_SWITCHES = []


def switches():
    """`{hook id: "on"|"off"}` a partir da seleção, resolvida como um hook a resolve: não estritamente.

    Uma seleção que não resolve deixa todo hook ligado, e um hook essencial desligado sem seu
    reconhecimento resolve `on` (`posture.core_refusals`), então um arquivo quebrado nunca
    desliga a imposição.
    """
    if _SWITCHES:
        return _SWITCHES[-1]
    try:
        return load("posture").selection(strict=False).get("hooks") or {}
    except Exception:
        return {}


def enabled(name):
    """Se o hook de id `name` está ligado. Os ids são `catalog.HOOK_IDS`, os mesmos em toda runtime."""
    return switches().get(name) != "off"


def invoke(name, event):
    """Roda o módulo de política `name` sobre `event`; `{}`, sem carregá-lo, quando seu id está desligado."""
    if not enabled(name):
        return {}
    module = load(name)
    output = io.StringIO()
    old = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(event))
        with contextlib.redirect_stdout(output):
            module.main()
    finally:
        sys.stdin = old
    text = output.getvalue().strip()
    return json.loads(text) if text else {}


def selected(name, fallback):
    """A variante de uma dimensão, resolvida pelo mesmo arquivo que os hooks de política carregam."""
    return load("posture").selected(name, fallback)


def investigating(runtime, event):
    """Se esta chamada é investigação de modo plano que a postura selecionada já autoriza.

    O modo plano existe para forçar um plano, perguntas e uma espera antes que qualquer coisa
    seja executada. Não é motivo para reduzir a pesquisa abaixo da postura de permissão que o
    usuário escolheu para todo outro modo, então sob `bypass` ou `auto` o harness responde pelos
    comandos sobre os quais o modo plano nativo de outra forma perguntaria. Sob `manual` e
    `inherit` não responde nada de novo, e o Codex é deixado de fora porque seu cliente rejeita
    `allow` de bandeja.

    Falha fechado: uma config que não abre não é uma postura que alguém selecionou.
    """
    if runtime != "claude-code" or event.get("permission_mode") != "plan":
        return False
    try:
        module = load("posture")
        return module.permissions() in module.OPEN_POSTURES
    except Exception:
        return False


def plan_allowed_tool(tool):
    """Se `tool` combina com um glob que o usuário listou sob `plan_allow_tools`.

    Nada é inferido do próprio nome da ferramenta: um payload de PreToolUse não diz nada sobre
    se uma ferramenta MCP lê ou escreve, então a lista fica vazia até o usuário preenchê-la.
    """
    if not isinstance(tool, str) or not tool:
        return False
    try:
        patterns = load("posture").plan_allow_tools()
    except Exception:
        return False
    return any(fnmatch.fnmatchcase(tool, pattern) for pattern in patterns)


def constrained_role(name):
    """O contrato de `name` quando é um papel compartilhado que um worker isolado deve rodar, senão None."""
    if not (isinstance(name, str) and ROLE_NAME.fullmatch(name)):
        return None
    if not (ROOT / "primitives/roles" / (name + ".md")).is_file():
        return None
    from . import catalog
    try:
        fields, _ = catalog.role_contract(ROOT, name)
    except ValueError:
        # Um contrato embutido que não carrega é o único caso que a proteção não consegue julgar,
        # então ela julga contra si mesma. Recusar um disparo nativo de um papel cujo próprio
        # arquivo está quebrado custa uma mensagem; permitir um roda um papel restrito sem
        # confinamento, que é o defeito para o qual esta proteção existe. `UNRESOLVED` diz isso,
        # e não carrega classe alguma para vincular a um modelo.
        return dict(UNRESOLVED, name=name)
    return fields if fields["authority"] in ("read-only", "artifact-write") else None


# A autoridade é a suposição segura, não uma leitura do arquivo: nada aqui veio de um.
UNRESOLVED = {"authority": "read-only", "unresolved": True}


# Um worker que pode tanto ler um workspace quanto alcançar a rede pode carregar o que leu de
# volta para fora, então os adaptadores isolados restringem todo papel a Read/Grep/Glob. Só
# `gatherer` é rotineiramente solicitado a buscar evidência online, então só sua recusa tem para
# onde enviar aquela metade do trabalho.
OFFLINE_NOTE = {"gatherer": "An isolated gatherer is offline — Read, Grep and Glob, no WebFetch or "
                            "WebSearch — so send a file or repository dimension to the worker and a web "
                            "dimension to an in-session band worker (worker-a, worker-b or worker-c)."}


# A única frase que a recusa, a stance `delegation` e as descrições de papel compartilhadas
# carregam, palavra por palavra, para que uma sessão que segue a stance nunca seja surpreendida
# pela recusa (issue #304). `tests/test_role_refusal_matches_the_stance.py` mantém as três cópias juntas.
CONFINEMENT_SENTENCE = ("A read-only role runs through `citizen role run <role>`: confinement is "
                        "read roots and return shape, not the absence of write tools, so `builder` "
                        "needs neither and spawns natively.")


def harness_command():
    """A CLI pelo caminho absoluto deste checkout, entre aspas para um shell.

    Nenhuma instalação documentada coloca `harness` no `PATH`, então um nome nu na recusa é um
    comando que o cliente recusado não consegue rodar (issue #761). O checkout de onde o hook
    roda é o que responde.
    """
    return shlex.quote(str(ROOT / "bin" / "harness"))


def role_instruction(runtime, name, fields):
    """Como este papel de fato roda, terminando na frase que a stance e os papéis também carregam."""
    from . import catalog
    # A classe do papel escolhe o modelo; o da sessão é o fallback, nunca o padrão.
    mapped = (fields is not None and not fields.get("unresolved")
              and "model" in catalog.role_binding(ROOT, runtime, fields))
    return ("Use " + harness_command() + " role run " + name + " --runtime " + runtime
            + ("" if mapped else " --model <session-model>")
            + " --workspace <repo> --prompt-file <brief-file>. "
            "Planner workers also require --artifact <new-plan.md>. " + CONFINEMENT_SENTENCE
            + (" " + OFFLINE_NOTE[name] if name in OFFLINE_NOTE else ""))


def role_deny(runtime, name, fields, origin=None):
    """A recusa que o disparo de um papel restrito recebe. `origin` diz o que o harness reconheceu."""
    reason = ("This constrained harness role requires an isolated worker. "
              + role_instruction(runtime, name, fields))
    return {"hookSpecificOutput": {"permissionDecision": "deny",
            "permissionDecisionReason": origin + " " + reason if origin else reason}}


def confinement_deny(runtime, session_id, name, fields, prompt, recognised):
    """`role_deny`, com a linha de log de decisão que toda recusa de confinamento escreve.

    `recognised` é o que nomeou o papel: o `subagent_type` do disparo, ou uma linha `harness-role:`
    em seu brief. A entrada da linha começa com o papel e esse sinal, depois a fingerprint do
    brief, para que uma recusa seja contável por papel sem um segundo campo na linha, e um
    disparo recusado nunca seja confundido com um disparo que rodou: a própria regra do ledger de
    uso para isso está em `usage-log.py`.
    """
    module = decisions()
    if module is not None:
        module.record("role-confinement", "deny",
                      name + " (" + recognised + "): " + fingerprint(prompt),
                      {"session_id": session_id}, runtime)
    return role_deny(runtime, name, fields)


def marker_role(prompt):
    """`(name, fields)` para um brief que declara seu papel numa linha `harness-role:`, senão None.

    Um marcador nomeando algo que não é um papel compartilhado restrito não diz nada: a proteção
    é uma declaração que o harness consegue verificar, não uma palavra que o modelo pode usar para
    recusar trabalho arbitrário.
    """
    if not isinstance(prompt, str):
        return None
    for name in ROLE_MARKER.findall(prompt):
        fields = constrained_role(name)
        if fields is not None:
            return name, fields
    return None


# As chamadas `agent()` de um script de workflow nunca alcançam os hooks de `Agent`, então o
# lançamento é a única chamada que o harness enxerga
# (docs/spikes/2026-09-22-workflow-tool-band-routing-and-ledger.md). O script é JavaScript: um
# papel é nomeado como um valor `agentType` entre aspas, e a linha `harness-role:` de um brief
# geralmente fica dentro de um literal de string, delimitada por uma aspa ou um escape `\n` em
# vez de uma quebra de linha real.
WORKFLOW_POINT = "workflow-launch"
WORKFLOW_AGENT_TYPE = re.compile(r"\bagentType\b")
# Um literal só conta quando é o valor inteiro: `'worker-a' && 'reviewer'` é computado.
WORKFLOW_AGENT_VALUE = re.compile(r"""['"]?\s*[:=]\s*(['"`])([^'"`\\\n]*)\1(?=\s*(?:[,;)\]}]|$))""")
WORKFLOW_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
WORKFLOW_LITERAL = re.compile(r"""(['"`])([a-z][a-z0-9-]*)\1""")
# Um literal com um escape nele, como `'re\u0076iewer'`, que se avalia como um nome de papel.
WORKFLOW_ESCAPED = re.compile(r"""(['"`])((?:(?!\1)[^\\\n])*\\.(?:(?!\1)[^\\\n]|\\.)*)\1""")
WORKFLOW_ESCAPE = re.compile(r"""\\(?:u\{([0-9A-Fa-f]{1,6})\}|u([0-9A-Fa-f]{4})|x([0-9A-Fa-f]{2})|([nrtvfb0])|(.))""",
                             re.S)
WORKFLOW_CONTROL = {"n": "\n", "r": "\r", "t": "\t", "v": "\v", "f": "\f", "b": "\b", "0": "\0"}
WORKFLOW_MARKER = re.compile(r"""(?:^|\\n|['"`])[ \t]*harness-role:[ \t]*([a-z][a-z0-9-]*)[ \t]*"""
                             r"""(?=$|\\n|\\r|['"`])""", re.M)
WORKFLOW_SCRIPT_MAX = 1024 * 1024
# Um arquivo mais longo que o limite de leitura roda por inteiro mas não pode ser julgado por
# inteiro, então é recusado.
WORKFLOW_TOO_LARGE = object()


def workflow_script(event):
    """O texto que um lançamento `Workflow` vai rodar, None quando este hook não consegue lê-lo, ou
    `WORKFLOW_TOO_LARGE` para um arquivo além de `WORKFLOW_SCRIPT_MAX` caracteres.

    O runtime prioriza `scriptPath` sobre `script` sobre `name`; um nome resolve para um arquivo
    sob um diretório `.claude/workflows/`, o do projeto primeiro. Um workflow embutido e uma
    retomada por id de execução não carregam texto aqui: o primeiro é o próprio script do
    runtime, e o segundo re-executa um cujo lançamento este hook já julgou.
    """
    inputs = event.get("tool_input") or {}
    cwd = Path(event.get("cwd") or os.getcwd())
    candidates = []
    if isinstance(inputs.get("scriptPath"), str) and inputs["scriptPath"]:
        candidates.append(cwd / Path(inputs["scriptPath"]).expanduser())
    elif isinstance(inputs.get("script"), str):
        return inputs["script"]
    elif isinstance(inputs.get("name"), str) and WORKFLOW_NAME.fullmatch(inputs["name"]):
        for base in (cwd, Path(os.environ.get("HOME") or Path.home())):
            for suffix in (".js", ".mjs", ".ts"):
                candidates.append(base / ".claude" / "workflows" / (inputs["name"] + suffix))
    for candidate in candidates:
        try:
            if candidate.is_file():
                with open(str(candidate), encoding="utf-8", errors="replace") as stream:
                    text = stream.read(WORKFLOW_SCRIPT_MAX + 1)
                return WORKFLOW_TOO_LARGE if len(text) > WORKFLOW_SCRIPT_MAX else text
        except OSError:
            continue
    return None


def workflow_literal(text, keep_quoting=False):
    """`text` com seus escapes de JavaScript decodificados: o corpo de um literal, ou, com
    `keep_quoting`, um script inteiro, onde uma aspa ou escape de barra invertida permanece
    escapado para que os literais mantenham seus limites."""
    def decode(match):
        code = match.group(1) or match.group(2) or match.group(3)
        if code is not None:
            return chr(min(int(code, 16), 0x10FFFF))
        if match.group(4) is not None:
            return WORKFLOW_CONTROL[match.group(4)]
        return match.group(0) if keep_quoting else match.group(5)
    return WORKFLOW_ESCAPE.sub(decode, text)


def workflow_role(script):
    """`(name, fields, how)` para o primeiro papel restrito que um script de workflow nomeia, senão None.

    O script é lido duas vezes, como está escrito e com seus escapes decodificados, porque uma
    chave escapada (`agent\\u0054ype`) ou uma quebra de linha escapada ao redor de uma linha
    `harness-role:` lê como a forma simples assim que o JavaScript a avalia. Veja
    `workflow_role_in` para uma leitura.
    """
    if not isinstance(script, str):
        return None
    named = workflow_role_in(script)
    decoded = workflow_literal(script, keep_quoting=True)
    if named is None and decoded != script:
        named = workflow_role_in(decoded)
    return named


def workflow_role_in(script):
    """O papel restrito que uma leitura de um script de workflow nomeia, como `workflow_role` o retorna.

    Um valor `agentType` entre aspas é lido diretamente. Qualquer outra menção a `agentType` — um
    valor computado, uma propriedade abreviada — não pode ser, então qualquer literal de string
    inteiro nomeando um papel restrito conta: um script que escolhe seu tipo de agente em tempo
    de execução a partir de uma lista contendo `'reviewer'` nomeia esse papel tão certamente
    quanto um que o escreve inline. Isso erra a favor da recusa, como `constrained_role` faz para
    um contrato que não consegue carregar. Um marcador é comparado como `marker_role` compara um,
    uma declaração isolada nomeando um papel compartilhado restrito.
    """
    computed = False
    for mention in WORKFLOW_AGENT_TYPE.finditer(script):
        match = WORKFLOW_AGENT_VALUE.match(script, mention.end())
        if match is None or "${" in match.group(2):
            computed = True
            continue
        fields = constrained_role(match.group(2))
        if fields is not None:
            return match.group(2), fields, "names `" + match.group(2) + "` in agentType"
    for name in WORKFLOW_MARKER.findall(script):
        fields = constrained_role(name)
        if fields is not None:
            return name, fields, "carries a `harness-role: " + name + "` marker"
    if computed:
        literals = [m.group(2) for m in WORKFLOW_LITERAL.finditer(script)]
        literals += [workflow_literal(m.group(2)) for m in WORKFLOW_ESCAPED.finditer(script)]
        for value in literals:
            fields = constrained_role(value) if re.fullmatch(r"[a-z][a-z0-9-]*", value) else None
            if fields is not None:
                return (value, fields, "computes agentType and names `" + value
                        + "` in a string literal")
    return None


def workflow_results(runtime, event):
    """As respostas a um lançamento `Workflow`, com sua linha de decisão escrita.

    Todo lançamento é uma linha, os permitidos incluídos, porque um lançamento é um lote de
    disparos que nenhuma outra linha contabiliza. A entrada da linha é o script como foi julgado,
    ou a entrada da ferramenta quando o script não pôde ser lido.
    """
    results = []
    script = workflow_script(event)
    if script is WORKFLOW_TOO_LARGE:
        results.append({"hookSpecificOutput": {"permissionDecision": "deny",
            "permissionDecisionReason": "This workflow script is longer than the "
            + str(WORKFLOW_SCRIPT_MAX) + " characters the guard reads, so the constrained roles "
            "it names cannot be checked; split it or send it inline."}})
    elif selected("delegation", "tiered") == "off":
        results.append({"hookSpecificOutput": {"permissionDecision": "deny",
            "permissionDecisionReason": "Delegation is off, and every agent() call in a workflow "
            "script is a spawn; perform the work inline or change the selected stance."}})
    else:
        named = workflow_role(script)
        if named is not None:
            results.append(role_deny(runtime, named[0], named[1],
                                     "This workflow script " + named[2] + ", and a script's "
                                     "agent() calls run in session, past every spawn guard."))
    if not results and enabled("allow-readonly-bash") and investigating(runtime, event) \
            and plan_allowed_tool("Workflow"):
        results.append({"hookSpecificOutput": {"permissionDecision": "allow",
            "permissionDecisionReason": "Plan-mode research tool named by plan_allow_tools, "
            "run at the permission posture you selected."}})
    module = decisions()
    if module is not None:
        denied = any(r["hookSpecificOutput"].get("permissionDecision") == "deny" for r in results)
        text = script if isinstance(script, str) else json.dumps(event.get("tool_input") or {}, sort_keys=True)
        module.record(WORKFLOW_POINT, "deny" if denied else "allow", text, event, runtime)
    return results


def framework_deny(runtime, session_id, prompt, subagent_type):
    """A recusa que o disparo de uma integração declarada recebe, ou None quando esta chamada não é uma.

    A classificação é do descritor, não do modelo: `subagent_type` é um sinal entre vários e não
    carrega mais peso que os demais. Só um papel que a proteção restringiria é comparado, então
    um mapeamento não pode ser usado para recusar trabalho que o harness não confina.

    Esta recusa deliberadamente não é lembrada. Uma lembrada é comparada por prefixo ou
    similaridade pelo resto da sessão, então uma classificação errada continuaria recusando o
    brief corrigido também; o descritor responde a cada disparo pela sua própria evidência em vez
    disso. Veja `frameworks.py`.
    """
    try:
        from . import frameworks
        match = frameworks.classify(prompt, subagent_type, accept=lambda role: constrained_role(role) is not None)
    except Exception:
        return None
    if match is None:
        return None
    name = match["role"]
    fields = constrained_role(name)
    if fields is None:
        return None
    module = decisions()
    if module is not None:
        module.record("framework-spawn", "deny", fingerprint(prompt),
                      {"session_id": session_id}, runtime)
    return role_deny(runtime, name, fields, frameworks.origin(match))


def descriptor_notice(session_id):
    """Um único `systemMessage` nomeando cada descritor de integração que o carregador não conseguiu usar.

    Dito uma vez por sessão, porque um descritor que ninguém consegue carregar é imposição que
    parou, e o único lugar onde um usuário de outra forma veria isso é numa recusa que nunca veio.
    """
    try:
        from . import frameworks
        broken = frameworks.ignored()
    except Exception:
        return None
    if not broken or not notice_once(session_id, "integration-descriptors"):
        return None
    module = decisions()
    for name, reason in broken:
        if module is not None:
            module.record("integration-descriptor", "ignored", name + ": " + reason,
                          {"session_id": session_id})
    return {"systemMessage": "harness:integrations: ignored " + "; ".join(
        name + " (" + reason + ")" for name, reason in broken)
        + ". Spawns that descriptor would have confined are not being classified."}


def notice_once(session_id, key):
    """Se esta sessão ainda não recebeu o aviso `key`. Registra que agora recebeu. Nunca levanta exceção."""
    try:
        posture = load("posture")
        record = posture.read_session_record(session_id) or {}
        said = [k for k in record.get(NOTICED_KEY, []) if isinstance(k, str)]
        if key in said:
            return False
        posture.write_session_record(session_id, dict(record, **{NOTICED_KEY: (said + [key])[-DENIED_MAX:]}))
        return True
    except Exception:
        return False


def fingerprint(prompt):
    """Um brief reduzido ao que um re-disparo não consegue variar: espaço, caixa e comprimento removidos."""
    return " ".join(prompt.split()).casefold()[:FINGERPRINT_MAX] if isinstance(prompt, str) else ""


def same_work(left, right):
    """Se duas fingerprints são o mesmo brief. Igualdade, contenção, depois similaridade.

    A contenção só é testada num prefixo longo o bastante para ser evidência; um brief curto que
    por acaso aparece dentro de um mais longo e não relacionado é uma recusa falsa, e uma recusa
    que ninguém consegue explicar é pior que a evasão que ela previne.
    """
    if not left or not right:
        return False
    if left == right:
        return True
    for a, b in ((left, right), (right, left)):
        if len(a) >= PREFIX_MATCH and a[:PREFIX_MATCH] in b:
            return True
    return difflib.SequenceMatcher(None, left, right).ratio() >= SIMILARITY


def denied_spawns(session_id):
    """O que esta sessão já recusou como disparo de papel restrito; `[]` para qualquer outra coisa.

    Um estado que um hook não consegue ler é um estado que não existe. A proteção então se
    comporta exatamente como se comportava antes de ser escrita, porque um hook de disparo que
    levanta exceção é pior que um que esquece.
    """
    try:
        record = load("posture").read_session_record(session_id)
        entries = (record or {}).get(DENIED_KEY)
        return [e for e in entries if isinstance(e, dict) and isinstance(e.get("prompt"), str)] \
            if isinstance(entries, list) else []
    except Exception:
        return []


def remember_denial(session_id, name, prompt):
    """Adiciona uma recusa à memória da sessão, a mais nova por último. Melhor esforço, nunca levanta exceção."""
    text = fingerprint(prompt)
    if not text:
        return False
    try:
        posture = load("posture")
        record = posture.read_session_record(session_id) or {}
        entries = [e for e in denied_spawns(session_id) if e.get("prompt") != text]
        entries.append({"role": name, "prompt": text})
        return bool(posture.write_session_record(session_id, dict(record, **{DENIED_KEY: entries[-DENIED_MAX:]})))
    except Exception:
        return False


def evasion_deny(runtime, session_id, prompt):
    """A recusa que um re-disparo de trabalho já recusado recebe, ou None quando não é esse o caso."""
    text = fingerprint(prompt)
    for entry in reversed(denied_spawns(session_id)):
        if same_work(text, entry["prompt"]):
            name = entry.get("role") if isinstance(entry.get("role"), str) else ""
            module = decisions()
            if module is not None:
                # A fingerprint, não o brief: é sobre o que a comparação de fato rodou, e uma
                # recusa correspondida é o único julgamento aqui que vale um rótulo.
                module.record("evasion-deny", "deny", text, {"session_id": session_id}, runtime)
            return {"hookSpecificOutput": {"permissionDecision": "deny",
                    "permissionDecisionReason": "This work was refused as a native " + name
                    + " spawn in this session; dropping or changing the role name does not change that. "
                    + role_instruction(runtime, name, constrained_role(name))}}
    return None


def log_bash_decision(runtime, event, results, command=None, confirmed=False):
    """Registra a resposta de permissão que o harness deu a este comando, quando deu uma.

    Só `ask` e `deny` são linhas avaliadas. Uma aprovação é o harness optando por não interromper,
    e "rodou" não diz nada sobre se não interromper foi certo; uma recusa ou um prompt é o
    julgamento que um rótulo posterior pode avaliar. A linha é escrita aqui em vez de em
    `grade-bash.py` porque é aqui que a resposta é composta: o limiar do avaliador, o modo de
    permissão e a investigação de modo plano se combinam numa única resposta, e só uma é dada.

    Um comando permitido vai para `record_allowed`, que mantém um em cada vinte como um negativo
    não avaliado — mas só onde o harness deu o allow *e o runtime foi avisado*. Um comando sobre o
    qual o harness não disse nada é responsabilidade do próprio runtime e ainda pode receber
    prompt ou ser recusado, e no Codex uma aprovação simples é descartada da saída pela razão que
    `_encode_pre` dá, então nenhum dos dois é evidência de que algo foi permitido. Um comando
    confirmado também não é um: chegou aqui porque o usuário respondeu a um prompt que o harness
    levantou, então pertence à linha `ask` anterior.
    """
    module = decisions()
    if module is None:
        return
    answers = [r.get("hookSpecificOutput", {}).get("permissionDecision") for r in results]
    answer = next((choice for choice in ("deny", "ask", "allow") if choice in answers), None)
    if answer not in ("deny", "ask"):
        if answer == "allow" and not confirmed and runtime != "codex":
            module.record_allowed(command if command is not None
                                  else event["tool_input"]["command"], event, runtime)
        return
    command = event["tool_input"]["command"]
    module.record("grade-bash", answer, command, event, runtime,
                  key=module.match_key(event, command))


def log_bash_outcome(runtime, event):
    """Junta `ran` à decisão a que este comando concluído pertence, quando havia uma.

    A ferramenta rodou, então seja lá o que o harness perguntou, o usuário deixou passar. Um
    comando sobre o qual nada foi perguntado não tem decisão no log e não recebe registro; um
    comando sobre o qual se perguntou e que nunca voltou é fechado como `not_run` no SessionEnd,
    porque uma recusa direta e um turno interrompido parecem idênticos daqui.
    """
    module = decisions()
    if module is None:
        return
    command = (event.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or not command:
        return
    identity = module.decision_id("grade-bash", module.match_key(event, command))
    module.observe_if_logged(identity, module.RAN, "grade-bash", event.get("session_id") or "")


def encode_pre(runtime, original, normalized, results):
    encoded = _encode_pre(runtime, original, normalized, results)
    # O aviso de uma política é o único rastro de uma reescrita que o usuário de outra forma nunca veria.
    notices = [r["systemMessage"] for r in results if isinstance(r.get("systemMessage"), str) and r["systemMessage"]]
    if notices and runtime == "claude-code":
        encoded = dict(encoded, systemMessage="\n".join(notices))
    return encoded


def _encode_pre(runtime, original, normalized, results):
    decisions = [r.get("hookSpecificOutput", {}).get("permissionDecision") for r in results]
    strongest = next((choice for choice in ("deny", "ask", "allow") if choice in decisions), None)
    reasons = [r.get("hookSpecificOutput", {}).get("permissionDecisionReason", "") for r in results]
    reason = "\n".join(x for x in reasons if x)
    fields = {"hookEventName": "PreToolUse"}
    # Um cliente Codex rejeita toda a saída do hook quando ela carrega um `allow` não suportado,
    # então uma aprovação simples não diz nada e deixa o padrão próprio daquele runtime valer.
    if strongest and not (runtime == "codex" and strongest == "allow"):
        fields["permissionDecision"] = "deny" if runtime == "codex" and strongest == "ask" else strongest
        fields["permissionDecisionReason"] = reason
    if strongest in ("deny", "ask"):
        return {"hookSpecificOutput": fields}
    changes = {}
    for result in results:
        changes.update({key: value for key, value in result.get("hookSpecificOutput", {}).get("updatedInput", {}).items()
                        if normalized["tool_input"].get(key) != value})
    if changes:
        updated = dict(original.get("tool_input") or {})
        before = normalized["tool_input"]
        for key, value in changes.items():
            if before.get(key) == value:
                continue
            native_key = key
            if key == "command" and "cmd" in updated:
                native_key = "cmd"
            elif key == "prompt" and "message" in updated:
                native_key = "message"
            elif key == "subagent_type" and "agent_type" in updated:
                native_key = "agent_type"
            updated[native_key] = value
        # O Codex exige allow para reescritas. Não fabrique uma aprovação só para formatar a saída.
        can_rewrite = runtime == "claude-code" or strongest == "allow" or normalized["tool_name"] == "Agent"
        if can_rewrite and updated != original.get("tool_input"):
            fields["updatedInput"] = updated
            if runtime == "codex":
                fields["permissionDecision"] = "allow"
                if reason:
                    fields["permissionDecisionReason"] = reason
    return {"hookSpecificOutput": fields} if len(fields) > 1 else {}


def policy_file_result(runtime, event):
    """A resposta a uma escrita de ferramenta de arquivo num arquivo de política de governança, ou None.

    Perguntado num modo de prompt. Onde nada pode perguntar é recusado, e no modo auto do Claude
    Code a recusa nomeia um código de aprovação para essa edição exata, que a resposta
    `approve <code>` do usuário deixa passar uma vez, como faz com um comando Bash que
    `grade-bash` recusou.
    """
    grader = load("grade-bash")
    guarded = grader.govern_file(event["tool_name"], event["tool_input"], patch_paths(event),
                                 event, runtime)
    if guarded is None:
        return None
    subject, sentence = guarded
    mode, session = event.get("permission_mode"), event.get("session_id")
    if runtime != "codex" and mode not in grader.DENY_MODES:
        return {"hookSpecificOutput": {"permissionDecision": "ask",
                                       "permissionDecisionReason": sentence}}
    code = grader.approval_code(mode, session, subject) if runtime == "claude-code" else None
    if code is not None and grader.approved(mode, session, subject):
        return None
    tail = grader.FILE_APPROVAL_TAIL % code if code else grader.FILE_DENY_TAIL
    return {"hookSpecificOutput": {"permissionDecision": "deny",
                                   "permissionDecisionReason": sentence + tail}}


def patch_paths(event):
    inputs = event["tool_input"]
    paths = [inputs.get("file_path"), inputs.get("path")]
    response = event.get("tool_response")
    if isinstance(response, dict):
        paths.append(response.get("filePath"))
    if event["tool_name"] == "apply_patch":
        patch = inputs.get("command", inputs.get("patch", ""))
        if isinstance(patch, str):
            # Todo caminho que um patch toca, exclusões incluídas: um patch só de exclusão que
            # não nomeasse nenhum caminho de outra forma passaria por toda proteção num arquivo
            # que remove.
            paths.extend(re.findall(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$",
                                    patch, re.M))
    return sorted(set(str(Path(event.get("cwd") or os.getcwd()) / p) for p in paths if p))


def store_write_deny(paths):
    """A proteção do store sem `approvals.py`, para quando aquele módulo não consegue carregar.

    Toda chamada de ferramenta de arquivo de outra forma falharia no carregamento e seria negada
    como não verificada; isto recusa só uma escrita sob o diretório de aprovações e deixa o resto
    passar. O caminho é o mesmo que `approvals.store_dir` nomeia, resolvido aqui a partir do
    mesmo ambiente."""
    home = os.environ.get("HARNESS_HOME") or os.environ.get("HOME") or str(Path.home())
    root = os.path.realpath(os.path.join(home, ".local", "state", "agent-harness", "approvals"))
    for path in paths:
        target = os.path.realpath(os.path.expanduser(str(path)))
        if target == root or target.startswith(root + os.sep):
            return {"hookSpecificOutput": {"permissionDecision": "deny",
                    "permissionDecisionReason": "The approvals store is written only from the user's "
                    "own prompt, so no tool may write to it."}}
    return None


def dispatch(runtime, payload):
    if runtime not in ("claude-code", "codex"):
        raise ValueError("unknown runtime")
    _SWITCHES.append(switches())
    try:
        return _dispatch(runtime, payload)
    finally:
        _SWITCHES.pop()


def _dispatch(runtime, payload):
    """Compõe as políticas para um evento. Lógica que não é um `invoke` verifica seu próprio id
    dono: avaliação de Bash, seu ask e seu log de decisão são `grade-bash`; allows de modo plano e
    somente leitura são `allow-readonly-bash`; o aviso de integração é `tier-agent-spawns`. O
    confinamento de papel, por nome, marcador, mapeamento de framework ou evasão, não tem id e
    roda com todo hook desligado, assim como a proteção de lançamento de Workflow: um switch
    roteia disparos, nunca desconfina um papel."""
    event = normalize(payload)
    kind, tool = event.get("hook_event_name"), event.get("tool_name")
    if kind == "PreToolUse":
        results = []
        # O store de aprovações que o usuário digitou pertence só ao usuário; `grade-bash` o
        # consome, então também o protege. Uma escrita Bash nele é avaliada, uma escrita de
        # ferramenta de arquivo é recusada aqui.
        if tool in FILE_TOOLS and enabled("grade-bash"):
            paths = patch_paths(event)
            try:
                forged = load("approvals").file_write_deny(paths)
            except Exception:
                forged = store_write_deny(paths)
            if forged is not None:
                results.append(forged)
            if forged is None:
                # Um arquivo de política de governança só é editado com o sim do usuário, toda
                # vez: o provedor o lê, então o agente que ele governa não pode conceder a si
                # mesmo um nível.
                guarded = policy_file_result(runtime, event)
                if guarded is not None:
                    results.append(guarded)
        # Só uma reescrita: a aprovação de modo plano abaixo ainda responde por esta ferramenta.
        if tool == "SendUserFile" and runtime == "claude-code":
            results.append(invoke("stage-user-files", event))
        if tool == "Bash":
            grading, readonly = enabled("grade-bash"), enabled("allow-readonly-bash")
            grader = load("grade-bash") if grading or readonly else None
            if grader is not None and grader.ro is None:
                raise RuntimeError("command classifier unavailable")
            # A resolução de stance compartilhada inclui seleções explícitas de projeto e de sessão.
            variant = selected("autonomy", "execute")
            raw = command = event["tool_input"]["command"]
            confirmed = False
            grade = verb = target = family = None
            if grader is not None:
                command, confirmed = grader.strip_marker(command)
                grade, verb, target, family = grader.grade_text(command, event.get("cwd", ""))
            asked = grading and bool(grade) and not confirmed and grade >= grader.THRESHOLDS.get(variant, 1)
            # O provedor de decisão, quando um está configurado, só é consultado sobre o que a
            # stance deixa passar, para que possa adicionar um prompt e nunca remover um.
            governed = None
            if grading and bool(grade) and not confirmed and not asked:
                governed = grader.govern(command, event.get("cwd", ""), grade, variant, event, runtime)
                asked = governed is not None
            if asked and governed is not None and governed[0] == "deny":
                results.append({"hookSpecificOutput": {"permissionDecision": "deny",
                    "permissionDecisionReason": grader.reason(grade, verb, target, family, variant)
                    + " " + governed[1]}})
            elif asked:
                mode, session = event.get("permission_mode"), event.get("session_id")
                decision = "deny" if runtime == "codex" or mode in grader.DENY_MODES else "ask"
                # O Codex não dispara UserPromptSubmit, então só o modo auto do Claude Code pode
                # carregar uma aprovação que o usuário digitou; `grade-bash.py` é dono do canal e
                # da sua redação.
                channel = runtime == "claude-code" and decision == "deny"
                if channel and grader.approved(mode, session, raw):
                    asked, confirmed = False, True
                else:
                    why = grader.reason(grade, verb, target, family, variant)
                    if governed is not None:
                        why += " " + governed[1]
                    code = grader.approval_code(mode, session, raw) if channel else None
                    results.append({"hookSpecificOutput": {"permissionDecision": decision,
                        "permissionDecisionReason": why + (grader.APPROVAL_TAIL % code if code else "")}})
            # A nota 0 é provadamente somente leitura, então é aprovada em todo modo. As notas 1 e
            # 2 são aquelas sobre as quais o modo plano nativo pergunta: um script que a gramática
            # não consegue interpretar por completo, um redirecionamento para scratch, uma
            # execução de teste. Sob uma postura aberta, a primeira é investigação e a segunda
            # não é, e a stance de autonomia ainda tem prioridade sobre ambas quando já perguntou.
            plan = readonly and investigating(runtime, event)
            if readonly and grade == 0:
                results.append({"hookSpecificOutput": {"permissionDecision": "allow"}})
            elif plan and not asked and grade == 1:
                results.append({"hookSpecificOutput": {"permissionDecision": "allow",
                    "permissionDecisionReason": "Plan-mode investigation, run at the permission posture you selected."}})
            elif plan and not asked and not confirmed and grade == 2:
                results.append({"hookSpecificOutput": {"permissionDecision": "ask",
                    "permissionDecisionReason": "This reaches past the workspace, so it is execution rather than "
                    "planning. Plan mode widens investigation, not the build. "
                    + grader.reason(grade, verb, target, family, variant)}})
            results.append(invoke("filter-output", event))
            if grading:
                log_bash_decision(runtime, event, results, command, confirmed)
        elif tool == "Agent":
            delegation = selected("delegation", "tiered")
            inputs = event["tool_input"]
            role_name, prompt = inputs.get("subagent_type"), inputs.get("prompt")
            session = event.get("session_id")
            fields = constrained_role(role_name)
            if fields is not None:
                results.append(confinement_deny(runtime, session, role_name, fields, prompt,
                                                "subagent_type"))
            # Recusar o disparo nomeado só desloca o trabalho: o mesmo brief volta com o nome do
            # papel removido, e nada percebe. Então um disparo é classificado tanto pelo que
            # carrega quanto pelo que se autodenominou — uma linha `harness-role:`, depois o
            # próprio mapeamento de uma integração de framework declarada. Uma recusa que o
            # disparo declarou, por nome de papel ou marcador, é lembrada pela sessão para que a
            # próxima reformulação também seja recusada; uma recusa que o classificador inferiu
            # não é, porque uma inferência errada lembrada é uma sessão que não consegue passar o
            # brief corrigido. Nada disso roda onde a stance já nega todo disparo.
            if delegation != "off":
                if fields is not None:
                    remember_denial(session, role_name, prompt)
                else:
                    marked = marker_role(prompt)
                    if marked is not None:
                        results.append(confinement_deny(runtime, session, marked[0], marked[1],
                                                        prompt, "harness-role marker"))
                        remember_denial(session, marked[0], prompt)
                    else:
                        framed = framework_deny(runtime, session, prompt, role_name)
                        evaded = framed or evasion_deny(runtime, session, prompt)
                        if evaded is not None:
                            results.append(evaded)
                notice = descriptor_notice(session) if enabled("tier-agent-spawns") else None
                if notice is not None:
                    results.append(notice)
            if delegation == "off":
                results.append({"hookSpecificOutput": {"permissionDecision": "deny",
                    "permissionDecisionReason": "Delegation is off; perform the work inline or change the selected stance."}})
            else:
                if runtime == "claude-code":
                    results.append(invoke("tier-agent-spawns", event))
                results.append(invoke("brief-guard", event))
        elif tool == "Workflow":
            results.extend(workflow_results(runtime, event))
        elif tool == "WebFetch":
            results.append(invoke("allow-plan-webfetch", event))
        elif enabled("allow-readonly-bash") and investigating(runtime, event) and plan_allowed_tool(tool):
            results.append({"hookSpecificOutput": {"permissionDecision": "allow",
                "permissionDecisionReason": "Plan-mode research tool named by plan_allow_tools, "
                "run at the permission posture you selected."}})
        return encode_pre(runtime, payload, event, results)
    if kind == "PostToolUse":
        contexts = []
        if tool == "Bash" and enabled("grade-bash"):
            log_bash_outcome(runtime, event)
        if selected("plan-ceremony", "review-card") == "review-card":
            for path in patch_paths(event):
                result = invoke("validate-plan-card", dict(event, tool_input={"file_path": path},
                                                          tool_response={"filePath": path}))
                context = result.get("hookSpecificOutput", {}).get("additionalContext")
                if context:
                    contexts.append(context)
        warning = invoke("neutralize-tool-output", event)
        if warning:
            contexts.append(warning.get("hookSpecificOutput", {}).get("additionalContext") or warning.get("systemMessage", ""))
        if runtime == "claude-code" and tool == "Agent":
            feed = invoke("usage-feed", event).get("hookSpecificOutput", {}).get("additionalContext")
            if feed:
                contexts.append(feed)
        return {"hookSpecificOutput": {"hookEventName": kind, "additionalContext": "\n".join(contexts)}} if any(contexts) else {}
    if kind in FEED_EVENTS:
        # A feed never denies, never blocks and never speaks for another policy, so it answers
        # its own two events alone. The approvals recorder speaks for nothing either: it only
        # keeps the `approve <code>` replies in the user's prompt.
        if runtime != "claude-code":
            return {}
        if kind == "UserPromptSubmit":
            invoke("approvals", event)
        return invoke("usage-feed", event)
    if kind == "SessionStart":
        return invoke("harness-session", event)
    if kind == "Stop":
        return invoke("stop-gate", event)
    if kind == "SessionEnd":
        # Nothing will arrive for this session again, so an ask with no PostToolUse is settled:
        # the command did not run. Done before the usage worker is spawned, and bounded by the
        # session's own rows, so the 1.5-second SessionEnd budget pays for one read of a file
        # that only a permission prompt writes to.
        log = decisions()
        if log is not None:
            log.close_session(event.get("session_id") or "")
        if not enabled("usage-log"):
            return {}
        module = load("usage-log")
        old = sys.stdin
        try:
            sys.stdin = io.StringIO(json.dumps(event))
            module.main([])
        finally:
            sys.stdin = old
    return {}


def registration(root, runtime):
    command = "python3 " + shlex.quote(str(root / "adapters" / runtime / "hook.py"))
    return {"hooks": {event: [{"hooks": [{"type": "command", "command": command + " # harness:runtime-" + event.lower(),
                                         "timeout": 300 if event == "Stop" else 2 if event == "SessionEnd" else 10}]}]
                      for event in EVENTS.get(runtime, BASE_EVENTS)}}


def main(runtime):
    os.environ["HARNESS_RUNTIME"] = runtime
    kind = ""
    try:
        payload = json.load(sys.stdin)
        kind = payload.get("hook_event_name", "")
        result = dispatch(runtime, payload)
    except Exception as exc:
        message = "Harness policy is unverified: " + type(exc).__name__ + ": " + str(exc)
        if kind == "PreToolUse":
            result = {"hookSpecificOutput": {"hookEventName": kind, "permissionDecision": "deny", "permissionDecisionReason": message}}
        elif kind == "Stop":
            result = {"decision": "block", "reason": message}
        else:
            result = {"systemMessage": message}
    if result:
        print(json.dumps(result))
