"""A linha do ledger de uso que uma chamada de provedor deixa para trás: o que custou, e nada sobre o que perguntou.

Um provedor que sai da máquina gasta tokens e tempo de relógio, e ambos pertencem ao lado do
gasto de sessão que o ledger já guarda — um julgamento que custa dólares e nunca é precificado
lê como grátis, e uma chamada que soma um segundo a cada hook lê como uma máquina rápida. Então
cada chamada escreve uma linha `kind: "decision"` em `~/.local/state/agent-harness/usage.jsonl`
através do próprio escritor do ledger, e `harness usage --by provider` a precifica a partir de
`policy/prices.json` como qualquer outra linha. A escrita é um append sob o lock do ledger em vez
da reescrita que `upsert` faz: uma linha que nada jamais substitui não deve custar a um hook uma
leitura e reescrita do arquivo inteiro, e o lock é o que a impede de se entrelaçar com um registro
de sessão sendo atualizado.

O que a linha pode carregar é a mesma pergunta de allowlist que `controls.py` responde para a
rede, decidida da mesma forma: a linha é construída chave por chave a partir de uma lista fixa,
então um campo que ninguém nomeou não tem caminho de entrada. Ela guarda o ponto de decisão, o
modo, o status, os ids de modelo, os hashes do pacote e da requisição, as contagens de tokens e a
latência. Nunca guarda o estado que saiu, a prosa de uma resposta, um prompt, um caminho de
arquivo ou um valor de ambiente — `row()` não lê nenhum deles, e `test_jev_decision_rows.py`
garante que uma linha construída a partir de um contexto cheio deles não carrega nenhum.

Uma chamada cujo uso ninguém reportou é `partial`, que é como a tabela de preços já soletra
"desconhecido": uma linha sem preço é nomeada no rodapé do relatório, onde um zero teria dito que
o julgamento foi de graça.
"""
import hashlib
import os
import re
import time
from typing import Any, Dict, List, Optional

from .. import decision

KIND = "decision"
# Uma linha de decisão é escrita pelo próprio harness em vez de por uma sessão de cliente, então
# não nomeia runtime próprio. Presente porque `row_key` a lê em toda linha.
RUNTIME = "harness"

# As colunas de token nas quais toda linha do ledger é precificada. Uma resposta Jev reporta
# `input_tokens` e `output_tokens` e não há um terceiro campo no seu contrato de uso, então as
# duas colunas de cache são zero em vez de desconhecidas: nada foi servido de um cache porque
# nenhum cache foi oferecido.
CACHE_COLUMNS = ("cache_read", "cache_write")

_COUNTER = [0]


def _ident(request_hash: Optional[str], now: float) -> str:
    """Uma chave com a qual nenhuma chamada concorrente pode colidir.

    Duas requisições idênticas numa sessão hasheiam igual, e um `upsert` chaveado nesse hash
    manteria uma linha e descartaria a outra; o processo, o relógio e um contador fazem delas os
    dois registros separados que são.
    """
    _COUNTER[0] += 1
    seed = "|".join([str(request_hash or ""), str(os.getpid()), repr(now), str(_COUNTER[0])])
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


# A única forma de contraparte que uma linha pode manter literalmente: o slug que
# `decision.counterparty()` deriva. Ambas as metades são limitadas, porque uma linha é mantida
# por meses e um nome de branch não tem comprimento que ninguém imponha.
SLUG = re.compile(r"^repo:[A-Za-z0-9._-]{1,64}/[A-Za-z0-9._/-]{1,96}$")


def _counterparty(value: Any) -> str:
    """A contraparte como uma linha pode mantê-la: a forma de slug, ou um digest de qualquer outra coisa.

    `counterparty` é uma string de um chamador e parte do que sai na requisição, então um caminho
    absoluto pode chegar aqui — e um caminho nesta máquina é exatamente o que uma linha mantida
    por meses não deve guardar. Uma contraparte que este módulo não reconhece vira um digest
    curto, que ainda agrupa um relatório e não nomeia nada.
    """
    slug = str(value or "")
    if SLUG.match(slug):
        return slug
    return "sha256:" + hashlib.sha256(slug.encode("utf-8", "replace")).hexdigest()[:16]


def _repo(counterparty: str) -> str:
    """O nome do repositório dentro de um slug `repo:<name>/<branch>` mantido, ou o slug como foi mantido."""
    if not counterparty.startswith("repo:"):
        return counterparty
    return counterparty[len("repo:"):].split("/")[0]


def row(point: Optional[str], mode: str, result: Dict[str, Any], action_class: str,
        counterparty: str, session_id: str = "", now: Optional[float] = None,
        started: Optional[float] = None, judgment: Optional[str] = None,
        severity: Optional[str] = None, base_outcome: Optional[str] = None,
        advised_outcome: Optional[str] = None) -> Dict[str, Any]:
    """Uma linha `kind: "decision"`, construída campo por campo a partir de um resultado que `jev.ask` retornou.

    `started` é o próprio início da chamada, então uma linha cobre a requisição inteira em vez do
    instante em que terminou; sem ele, a latência do resultado é subtraída de `now`.

    Os quatro rótulos são os do log de decisão, repetidos aqui em vez de unidos entre dois
    arquivos: uma chamada precificada neste relatório vale a pena ser lida ao lado do que julgou
    e do que teria mudado, e uma linha `shadow` que não nomeasse nenhum dos dois não mediria
    nada. São rótulos de vocabulários fechados — uma escolha, um nível e dois resultados — e
    nunca a prosa de uma resposta.
    """
    now = time.time() if now is None else now
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else None
    latency = result.get("latency_ms")
    latency = float(latency) if isinstance(latency, (int, float)) else 0.0
    began = now - latency / 1000.0 if started is None else started
    kept = _counterparty(counterparty)
    record = {
        "kind": KIND, "runtime": RUNTIME, "provider": "jev",
        "session_id": str(session_id or ""),
        "agent_id": _ident(result.get("request_hash"), now),
        "repo": _repo(kept), "counterparty": kept,
        "action_class": str(action_class or ""),
        "point": str(point) if point else None,
        "mode": str(mode or ""),
        "status": str(result.get("status") or ""),
        "judgment": judgment, "severity": severity,
        "base_outcome": base_outcome, "advised_outcome": advised_outcome,
        "error": result.get("error") if isinstance(result.get("error"), str) else None,
        "requested_model": result.get("requested_model") or "",
        "model": result.get("model") or "",
        "pack_hash": result.get("pack_hash"), "request_hash": result.get("request_hash"),
        "ms": round(latency, 3),
        "harness_version": _version(),
        "started": _stamp(began), "ended": _stamp(now),
    }
    if usage is None:
        # Nenhum uso significa nenhuma conta que alguém consiga calcular. `partial` é o que a
        # tabela de preços já lê como desconhecido, então a linha é contada como sem preço em
        # vez de zero dólares.
        record["partial"] = True
        record["input"] = None
        record["output"] = None
        for name in CACHE_COLUMNS:
            record[name] = None
        return record
    record["input"] = _count(usage.get("input_tokens"))
    record["output"] = _count(usage.get("output_tokens"))
    for name in CACHE_COLUMNS:
        record[name] = 0
    if record["input"] is None or record["output"] is None:
        record["partial"] = True
    return record


def _count(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _stamp(epoch: float) -> str:
    module = decision._hook_module("usage-log")
    if module is None:
        return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(epoch))
    return module.stamp(epoch)


def _version() -> Optional[str]:
    module = decision._hook_module("usage-log")
    try:
        return module.harness_version() if module is not None else None
    except Exception:
        return None


def append(record: Dict[str, Any], target: Optional[str] = None) -> bool:
    """Escreve uma linha de decisão no ledger de uso. Nunca levanta exceção; diz se escreveu.

    Suprimida com `decision.events_suppressed`, e totalmente desligada quando `telemetry.decisions`
    está off: um usuário que desligou o log do provedor não pediu a mesma chamada num segundo
    arquivo. Uma escrita que falha custa o registro e nada mais — uma decisão nunca deve depender
    de um ledger, a regra que `append_event` já segue.
    """
    if decision.suppressed():
        return False
    usage = decision._hook_module("usage-log")
    decisions = decision._ledger()
    if usage is None or decisions is None:
        return False
    try:
        if not decisions.enabled():
            return False
        usage.append_row(record, path=target)
        return True
    except Exception as exc:
        # Uma escrita engolida é desconhecida, não ausente: a falha cai no arquivo de erros que
        # todo outro escritor de ledger usa, então uma sequência de relatórios vazios tem onde
        # ser explicada.
        try:
            usage.record_error(exc, path=target, where="decision-row")
        except Exception:
            pass
        return False


def rows(path=None) -> List[Dict[str, Any]]:
    """Toda linha de decisão no ledger de uso, mais antiga primeiro. Um arquivo ilegível é nenhuma linha."""
    module = decision._hook_module("usage-log")
    if module is None:
        return []
    try:
        location = module.usage_path() if path is None else path
        with open(str(location), encoding="utf-8") as stream:
            text = stream.read()
    except (OSError, AttributeError):
        return []
    # O próprio leitor do ledger, então um campo renomeado é dobrado aqui como é em todo lugar.
    return [row for row in module.ledger_rows(text) if row.get("kind") == KIND]
