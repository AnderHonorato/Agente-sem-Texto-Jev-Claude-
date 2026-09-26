"""Estabilidade do prefixo de cache, lida de volta a partir do ledger de uso.

`primitives/rules/cache-hygiene.md` pede a uma sessão que mantenha seu prefixo em cache durante
a tarefa, e nada informava se ela o fez. Uma mudança no conjunto de ferramentas, na lista de MCP,
no modelo ou no seletor de esforço transforma as leituras de cache do próximo turno em escritas
de cache, e o único sintoma visível é uma conta maior. A cifra aqui é
`cache_write / (cache_read + cache_write)` sobre o contexto **próprio** de uma sessão: a fração
do seu prefixo que o provedor teve que reescrever em vez de servir.

Ela mede e não impõe. Nada neste módulo nega, avisa ou bloqueia uma mudança de prefixo;
`harness usage --by prefix` é retrospectivo e somente leitura.

Quatro coisas que essa cifra se recusa a supor:

- **Os tokens de um subagente não são o prefixo da sessão.** Uma linha de sessão do Claude Code
  soma os tokens dos seus subagentes aos próprios (`claude/hooks/usage-log.py`, `daily`), e cada
  fan-out escreve um prefixo novo. Se deixado somado, uma sessão que manteve seu contexto
  perfeitamente ao longo de seis disparos aparenta ter recomprado um quarto dele. Por isso os
  campos de cache das linhas de subagente são subtraídos dos da sessão antes de calcular a razão,
  e uma sessão cujo contador `subagents` é maior que as linhas encontradas para ela, ou cuja
  subtração fica negativa, reporta `unknown` em vez de um número com aparência corrigida.
- **O degrau também não é medido através de tokens somados.** As fatias de `days` também somam
  os mesmos tokens de subagente por dia, e uma linha de subagente não carrega um mapa `days` para
  subtrair, então uma sessão que gerou qualquer disparo não reporta degrau algum, em vez do pico
  que seu dia de fan-out fabricaria.
- **Zero nunca é usado como desconhecido.** Uma linha sem campos de cache, ou com dois zeros, é
  reportada como `unknown`, assim como toda linha de um runtime que não exporta nenhuma cifra de
  escrita em cache (`adapters/codex/capabilities.json`). Uma razão de 0% de miss seria lida como
  uma sessão que manteve seu prefixo perfeitamente, em vez de um runtime que não sabe dizer. Num
  runtime que reporta escritas, leituras contra zero escritas são exatamente isso: um dia que
  manteve o prefixo.
- **O degrau é localizado com a granularidade que o ledger registra, nem mais fina.** O único
  fatiamento dentro da sessão que uma linha existente carrega é seu mapa `days`, que guarda os
  mesmos campos de token e a contagem de turnos daquele dia. Então o degrau é encontrado entre
  fatias de dia e identificado pelo índice de turno em que a fatia do degrau começa, que é o
  índice mais fino que o ledger consegue honestamente sustentar sem um evento novo.
"""

# A subida na razão de miss entre duas fatias consecutivas que conta como degrau em vez de deriva.
# Um prefixo mantido oscila alguns pontos conforme os turnos variam de tamanho; vinte pontos é a
# forma de um prefixo que foi reescrito, não de um que simplesmente cresceu.
MISS_STEP = 0.2

# Runtimes que reportam leituras em cache mas nenhuma cifra de escrita em cache, então nenhuma
# razão sobre suas linhas significa nada. Codex escreve `cache_read` a partir de
# `cached_input_tokens` e deixa `cache_write` sem reportar; onde isso chega como zero em vez de
# nulo, uma razão calculada sobre o par seria lida como um prefixo perfeitamente mantido.
NO_CACHE_WRITES = ("codex",)


def _count(row, name):
    """O campo de token de uma linha como um int não negativo, ou None quando ausente ou ilegível."""
    value = row.get(name)
    if value is None:
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return max(value, 0)


def _ratio(read, write, runtime=""):
    """`write / (read + write)`, ou None quando o par não consegue determinar uma."""
    if runtime in NO_CACHE_WRITES:
        return None
    if read is None or write is None:
        return None
    served = read + write
    return write / served if served else None


def miss_ratio(row, runtime=None):
    """A razão de miss sobre os campos de cache de uma linha **como estão**, ou None.

    Usada diretamente sobre uma fatia de `days`, por isso `runtime` pode ser passado: uma fatia
    não carrega runtime próprio e herda o da sua linha. Os próprios campos de uma linha de sessão
    incluem os dos seus subagentes, então `figure` os corrige primeiro via `own_cache`, em vez de
    chamar esta função.
    """
    if runtime is None:
        runtime = row.get("runtime") or ""
    return _ratio(_count(row, "cache_read"), _count(row, "cache_write"), runtime)


def folds_subagents(row):
    """Se os totais desta linha já contêm os tokens dos seus subagentes.

    A mesma regra pela qual `pricing.session_children` precifica: uma linha de sessão do Claude
    Code os soma, uma linha de sessão do Codex não, e a linha de uma execução delegada carrega
    apenas os próprios.
    """
    return (row.get("kind") or "session") == "session" and row.get("runtime") != "codex"


def own_cache(row, children=()):
    """As cifras de cache próprias de uma sessão, com os tokens de subagente somados retirados.

    Retorna `(None, None)` quando a correção não pode ser feita honestamente: um campo ausente na
    sessão ou em algum filho, menos linhas filhas do que a sessão diz ter gerado, ou uma subtração
    que fica negativa. Cada um desses casos significa que o resto não é o prefixo da sessão, e um
    número com aparência corrigida seria pior do que nenhum.
    """
    read, write = _count(row, "cache_read"), _count(row, "cache_write")
    if read is None or write is None or not folds_subagents(row):
        return read, write
    spawned = row.get("subagents") if isinstance(row.get("subagents"), int) else 0
    if max(spawned, 0) > len(children):
        return None, None
    for child in children:
        child_read, child_write = _count(child, "cache_read"), _count(child, "cache_write")
        if child_read is None or child_write is None:
            return None, None
        read -= child_read
        write -= child_write
    if read < 0 or write < 0:
        return None, None
    return read, write


def step(row, children=()):
    """A subida mais acentuada na razão de miss entre fatias de dia consecutivas, ou None.

    Retorna `{"turn", "day", "before", "after"}`, onde `turn` é o índice de 1 do primeiro turno da
    fatia cuja razão subiu, e as duas razões são a da fatia do degrau e a da fatia anterior a ela.
    Quando uma sessão deu um degrau mais de uma vez, a subida mais acentuada é a reportada.

    Uma fatia que não consegue determinar uma razão quebra a cadeia em vez de ser comparada
    através dela: o `before -> after` impresso é lido como uma fatia contra a fatia imediatamente
    anterior, então comparar através de uma lacuna nomearia dois dias que nunca foram adjacentes
    na cifra.

    Uma sessão que gerou qualquer disparo não recebe degrau. Suas fatias somam os tokens dos seus
    subagentes por dia, e uma linha de subagente não carrega um mapa `days` para subtrair, então o
    único degrau que essas fatias poderiam mostrar seria o próprio fan-out.
    """
    days = row.get("days")
    if not isinstance(days, dict):
        return None
    spawned = row.get("subagents") if isinstance(row.get("subagents"), int) else 0
    if folds_subagents(row) and (max(spawned, 0) or children):
        return None
    runtime = row.get("runtime") or ""
    found, turn, previous = None, 1, None
    for day in sorted(days):
        slice_ = days[day]
        ratio = miss_ratio(slice_, runtime) if isinstance(slice_, dict) else None
        if ratio is None:
            previous = None
        else:
            if previous is not None and ratio - previous >= MISS_STEP:
                rise = ratio - previous
                if found is None or rise > found["rise"]:
                    found = {"turn": turn, "day": day, "before": previous,
                             "after": ratio, "rise": rise}
            previous = ratio
        if isinstance(slice_, dict):
            turn += _count(slice_, "turns") or 0
    if found is not None:
        found.pop("rise", None)
    return found


def figure(row, children=()):
    """A linha de prefixo de cache de uma sessão: identidade, seus totais próprios de cache, razão e degrau."""
    models = row.get("models") if isinstance(row.get("models"), list) else []
    if not models and row.get("model"):
        models = [row["model"]]
    read, write = own_cache(row, children)
    spawned = row.get("subagents") if isinstance(row.get("subagents"), int) else 0
    return {
        "session_id": row.get("session_id") or "(unknown)",
        "repo": row.get("repo") or "(no repo)",
        "models": [name for name in models if isinstance(name, str) and name],
        "ended": row.get("ended") or "",
        "turns": _count(row, "turns"),
        "subagents": max(spawned, 0),
        "cache_read": read,
        "cache_write": write,
        "ratio": _ratio(read, write, row.get("runtime") or ""),
        "step": step(row, children),
        # Dito em vez de inferido a partir de um degrau vazio: nenhum degrau encontrado e nenhum
        # degrau mensurável são respostas diferentes, e o relatório as imprime de forma diferente.
        "step_blocked": folds_subagents(row) and bool(max(spawned, 0) or children),
    }


def figures(ledger, cutoff=""):
    """As cifras por sessão para as linhas dentro da janela, sessão mais antiga primeiro.

    Apenas linhas de sessão são reportadas, e o ledger inteiro é indexado por filhos primeiro:
    uma linha de subagente fora da janela ainda é somada aos totais do seu pai e ainda precisa ser
    retirada de volta.
    """
    children = {}
    for row in ledger:
        if not isinstance(row, dict):
            continue
        if row.get("kind") == "subagent" and row.get("runtime") != "codex" and row.get("session_id"):
            children.setdefault(row["session_id"], []).append(row)
    found = []
    for row in ledger:
        if not isinstance(row, dict) or (row.get("kind") or "session") != "session":
            continue
        if (row.get("ended") or "") < cutoff:
            continue
        found.append(figure(row, children.get(row.get("session_id") or "", ())))
    found.sort(key=lambda item: (item["ended"], item["session_id"]))
    return found


def _cell(value, width, unknown="unknown"):
    return "{:>{}}".format(unknown if value is None else "{:,}".format(value), width)


def report(ledger, cutoff, days, say):
    """`harness usage --by prefix`: a razão de miss por sessão, e onde ela deu um salto."""
    found = figures(ledger, cutoff)
    if not found:
        say("no sessions recorded in the last {} day(s)".format(days))
        return 0
    head = ("{:<20}{:<16}{:<22}{:>7}{:>14}{:>14}{:>9}  {}"
            .format("session", "repo", "models", "turns", "own_read", "own_write",
                    "miss", "step"))
    say("The miss ratio measures cache-prefix stability; nothing here denies a prefix change.")
    say("Subagent tokens are subtracted: the figure is the session's own prefix.")
    say(head)
    say("-" * len(head))
    unknown = 0
    for item in found:
        if item["ratio"] is None:
            unknown += 1
            ratio = "{:>9}".format("unknown")
        else:
            ratio = "{:>9.0%}".format(item["ratio"])
        jump = item["step"]
        if jump is not None:
            detail = ("turn {} ({}): {:.0%} -> {:.0%}"
                      .format(jump["turn"], jump["day"], jump["before"], jump["after"]))
        else:
            detail = "not measurable (subagents)" if item["step_blocked"] else "-"
        say("{:<20}{:<16}{:<22}{}{}{}{}  {}"
            .format(item["session_id"][:19], item["repo"][:15],
                    ("+".join(item["models"]) or "(unknown)")[:21],
                    _cell(item["turns"], 7, "?"), _cell(item["cache_read"], 14),
                    _cell(item["cache_write"], 14), ratio, detail))
    say("-" * len(head))
    stepped = sum(1 for item in found if item["step"] is not None)
    say("{} session(s), {} with a mid-session step, {} reporting no cache figures"
        .format(len(found), stepped, unknown))
    return 0
