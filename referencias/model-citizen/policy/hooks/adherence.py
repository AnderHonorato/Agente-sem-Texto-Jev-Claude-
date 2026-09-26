#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Eventos de aderência: cada recomendação que um hook emite, e se o usuário a seguiu (AD-23).

`~/.local/state/agent-harness/adherence.jsonl`, ao lado de `observation.jsonl`. Dois tipos de
linha, unidos por `adherence_id` do jeito que o log de decisão une uma decisão ao seu resultado,
e nunca reescritos:

    {"kind": "emitted", "adherence_id": "…", "recommendation": "fresh-session",
     "module": "hooks/usage-feed", "session_id": "…", "turn": 7, "ts": "…",
     "profile_fingerprint": "…", "schema_version": 1}
    {"kind": "response", "adherence_id": "…", "recommendation": "fresh-session",
     "module": "hooks/usage-feed", "session_id": "…", "turn": 7, "outcome": "followed",
     "reason": "SessionEnd", "turns_after": 1, "window": 3, "ts": "…",
     "profile_fingerprint": "…", "schema_version": 1}

Aderência é observação, então a saída de um hook emissor é a mesma com o registro ligado,
desligado ou falhando: `emit` não retorna nada que um chamador pudesse imprimir e engole todo
erro. Nenhuma linha guarda um prompt, uma entrada de ferramenta, um resultado de ferramenta ou o
próprio texto da recomendação, então a taxa por recomendação é calculada só a partir de
identificadores.

**Se uma recomendação foi seguida é lido do ledger de observação**, a linha só-de-identificador
por evento de hook que `harness_core.observer` escreve. `turn` é a contagem do hook emissor dos
prompts da sessão, e a resposta olha as linhas de observação da sessão depois do seu
`turn`-ésimo `UserPromptSubmit`, ou depois do último carimbado não mais tarde que a emissão
quando isso está mais à frente. Seguida: um dos eventos `follow` da recomendação chega antes que
a janela de `window` prompts adicionais tenha passado. Não seguida: o prompt `turn + window + 1`
da sessão chega primeiro. Desconhecida: nenhum dos dois pode ainda ser lido. Uma emissão só é
respondida `unknown` definitivamente quando tem `UNKNOWN_AFTER` de idade, com `reason` dizendo
por quê: `unobserved` quando o ledger não guarda linha nenhuma para seu turno, que é toda
emissão até o ponto de entrada de observação ser registrado em sessões reais, e `window_open` nos demais casos.

Este módulo fica ao lado dos hooks em vez de em `lib/harness_core` pela razão que `decisions.py`
dá: um hook é alcançado através de `~/.claude/hooks/harness` e nada acima disso resolve.
"""
import datetime
import importlib.util
import json
import os
import uuid
from pathlib import Path

SCHEMA_KEY = "schema_version"
SCHEMA_VERSION = 1
FINGERPRINT_KEY = "profile_fingerprint"
LEDGER = "adherence.jsonl"
OBSERVATION = "observation.jsonl"
OUTCOMES = ("followed", "not_followed", "unknown")
PROMPT = "UserPromptSubmit"
# Uma emissão que nenhum dos resultados alcançou num dia não vai mais ser lida: uma sessão ociosa
# por tanto tempo foi abandonada, e o ledger que diria isso ou não foi escrito ou está incompleto.
UNKNOWN_AFTER = 86400

# Toda recomendação que um hook emite, o `hooks/<id>` que a emite, os prompts após o emissor
# dentro dos quais agir sobre ela conta, e os eventos de observação que contam como ação. Um tipo
# não nomeado aqui nunca é registrado, então um erro de digitação num ponto de chamada não escreve nada.
KINDS = {
    # "Termine a tarefa, escreva a passagem de bastão, comece uma sessão nova": terminar e a
    # passagem de bastão são um turno ou dois cada, então a sessão tem mais três prompts para
    # encerrar. `/clear` e uma saída disparam SessionEnd; uma compactação não, e continuar
    # compactado não é seguir.
    "fresh-session": {"module": "hooks/usage-feed", "window": 3, "follow": ("SessionEnd",)},
}

_POSTURE = []


def home(env=None):
    env = os.environ if env is None else env
    return Path(env.get("HARNESS_HOME") or env.get("HOME") or Path.home())


def state_dir(env=None):
    return home(env) / ".local" / "state" / "agent-harness"


def path(env=None):
    return state_dir(env) / LEDGER


def observation_path(env=None):
    return state_dir(env) / OBSERVATION


def now_ts(now=None):
    moment = (datetime.datetime.now(datetime.timezone.utc) if now is None
              else datetime.datetime.fromtimestamp(now, datetime.timezone.utc))
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value):
    """Segundos de epoch para o `ts` de uma linha, ou None para um que não consegue ler."""
    try:
        moment = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None
    return moment.replace(tzinfo=datetime.timezone.utc).timestamp()


def profile_fingerprint():
    """O perfil em vigor, a partir do `posture.py` ao lado deste arquivo, ou None; veja `decisions.py`."""
    if not _POSTURE:
        location = Path(os.path.realpath(__file__)).parent / "posture.py"
        try:
            spec = importlib.util.spec_from_file_location("harness_adherence_posture", str(location))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            module = None
        _POSTURE.append(module)
    try:
        return _POSTURE[0].fingerprint() if _POSTURE[0] else None
    except Exception:
        return None


def whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _append(row, target):
    """Uma linha, um `write`, para um arquivo que só seu dono consegue ler."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(target), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (json.dumps(row, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        os.close(fd)


def emission(recommendation, session_id, turn, now=None):
    """A linha `emitted` para uma recomendação, ou None para um tipo ou id que isto não consegue registrar."""
    spec = KINDS.get(recommendation)
    if spec is None or not isinstance(session_id, str) or not session_id:
        return None
    if not whole(turn) or turn < 1:
        return None
    return {"kind": "emitted", "adherence_id": uuid.uuid4().hex, "recommendation": recommendation,
            "module": spec["module"], "session_id": session_id, "turn": turn, "ts": now_ts(now),
            FINGERPRINT_KEY: profile_fingerprint(), SCHEMA_KEY: SCHEMA_VERSION}


def emit(recommendation, session_id, turn, env=None, now=None):
    """Registra que um hook emitiu `recommendation` no prompt `turn` da sessão.

    Retorna None em todo caminho, e nunca levanta exceção: a saída do hook emissor não deve
    depender de isso ter funcionado.
    """
    try:
        row = emission(recommendation, session_id, turn, now)
        if row is not None:
            _append(row, path(env))
    except Exception:
        pass


def read_rows(target):
    """Toda linha-objeto num arquivo JSONL, em ordem; um arquivo ausente ou uma linha rasgada é pulada."""
    try:
        with open(str(target), "rb") as handle:
            raw = handle.read()
    except OSError:
        return []
    rows = []
    for line in raw.splitlines():
        try:
            row = json.loads(line.decode("utf-8", "replace"))
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def prompts_by(ts, session, observed):
    """Os prompts observados da sessão carimbados não mais tarde que `ts`, ou 0 quando `ts` é ilegível.

    A própria contagem do feed pode ficar atrás da do ledger, quando ele pula um prompt que não
    conseguiu travar ou reseta um arquivo de estado que não conseguiu ler, e um turno atrasado
    fecharia a janela cedo demais. O próximo prompt não pode chegar antes de o hook do emissor
    ter rodado, então nenhum é contado aqui.
    """
    moment = parse_ts(ts)
    if moment is None:
        return 0
    count = 0
    for item in observed:
        if item.get("session_id") == session and item.get("event") == PROMPT:
            stamped = parse_ts(item.get("ts"))
            if stamped is not None and stamped <= moment:
                count += 1
    return count


def respond(row, observed):
    """`(outcome, reason, turns_after)` para uma emissão contra as linhas de observação da sessão.

    `observed` são as linhas do ledger de observação na ordem do arquivo; só `event`,
    `session_id` e `ts` são lidos. `turns_after` conta os prompts vistos após o emissor, limitado
    pela janela.
    """
    spec = KINDS.get(row.get("recommendation"))
    turn, session = row.get("turn"), row.get("session_id")
    if spec is None or not whole(turn) or turn < 1 or not isinstance(session, str):
        return "unknown", "unrecognised", 0
    turn = max(turn, prompts_by(row.get("ts"), session, observed))
    prompts = 0
    for item in observed:
        if item.get("session_id") != session:
            continue
        event = item.get("event")
        if event == PROMPT:
            prompts += 1
            if prompts > turn + spec["window"]:
                return "not_followed", PROMPT, spec["window"]
        elif prompts >= turn and event in spec["follow"]:
            return "followed", event, prompts - turn
    if prompts < turn:
        return "unknown", "unobserved", 0
    return "unknown", "window_open", prompts - turn


def responses(rows):
    """A primeira resposta a cada emissão, por `adherence_id`. Uma segunda é uma duplicata."""
    out = {}
    for row in rows:
        if row.get("kind") == "response" and isinstance(row.get("adherence_id"), str):
            out.setdefault(row["adherence_id"], row)
    return out


def settle(env=None, now=None):
    """Acrescenta uma resposta para toda emissão que uma leitura já consegue responder, e retorna essas linhas.

    Uma leitura seguida ou não seguida é final quando é feita. Uma desconhecida só é escrita
    quando a emissão tem `UNKNOWN_AFTER` de idade; antes disso é deixada para uma leitura posterior.
    """
    now = datetime.datetime.now(datetime.timezone.utc).timestamp() if now is None else now
    rows = read_rows(path(env))
    answered = responses(rows)
    observed = read_rows(observation_path(env))
    written = []
    for row in rows:
        ident = row.get("adherence_id")
        if row.get("kind") != "emitted" or not isinstance(ident, str) or ident in answered:
            continue
        outcome, reason, after = respond(row, observed)
        if outcome == "unknown":
            emitted_at = parse_ts(row.get("ts"))
            if emitted_at is not None and now - emitted_at < UNKNOWN_AFTER:
                continue
        spec = KINDS.get(row.get("recommendation")) or {}
        answer = {"kind": "response", "adherence_id": ident,
                  "recommendation": row.get("recommendation"), "module": row.get("module"),
                  "session_id": row.get("session_id"), "turn": row.get("turn"),
                  "outcome": outcome, "reason": reason, "turns_after": after,
                  "window": spec.get("window"), "ts": now_ts(now),
                  FINGERPRINT_KEY: row.get(FINGERPRINT_KEY), SCHEMA_KEY: SCHEMA_VERSION}
        _append(answer, path(env))
        answered[ident] = answer
        written.append(answer)
    return written


def rates(rows):
    """Por recomendação: emitidas, cada resultado, pendentes, e a taxa seguida das já julgadas.

    `rate` é seguida sobre seguida mais não seguida, e None enquanto nenhuma das duas aconteceu:
    uma desconhecida não é nenhuma das duas, e contá-la como qualquer uma delas inventaria uma
    resposta que o ledger nunca deu.
    """
    answered = responses(rows)
    out = {}
    for row in rows:
        if row.get("kind") != "emitted" or not isinstance(row.get("adherence_id"), str):
            continue
        entry = out.setdefault(row.get("recommendation"), dict(
            {"emitted": 0, "pending": 0, "rate": None}, **{name: 0 for name in OUTCOMES}))
        entry["emitted"] += 1
        answer = answered.get(row["adherence_id"])
        outcome = answer.get("outcome") if answer else None
        if outcome in OUTCOMES:
            entry[outcome] += 1
        else:
            entry["pending"] += 1
    for entry in out.values():
        judged = entry["followed"] + entry["not_followed"]
        entry["rate"] = entry["followed"] / float(judged) if judged else None
    return out
