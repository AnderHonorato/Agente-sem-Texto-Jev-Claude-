#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hook de PreToolUse: aplica a stance de delegação a todo disparo de subagente, seja lá quem escreveu o brief.

Os níveis da stance viajam como frontmatter nos agentes que o harness distribui, então alcançam
qualquer disparo que nomeie um. Um disparo que não nomeia nada — sem `subagent_type`, ou
`general-purpose`, e sem `model` — é o que um framework de planejamento ou um plugin produz
quando o texto da sua skill diz "lance um subagente", e nada mais no harness o alcança. Este hook
alcança. Uma chamada que nomeia uma definição de agente ou passa `model` é deixada como estava,
com uma exceção: a classe mais forte é alcançada através de um papel que a declara, nunca por
pedido. Um disparo que pede por ela via `model` recebe em vez disso o modelo que sua definição de
agente nomeia, ou a classe abaixo quando não há definição para ler — para que nem um
orquestrador nem o texto de skill de um framework ("rode revisores na capacidade da sessão")
consiga colocar trabalho ad-hoc no nível mais escasso. O pedido é reescrito, nunca removido: uma
reescrita sobrevive à composição com outros hooks.

O que um disparo nu recebe depende da stance `delegation`, que `posture.py` resolve para todo
hook igualmente:

    tiered         roteia-o para o band worker padrão da variante de custo, na classe daquela banda;
                   sem banda padrão, reescreve `model` para um nível abaixo do modelo da sessão,
                   sendo a classe mais fraca da escada o piso; recusa o nível mais alto por pedido
    session-model  deixa-o em paz
    off            nega todo disparo, nomeado ou não, como a stance diz; o ciclo de vida nega
                   primeiro e nunca invoca este hook, então este ramo só decide uma execução direta

Os band workers existem porque a ferramenta `Agent` não tem entrada de esforço: um disparo que
não nomeia nada herda o esforço da sessão, e só uma definição de agente pode carregar o da
postura. Então um disparo sem `subagent_type`, ou `general-purpose`, é reescrito para
`worker-a`, `worker-b` ou `worker-c` — o `default_band` da variante — e o orquestrador que
queria uma banda diferente dispara aquele worker pelo nome. Uma máquina cujas definições de
worker não estão instaladas não é roteada de forma alguma: um `subagent_type` que a ferramenta
não consegue resolver falharia o disparo. Nem é uma sessão que começou antes de eles serem
instalados e não foi avisada disso desde então — então o reroteamento pergunta ao registro de
sessão que `posture.sessions_dir` descreve e ao recarregamento que o transcript anuncia, não ao
disco, e um reroteamento nunca transforma um disparo que teria funcionado num que falha.

A escada é a tabela de classes de `bindings.json` do adaptador, classe mais forte primeiro,
comparada como substrings dos ids de modelo que um transcript registra; nenhum nome de modelo é
escrito aqui.

Um repositório que carrega um framework de planejamento é nivelado como qualquer outro. O
framework mantém suas personas, prompts e estrutura de revisão; modelo e esforço são escolha do
harness, e os templates de override do framework nomeiam os papéis do harness onde a receita
permite, que é o que carrega ferramentas e esforço.

O modelo da sessão é lido do registro de assistente de linha principal mais novo no transcript,
que o Claude Code escreve assim que uma resposta começa a executar ferramentas, então um disparo
na primeiríssima resposta de uma sessão é deixado em paz: nada mais diz em que a sessão roda (a
chave `model` nas settings é um padrão que a sessão pode não estar usando). Um modelo de sessão
que a escada não conhece é deixado intocado em vez de adivinhado, e o hook diz isso, porque um
nome de modelo novo de outra forma desligaria o nivelamento sem um som. Nunca falha: todo erro
cai no fluxo normal e a chamada roda como foi escrita.

Teste: printf '%s' '{"tool_name":"Agent","tool_input":{"prompt":"x"}}' | HARNESS_STANCE_DELEGATION=off python3 tier-agent-spawns.py
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
DEFAULT_STANCE = "tiered"
TAIL_BYTES = 1 << 20
HOOK = "tier-agent-spawns hook"
AGENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
# Os dois avisos que uma sessão ouve uma vez em vez de a cada disparo: para onde um disparo sem
# nome vai, e que o worker está em disco mas o registro desta sessão é anterior a ele. Ambos
# descrevem o arranjo permanente, então repeti-los a cada disparo é ruído. Um aviso sobre algo
# que o chamador pediu sendo mudado ou recusado continua por ocorrência.
ROUTED_NOTICE = "routed-to-band"
UNRESOLVABLE_NOTICE = "worker-unresolvable"
_LOADED = {}


def sibling(name):
    """Um módulo ao lado deste hook, ou None. Um hook nunca deve parar um disparo porque um import falhou."""
    try:
        spec = importlib.util.spec_from_file_location(
            "harness_" + name.replace("-", "_"), str(HOOKS / (name + ".py")))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def posture_module():
    """O irmão compartilhado, carregado no máximo uma vez por execução: toda pergunta aqui pergunta à mesma cópia."""
    if "posture" not in _LOADED:
        _LOADED["posture"] = sibling("posture")
    return _LOADED["posture"]


def log_route(payload, tool_input, route):
    """Registra para qual banda um disparo sem nome foi roteado. Veja `decisions.py`; nunca levanta exceção."""
    if "decisions" not in _LOADED:
        _LOADED["decisions"] = sibling("decisions")
    module = _LOADED["decisions"]
    if module is not None:
        prompt = tool_input.get("prompt")
        module.record("tier-agent-spawns", route["worker"],
                      prompt if isinstance(prompt, str) else "",
                      payload if isinstance(payload, dict) else {})


def notice_once(session, key):
    """Se deve dizer `key` nesta sessão agora; o registro de sessão é o que o lembra.

    Nada que não pode ser lembrado é dito, porque um hook é um processo por evento e um aviso que
    ninguém registra é um aviso repetido a cada disparo.
    """
    module = posture_module()
    try:
        return bool(module.note_once(session, key))
    except Exception:
        return False


def tier_of(model, ladder):
    """O nome de escada dentro de um id de modelo ou alias, ou None para qualquer coisa que a escada não tenha."""
    if not isinstance(model, str):
        return None
    low = model.lower()
    for name in ladder:
        if name in low:
            return name
    return None


def transcript_model(path):
    """O modelo no registro de assistente de linha principal mais novo, lendo só o final do transcript."""
    if not path:
        return None
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - TAIL_BYTES))
            tail = fh.read().decode("utf-8", "replace")
    except Exception:
        return None
    for line in reversed(tail.splitlines()):
        if '"assistant"' not in line:
            continue
        try:
            record = json.loads(line)
        except Exception:
            continue
        if not isinstance(record, dict) or record.get("type") != "assistant" or record.get("isSidechain"):
            continue
        message = record.get("message")
        model = message.get("model") if isinstance(message, dict) else None
        # Registros de placeholder ("<synthetic>") não nomeiam modelo; qualquer outra coisa é o da sessão, conhecido ou não.
        if isinstance(model, str) and model and not model.startswith("<"):
            return model
    return None


def agents_dirs(cwd):
    """`(diretórios de projeto, o do usuário)` onde o Claude Code resolve uma definição de agente.

    Projeto antes de usuário, que é a própria precedência da ferramenta. `posture.user_agents_dir`
    guarda a regra do diretório do usuário, então este hook e a política de SessionStart leem um
    único diretório; a mesma expressão substitui na execução onde aquele irmão não importaria.
    """
    module = posture_module()
    if module is not None:
        user = module.user_agents_dir(os.environ)
    else:
        config = os.environ.get("CLAUDE_CONFIG_DIR")
        user = (Path(config) if config else Path.home() / ".claude") / "agents"
    return ([Path(cwd) / ".claude" / "agents"] if isinstance(cwd, str) and cwd else []), user


def definition(kind, cwd):
    """O frontmatter da definição que um disparo deste tipo resolveria, ou None.

    Um leitor para toda pergunta que este hook faz sobre uma definição de agente, para que "qual
    arquivo a ferramenta usaria" seja respondida uma vez. Um arquivo que existe mas não parseia
    encerra a busca do jeito que sempre encerrou: a ferramenta o resolveria, então nenhuma raiz
    mais fraca o substitui.
    """
    if not isinstance(kind, str) or not AGENT_NAME.fullmatch(kind):
        return None
    project, user = agents_dirs(cwd)
    for root in project + [user]:
        try:
            header = (root / (kind + ".md")).read_text(encoding="utf-8").split("---", 2)[1]
        except Exception:
            continue
        fields = {}
        for line in header.splitlines():
            key, sep, value = line.partition(":")
            if sep:
                fields.setdefault(key.strip(), value.strip())
        return fields
    return None


def defined_tier(kind, cwd, ladder):
    """O nome de escada que a linha `model:` de uma definição de agente carrega, projeto antes de usuário, ou None."""
    fields = definition(kind, cwd)
    return tier_of(fields.get("model"), ladder) if fields else None


def is_unnamed(tool_input):
    """Um disparo que não nomeou nenhuma definição de agente, seja qual for o modelo que pediu."""
    kind = tool_input.get("subagent_type")
    return not kind or kind == "general-purpose"


def is_bare(tool_input):
    return not tool_input.get("model") and is_unnamed(tool_input)


def announced(module, session, transcript, kind):
    """Se esta sessão foi avisada, depois de ter começado, que resolve `kind`.

    A própria declaração do runtime tem prioridade sobre o registro escrito no início da sessão,
    porque é mais recente e é sobre esta sessão: uma sessão que não recarregou nada não anuncia
    nada, então isso só pode alargar o que roteia. O transcript é o caminho de descoberta e o
    registro é a memória — a leitura do final é limitada, então o que encontrou é guardado onde o
    próximo disparo consegue ler sem o delta ainda estar no final. Um `posture.py` mais antigo ao
    lado deste hook não responde nada disso, que é o portão conservador.
    """
    if module is None:
        return False
    reader = getattr(module, "transcript_agents", None)
    keeper = getattr(module, "remember_agents", None)
    remembered = getattr(module, "session_announced", None)
    try:
        names = reader(transcript) if reader else None
        if names is None:
            names = remembered(session) if remembered else None
        elif keeper:
            keeper(session, names)
        return kind in (names or ())
    except Exception:
        return False


def routable(kind, cwd, session=None, announce=False, transcript=None):
    """`(a definição do usuário, aviso)` para um worker que um reroteamento nomearia; um dos dois é None.

    Um reroteamento precisa pousar na definição que o harness sincronizou e em nenhuma outra. Um
    `.claude/agents/<worker>.md` em nível de projeto tem prioridade sobre o do usuário, então um
    repositório que traz um colocaria suas próprias instruções em todo disparo sem nome de
    qualquer um que o clonasse: esse arquivo é um motivo para não rotear nada, dito em voz alta.
    Uma máquina que não sincronizou os workers é a mesma resposta pela razão mais simples de que
    a ferramenta não conseguiria resolver o tipo de forma alguma.

    Um arquivo em disco não basta: uma sessão resolve o registro que carregou, então esta sessão
    também precisa ter registrado o worker no próprio início (`posture.sessions_dir`) ou ter sido
    avisada sobre ele desde então (`posture.transcript_agents`). Sem nenhum dos dois o disparo é
    deixado como estava, porque um `subagent_type` que esta sessão não consegue resolver falha a
    chamada de vez. `announce` é o chamador que fala — o hook de disparo, não o de precificação —
    e só ele gasta a memória de uma-vez-por-sessão nesse aviso.
    """
    if not isinstance(kind, str) or not AGENT_NAME.fullmatch(kind):
        return None, None
    project, user = agents_dirs(cwd)
    for root in project:
        path = root / (kind + ".md")
        if path.is_file():
            return None, ("this repository ships " + str(path) + ", which would outrank the "
                          "harness's " + kind + ", so this spawn is not routed to the variant's "
                          "default band")
    if not (user / (kind + ".md")).is_file():
        return None, ("no " + kind + " definition is installed, so this spawn is not routed to "
                      "the variant's default band; run `citizen sync`")
    module = posture_module()
    known = module.session_agents(session) if module else None
    if known is not None:
        # Ler o registro é evidência de que esta sessão está viva, o que mantém uma sessão de
        # longa duração fora da varredura de outra sessão.
        module.refresh_session_record(session)
    if known is None or kind not in known:
        if announced(module, session, transcript, kind):
            return definition(kind, cwd) or {}, None
        notice = (kind + " is installed but this session started before it was; start a new "
                  "session to route unnamed spawns")
        if not (announce and notice_once(session, UNRESOLVABLE_NOTICE)):
            notice = None
        return None, notice
    return definition(kind, cwd) or {}, None


def switched_off(posture, role):
    """Se a seleção em vigor desliga `role`; um `posture.py` que não consegue dizer significa não.

    A sincronização retém a definição de um papel `off`, mas uma camada de sessão ou de projeto
    pode desligar um sem uma sincronização, e o arquivo que a última sincronização escreveu ainda
    está em disco. A seleção decide.
    """
    reader = getattr(posture, "selection", None)
    if reader is None:
        return False
    try:
        return (reader(strict=False).get("roles") or {}).get(role) == "off"
    except Exception:
        return False


def band_route(posture, models, cwd, table=None, session=None, announce=False, transcript=None):
    """`(route, notice)` para um disparo que não nomeou nada; a rota é None quando nada a roteia.

    A tabela de custo é lida aqui e em nenhum outro lugar deste hook, então um disparo que nomeou
    um papel nunca paga por ela. Uma variante sem `default_band` — e uma tabela que não
    resolveria — não roteia nada, que é o que mantém o comportamento da 0.10.0 byte a byte.

    `brief-guard` chama isto para precificar um disparo pelo worker para o qual está prestes a
    ser roteado, e passa a tabela que já construiu em vez de fazer isto construir uma segunda;
    uma resposta para "para onde vai um disparo sem nome" é o propósito da função compartilhada.

    O esforço em que um disparo reroteado de fato roda é o da definição instalada, porque esforço
    é escrito na sincronização e a ferramenta `Agent` não recebe nenhum; o da linha é o que a
    variante selecionada escreveria na próxima sincronização. A rota carrega os dois para que o
    aviso possa nomear a diferença.
    """
    try:
        table = posture.cost_table() if table is None else table
    except Exception:
        return None, None
    band = table.get("default_band")
    if band not in getattr(posture, "BANDS", ()):
        return None, None
    worker = posture.BAND_ROLES[band]
    if switched_off(posture, worker):
        return None, (worker + " is switched off in the selection, so this spawn is not routed to "
                      "the variant's default band")
    fields, notice = routable(worker, cwd, session, announce, transcript)
    if fields is None:
        return None, notice
    row = posture.row_for(table, worker) or {}
    return {"worker": worker, "row": row,
            "model": models.get(row.get("class")) if table.get("class_applies") else None,
            "effort": fields.get("effort") or row.get("effort"),
            "stale": bool(row.get("effort")) and fields.get("effort") != row.get("effort")}, None


def one_rung(payload, ladder):
    """A regra de hoje para um disparo que não nomeou nada: `(modelo um nível abaixo, mensagem)`.

    Um modelo None com uma mensagem é um disparo que este hook decidiu não mover e disse por quê;
    ambos None é um disparo sobre o qual não tem nada a dizer — a sessão já está na classe mais
    fraca, ou o transcript ainda não nomeia um modelo.
    """
    session = transcript_model(payload.get("transcript_path"))
    current = tier_of(session, ladder)
    if session and current is None:
        # Uma mudança de alinhamento que a escada não acompanhou não deve passar como "nada a fazer".
        return None, (f"the session model {session} is not on the ladder "
                      f"({', '.join(ladder)}), so this bare subagent stays on it; name a model or a role")
    if current is None or current == ladder[-1]:
        return None, None
    below = ladder[ladder.index(current) + 1]
    return below, f"bare subagent runs on {below}, one tier below the session's {current}"


def routed_message(route, model, requested):
    """Para onde o disparo foi, em que, e como escolher da próxima vez; o prefixo do hook é do chamador."""
    detail = [("model " + requested + " as asked") if requested
              else (route["row"].get("class") or model)]
    if route.get("effort"):
        detail.append(route["effort"] + " effort")
    shown = ", ".join(part for part in detail if part)
    return (f"unnamed subagent routed to {route['worker']}" + (f" ({shown})" if shown else "") +
            "; spawn worker-a, worker-b or worker-c to choose the band" +
            (" · the installed definition's effort is not the selected variant's; run "
             "`citizen sync` to apply the selected posture" if route.get("stale") else ""))


def emit(fields, system_message=None):
    fields["hookEventName"] = "PreToolUse"
    out = {"hookSpecificOutput": fields}
    if system_message:
        out["systemMessage"] = system_message
    print(json.dumps(out))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict) or payload.get("tool_name") != "Agent":
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    posture = posture_module()
    variant = posture.selected("delegation", DEFAULT_STANCE, strict=False) if posture else DEFAULT_STANCE
    if variant == "off":
        emit({
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Delegation is off; perform the work inline or change the selected stance. ({HOOK})",
        })
        return
    if variant != "tiered":
        return
    # Classe mais forte primeiro, a partir dos bindings do adaptador. Sem isso não há nível para
    # o qual mover um disparo, então a chamada roda como foi escrita e diz por quê, exatamente
    # como um modelo desconhecido faz.
    models = posture.tier_models() if posture and hasattr(posture, "tier_models") else {}
    ladder = list(models.values())
    if len(ladder) < 2:
        # Só uma chamada cujo modelo este hook teria decidido — um disparo nu, ou um pedindo uma
        # classe pelo nome — vale um aviso; um papel nomeado com seu próprio modelo não é deste hook.
        if is_bare(tool_input) or tool_input.get("model"):
            print(json.dumps({"systemMessage": f"{HOOK}: the adapter's class table names no tier to move a "
                              "spawn to, so this one runs as written; check the harness installation"}))
        return
    # Para onde vai um disparo que não nomeou nada, que só a tabela de custo conhece. Construída
    # aqui e só aqui, para que um disparo que nomeia um papel nunca leia um sidecar.
    route = notice = None
    if posture and is_unnamed(tool_input) and hasattr(posture, "row_for"):
        try:
            route, notice = band_route(posture, models, payload.get("cwd"), None,
                                       payload.get("session_id"), True,
                                       payload.get("transcript_path"))
        except Exception:
            # Um `posture.py` mais antigo ao lado de um hook mais novo não responde nada disso. A
            # decisão de roteamento inteira é uma única pergunta tudo-ou-nada, e a resposta segura
            # é o comportamento que este hook tinha antes de bandas existirem: não rotear, não
            # dizer nada sobre isso. Uma exceção escapando aqui alcança o coordenador, que nega o disparo.
            route = notice = None
    top = tier_of(tool_input.get("model"), ladder) == ladder[0]
    if top and not route:
        kind = tool_input.get("subagent_type")
        named = bool(kind) and kind != "general-purpose"
        declared = defined_tier(kind, payload.get("cwd"), ladder) if named else None
        if declared == ladder[0]:
            return  # o papel declara a classe mais alta por conta própria; o pedido só a repete
        updated = dict(tool_input, model=declared or ladder[1])
        emit({"updatedInput": updated},
             system_message=f"{HOOK}: {ladder[0]} is reached through a role that declares it, not by request; "
                            f"{kind if named else 'this spawn'} runs on {updated['model']}"
                            + (" · " + notice if notice else ""))
        return
    if route:
        log_route(payload, tool_input, route)
        updated = dict(tool_input, subagent_type=route["worker"])
        # Um pedido pela classe mais alta não é um modelo que este disparo nomeou: é um pedido que
        # o hook recusa, e recusá-lo rebaixando um nível deixaria um disparo sem nome superar uma
        # banda precificada abaixo daquele nível. Então a própria classe da banda decide,
        # exatamente como se nenhuma tivesse sido pedida.
        requested = None if top else tool_input.get("model")
        message = None
        if not requested:
            updated.pop("model", None)
            if route["model"]:
                updated["model"] = route["model"]
            else:
                # A banda não nomeia classe nenhuma que este adaptador mapeia, então o disparo
                # cai na regra de hoje.
                fallback, message = one_rung(payload, ladder)
                if fallback:
                    updated["model"] = fallback
        # Para onde vai um disparo sem nome é o arranjo permanente, dito uma vez por sessão. O
        # que o chamador pediu e não recebeu é dito toda vez que acontece.
        parts = []
        if notice_once(payload.get("session_id"), ROUTED_NOTICE):
            parts.append(routed_message(route, updated.get("model"), requested))
        if message:
            parts.append(message)
        if top:
            parts.append(f"{ladder[0]} is reached through a role that declares it, not by request")
        emit({"updatedInput": updated},
             system_message=(f"{HOOK}: " + " · ".join(parts)) if parts else None)
        return
    if not is_bare(tool_input):
        return
    below, message = one_rung(payload, ladder)
    if below is None:
        if message:
            print(json.dumps({"systemMessage": f"{HOOK}: {message}"
                              + (" · " + notice if notice else "")}))
        return
    updated = dict(tool_input, model=below)
    emit({"updatedInput": updated},
         system_message=f"{HOOK}: {message}" + (" · " + notice if notice else ""))


if __name__ == "__main__":
    main()
