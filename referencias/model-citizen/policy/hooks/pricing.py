#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Preços de lista para linhas de ledger: o único caminho de código que `harness usage` e o
exportador usam.

A cifra em dólar que um relatório imprime e a cifra em dólar que uma linha exportada carrega
precisam ser o mesmo número, então as taxas, a normalização de id e a junção sessão/subagente
vivem aqui e são chamadas de ambos os lados em vez de implementadas duas vezes.

Este módulo fica ao lado de `usage-log.py` pela razão que `telemetry.py` também fica: o hook
também é um script standalone alcançado através de `~/.claude/hooks/harness`, a partir do qual
nada acima do diretório de hooks resolve. `bin/harness` o carrega do jeito que carrega os
detectores, e os dois pontos de entrada caem no mesmo `policy/prices.json` — a CLI a partir da
raiz do seu checkout, este módulo a partir do seu próprio caminho real, que segue o symlink
`claude/hooks -> ../policy/hooks` de volta ao checkout.

Nada aqui levanta exceção por um preço que não consegue encontrar: uma linha sem preço é `None`,
nunca zero. Uma cifra subestimada é pior que uma ausente, porque nada na linha diz que está incompleta.
"""
import json
import os
import re
import time
from pathlib import Path

# As quatro colunas que toda entrada precisa carregar para precificar qualquer coisa; uma taxa
# que falta uma delas deixa o modelo sem preço em vez de cobrar a parte que conhece.
RATE_FIELDS = ("input", "output", "cache_read", "cache_write")
TOKEN_TIERS = ("cache_write_5m", "cache_write_1h")
# Um preço lido um trimestre atrás é um chute. `doctor` diz isso em vez de um relatório derivar silenciosamente.
PRICE_STALE_DAYS = 90
# Um sufixo de lançamento nomeia quando um modelo foi lançado, não qual modelo é: um carimbo de
# data, ou uma tag de versão de um revendedor de nuvem. Só esses são removidos a caminho de uma
# chave de tabela. Uma palavra depois do nome da família — `-pro`, `-mini` — é um modelo
# diferente a um preço diferente e permanece.
RELEASE_SUFFIX = re.compile(r"(?:[-@](?:20\d{6}|20\d{2}-\d{2}-\d{2})|-v\d+(?::\d+)?)$")


def prices_path():
    """`policy/prices.json` no checkout em que este arquivo de fato vive.

    Resolvido a partir do caminho real para que o hook, alcançado através de dois symlinks, leia
    o mesmo arquivo que a CLI lê a partir da raiz do seu checkout.
    """
    return Path(os.path.realpath(__file__)).parent.parent / "prices.json"


def shipped_prices(path=None):
    """O arquivo de preços como está escrito, ou uma tabela vazia quando está ausente ou ilegível.

    Um arquivo de preços quebrado custa ao relatório sua coluna de dólares e nada mais: `usage`
    ainda conta tokens, que é o que fazia antes de preços existirem.
    """
    try:
        with open(str(prices_path() if path is None else path), encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        return {}
    models = data.get("models") if isinstance(data, dict) else None
    return models if isinstance(models, dict) else {}


def load_prices(cfg, path=None):
    """A tabela embutida com o bloco `prices` do usuário mesclado por cima, campo por campo.

    Mesclado por id de modelo em vez de por atacado, para que um override que nomeia uma taxa
    mantenha o `as_of` e `source` embutidos para o resto da entrada e um modelo novo possa ser
    adicionado por completo. Os ids são normalizados dos dois lados, então um override escrito
    em caixa mista, com um prefixo de revendedor ou com um sufixo de janela de contexto ainda
    alcança a entrada que pretende substituir.
    """
    table = dict((normalise_model(key), value) for key, value in shipped_prices(path).items()
                 if isinstance(value, dict))
    overrides = cfg.get("prices") if isinstance(cfg, dict) and isinstance(cfg.get("prices"), dict) else {}
    for key, value in overrides.items():
        if not isinstance(value, dict):
            continue
        name = normalise_model(key)
        merged = dict(table.get(name) or {})
        merged.update(value)
        table[name] = merged
    return table


def normalise_model(model):
    """Uma grafia de id de modelo: minúsculas, sem prefixo de fornecedor, sem sufixo de janela ou lançamento.

    Um ledger guarda o id que cada runtime reportou, e o mesmo modelo chega de várias formas: nu,
    como `<vendor>.<family>-<date>-v1:0` num revendedor de nuvem, como `<family>@<date>` em outro,
    e com um sufixo de janela de contexto entre colchetes numa sessão de contexto longo. O sufixo
    de janela é removido porque o provedor precifica a janela maior à taxa padrão, e o sufixo de
    lançamento porque um carimbo de data nomeia quando um modelo foi lançado em vez de qual
    modelo é. O que sobra é comparado exatamente, nunca por prefixo: veja `price_key`. Nenhum
    nome de modelo é escrito aqui: `policy/prices.json` guarda os ids.
    """
    name = (model or "").strip().lower()
    name = re.sub(r"\[[^\]]*\]", "", name).split("/")[-1]
    while True:
        head, dot, rest = name.partition(".")
        if not (dot and rest and head.isalpha()):
            break
        name = rest
    while True:
        trimmed = RELEASE_SUFFIX.sub("", name)
        if trimmed == name:
            break
        name = trimmed
    return name.strip("-").strip()


def usable_rate(entry):
    """As quatro taxas de uma entrada como floats, ou None quando alguma está ausente ou não é um número."""
    if not isinstance(entry, dict):
        return None
    rate = {}
    for field in RATE_FIELDS + TOKEN_TIERS:
        value = entry.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            if field in RATE_FIELDS:
                return None
            continue
        rate[field] = float(value)
    return rate


def price_key(table, model):
    """A chave de tabela que governa um id de modelo: sua forma normalizada, listada exatamente, ou "".

    Nada resolve por prefixo. Uma variante de uma família listada é um modelo diferente a um
    preço diferente — `gpt-5.5-pro` é $30/$180 onde `gpt-5.5` é $5/$30 — então um id que a
    tabela não nomeia fica sem preço em vez de ser cobrado pelo parente listado mais próximo.
    Para precificar um, adicione-o a `policy/prices.json` ou o sobreponha sob `prices` em
    `config.json`.
    """
    name = normalise_model(model)
    return name if name in table else ""


def price_for(table, model):
    """A taxa que governa um id de modelo, ou None quando nenhuma entrada carrega uma utilizável."""
    key = price_key(table, model)
    return usable_rate(table.get(key)) if key else None


def row_tokens(row, rate=None):
    """As quatro contagens de token de uma linha, ou None quando a linha não pode ser precificada por elas.

    Uma linha marcada `partial` — um transcript lido até um orçamento, ou um snapshot do Codex
    carregando só um total — fica sem preço, nunca precificada pelo que era legível: uma cifra em
    dólar subestimada é pior que uma ausente, porque nada na linha diz que está incompleta.

    Uma contagem não reportada contra uma taxa de zero é lida como zero em vez de desconhecida,
    porque não pode mudar a conta de qualquer forma. É isso que torna uma linha do Codex
    precificável: seu rollout não nomeia cifra de escrita em cache nenhuma, e a OpenAI não cobra
    nada por uma.
    """
    if row.get("partial"):
        return None
    tokens = {}
    for name in RATE_FIELDS:
        value = row.get(name)
        if value is None and rate is not None and not rate.get(name):
            value = 0
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        tokens[name] = max(value, 0)
    for name in TOKEN_TIERS:
        value = row.get(name)
        if not isinstance(value, bool) and isinstance(value, int):
            tokens[name] = max(value, 0)
    return tokens


def tokens_cost(tokens, rate):
    """USD para um conjunto de contagens de token a uma taxa.

    Escritas em cache são cobradas nível por nível só quando os níveis da linha somam o total de
    escrita em cache dela: uma linha que não reporta divisão, ou cuja divisão discorda do seu
    total, é cobrada inteira em `cache_write`. Checar a soma em vez da presença das chaves
    significa que uma linha cujos níveis são ambos zero porque o runtime não reportou nenhum não
    é lida como escritas na taxa de 5 minutos.
    """
    total = (tokens["input"] * rate["input"] + tokens["output"] * rate["output"]
             + tokens["cache_read"] * rate["cache_read"])
    write = tokens["cache_write"]
    tiers = dict((name, tokens.get(name) or 0) for name in TOKEN_TIERS)
    if write and sum(tiers.values()) == write:
        for name in TOKEN_TIERS:
            total += tiers[name] * rate.get(name, rate["cache_write"])
    else:
        total += write * rate["cache_write"]
    return total / 1000000


def breakdown_cost(row, table):
    """USD para uma linha a partir do seu detalhamento por modelo, ou None quando o mapa não consegue carregar isso.

    As maiores sessões são as que trocaram de modelo, e seus totais sozinhos nomeiam várias taxas
    e nenhuma divisão entre elas. `usage-log.py` registra a divisão como `by_model`, checada
    contra os próprios totais da linha antes de ser escrita, então isto é uma soma de partes e
    não uma alocação. Qualquer parte que não possa ser precificada deixa a linha inteira sem preço.

    Uma parte nomeada por um turno gerado pelo harness — `<synthetic>`, e qualquer outra coisa
    que o transcript coloca entre colchetes — não é um modelo e não tem taxa. É pulada quando não
    gastou nada, que é o único caso em que os modelos reais ainda contabilizam todo token.
    """
    parts = row.get("by_model")
    if not isinstance(parts, dict) or not parts:
        return None
    total = 0.0
    for name, part in parts.items():
        if not isinstance(name, str) or not isinstance(part, dict):
            return None
        if name.startswith("<"):
            if any(part.get(field) for field in RATE_FIELDS):
                return None
            continue
        rate = price_for(table, name)
        if rate is None:
            return None
        tokens = row_tokens(dict(part, partial=row.get("partial")), rate)
        if tokens is None:
            return None
        total += tokens_cost(tokens, rate)
    return total


def row_model(row, excluded=None):
    """O único modelo em que os tokens de uma linha foram gastos, ou None quando a linha nomeia vários.

    Uma linha de sessão nomeia todo modelo em que rodou e carrega um único conjunto de totais,
    então uma sessão que trocou de modelo no meio do caminho não pode ser dividida e fica sem
    preço. Os modelos dos seus subagentes são retirados da lista primeiro, já que os tokens deles
    estão sendo precificados separadamente — a menos que isso a esvaziasse, que é a sessão que
    rodou o mesmo modelo que seu subagente.
    """
    models = [m for m in (row.get("models") or []) if isinstance(m, str) and m]
    if excluded:
        models = [m for m in models if normalise_model(m) not in excluded] or models
    if not models and isinstance(row.get("model"), str) and row["model"]:
        models = [row["model"]]
    return models[0] if len(models) == 1 else None


def row_cost(row, table, children=None):
    """USD para uma linha de ledger, ou None quando não pode ser precificada.

    Uma linha que carrega um detalhamento por modelo é precificada a partir dele e de mais nada,
    que é a única forma de uma sessão que trocou de modelo poder ser precificada de algum jeito;
    veja `breakdown_cost`. O que segue é para as linhas escritas antes de aquele mapa existir.

    Os totais de uma sessão do Claude Code já incluem os dos seus subagentes, que rodaram em
    seus próprios modelos às suas próprias taxas — a sessão oracle precificada nos testes gastou
    85% dos seus dólares em escritas de cache de 1 hora à taxa do pai e o resto em escritas de 5
    minutos de um subagente a outra taxa. Então os tokens dos filhos saem dos totais do pai, cada
    filho é precificado no seu próprio modelo, e os dois são somados. Um filho que não pode ser
    precificado deixa a sessão inteira sem preço, porque o restante sozinho seria lido como a
    conta da sessão.

    Uma linha cujos totais não cobrem seus filhos — uma linha antiga escrita antes de tokens de
    subagente serem capturados — é precificada sozinha, exatamente como seus tokens são
    reportados sozinhos. A cobertura é decidida pelas contagens, antes de qualquer coisa ser
    precificada, então um filho impreçável não transforma um pai que nunca guardou seus tokens
    numa linha sem preço.
    """
    if row.get("partial"):
        return None
    # Um detalhamento é a conta inteira: para o Claude Code é recortado do mesmo mapa sobre o
    # qual os totais são somados, registros de subagente incluídos, então nada é somado a ele.
    direct = breakdown_cost(row, table)
    if direct is not None:
        return direct
    joined = None
    child_cost = 0.0
    excluded = set()
    base = row_tokens(row) if children else None
    parts = [row_tokens(child) for child in children or []]
    if base is not None and all(part is not None for part in parts) \
            and all(base[name] >= sum(part[name] for part in parts) for name in RATE_FIELDS):
        joined = dict(base)
        for part in parts:
            for name in RATE_FIELDS + TOKEN_TIERS:
                if name in joined and name in part:
                    joined[name] = max(joined[name] - part[name], 0)
        for child in children or []:
            cost = row_cost(child, table)
            if cost is None:
                return None
            child_cost += cost
        excluded = set(normalise_model(c.get("model") or "") for c in children or [])
    rate = price_for(table, row_model(row, excluded) or "")
    if rate is None:
        return None
    tokens = joined if joined is not None else row_tokens(row, rate)
    if tokens is None:
        return None
    return tokens_cost(tokens, rate) + child_cost


def session_children(rows):
    """Linhas de subagente do Claude Code chaveadas pela sessão cujos totais já guardam seus tokens."""
    children = {}
    for row in rows:
        if row.get("kind") == "subagent" and row.get("runtime") != "codex" and row.get("session_id"):
            children.setdefault(row["session_id"], []).append(row)
    return children


def row_children(row, children):
    """As linhas de subagente que pertencem dentro da conta desta linha, ou None quando nenhuma pode.

    A regra que o relatório aplica: só os totais de uma sessão do Claude Code já guardam os
    tokens dos seus subagentes. Uma linha de subagente do Codex e uma linha de worker de
    execução de papel são cada uma precificada sozinha, exatamente como são reportadas sozinhas.
    """
    if (row.get("kind") or "session") != "session" or row.get("runtime") == "codex":
        return None
    return children.get(row.get("session_id") or "")


def newest_as_of(table):
    """O `as_of` mais recente na tabela, ou "" quando nenhuma entrada carrega um."""
    dates = [e["as_of"] for e in table.values()
             if isinstance(e, dict) and isinstance(e.get("as_of"), str) and e["as_of"]]
    return max(dates) if dates else ""


def row_models(row, children=None):
    """Todo id de modelo através do qual uma linha foi precificada, o próprio e os dos seus filhos."""
    names = []
    parts = row.get("by_model")
    if isinstance(parts, dict):
        names.extend(name for name in parts if isinstance(name, str) and not name.startswith("<"))
    names.extend(m for m in (row.get("models") or []) if isinstance(m, str))
    if isinstance(row.get("model"), str):
        names.append(row["model"])
    for child in children or []:
        names.extend(row_models(child))
    return [name for name in names if name]


def row_as_of(row, table, children=None):
    """O `as_of` mais novo entre as entradas que precificaram esta linha, ou "" quando nenhuma carrega um.

    A data pertence à cifra, não ao arquivo: uma linha precificada a partir da entrada de uma
    família é carimbada com a data daquela entrada mesmo quando uma entrada mais nova para outro
    modelo está ao lado.
    """
    dates = []
    for name in row_models(row, children):
        entry = table.get(price_key(table, name))
        if isinstance(entry, dict) and isinstance(entry.get("as_of"), str) and entry["as_of"]:
            dates.append(entry["as_of"])
    return max(dates) if dates else ""


def priced(rows, table):
    """`(usd, as_of)` por linha, na ordem dada: as cifras que `harness usage` reporta.

    Uma linha que não pode ser precificada é `(None, "")` — nunca `(0.0, …)`. Sessões são
    precificadas com suas linhas de subagente em mãos, sobre a lista inteira, então a cifra numa
    linha de sessão do Claude Code já inclui seus subagentes e os dois nunca devem ser somados.
    """
    rows = [r for r in rows if isinstance(r, dict)]
    children = session_children(rows)
    out = []
    for row in rows:
        kids = row_children(row, children)
        cost = row_cost(row, table, kids)
        out.append((cost, row_as_of(row, table, kids) if cost is not None else ""))
    return out


def price_age_days(as_of, now=None):
    """Dias inteiros entre uma data `as_of` e hoje, ou None quando a data não parseia."""
    try:
        stamp = time.mktime(time.strptime(as_of, "%Y-%m-%d"))
    except (ValueError, TypeError):
        return None
    return int((time.time() if now is None else now) - stamp) // 86400
