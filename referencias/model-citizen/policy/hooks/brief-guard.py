#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""PreToolUse em `Agent`: acrescenta um limite de retorno, e o orçamento leve da postura, a um brief
que não declara nenhum dos dois.

`delegation.md` diz para limitar o brief, e `transcript-hygiene/model-wrote-no-cap` mede que não
é o caso: 536 ocorrências em 30 por cento das sessões. Pedir ao orquestrador para escrever o
teto não funciona, então o hook o escreve em vez disso.

Aquele detector conta briefs como o modelo os escreveu, e continua os contando depois que este
hook os limita: um transcript registra a entrada `tool_use` do modelo, não o `updatedInput` que
este hook retorna (#324). Seu número diz se o orquestrador ainda precisa do hook, e não é
evidência de que um brief sem teto alcançou um subagente.

Adaptado de unclebob/swarm-forge, cujo auxiliar de passagem de bastão preenche o SHA do commit a
partir do HEAD do remetente enquanto a constituição diz "não digite um SHA". O agente não
consegue errar um campo que nunca escreve.

O que conta como um limite, e quais agentes são isentos, vêm de `rule-detectors.py` em vez de
uma segunda cópia aqui, para que o hook acrescente um teto exatamente aos briefs que o detector
conta. Uma segunda cópia divergiria, e as duas então discordariam sobre quais briefs o
orquestrador limitou — o hook acrescentando a um brief que já declara um teto, ou deixando um que
o detector conta.

O orçamento é o mesmo argumento para o gasto. Um subagente não consegue ver a variante de custo
que o precificou, então os tokens de saída e chamadas de ferramenta esperados da linha são
declarados no brief, uma vez, na redação que `posture.py` fixa para todo brief que o harness
escreve, incluindo o de um worker de papel isolado. Uma linha sem orçamentos, uma tabela que não
constrói, e um brief que já se precifica sozinho significam todos nenhuma frase, que é o que
mantém uma variante nula byte-idêntica.

Um disparo que nomeou um papel é precificado em todo runtime. Um disparo que não nomeou nenhum é
precificado pelo band worker para o qual está prestes a ser roteado, então só é precificado onde
esse reroteamento acontece — Claude Code, cujo hook reescreve `subagent_type`. Em qualquer outro
runtime nada roteia tal disparo, e um orçamento nomeando uma banda em que não vai rodar é pior
que nenhum.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

HOOK = "harness:brief-guard"
HOOKS = Path(__file__).resolve().parent
# O runtime cujo hook de disparo reroteia um disparo sem nome para um band worker. O coordenador
# define `HARNESS_RUNTIME`; um hook rodado à mão não tem coordenador e é este.
ROUTING_RUNTIME = "claude-code"

# Escrito para combinar com o próprio padrão de teto do detector; um limite que o detector não
# consegue ver não é um limite. `tests/test_brief_guard.py` garante essa paridade.
BOUND = ("\n\nReturn at most 400 words: the result in your first sentence, then only the findings "
         "that change a decision, in plain sentences or short bullets with no section labels. "
         "Write anything longer to a file and return its path, not its contents.")
CAP_NOTE = "the brief stated no return bound, so a 400-word cap was added"
# A frase de orçamento não carrega aviso próprio algum. Declarar o gasto da variante é o que este
# hook faz em quase todo disparo, e um alerta no caso comum é ruído que um leitor aprende a
# ignorar; o teto mantém seu aviso porque um brief que não declara limite é a exceção.
#
# Sua redação, e o que conta como um brief que já se precifica sozinho, são de `posture.py`:
# `budget_sentence` e `budget_stated`: o brief de um worker de papel isolado carrega a mesma
# frase, e duas cópias dela divergiriam.


def sibling(name):
    """Um módulo ao lado deste hook, ou None. Um hook nunca deve bloquear um disparo porque um import falhou."""
    try:
        spec = importlib.util.spec_from_file_location(
            "harness_" + name.replace("-", "_"), str(HOOKS / (name + ".py")))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def detectors():
    """O módulo detector, ou None."""
    return sibling("rule-detectors")


def stance():
    """A stance `delegation` selecionada, resolvida por `posture.py` para todo hook igualmente."""
    module = sibling("posture")
    return module.selected("delegation", "tiered", strict=False) if module else "tiered"


def needs_bound(module, tool_input):
    """True quando este brief não carrega teto e a própria definição do agente também não carrega nenhum."""
    kind = tool_input.get("subagent_type")
    if isinstance(kind, str) and kind.strip() in module.CAPPED_AGENTS:
        return False
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return False
    return not module.WORD_CAP_RE.search(prompt)


def effective_role(payload, tool_input, posture, router, table, variant):
    """O papel cuja linha precifica este disparo, ou None quando nada o precifica.

    Um disparo que nomeou uma definição é precificado por aquele papel. Um disparo que não nomeou
    nenhum é precificado pelo band worker para o qual está prestes a ser roteado — o que este
    hook não consegue ler do evento, porque o coordenador entrega aos dois hooks a chamada
    original e não a reescrita um do outro. Então a rota é computada chamando o próprio
    `band_route` de `tier-agent-spawns`, sobre a única tabela que `table()` constrói: uma segunda
    resposta para "para onde vai um disparo sem nome", ou uma segunda tabela, mais cedo ou mais
    tarde precificaria a banda errada. Quais disparos contam como sem nome também é o predicado
    daquele hook, então um `subagent_type` de espaço em branco não pode ser precificado aqui e
    roteado a lugar nenhum.

    Um disparo que nada roteia — outro runtime, nenhuma banda padrão, um worker não instalado ou
    fora do registro desta sessão, um repositório que traz o seu próprio, uma stance de
    delegação que não é `tiered` — não é precificado por nada, como era antes.
    """
    if router is None:
        return None
    if not router.is_unnamed(tool_input):
        return tool_input.get("subagent_type")
    if variant != "tiered" or os.environ.get("HARNESS_RUNTIME", ROUTING_RUNTIME) != ROUTING_RUNTIME:
        return None
    models = posture.tier_models()
    if len(models) < 2:
        return None
    route, _ = router.band_route(posture, models, payload.get("cwd"), table(),
                                 payload.get("session_id"),
                                 transcript=payload.get("transcript_path"))
    return route["worker"] if route else None


def budget_for(payload, tool_input, module, variant):
    """A frase de orçamento que este brief está sem, ou None. Nunca levanta exceção: um disparo tem prioridade sobre uma linha.

    A tabela de custo é lida aqui e em nenhum outro lugar deste hook, no máximo uma vez, e nunca
    para um disparo que nada precificaria: uma tabela é uma varredura de todo sidecar na cadeia
    `extends`, e este hook roda numa chamada de ferramenta. Qualquer falha ao construí-la é
    simplesmente nenhuma frase — assim como qualquer falha ao perguntar para onde o disparo vai,
    incluindo um `posture.py` mais antigo ao lado de um hook de disparo mais novo, cujas funções
    ausentes de outra forma levantariam exceção no coordenador e negariam a chamada.
    """
    posture, router = sibling("posture"), sibling("tier-agent-spawns")
    if posture is None or router is None or not hasattr(posture, "budget_stated"):
        return None
    if posture.budget_stated(tool_input.get("prompt"), module):
        return None
    built = []

    def table():
        if not built:
            built.append(posture.cost_table())
        return built[0]

    try:
        role = effective_role(payload, tool_input, posture, router, table, variant)
        if not role:
            return None
        return posture.budget_sentence(posture.row_for(table(), role))
    except Exception:
        return None


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
    variant = stance()
    if variant == "off":
        # O ciclo de vida já nega todo disparo aqui; um segundo hook acrescentando um brief a um
        # evento que já é recusado de qualquer forma é ruído.
        return
    module = detectors()
    prompt = tool_input.get("prompt")
    if module is None or not isinstance(prompt, str) or not prompt.strip():
        return
    # O limite primeiro e o orçamento depois dele, para que um brief sem os dois se leia como a
    # forma do retorno e depois o que pode gastar para chegar lá.
    added, notes = "", []
    if needs_bound(module, tool_input):
        added, notes = BOUND, [CAP_NOTE]
    budget = budget_for(payload, tool_input, module, variant)
    if budget:
        added += budget
    if not added:
        return
    # O que este hook escreveu no brief, contra o brief que recebeu. Veja `decisions.py`.
    log = sibling("decisions")
    if log is not None:
        log.record("brief-guard", "cap+budget" if notes and budget else ("cap" if notes else "budget"),
                   prompt, payload)
    updated = dict(tool_input)
    updated["prompt"] = prompt.rstrip() + added
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": updated}}
    if notes:
        out["systemMessage"] = f"{HOOK}: " + " · ".join(notes)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
