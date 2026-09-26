#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hook de SessionEnd: registra o uso de tokens de uma sessão em ~/.local/state/agent-harness/usage.jsonl.

Um arquivo local, e nada pela rede a menos que um bloco `telemetry` ligue a exportação — veja
`telemetry.py` e docs/telemetry.md. SessionEnd compartilha um orçamento de 1,5 segundo, então o hook
lança um worker desacoplado e retorna; o worker faz streaming da transcrição linha por linha e faz upsert de
uma linha para a sessão, uma para cada subagente que ela lançou e uma para cada worker de
execução de papel recente. Leia com `harness usage`.

A mesma passagem constrói a lista de eventos que `rule-detectors.py` documenta, então a telemetria de regras custa
uma leitura da transcrição em vez de duas: o registro ganha `rules`, `counts` e `stances`.
Um registro que não importa custa ao registro só sua chave `rules` e nada mais.

O Codex é lido a partir de seus arquivos rollout em vez disso, por `scan_codex`, e os dois runtimes discordam
sobre o que os tokens de um pai significam: veja `codex_totals` e `cmd_usage` em `bin/harness`.

Toda linha nomeia o `harness_version` que a escreveu, uma linha de sessão nomeia o `effort` que
cobriu a maior parte da sua saída, e uma linha de sessão carrega fatias por dia em `days` para que uma sessão
que rodou por duas semanas não seja debitada ao dia em que terminou. Veja `harness_version`, `dominant`
e `daily`.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

FIELDS = (
    ("input", "input_tokens"),
    ("output", "output_tokens"),
    ("cache_read", "cache_read_input_tokens"),
    ("cache_write", "cache_creation_input_tokens"),
)

# Uma escrita de cache é precificada pelo seu tempo de vida — 1,25x o input base por cinco minutos, 2x por
# uma hora — e o Claude Code reporta a divisão sob `cache_creation` ao lado do total único
# `cache_creation_input_tokens`. A linha registra ambas as camadas para que `harness usage` possa precificar
# cada uma na sua própria taxa. As chaves são aditivas e só escritas quando uma camada é não-zero: uma linha
# de antes deste lançamento não carrega nenhuma e é precificada na taxa de 5 minutos, o que subestima
# uma escrita de 1 hora. Veja policy/prices.json.
CACHE_TIERS = (("cache_write_5m", "ephemeral_5m_input_tokens"),
               ("cache_write_1h", "ephemeral_1h_input_tokens"))

# Um resultado de ferramenta cujo texto vale a pena manter: os dois que os detectores leem. 64 KB está bem além de qualquer
# brief ou bloco cercado e bem aquém do maior resultado de uma transcrição.
TEXT_KEPT_FOR = ("Bash", "Agent")
MAX_RESULT_TEXT = 64 * 1024


def sibling(name, required=True):
    """Um módulo ao lado deste. Levanta exceção quando obrigatório, para o chamador registrar por que está ausente."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    try:
        spec = importlib.util.spec_from_file_location("harness_" + name.replace("-", "_"), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        if required:
            raise
        return None


def detectors():
    """O registro de detectores irmão. Levanta exceção, para o chamador registrar por que está ausente."""
    return sibling("rule-detectors")


def stances(env=None):
    """O mapa resolvido `{dimension: variant}`, a partir de `posture.py` e de mais nenhum lugar.

    Uma cópia deste hook rodando longe do seu resolvedor irmão não registra posturas em vez
    de uma segunda opinião sobre elas; o registro mantém todo outro campo.
    """
    module = sibling("posture", required=False)
    return module.resolve(env, strict=False)["stances"] if module else {}


# Reexportado, não redeclarado: os padrões são de `posture.py`, e um leitor de um registro de uso
# não deveria precisar saber qual arquivo os guarda.
DEFAULT_STANCES = getattr(sibling("posture", required=False), "DEFAULT_STANCES", {})

# As chaves sob as quais uma linha de subagente carrega seu orçamento suave, para que um estouro seja uma subtração numa
# linha em vez de um join contra a tabela de custo como ela está hoje. Escrito como `null` quando
# nada precifica o papel: um zero diria que o spawn foi orçado com nada.
BUDGET_KEYS = ("budget_output_tokens", "budget_tool_calls")
_COST = []

# As duas coisas para as quais um retorno é medido, na mesma linha em que o orçamento fica: se ele devolveu
# um caminho que um leitor pode abrir em vez do payload, e se ficou dentro do teto de palavras que
# seu brief declarava. Ambos são `null` quando a varredura não conseguiu medi-los — nenhuma chamada pai para
# unir, nenhum texto de retorno, nenhum teto que possa conhecer, um runtime que não reporta retorno nenhum.
RETURN_KEYS = ("return_path", "return_over_budget")
# Por que um retorno não foi medido, quando o motivo é um que um leitor de outra forma confundiria com um
# retorno curto: um resultado do qual a varredura manteve só os primeiros 64 KB não é um retorno cujas
# palavras ela pode contar, e dizer isso vence um número tirado sobre parte do texto.
MEASURED_KEY = "return_measured"
# Um caminho como um retorno o escreve: dentro de uma cerca, dentro de crases, ou nu em prosa. Os três
# diferem no que prova que um token é um caminho, ponto final. Texto entre aspas é tomado ao pé da letra; prosa
# nua não, porque `pass/fail`, `24/7`, `2026/09/22` e `they/them` são prosa e cada um
# deles carrega um separador. Ali um token conta só quando carrega a forma própria de um caminho.
QUOTED = re.compile(r"`{3,}[^\n]*\n(.*?)(?:`{3,}|\Z)|`([^`\n]+)`", re.S)
PATH_TOKEN = re.compile(r"[^\s`'\"<>|*?,;:()\[\]{}]*/[^\s`'\"<>|*?,;:()\[\]{}]*")
# Só à direita: um `.` à esquerda é `./notes`, e removê-lo tornaria o caminho absoluto e
# o mandaria procurar na raiz do sistema de arquivos.
PATH_TRIM = ".,;:!?'\")]}>"
PATH_ROOTS = ("/", "./", "../", "~/")
PATH_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,8}\Z")
# Uma URL nomeia o arquivo de outra pessoa, então não contribui com nada, ponto final — nem mesmo sua parte de caminho.
URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S+")
# O que conta como palavra quando um retorno é medido contra seu teto: um token carregando uma letra ou
# um dígito. Uma linha de cerca, o `-` de um marcador e um separador `·` são pontuação, e contá-los
# colocaria um retorno acima de um teto que ele respeitou.
WORD = re.compile(r"[A-Za-z0-9]")
# O número que um teto declara é o que está ao lado da palavra `words`, não o primeiro na frase:
# "cap each of the 3 sections at 200 words" é um teto de 200 palavras.
CAP_NUMBER = re.compile(r"(?i)(\d+)\s*[- ]?words?|word\s+cap\s*(?:of\s+)?(\d+)")
# Quantos candidatos um retorno é checado contra o sistema de arquivos. Um retorno que nomeou quarenta
# caminhos e não resolveu nenhum deles não é respondido de forma diferente pelo seu quadragésimo primeiro.
MAX_CANDIDATES = 40
# Um número deste tamanho é prosa sobre outra coisa, não um limite de retorno.
MAX_WORD_CAP = 100000
_RETURN_RULES = []


def budget_fields(role):
    """O orçamento suave sob o qual um spawn de `role` rodou, como as próprias chaves da linha.

    Os números são de `posture.py`, lidos da mesma tabela com que `brief-guard` precifica um brief,
    uma vez por varredura: uma revarredura de cem transcrições não deve percorrer todo sidecar cem
    vezes. A tabela é a de hoje, que é o que a linha pode saber — o brief que o spawn recebeu
    não é registrado em lugar nenhum que a varredura possa ler — então uma linha escrita depois que a variante mudou
    nomeia o orçamento que o papel carrega agora. Um irmão ausente, um papel não precificado e uma tabela que
    não vai construir são todos `null`.
    """
    fields = dict((key, None) for key in BUDGET_KEYS)
    if not _COST:
        module = sibling("posture", required=False)
        try:
            _COST.append((module, module.cost_table() if module else {}))
        except Exception:
            _COST.append((None, {}))
    module, table = _COST[0]
    if module is None or not role:
        return fields
    try:
        fields.update(module.budget_figures(module.row_for(table, role)))
    except Exception:
        return dict((key, None) for key in BUDGET_KEYS)
    return fields


def harness_version():
    """A versão que `harness --version` imprime, lida do mesmo arquivo `VERSION` na raiz.

    O hook roda como um script independente, então sobe a partir do seu próprio caminho real — através do
    symlink `claude/hooks -> ../policy/hooks` e através de `~/.claude/hooks/harness` — até o
    checkout que carrega um arquivo `VERSION` e `bin/harness`, e nunca importa a CLI.
    Uma cópia deste hook rodando fora de um checkout não registra versão em vez de um chute.
    """
    here = Path(os.path.realpath(__file__)).parent
    for parent in [here] + list(here.parents):
        marker = parent / "VERSION"
        if marker.is_file() and (parent / "bin" / "harness").exists():
            try:
                return marker.read_text(encoding="utf-8").strip() or None
            except OSError:
                return None
    return None


def stamped_version(rescan):
    """A versão a carimbar numa linha: nenhuma, ponto final, quando a linha é um preenchimento retroativo.

    Uma revarredura lê uma transcrição escrita por qualquer versão que estava instalada na época, o que é
    incognoscível a partir do arquivo, então a linha carrega `null` ao lado do seu `stances_source: "rescan"`.
    Carimbar a versão atual faria toda sessão passada parecer o lançamento de hoje.
    """
    return None if rescan else harness_version()


def usage_path():
    return Path.home() / ".local" / "state" / "agent-harness" / "usage.jsonl"


# O razão cresce de forma compatível: uma mudança adiciona um campo, uma renomeação distribui uma dobra, e nada é
# removido no lugar. Toda linha escrita a partir desta versão nomeia o esquema sob o qual foi escrita;
# uma linha sem a chave é anterior a isso e é lida como versão 0. Suba a versão a cada
# mudança no que uma linha carrega, e adicione uma renomeação a FIELD_FOLDS como `nome antigo: nome novo`, nunca
# reescrevendo linhas antigas. Veja docs/usage.md, "Ledger schema".
SCHEMA_KEY = "schema_version"
# A versão 1 é lançada primeiro na v0.14.0 e carrega todo campo que esse lançamento adiciona,
# `profile_fingerprint` entre eles.
SCHEMA_VERSION = 1
FIELD_FOLDS = {}
FINGERPRINT_KEY = "profile_fingerprint"
_POSTURE = []


def profile_fingerprint():
    """A impressão digital do perfil em vigor, a partir de `posture.py`; None quando não pode ser obtida.

    Uma cópia deste hook longe do seu resolvedor, ou um resolvedor que falha, carimba null: uma
    linha não atribuída, nunca uma adivinhada. O resolvedor lembra a resposta para o processo.
    """
    if not _POSTURE:
        _POSTURE.append(sibling("posture", required=False))
    try:
        return _POSTURE[0].fingerprint() if _POSTURE[0] else None
    except Exception:
        return None


def stamped(record):
    """Uma cópia de `record` nomeando o esquema e o perfil. O dict do chamador fica intocado.

    Um registro que já nomeia seu perfil o mantém, null incluso: a linha de um worker carrega o
    perfil sob o qual sua execução começou, e uma linha preenchida retroativamente carrega só o que o razão já
    sabia, então nenhuma das duas é carimbada com o perfil de quem quer que a escreva.
    """
    out = dict(record, **{SCHEMA_KEY: SCHEMA_VERSION})
    if FINGERPRINT_KEY not in out:
        out[FINGERPRINT_KEY] = profile_fingerprint()
    return out


ATTRIBUTION_KEY = "context_attribution"


def context_attribution():
    """Tokens de contexto por módulo para a seleção em vigor, a partir de `posture.py`; None sem ele.

    Uma estimativa suave, rotulada com seu método: veja `posture.context_attribution`.
    """
    if not _POSTURE:
        _POSTURE.append(sibling("posture", required=False))
    try:
        return _POSTURE[0].context_attribution() if _POSTURE[0] else None
    except Exception:
        return None


def attributed(record, prior=None, rescan=False):
    """Dá a uma linha de sessão sua atribuição de contexto: a própria do razão, uma leitura ao vivo, ou nenhuma.

    A mesma regra da impressão digital. Uma transcrição não diz quais módulos sua sessão
    carregou, então uma revarredura mantém o que o razão já guarda para aquela sessão e caso contrário
    deixa o campo de fora, em vez de atribuir uma sessão passada à seleção deste minuto.
    """
    known = prior.get(ATTRIBUTION_KEY) if isinstance(prior, dict) else None
    if isinstance(known, dict):
        record[ATTRIBUTION_KEY] = known
    elif not rescan:
        value = context_attribution()
        if value is not None:
            record[ATTRIBUTION_KEY] = value
    return record


def fold(row, folds=None):
    """Uma cópia de `row` com todo campo renomeado sob seu nome atual.

    Um campo cujo nome atual já está presente mantém esse valor: a linha foi escrita depois
    da renomeação, e a chave antiga é só um resto. Campos desconhecidos passam intocados, então uma
    linha de um escritor mais novo é lida com tudo o que carrega.
    """
    folds = FIELD_FOLDS if folds is None else folds
    out = dict(row)
    for old, new in folds.items():
        if old in out:
            value = out.pop(old)
            out.setdefault(new, value)
    return out


def ledger_rows(text, folds=None):
    """As linhas que o texto de um razão contém, dobradas, mais antigas primeiro.

    Uma linha que não é um objeto JSON é pulada em vez de fatal, e uma linha nunca é recusada
    por um campo ou uma versão de esquema que este leitor não conhece.
    """
    rows = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(fold(row, folds))
    return rows


def projects_dir():
    return Path.home() / ".claude" / "projects"


def git(cwd, *args):
    try:
        out = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True, timeout=5)
    except Exception:
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _result_parts(content, tool_name):
    """O texto de um resultado de ferramenta e se foi cortado, de uma string ou de uma lista de blocos igualmente.

    Só as duas ferramentas que um detector lê mantêm seu texto, e só os primeiros 64 KB dele: a
    lista de eventos é mantida inteira em memória, e um `Read` de um arquivo grande de outra forma seria carregado
    por toda a varredura à toa. Se o bit de corte é retornado ao lado do texto,
    porque uma medição tomada sobre o começo de um resultado não é uma medição do resultado.
    """
    if tool_name not in TEXT_KEPT_FOR:
        return "", False
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n".join(b.get("text") or "" for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    else:
        return "", False
    return text[:MAX_RESULT_TEXT], len(text) > MAX_RESULT_TEXT


def _result_text(content, tool_name):
    """Só o texto, para um chamador que não se importa se foi cortado."""
    return _result_parts(content, tool_name)[0]


def merge_slot(per_message, old_key, new_key):
    """Dobra um slot para dentro de outro campo a campo, do jeito que `record_usage` mantém um número.

    Usado quando um id de requisição que tinha aberto um slot próprio acaba nomeando um id de mensagem,
    o que acontece sempre que os registros com id de uma chamada são lidos depois dos sem id.
    """
    slot = per_message.pop(old_key, None)
    if slot is None:
        return
    target = per_message.get(new_key)
    if target is None:
        per_message[new_key] = slot
        return
    for name in ("day", "model"):
        if slot.get(name) and not target.get(name):
            target[name] = slot[name]
    for name in [field for field, _ in FIELDS] + [field for field, _ in CACHE_TIERS]:
        value = slot.get(name) or 0
        if value > (target.get(name) or 0):
            target[name] = value


def usage_key(links, maps, mid, request_id):
    """O slot sob o qual o uso de um registro de assistente é contado, e o slot que essa chave substitui.

    Um id de mensagem é a chave, como sempre. Um registro sem id mas com `requestId` indexa por
    ele em vez disso, sem escopo por arquivo: o id nomeia uma chamada de API, então a mesma chamada escrita tanto num
    arquivo de sessão quanto num arquivo de subagente é uma resposta, e uma chamada cujos outros registros carregam um
    id de mensagem se junta ao slot deles em vez de abrir um segundo. `links` lembra para qual chave um
    id de requisição resolveu, e `maps` são os mapas de slot nos quais dobrar um slot substituído, porque
    os arquivos não são lidos na ordem em que foram escritos. Um registro sem nenhum dos dois ids é desconhecido
    em vez de um duplicado, então não é deduplicado de jeito nenhum e o chamador o conta.
    """
    request_id = request_id.strip() if isinstance(request_id, str) else ""
    if not mid and not request_id:
        return None, None
    if not request_id:
        return mid, None
    linked = links.get(request_id)
    key = mid or linked or ("request", request_id)
    superseded = None
    # Só um slot que esta função abriu é jamais dobrado para fora; dois ids de mensagem sob um id
    # de requisição são duas mensagens, seja lá o que o runtime quis dizer com isso.
    if isinstance(linked, tuple) and linked != key:
        superseded = linked
        for per_message in maps:
            merge_slot(per_message, linked, key)
    links[request_id] = key
    return key, superseded


def record_usage(per_message, key, usage, day="", model=""):
    """Mantém o maior número que um id de mensagem já reportou para cada campo.

    Uma resposta de API é escrita como vários registros. Os primeiros carregam um `output_tokens`
    parcial de streaming e o último carrega o número verdadeiro, então tomar o primeiro subconta a
    resposta seriamente — numa transcrição real de subagente, 7.126 tokens de saída contra 40.868. O
    máximo campo a campo mantém o número final sem confiar na ordem do arquivo, que uma
    cauda reordenada ou truncada de outra forma diminuiria.

    `day` é a data UTC daquele registro, mantida no slot para que as fatias por dia sejam cortadas do
    mesmo mapa deduplicado sobre o qual os totais são somados e não possam discordar deles. A primeira
    data sob a qual um id de mensagem é visto é a que vale: uma resposta escrita atravessando a meia-noite
    é uma mensagem e pertence a um dia.

    `model` é mantido da mesma forma e pelo mesmo motivo: a divisão por modelo é cortada de
    this one deduplicated map, so it cannot disagree with the totals summed over it.
    """
    slot = per_message.setdefault(key, dict([(name, 0) for name, _ in FIELDS]
                                            + [("day", ""), ("model", "")]))
    if day and not slot.get("day"):
        slot["day"] = day
    if model and not slot.get("model"):
        slot["model"] = model
    for name, field in FIELDS:
        try:
            value = int(usage.get(field) or 0)
        except (TypeError, ValueError):
            continue
        if value > slot[name]:
            slot[name] = value
    tiers = usage.get("cache_creation")
    if isinstance(tiers, dict):
        for name, field in CACHE_TIERS:
            try:
                value = int(tiers.get(field) or 0)
            except (TypeError, ValueError):
                continue
            if value > slot.get(name, 0):
                slot[name] = value


# O que uma linha diz quando nada mediu seu número bruto: uma linha do Codex, uma linha de worker, uma linha
# escrita antes deste lançamento. Nunca 1.0 por padrão — isso alegaria que a deduplicação
# não removeu nada, o que é uma medição que ninguém fez.
RAW_UNKNOWN = "unknown"


def add_raw(raw, usage):
    """Soma o uso de um registro como escrito, antes de qualquer deduplicação. Veja `inflation`."""
    if raw is None:
        return
    for name, field in FIELDS:
        try:
            value = int(usage.get(field) or 0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            raw[name] = raw.get(name, 0) + value


def inflation(raw, totals):
    """A soma bruta por linha sobre o total deduplicado, através dos quatro campos de token juntos.

    Um único ratio em vez de um por campo: os campos são deduplicados pelos mesmos slots, então quatro
    números seriam quatro visões de uma medição, e a linha já carrega todo campo para
    um leitor que os queira separados. Uma transcrição sem nada para remover mede 1.0, que é
    o resultado — não o padrão, que é `RAW_UNKNOWN`.
    """
    if not raw:
        return RAW_UNKNOWN
    counted = sum(max(int(totals.get(name) or 0), 0) for name, _ in FIELDS)
    if counted <= 0:
        return RAW_UNKNOWN
    return round(sum(max(int(raw.get(name) or 0), 0) for name, _ in FIELDS) / float(counted), 3)


def summed(per_message):
    """Os quatro totais de token sobre as mensagens, cada um contado uma vez no seu maior valor.

    As camadas de escrita de cache pegam carona quando qualquer mensagem reportou uma, então uma linha que pode ser precificada
    camada a camada diz isso e uma que não pode carrega nenhuma das chaves em vez de um par de zeros
    que se leria como escritas na taxa mais barata.
    """
    totals = {name: sum(slot[name] for slot in per_message.values()) for name, _ in FIELDS}
    tiers = {name: sum(slot.get(name) or 0 for slot in per_message.values())
             for name, _ in CACHE_TIERS}
    if any(tiers.values()):
        totals.update(tiers)
    return totals


def empty_slice():
    return dict([(name, 0) for name, _ in FIELDS] + [("turns", 0)])


# Todo campo de token que uma parte por modelo pode carregar: as quatro colunas e as duas camadas de escrita de cache.
PART_FIELDS = tuple(name for name, _ in FIELDS) + tuple(name for name, _ in CACHE_TIERS)


def by_model(per_message):
    """Totais de token por id de modelo, cortados do mesmo mapa sobre o qual os totais da linha são somados.

    Uma sessão que trocou de modelos — uma compactação num mais barato, um subagente noutro —
    mantém um conjunto de totais e várias taxas, então sem este mapa só pode ser reportada em
    tokens. Um registro que não nomeia modelo nenhum torna o mapa não atribuível em vez de curto, então
    o mapa inteiro é descartado: `harness usage` preferiria reportar a linha sem preço a precificar
    parte dela.
    """
    out = {}
    for slot in per_message.values():
        name = slot.get("model") or ""
        if not name:
            return {}
        part = out.setdefault(name, dict((field, 0) for field, _ in FIELDS))
        for field in PART_FIELDS:
            value = slot.get(field) or 0
            if value:
                part[field] = part.get(field, 0) + value
    return out


def models_agree(parts, totals):
    """Se uma divisão por modelo soma até os próprios totais da linha, campo a campo.

    O mesmo teste que `slices_agree` aplica às fatias por dia, pelo mesmo motivo: uma divisão
    que discordasse da linha em que se apoia precificaria parte de uma sessão duas vezes ou nenhuma vez.
    Um campo que o runtime nunca reportou é desconhecido de ambos os lados e não é comparado.
    """
    if not parts:
        return False
    for name, _ in FIELDS:
        total = totals.get(name)
        if total is None:
            continue
        if sum(part.get(name) or 0 for part in parts.values()) != total:
            return False
    return True


def daily(per_message, turns_by_day, fallback=""):
    """O mapa `days`: quatro totais de token e uma contagem de turnos por data UTC.

    Cortado do mesmo mapa de id de mensagem sobre o qual os totais da linha são somados, então para o Claude Code
    a fatia de um dia **inclui os tokens de subagente daquele dia** exatamente como o total da sessão faz —
    a linha de sessão tem um único significado, e uma fatia que os excluísse não somaria até ele.
    Uma mensagem cujo registro não carregava timestamp cai em `fallback`, a data de término da sessão,
    em vez de ser deixada de fora de toda fatia; sem fallback nenhum também não há fatias,
    porque uma parcial se leria como um dia que custou menos do que custou.
    """
    days = {}
    for slot in per_message.values():
        day = slot.get("day") or fallback
        if not day:
            return {}
        row = days.setdefault(day, empty_slice())
        for name, _ in FIELDS:
            row[name] += slot.get(name) or 0
    for day, turns in turns_by_day.items():
        key = day or fallback
        if key:
            days.setdefault(key, empty_slice())["turns"] += turns
    return days


def slices_agree(days, totals):
    """Se as fatias somam até os próprios totais da linha, campo a campo.

    Checado antes do mapa ser escrito, nunca depois: um mapa `days` que discorda da linha em que
    se apoia seria lido como a verdade sobre uma data e silenciosamente dobraria ou perderia o gasto de um dia.
    Uma linha cujas fatias não concordam não carrega nenhuma e recai na sua data de término no relatório.
    """
    if not days:
        return False
    for name, _ in FIELDS:
        if sum(day.get(name) or 0 for day in days.values()) != (totals.get(name) or 0):
            return False
    return True


def dominant(weights):
    """A chave que cobre a maior parte dos tokens de saída, ou "" quando nada foi pesado.

    O esforço muda no meio da sessão em ambos os runtimes — 14 de 112 transcrições do Claude Code e 4 de 44
    rollouts do Codex medidos numa máquina — então uma linha registra o valor que cobriu a maior parte
    da saída em vez do primeiro ou do último, e `effort_source` nomeia de onde foi lido.
    Empates se resolvem pelo nome para que duas leituras de uma transcrição concordem.
    """
    weights = dict((key, value) for key, value in weights.items() if key)
    if not weights:
        return ""
    return max(sorted(weights), key=lambda key: weights[key])


def reported_model(counts):
    """O modelo que os registros de assistente de uma transcrição nomeiam com mais frequência; o mais recente em caso de empate.

    Um registro é um voto, então uma resposta escrita como vários registros pesa tanto quanto custou para
    escrever. O desempate é o último modelo visto, porque uma sessão que mudou de modelo no meio da execução
    rodou mais recentemente no mais recente.
    """
    if not counts:
        return ""
    return max(counts.items(), key=lambda item: item[1])[0]


def note_model(counts, name, order):
    """O modelo de um registro de assistente contra a contagem: `{name: (hits, last seen)}`."""
    if not isinstance(name, str) or not name:
        return
    hits = counts.get(name, (0, 0))[0]
    counts[name] = (hits + 1, order)


def _agent_row(path, shared=None, budget=None, max_bytes=None, version=None, links=None,
               raw=None):
    """Uma linha `kind: "subagent"` de um `agent-<id>.jsonl`, ou None quando não contém turno.

    O `agent-<id>.meta.json` irmão nomeia o tipo do agente e a profundidade do spawn; a transcrição
    carrega os tokens, as chamadas de ferramenta, o modelo e, em alguns registros, o esforço. Só contagens:
    nenhum texto de prompt e nenhum texto de comando chega ao registro.

    O modelo é o da transcrição, não o do arquivo de meta: o meta de um spawn roteado carrega o alias
    que o hook de spawn pediu enquanto o de um agente lançado diretamente carrega o id completo, e
    um modelo sob dois nomes divide `usage --by model` ao meio. O alias é o fallback para
    um agente que não registrou modelo nenhum.

    `shared` é o mapa de id de mensagem da sessão. A linha mantém seu próprio total, mas o total
    da sessão é tomado sobre esse mapa compartilhado, então um id de mensagem escrito tanto aqui quanto como uma
    linha de sidechain no arquivo de sessão é uma mensagem e é pago uma vez. `raw` é a contraparte
    não deduplicada desse mapa: os registros deste arquivo estão nos totais da sessão, então estão em
    `raw_vs_deduped` da sessão também.

    `budget` em segundos e `max_bytes` a partir da cauda são para um chamador trabalhando contra um timeout
    de hook: o worker desacoplado de `SessionEnd` tem todo o tempo do mundo e não passa nenhum dos dois,
    enquanto um hook ao vivo não pode ser morto no meio de um arquivo de agente muito grande. Quando um dos dois
    morde, a linha carrega `partial: True` e seus totais são da parte que foi lida.
    """
    per_message, idless = {}, 0
    links = {} if links is None else links
    maps = [per_message] if shared is None else [per_message, shared]
    partial = False
    try:
        meta = json.loads(path.with_name(path.stem + ".meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    seen, tools, models = set(), set(), {}
    calls = turns = records = 0
    effort = started = ended = ""
    try:
        handle = path.open("rb")
    except OSError:
        return None
    deadline = None if budget is None else time.monotonic() + budget
    with handle:
        if max_bytes:
            try:
                size = os.fstat(handle.fileno()).st_size
            except OSError:
                size = 0
            if size > max_bytes:
                # A cauda, porque as últimas respostas carregam os maiores números e um arquivo
                # deste tamanho não vai terminar dentro do timeout de um hook de qualquer forma.
                handle.seek(size - max_bytes)
                handle.readline()
                partial = True
        for index, line in enumerate(handle):
            if deadline is not None and not index % 256 and time.monotonic() > deadline:
                partial = True
                break
            try:
                entry = json.loads(line.decode("utf-8", "replace"))
            except Exception:
                continue
            if not isinstance(entry, dict):
                continue
            stamp = entry.get("timestamp") or ""
            if stamp:
                started = stamp if not started or stamp < started else started
                ended = stamp if stamp > ended else ended
            if not effort and isinstance(entry.get("effort"), str):
                effort = entry["effort"].strip()
            if entry.get("type") != "assistant":
                continue
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            mid = message.get("id")
            records += 1
            note_model(models, message.get("model"), records)
            for index, block in enumerate(message.get("content") or []):
                # A mesma repetição de bloco contra a qual a varredura de sessão se protege: uma resposta de API
                # é escrita como várias linhas que repetem seus blocos.
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                key = block.get("id") or (mid, block.get("apiBlockIndex", index))
                if key in tools:
                    continue
                tools.add(key)
                calls += 1
            usage = message.get("usage") or {}
            key, superseded = usage_key(links, maps, mid, entry.get("requestId"))
            if key is None:
                # Nada identifica este registro, então nada pode ser mesclado nele. Sua chave
                # nomeia o arquivo e a linha, como sempre fez, e é contado como desconhecido.
                idless += 1
                key = ("line", str(path), idless)
            record_usage(per_message, key, usage, stamp[:10], message.get("model") or "")
            add_raw(raw, usage)
            if shared is not None:
                record_usage(shared, key, usage, stamp[:10], message.get("model") or "")
            # Um slot dobrado para dentro de outro mantém o turno para o qual já foi contado.
            if superseded is not None and superseded in seen:
                seen.discard(superseded)
                seen.add(key)
            if key in seen:
                continue
            seen.add(key)
            turns += 1
    if not turns:
        # Nada legível, seja porque o arquivo não continha turno ou porque o orçamento parou antes de um:
        # o chamador registra isso como gasto desconhecido em vez de zero.
        return None
    workflow = path.parent.name if path.parent.name.startswith("wf_") else None
    row = {"kind": "subagent", "runtime": "claude-code", "harness_version": version,
           "session_id": "", "repo": "",
           "agent_id": path.stem[len("agent-"):],
           # Um agente da ferramenta Workflow pode não ter arquivo de meta nenhum; sem nome é um fato sobre o
           # registro, e "unknown" diz isso onde uma string vazia se leria como um campo faltando.
           "agent_type": meta.get("agentType") or "unknown",
           "model": reported_model(models) or meta.get("model") or "",
           "effort": effort or meta.get("effort") or "",
           "tool_calls": calls, "spawn_depth": meta.get("spawnDepth"), "workflow": workflow,
           # `mark_reroutes` preenche estes a partir do registro do pai da chamada, unidos por este id.
           "tool_use_id": meta.get("toolUseId") or "",
           "requested_type": "", "rerouted": False,
           # `mark_returns` preenche estes a partir do registro do pai do retorno, unidos pelo
           # mesmo id. Null é "não medido", nunca "medido e nada encontrado", e
           # `return_measured` nomeia o motivo onde um de outra forma seria confundido com o outro.
           "return_path": None, "return_over_budget": None, "return_measured": None,
           "turns": turns, "started": started, "ended": ended}
    if partial:
        row["partial"] = True
    # Registros que os totais desta linha incluem que nada identificou — nem id de mensagem nem
    # id de requisição — para que um leitor possa distinguir uma linha que foi deduplicada de uma que não pôde ser.
    if idless:
        row["idless_records"] = idless
    if workflow:
        # Um agente da ferramenta Workflow é lançado pela ferramenta, não gerado por spawn: nenhum hook de spawn o roteou e
        # nenhum brief lhe declarou um orçamento, então um nome de papel que ele por acaso carregue o precifica a nada.
        row["unconfined"] = True
        row.update(dict((key, None) for key in BUDGET_KEYS))
    else:
        row.update(budget_fields(row["agent_type"]))
    row.update(summed(per_message))
    return row


# As duas grafias de "este spawn não nomeou definição de agente nenhuma"; são um só pedido, então um spawn
# que rodou como `general-purpose` depois de pedir nada não foi roteado de novo.
UNNAMED_TYPES = ("", "general-purpose")
# Um tipo pedido é texto escrito pelo modelo. Só um nome que a ferramenta poderia de fato ter resolvido é
# mantido; qualquer outra coisa é registrada como o fato de que era outra coisa, porque uma linha de uso é
# uma contagem e não deve virar um lugar onde texto livre é armazenado.
AGENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def refused_spawns(agents, errored):
    """Os ids de chamada `Agent` em `errored` que nunca rodaram: nenhuma linha de subagente os nomeia.

    Um spawn que um hook `PreToolUse` recusou volta como um resultado de erro e não escreve
    transcrição de subagente, então contá-lo como subagente reporta trabalho que ninguém fez. Um spawn que rodou e então
    falhou também volta como um erro, mas deixou uma transcrição cujo meta nomeia a chamada, e
    permanece contado. Um arquivo de subagente cujo meta não nomeia chamada nenhuma ainda é uma linha em `agents`,
    e a contagem da sessão nunca fica abaixo disso, então é contado de qualquer forma.
    """
    ran = set(row.get("tool_use_id") for row in agents or [] if row.get("tool_use_id"))
    return set(use_id for use_id in errored if use_id not in ran)


def mark_reroutes(agents, requested):
    """Preenche `requested_type` e `rerouted` a partir dos inputs `Agent` do pai, unidos pelo id de uso de ferramenta.

    Uma transcrição registra um input de ferramenta como o modelo o escreveu, antes de qualquer hook `PreToolUse`
    reescrevê-lo, enquanto o `.meta.json` do subagente registra o tipo com que de fato rodou. Os dois
    discordarem é o reroteamento — medido a partir do que aconteceu, nunca anunciado pelo hook que
    o fez, então a conformidade do orquestrador é um número e não uma alegação. Verificado numa transcrição
    real: o pai registrou `general-purpose`, o meta do subagente dizia `Explore`,
    sob o mesmo id de uso de ferramenta.
    """
    for row in agents:
        use_id = row.get("tool_use_id")
        if not use_id or use_id not in requested:
            continue
        asked = requested[use_id]
        asked = asked.strip() if isinstance(asked, str) else ""
        ran = row.get("agent_type") or ""
        row["requested_type"] = asked if not asked or AGENT_NAME.fullmatch(asked) else "other"
        if ran and ran != "unknown":
            row["rerouted"] = asked != ran and not (asked in UNNAMED_TYPES and ran in UNNAMED_TYPES)


def return_rules():
    """`(padrão de teto, agentes cuja definição carrega o teto, o teto padrão)`, lido uma vez.

    Os três são dos próprios irmãos: `rule-detectors` decide o que conta como um limite declarado e
    quais agentes não precisam repetir um, e o `BOUND` de `brief-guard` é o teto que ele anexa a todo
    brief que não declara nenhum. Uma segunda cópia aqui mediria mais cedo ou mais tarde retornos contra um
    teto que nenhum brief jamais carregou. Um irmão que não importa deixa o teto desconhecido, que a
    linha registra como não medido.
    """
    if not _RETURN_RULES:
        rules = sibling("rule-detectors", required=False)
        guard = sibling("brief-guard", required=False)
        default = re.search(r"\d+", getattr(guard, "BOUND", "") or "")
        _RETURN_RULES.append((getattr(rules, "WORD_CAP_RE", None),
                              getattr(rules, "CAPPED_AGENTS", frozenset()),
                              int(default.group(0)) if default else None))
    return _RETURN_RULES[0]


def return_cap(brief, agent_type):
    """O teto de palavras que um retorno devia, ou None quando a varredura não pode saber um.

    Um brief que declara um teto é medido contra o número ao lado da palavra `words`, que
    nem sempre é o primeiro número na frase. Um brief que não declara nenhum foi limitado por
    `brief-guard` ao seu próprio padrão antes de chegar ao agente — a transcrição registra a
    chamada como o modelo a escreveu, não como o hook a reescreveu (#324) — então esse padrão é o teto.

    Dois briefs não recebem teto nenhum, porque o hook não anexa nenhum a eles: um prompt vazio, e um
    spawn de um agente cuja própria definição carrega o teto. `agent_type` ali é o tipo que a
    chamada pediu, como o hook o lê, e não o tipo com que o spawn rodou — um reroteamento não deve
    mover um retorno para um teto que seu brief nunca carregou.
    """
    pattern, capped, default = return_rules()
    if pattern is None or not (brief or "").strip():
        return None
    match = pattern.search(brief)
    if match is None:
        return None if (agent_type or "") in capped else default
    number = CAP_NUMBER.search(match.group(0))
    if number is None:
        return None
    cap = int(number.group(1) or number.group(2))
    return cap if 0 < cap <= MAX_WORD_CAP else None


def return_roots(cwd, top):
    """Onde um caminho que um retorno nomeia pode resolver: a worktree onde rodou, e o scratchpad.

    O scratchpad é o diretório temporário, que é onde `transcript-hygiene` diz que a versão
    longa vai. Um caminho que resolve fora de ambos — um arquivo de sistema, outro checkout — não é
    o detalhe que este retorno foi pedido para anotar, então não conta como um.
    """
    roots = []
    for base in (top, cwd, tempfile.gettempdir()):
        if not base:
            continue
        try:
            real = os.path.realpath(os.path.expanduser(str(base)))
        except (OSError, ValueError):
            continue
        if real not in roots and os.path.isdir(real):
            roots.append(real)
    return roots


def path_shaped(token):
    """True quando um token carrega a forma própria de um caminho em vez de uma barra entre duas palavras."""
    return token.startswith(PATH_ROOTS) or bool(PATH_EXTENSION.search(token.rsplit("/", 1)[-1]))


def path_candidates(text):
    """Todo token com forma de caminho num retorno, em ordem, sem repetições.

    Texto entre aspas — um bloco cercado ou crases em linha — é tomado ao pé da letra: um token escrito
    dentro dele com um separador nele foi escrito como um caminho. Prosa nua precisa parecer um.
    """
    body = URL.sub(" ", text or "")
    quoted = [(m.start(), m.end()) for m in QUOTED.finditer(body)]
    seen, found = set(), []
    for match in PATH_TOKEN.finditer(body):
        token = match.group(0).rstrip(PATH_TRIM)
        if len(token) < 2 or "/" not in token or token in seen:
            continue
        if not (path_shaped(token)
                or any(start <= match.start() and match.end() <= end
                       for start, end in quoted)):
            continue
        seen.add(token)
        found.append(token)
        if len(found) >= MAX_CANDIDATES:
            break
    return found


def resolves(token, roots):
    """True quando `token` nomeia algo que existe agora sob uma das `roots`.

    Um caminho relativo é tentado contra cada raiz, que é como um retorno que escreveu
    `notes/dimension-a.md` é lido. A resolução é tomada no momento em que a linha do razão é escrita:
    um caminho que desde então foi apagado não resolveu, e a linha diz isso em vez de
    adivinhar o que estava lá quando o agente retornou.
    """
    try:
        expanded = os.path.expanduser(token)
        tries = ([expanded] if os.path.isabs(expanded)
                 else [os.path.join(root, expanded) for root in roots])
        for candidate in tries:
            real = os.path.realpath(candidate)
            if not os.path.exists(real):
                continue
            if any(real == root or real.startswith(root + os.sep) for root in roots):
                return True
    except (OSError, ValueError):
        return False
    return False


def word_count(text):
    """As palavras que um teto conta: tokens carregando uma letra ou um dígito, nunca só pontuação."""
    return sum(1 for token in (text or "").split() if WORD.search(token))


def path_state(text, roots):
    """`"resolvable"`, `"unresolvable"` ou `"none"` para o texto de um retorno.

    Um retorno que não nomeou caminho nenhum carrega none. Isso é um fato sobre o retorno e não uma
    falha — um veredito de uma linha não deve arquivo nenhum — e o relatório o conta separado de um retorno
    cujo caminho não levou a lugar nenhum.
    """
    candidates = path_candidates(text)
    if not candidates:
        return "none"
    return "resolvable" if any(resolves(t, roots) for t in candidates) else "unresolvable"


def mark_returns(agents, briefs, returns, roots):
    """Preenche `return_path` e `return_over_budget` a partir da chamada `Agent` do pai e do seu resultado.

    Determinístico do início ao fim: um match de string para os caminhos, `os.path.exists` para se um
    resolve, uma contagem de palavras contra o teto que o brief declarava. Nada aqui julga o que o retorno
    disse — essa é a pergunta da #157, e estes dois campos são o input rotulado de que ela precisa.

    Uma linha cuja chamada pai não está nesta transcrição mantém ambos os campos `null`. O mesmo vale para um retorno
    que chegou vazio, e um do qual a varredura manteve só o começo: um resultado truncado é registrado
    como `return_measured: "truncated"` em vez de medido sobre a parte que foi lida.
    """
    for row in agents:
        use_id = row.get("tool_use_id")
        if not use_id or use_id not in returns:
            continue
        text, truncated = returns[use_id]
        if truncated:
            row[MEASURED_KEY] = "truncated"
            continue
        if not isinstance(text, str) or not text.strip():
            continue
        row["return_path"] = path_state(text, roots)
        cap = return_cap(briefs.get(use_id) or "", row.get("requested_type") or "")
        if cap:
            row["return_over_budget"] = word_count(text) > cap


def agent_rows(transcript, session_id="", shared=None, version=None, links=None, raw=None):
    """Toda linha de subagente pertencente a uma transcrição de sessão, por caminho.

    O Claude Code escreve cada subagente em `<session>/subagents/agent-<id>.jsonl` ao lado do
    próprio `<session>.jsonl` da sessão, e um agente da ferramenta Workflow um nível ainda mais fundo, sob
    `subagents/workflows/wf_<id>/`. A busca é recursiva por esse motivo. Esses tokens foram
    gastos por esta sessão, então a linha de sessão também os conta; as linhas por agente são o que
    torna `usage --by role` verdadeiro.
    """
    path = Path(os.path.expanduser(str(transcript)))
    rows = []
    try:
        files = sorted((path.with_suffix("") / "subagents").rglob("agent-*.jsonl"))
    except OSError:
        return rows
    for file in files:
        row = _agent_row(file, shared, version=version, links=links, raw=raw)
        if row:
            row["session_id"] = session_id or path.stem
            rows.append(row)
    return rows


def scan_all(transcript, session_id="", cwd="", prior=None, rescan=False):
    """Toda linha que uma transcrição produz: a sessão primeiro, então uma linha por subagente."""
    shared, links, raw = {}, {}, {}
    agents = agent_rows(transcript, session_id, shared, version=stamped_version(rescan),
                        links=links, raw=raw)
    record = scan(transcript, session_id, cwd, prior, rescan, agents=agents, shared=shared,
                  links=links, raw=raw)
    if record is None:
        return []
    if record.get("runtime") != "claude-code":
        return [record]
    for row in agents:
        row["session_id"] = record["session_id"]
        row["repo"] = record.get("repo", "")
    return [record] + agents


def scan(transcript, session_id="", cwd="", prior=None, rescan=False, agents=None, shared=None,
         links=None, raw=None):
    """Um registro de uma transcrição, ou None quando não há nada que valha a pena registrar.

    `prior` é o registro que esta sessão já tem, quando existe um; `rescan` diz que a leitura
    é um preenchimento retroativo em vez do fim da própria sessão. Juntos eles decidem o campo `stances`,
    que um preenchimento retroativo só pode adivinhar. `agents` são as linhas de subagente quando o chamador já
    as leu, para que `scan_all` leia cada arquivo de subagente uma vez em vez de duas, e
    `shared` é o mapa de id de mensagem que essas leituras preencheram.

    Os totais da sessão são tomados sobre esse único mapa, nunca como uma soma de duas fontes. O Claude
    Code mais antigo escrevia os turnos de um subagente no arquivo de sessão como linhas de sidechain enquanto o
    mais novo os escreve no próprio arquivo do subagente; uma transcrição carregando ambos pagaria
    por todo token delegado duas vezes se os dois fossem somados.
    """
    per_message = {} if shared is None else shared
    links = {} if links is None else links
    # Os mesmos registros de `per_message`, somados por linha em vez de por slot: a linha reporta
    # os dois contra o outro como `raw_vs_deduped` em vez de descartar o número bruto.
    raw = {} if raw is None else raw
    idless = 0
    models, agent_calls, seen, requested = [], set(), set(), {}
    # Chamadas `Agent` cujo resultado voltou como erro: um spawn que um hook recusou, ou um que
    # falhou depois de rodar. `refused_spawns` distingue os dois quando a linha é contada, mas
    # só por arquivos de subagente: um arquivo de sessão contendo linhas de sidechain é o formato mais antigo, onde
    # um spawn que rodou e falhou também não tem arquivo, então ali toda chamada com erro permanece contada.
    errored_calls = set()
    legacy_sidechains = False
    briefs = {}
    started = ended = branch = ""
    turns = 0
    turns_by_day, efforts = {}, {}
    events, tool_names, blocks_seen = [], {}, set()
    turn, pending_final = 0, None
    try:
        handle = open(os.path.expanduser(str(transcript)), encoding="utf-8", errors="replace")
    except OSError:
        return None
    with handle:
        first = handle.readline()
        handle.seek(0)
        if '"session_meta"' in first:
            return scan_codex(transcript, session_id, cwd, prior, rescan)
        if agents is None:
            agents = agent_rows(transcript, session_id, per_message,
                                version=stamped_version(rescan), links=links, raw=raw)
        for line in handle:
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if not isinstance(entry, dict):
                continue
            # Um subagente tem seu próprio arquivo de transcrição hoje, mas o Claude Code mais antigo escrevia seus
            # turnos neste como linhas de sidechain. São trabalho daquele agente, então não geram
            # evento nenhum aqui; seus tokens foram gastos por esta sessão e são somados como sempre.
            sidechain = bool(entry.get("isSidechain"))
            legacy_sidechains = legacy_sidechains or sidechain
            stamp = entry.get("timestamp") or ""
            if stamp:
                started = stamp if not started or stamp < started else started
                ended = stamp if stamp > ended else ended
            session_id = session_id or entry.get("sessionId") or ""
            cwd = cwd or entry.get("cwd") or ""
            branch = entry.get("gitBranch") or branch
            kind = entry.get("type")
            message = entry.get("message") or {}
            content = message.get("content") if isinstance(message, dict) else None
            mid = message.get("id") if isinstance(message, dict) else None
            if kind == "system":
                if entry.get("subtype") == "compact_boundary" and not sidechain:
                    events.append({"kind": "compact", "turn": turn})
                continue
            if kind == "user":
                blocks = content if isinstance(content, list) else []
                results = [b for b in blocks
                           if isinstance(b, dict) and b.get("type") == "tool_result"]
                if sidechain:
                    continue
                for block in results:
                    tool_use_id = block.get("tool_use_id") or ""
                    name = tool_names.get(tool_use_id, "")
                    if name == "Agent" and tool_use_id and block.get("is_error") is True:
                        errored_calls.add(tool_use_id)
                    text, cut = _result_parts(block.get("content"), name)
                    events.append({"kind": "tool_result", "turn": turn,
                                   "tool_use_id": tool_use_id, "tool_name": name,
                                   "text": text, "truncated": cut})
                if results or entry.get("isMeta") or entry.get("isCompactSummary"):
                    continue
                turn += 1
                if pending_final is not None:
                    pending_final["final"] = True
                    pending_final = None
                events.append({"kind": "user_prompt", "turn": turn})
                continue
            if kind != "assistant":
                continue
            # Um registro cujo `message` não é um dict não contém uso, nem modelo, nem blocos,
            # e lê-lo como um mapeamento costumava abortar a varredura da transcrição inteira;
            # `_agent_row` sempre o pulou.
            if not isinstance(message, dict):
                continue
            model = message.get("model")
            for index, block in enumerate(content or []):
                # Uma resposta de API é escrita como várias linhas que repetem o mesmo id de mensagem,
                # cada uma carregando um bloco; um bloco visto duas vezes é um bloco, não dois eventos.
                if sidechain or not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text = block.get("text") or ""
                    key = ("text", mid, block.get("apiBlockIndex", index), text)
                    if key in blocks_seen:
                        continue
                    blocks_seen.add(key)
                    pending_final = {"kind": "assistant_text", "turn": turn, "text": text,
                                     "final": False, "model": model or ""}
                    events.append(pending_final)
                elif block.get("type") == "tool_use":
                    use_id = block.get("id") or ""
                    key = ("tool_use", mid, block.get("apiBlockIndex", index), use_id)
                    if key in blocks_seen:
                        continue
                    blocks_seen.add(key)
                    tool_names[use_id] = block.get("name") or ""
                    events.append({"kind": "tool_use", "turn": turn, "id": use_id,
                                   "name": block.get("name") or "", "input": block.get("input")})
            for block in content or []:
                if isinstance(block, dict) and block.get("type") == "tool_use" \
                        and block.get("name") == "Agent":
                    agent_calls.add(block.get("id") or len(agent_calls))
                    called = block.get("input")
                    if block.get("id") and isinstance(called, dict):
                        requested.setdefault(block["id"], called.get("subagent_type") or "")
                        # O brief como o modelo o escreveu, mantido só o suficiente para ler o
                        # teto de palavras dele. Nenhuma linha o guarda: veja `mark_returns`.
                        brief = called.get("prompt")
                        briefs.setdefault(block["id"], brief if isinstance(brief, str) else "")
            # A mesma repetição é por que as somas de token são tomadas uma vez por id de mensagem, não uma
            # vez por linha, e no maior número daquele id em vez do primeiro: as linhas iniciais
            # de uma resposta carregam uma contagem parcial de streaming.
            key, superseded = usage_key(links, [per_message], mid, entry.get("requestId"))
            if key is None:
                # Nada identifica este registro, então nada pode ser mesclado nele. Sua chave
                # nomeia a linha de onde veio, e é contado como desconhecido em vez de
                # silenciosamente deduplicado contra um registro com o qual pode não ter nada a ver.
                idless += 1
                key = ("line", "session", idless)
            usage = message.get("usage") or {}
            record_usage(per_message, key, usage, stamp[:10], model or "")
            add_raw(raw, usage)
            # O Claude Code escreve o esforço em vigor em todo registro de assistente, como `effort` e
            # de novo como `perTurnEffort`; uma linha de sidechain carrega o do subagente, não o desta
            # sessão, então só os próprios registros da sessão são pesados.
            if mid and not sidechain:
                chosen = entry.get("effort") or entry.get("perTurnEffort")
                if isinstance(chosen, str) and chosen.strip():
                    efforts.setdefault(mid, chosen.strip())
            # Um slot dobrado para dentro de outro mantém o turno para o qual já foi contado.
            if superseded is not None and superseded in seen:
                seen.discard(superseded)
                seen.add(key)
            if key in seen:
                continue
            seen.add(key)
            turns += 1
            # Contado exatamente onde `turns` está, para que as contagens de turno das fatias somem até a da linha.
            turns_by_day[stamp[:10]] = turns_by_day.get(stamp[:10], 0) + 1
            if model and model not in models:
                models.append(model)
    if pending_final is not None:
        pending_final["final"] = True
    mark_reroutes(agents, requested)
    if not session_id or not turns:
        return None
    totals = summed(per_message)
    top = git(cwd, "rev-parse", "--show-toplevel") if cwd and os.path.isdir(cwd) else ""
    # Depois de `top`, porque os caminhos de um retorno são resolvidos contra a worktree onde rodou. Os
    # resultados são os que a lista de eventos já guardou para os detectores, então medir um retorno
    # não custa uma segunda leitura da transcrição.
    mark_returns(agents, briefs,
                 dict((e["tool_use_id"], (e["text"], e.get("truncated")))
                      for e in events
                      if e["kind"] == "tool_result" and e.get("tool_name") == "Agent"),
                 return_roots(cwd, top))
    record = {
        "kind": "session",
        "runtime": "claude-code",
        "runtime_version": None,
        "harness_version": stamped_version(rescan),
        "session_id": session_id,
        "repo": os.path.basename(top or str(cwd).rstrip("/")),
        "branch": (git(cwd, "rev-parse", "--abbrev-ref", "HEAD") if top else "") or branch,
        "models": models,
        "started": started,
        "ended": ended,
    }
    # Os tokens de um subagente são a conta da sessão, então a linha de sessão os carrega — uma vez,
    # porque `totals` é tomado sobre o único mapa que ambas as leituras preencheram. As linhas por agente carregam
    # os mesmos tokens de novo, atribuídos, o que é por que nenhum agrupamento soma os dois.
    for name, _ in FIELDS:
        record[name] = totals[name]
    for name, _ in CACHE_TIERS:
        if name in totals:
            record[name] = totals[name]
    refused = set() if legacy_sidechains else refused_spawns(agents, errored_calls)
    record["subagents"] = max(len(agents), len(agent_calls - refused))
    record["turns"] = turns
    # Todo registro que estes totais incluem que nada identificou — nem id de mensagem nem
    # id de requisição — os próprios desta sessão e os dos arquivos de subagente dobrados nela, já que
    # os totais incluem ambos. Uma linha sem a chave foi deduplicada por inteiro.
    unknown = idless + sum(int(row.get("idless_records") or 0) for row in agents or [])
    if unknown:
        record["idless_records"] = unknown
    # Quanto a deduplicação acima removeu, sobre os mesmos slots: os totais incluem os
    # arquivos de subagente, então o número bruto também.
    record["raw_vs_deduped"] = inflation(raw, totals)
    weights = {}
    for mid, chosen in efforts.items():
        weights[chosen] = weights.get(chosen, 0) + ((per_message.get(mid) or {}).get("output") or 0)
    record["effort"] = dominant(weights) or None
    record["effort_source"] = "transcript" if record["effort"] else None
    days = daily(per_message, turns_by_day, (ended or started)[:10])
    if slices_agree(days, totals):
        record["days"] = days
    parts = by_model(per_message)
    if models_agree(parts, totals):
        record["by_model"] = parts
    # Uma escrita ao vivo de SessionEnd sabe as posturas sob as quais a sessão de fato rodou. Uma revarredura
    # não sabe — o ambiente que lê é o deste minuto — então mantém o que o registro já
    # carrega, e carimba um registro que não tem nenhuma como um chute, que o relatório então exclui.
    prior_stances = (prior or {}).get("stances") if isinstance(prior, dict) else None
    if isinstance(prior_stances, dict) and prior_stances:
        record["stances"] = prior_stances
        if (prior or {}).get("stances_source"):
            record["stances_source"] = prior["stances_source"]
    else:
        record["stances"] = stances()
        if rescan:
            record["stances_source"] = "rescan"
    attributed(record, prior, rescan)
    try:
        module = detectors()
        record["counts"] = module.counts(events)
        errors = []
        record["rules"] = dict((did, len(hits))
                               for did, hits in module.run(events, record["stances"], errors=errors).items())
        if errors:
            record["rules_errors"] = errors
    except Exception as exc:
        # Um registro que está faltando, quebrado ou uma versão à parte custa ao registro seus campos
        # de regra e nada mais; a lacuna é nomeada para que um relatório nunca a leia como um zero silencioso.
        record.pop("counts", None)
        record.pop("rules", None)
        record["rules_error"] = "{}: {}".format(type(exc).__name__, exc).split("\n")[0][:200]
    return record


# O Codex nomeia seus campos de token de forma diferente do Claude Code e reporta `input_tokens`
# incluindo a parte em cache, então o mapeamento mora num só lugar e `codex_totals` é o único
# leitor dele.
CODEX_FIELDS = (("input", "input_tokens"), ("output", "output_tokens"),
                ("cache_read", "cached_input_tokens"),
                ("cache_write", "cache_write_input_tokens"))


def codex_home():
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))


def codex_spawn(meta):
    """O registro `thread_spawn` de um rollout de subagente do Codex, ou None para uma sessão de topo.

    O Codex escreve um subagente num arquivo de rollout próprio em vez de ao lado do seu pai, então
    o `session_meta` é a única coisa que distingue os dois: o `payload.source` de um rollout de topo
    é uma string nomeando o front end — `"vscode"`, `"cli"`, `"exec"` — enquanto o de um
    subagente é o objeto `{"subagent": {"thread_spawn": {...}}}`. Medido numa máquina,
    307 de 438 rollouts são threads de subagente, todos registrados como uma sessão até
    este teste existir.

    O próprio `parent_thread_id` do meta sob `thread_source: "subagent"` é o fallback, então um
    Codex que move ou renomeia `source` degrada para uma linha unida em vez de para uma falsa
    sessão; a profundidade que não consegue fornecer é registrada como desconhecida em vez de adivinhada como 1.
    """
    source = meta.get("source")
    if isinstance(source, dict):
        spawn = (source.get("subagent") or {}).get("thread_spawn")
        if isinstance(spawn, dict):
            return spawn
    parent = meta.get("parent_thread_id")
    if isinstance(parent, str) and parent and meta.get("thread_source") == "subagent":
        return {"parent_thread_id": parent, "depth": None,
                "agent_nickname": meta.get("agent_nickname"), "agent_role": None}
    return None


def codex_totals(record, totals):
    """Preenche os campos de token de uma linha do Codex a partir do último snapshot `total_token_usage`.

    `input_tokens` inclui `cached_input_tokens` e `total_tokens` é input mais
    output: checado nos 349 rollouts numa máquina que carregam uma divisão tipada, sem
    exceção. `reasoning_output_tokens` é parte de `output_tokens` em vez de ao lado dele, então
    nunca é somado em lugar nenhum.

    O Codex Desktop frequentemente escreve um snapshot cujos campos tipados são todos zero e cujo
    `total_tokens` sozinho está definido — 85 de 107 rollouts de topo do Desktop aqui. Ler isso como uma
    sessão que não gastou nada seria um erro na direção de grátis, então a linha mantém
    só `total`, carrega `partial`, e deixa todo campo tipado desconhecido para o relatório
    excluir das suas somas.
    """
    if not isinstance(totals, dict):
        return
    total = totals.get("total_tokens")
    record["total"] = total if isinstance(total, int) else None
    values = {}
    for name, field in CODEX_FIELDS:
        value = totals.get(field)
        values[name] = value if isinstance(value, int) else None
    if not any(values.values()):
        if record.get("total"):
            record["partial"] = True
        return
    if isinstance(values["input"], int) and isinstance(values["cache_read"], int):
        values["input"] = max(0, values["input"] - values["cache_read"])
    record.update(values)


def codex_days(raw_days, turns_by_day, record):
    """O mapa `days` de uma linha do Codex, a partir dos deltas entre seus snapshots cumulativos.

    Uma linha cujos campos tipados são desconhecidos — o snapshot do Codex Desktop carregando só
    `total_tokens` — não ganha fatia nenhuma: não há nada a fatiar, e um mapa de zeros se leria como
    dias que não custaram nada. `input` é feito líquido da parte em cache por dia, exatamente como
    `codex_totals` faz para o da própria linha.
    """
    if any(not isinstance(record.get(name), int) for name, _ in FIELDS):
        return {}
    days = {}
    for day, raw in raw_days.items():
        if not day:
            continue
        slice_ = empty_slice()
        for name, _ in FIELDS:
            slice_[name] = raw.get(name) or 0
        slice_["input"] -= slice_["cache_read"]
        days[day] = slice_
    for day, turns in turns_by_day.items():
        if day:
            days.setdefault(day, empty_slice())["turns"] += turns
    return days


def codex_by_model(raw_models, record):
    """A divisão por modelo de uma linha do Codex, a partir dos deltas entre seus snapshots cumulativos.

    `input` é feito líquido da parte em cache por modelo, exatamente como `codex_totals` faz para
    o da própria linha, então a parte de um modelo é cobrada da mesma forma que a linha é. Um campo que o rollout nunca
    reportou — `cache_write`, em todo rollout do Codex medido — é deixado de fora das partes como é
    deixado de fora da linha, em vez de escrito como um zero que a linha não alega. Uma linha cujos campos
    tipados são todos desconhecidos não ganha divisão nenhuma: não há nada a atribuir.
    """
    fields = [name for name, _ in FIELDS if isinstance(record.get(name), int)]
    if not fields:
        return {}
    parts = {}
    for model, raw in raw_models.items():
        if not model:
            continue
        part = dict((name, raw.get(name) or 0) for name in fields)
        if "input" in part and "cache_read" in part:
            part["input"] = max(part["input"] - part["cache_read"], 0)
        parts[model] = part
    return parts


def scan_codex(transcript, session_id="", cwd="", prior=None, rescan=False):
    """Uma linha de um rollout do Codex: uma sessão, ou uma thread de subagente quando foi lançada por spawn.

    Qual dos dois é vem de `codex_spawn` e de mais nada. Uma linha de subagente tem a mesma forma
    da que `_agent_row` constrói para o Claude Code, então `usage --by role` lê ambas sem
    saber qual runtime as escreveu.
    """
    events, models, totals, meta = [], [], None, {}
    started = ended = effort = ""
    turn = 0
    tool_names = {}
    malformed = 0
    # O Codex escreve um snapshot cumulativo em vez de um número por turno, então o gasto de um dia e o de um
    # esforço são as diferenças entre snapshots consecutivos, atribuídas à data do
    # snapshot que os fechou e ao esforço em vigor quando foi escrito.
    weights, raw_days, turns_by_day, last = {}, {}, {}, dict((name, 0) for name, _ in CODEX_FIELDS)
    # O mesmo delta, atribuído de uma segunda forma: ao modelo que `turn_context` nomeou por último. O Codex
    # muda de modelo no meio de uma thread, e uma thread que o fez não pode ser precificada só pelos seus totais.
    raw_models, model_now = {}, ""
    with open(transcript, encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                item = json.loads(line)
                payload = item.get("payload") or {}
                if not isinstance(payload, dict):
                    raise ValueError("invalid payload")
            except (ValueError, AttributeError):
                malformed += 1
                continue
            timestamp = item.get("timestamp") or ""
            started = started or timestamp
            ended = timestamp or ended
            if item.get("type") == "session_meta":
                # O primeiro `session_meta` é o próprio deste rollout. Um subagente que herdou o
                # histórico do seu pai carrega o meta do pai mais adiante — 36 de 307 aqui —
                # e ler esse entregaria ao filho o id do pai e a string `source` do
                # pai, que é como um subagente foi classificado como sessão da última vez.
                if meta:
                    continue
                meta = payload
                session_id = session_id or meta.get("id", "")
                cwd = cwd or meta.get("cwd", "")
            elif item.get("type") == "turn_context":
                turn += 1
                turns_by_day[timestamp[:10]] = turns_by_day.get(timestamp[:10], 0) + 1
                if payload.get("model"):
                    model_now = payload["model"]
                    if model_now not in models:
                        models.append(model_now)
                # O esforço em vigor daqui em diante: o Codex o registra por turno e ele muda
                # no meio da sessão, `ultra` e `max` entre os valores vistos.
                if isinstance(payload.get("effort"), str) and payload["effort"].strip():
                    effort = payload["effort"].strip()
            elif item.get("type") == "event_msg" and payload.get("type") == "token_count":
                value = (payload.get("info") or {}).get("total_token_usage")
                if isinstance(value, dict):
                    totals = value  # Snapshot cumulativo; somar snapshots conta o uso em dobro.
                    slice_ = raw_days.setdefault(timestamp[:10], empty_slice())
                    part = raw_models.setdefault(model_now, empty_slice()) if model_now else None
                    for name, field in CODEX_FIELDS:
                        now = value.get(field)
                        if not isinstance(now, int):
                            continue
                        slice_[name] += now - last[name]
                        if part is not None:
                            part[name] += now - last[name]
                        if name == "output":
                            weights[effort] = weights.get(effort, 0) + (now - last[name])
                        last[name] = now
            elif item.get("type") == "response_item":
                kind = payload.get("type")
                call_id = payload.get("call_id", "")
                if kind in ("function_call", "custom_tool_call"):
                    name = payload.get("name", "")
                    name = {"exec_command": "Bash", "spawn_agent": "Agent"}.get(name, name)
                    arguments = payload.get("arguments", payload.get("input", {}))
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except ValueError:
                            arguments = {"command": arguments}
                    if isinstance(arguments, dict) and "cmd" in arguments:
                        arguments = dict(arguments, command=arguments["cmd"])
                    tool_names[call_id] = name
                    events.append({"kind": "tool_use", "turn": turn, "id": call_id,
                                   "name": name, "input": arguments})
                elif kind in ("function_call_output", "custom_tool_call_output"):
                    name = tool_names.get(call_id, "")
                    events.append({"kind": "tool_result", "turn": turn, "tool_use_id": call_id,
                                   "tool_name": name, "text": _result_text(payload.get("output"), name)})
                elif kind == "message" and payload.get("role") == "assistant":
                    text = "\n".join(x.get("text", "") for x in payload.get("content", []) if isinstance(x, dict))
                    events.append({"kind": "assistant_text", "turn": turn, "text": text,
                                   "final": payload.get("phase") == "final_answer"})
    if not session_id:
        return None
    spawn = codex_spawn(meta)
    # Um subagente cujo pai não pode ser nomeado se uniria a nada e não apareceria em relatório nenhum, então
    # é mantido como a sessão sob a qual foi registrado em vez de virar uma linha invisível.
    parent = (spawn or {}).get("parent_thread_id") or meta.get("session_id") or ""
    if spawn and parent and parent != session_id:
        row = {
            "kind": "subagent", "runtime": "codex",
            "runtime_version": meta.get("cli_version"),
            "harness_version": stamped_version(rescan),
            # `session_id` é a thread que gerou esta, que na profundidade 1 é a sessão
            # e mais fundo é outro subagente; `spawn_depth` é o que diz qual.
            "session_id": parent, "agent_id": session_id,
            "repo": Path(cwd).name,
            # O Codex deixa `agent_role` nulo e nomeia a thread em todo rollout medido
            # aqui, então o apelido é o fallback que de fato carrega o relatório.
            "agent_type": spawn.get("agent_role") or spawn.get("agent_nickname")
                          or meta.get("agent_nickname") or "unknown",
            "model": models[-1] if models else "",
            "effort": dominant(weights) or effort,
            "tool_calls": sum(1 for e in events if e["kind"] == "tool_use"),
            "spawn_depth": spawn.get("depth"), "workflow": None,
            # O Codex não registra id de uso de ferramenta do lado do pai no filho, então não há nada para
            # unir um reroteamento a; null é essa ausência, não uma medição de nenhum reroteamento.
            "tool_use_id": None, "requested_type": None, "rerouted": False,
            # O Codex não dispara evento de retorno de subagente na thread pai e escreve o filho num
            # rollout próprio, então nenhum retorno é unido a esta linha e nenhum é medido;
            # `adapters/codex/capabilities.json` nomeia a lacuna.
            "return_path": None, "return_over_budget": None, "return_measured": None,
            "turns": turn, "started": started, "ended": ended,
            "parse_failures": malformed,
        }
        codex_totals(row, totals)
        return row
    record = {"kind": "session", "runtime": "codex",
              "runtime_version": meta.get("cli_version"),
              "harness_version": stamped_version(rescan), "session_id": session_id,
              "repo": Path(cwd).name, "branch": git(cwd, "rev-parse", "--abbrev-ref", "HEAD") if cwd else "",
              "models": models, "started": started, "ended": ended, "turns": turn,
              "subagents": sum(e.get("name") == "Agent" and e["kind"] == "tool_use" for e in events),
              "stances": (prior or {}).get("stances") or stances(), "input": None, "output": None,
              "cache_read": None, "cache_write": None, "parse_failures": malformed}
    if rescan and not (prior or {}).get("stances"):
        record["stances_source"] = "rescan"
    attributed(record, prior, rescan)
    codex_totals(record, totals)
    chosen = dominant(weights) or effort
    record["effort"] = chosen or None
    record["effort_source"] = "turn_context" if chosen else None
    # O Codex reporta snapshots cumulativos, não um número por registro, então não há soma por linha
    # contra a qual medir uma deduplicação e nenhuma é inventada.
    record["raw_vs_deduped"] = RAW_UNKNOWN
    days = codex_days(raw_days, turns_by_day, record)
    if slices_agree(days, record):
        record["days"] = days
    parts = codex_by_model(raw_models, record)
    if models_agree(parts, record):
        record["by_model"] = parts
    errors = []
    try:
        module = detectors()
        record["counts"] = module.counts(events)
        record["rules"] = {did: len(hits) for did, hits in module.run(events, record["stances"], errors=errors).items()}
        if errors:
            record["rules_errors"] = errors
    except Exception as exc:
        record["rules_error"] = type(exc).__name__
    return record


def row_key(row):
    """O que identifica uma linha. Uma linha escrita antes de `kind` existir é uma sessão, como sempre foi."""
    return (row.get("session_id"), row.get("runtime", "claude-code"),
            row.get("kind") or "session", row.get("agent_id") or "")


def upsert(record, path=None, drop=()):
    """Substitui as linhas que estes registros identificam, ou as anexa. Aceita um registro ou vários.

    Um lote mantém o último registro para uma chave, então uma reescrita travada é tudo o que uma revarredura inteira custa.

    `drop` são as chaves a apagar diretamente. Uma linha que muda de `kind` muda sua chave, então um
    upsert sozinho deixaria a linha antiga ao lado da nova e o razão carregaria a mesma
    thread duas vezes; nomear a chave obsoleta é como uma reclassificação migra em vez de dobrar.
    """
    records = [stamped(record)] if isinstance(record, dict) else list(
        {row_key(r): stamped(r) for r in record}.values())
    drop = set(drop)
    if not records and not drop:
        return Path(path) if path else usage_path()
    path = Path(path) if path else usage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = acquire(path)
    if lock is None:
        raise RuntimeError("usage lock unavailable; no record was overwritten")
    held = True
    try:
        rows = []
        replaced = {row_key(r) for r in records} | drop
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        # Uma linha existente é mantida exatamente como foi escrita, e comparada pela sua chave dobrada:
        # a reescrita substitui registros, não migra os de mais ninguém.
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict) and row_key(fold(row)) not in replaced:
                rows.append(row)
        rows.extend(records)
        tmp = path.with_name("{}.{}.tmp".format(path.name, os.getpid()))
        tmp.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        os.replace(str(tmp), str(path))
    finally:
        release(lock, held)
    return path


def acquire(path):
    """O arquivo de trava ao lado do razão, mantido, ou None quando outro escritor não o soltaria."""
    lock = path.with_name(path.name + ".lock")
    for _ in range(20):
        try:
            os.close(os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return lock
        except FileExistsError:
            time.sleep(0.05)
        except OSError:
            return None
    return None


def release(lock, held=True):
    if held and lock is not None:
        try:
            lock.unlink()
        except OSError:
            pass


def errors_path(path=None):
    """`usage.errors.jsonl` ao lado do razão que este caminho nomeia."""
    return (Path(path) if path else usage_path()).with_suffix(".errors.jsonl")


def record_error(error, path=None, where=""):
    """Anexa uma falha engolida ao lado do razão. Nunca levanta exceção.

    O mesmo arquivo em que a própria falha deste hook cai, porque uma escrita que falhou silenciosamente é
    desconhecida em vez de ausente: um relatório sem linhas nele tem um lugar para ser explicado. O
    tipo da exceção, nunca sua mensagem — uma mensagem pode carregar um caminho ou um valor.
    """
    entry = {"time": time.time(), "error": type(error).__name__ if isinstance(error, BaseException)
             else str(error)}
    if where:
        entry["where"] = where
    try:
        target = errors_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry) + "\n")
    except OSError:
        return False
    return True


def append_row(record, path=None):
    """Anexa uma linha ao razão sem reescrevê-lo, e retorna seu caminho.

    Para uma linha que nada jamais substitui. `upsert` lê e reescreve o arquivo inteiro, o que é certo
    para um registro de sessão atualizado enquanto a sessão roda e errado para uma linha escrita uma vez
    dentro do orçamento de um hook: um razão de dezenas de milhares de linhas seria relido e
    reescrito a cada chamada de provedor. O append é uma escrita de uma linha, sob a mesma trava,
    então uma reescrita concorrente não pode se intercalar com ela nem perdê-la.
    """
    path = Path(path) if path else usage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = acquire(path)
    if lock is None:
        raise RuntimeError("usage lock unavailable; the record was not appended")
    try:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(stamped(record)) + "\n")
    finally:
        release(lock)
    return path


def export(records):
    """Oferece linhas a um endpoint OTLP configurado, depois que o razão já as contém.

    Desligado por padrão, e silencioso em todo modo de falha: a linha está em disco, então um coletor que
    está caído, lento ou mal configurado custa uma linha em `usage.errors.jsonl` e nada mais.
    `harness usage export --since` reproduz o que foi perdido. Veja `telemetry.py`.
    """
    module = sibling("telemetry", required=False)
    if module is None:
        return 0, 0
    try:
        return module.export_rows(records, version=harness_version() or "",
                                  errors_path=usage_path().with_suffix(".errors.jsonl"))
    except Exception:
        return 0, 0


def recorded(path=None):
    """Os registros já em arquivo, por id de sessão, para uma revarredura poder manter o que não pode saber."""
    try:
        text = (Path(path) if path else usage_path()).read_text(encoding="utf-8")
    except OSError:
        return {}
    out = {}
    for row in ledger_rows(text):
        if row.get("session_id") and (row.get("kind") or "session") == "session":
            out[row["session_id"]] = row
    return out


def workers_dir():
    return Path.home() / ".local" / "state" / "agent-harness" / "workers"


def stamp(epoch):
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(float(epoch)))
    except (TypeError, ValueError):
        return ""


def worker_rows(cutoff=0.0):
    """Uma linha `kind: "worker"` por worker de `harness role run`, do seu próprio `status.json`.

    Um worker é uma sessão de CLI isolada cujo runtime reporta seus próprios totais de token; `workers.py`
    os escreve no registro de status. Um worker que não reportou nenhum mantém sua linha e deixa os
    campos de token desconhecidos, que o relatório então exclui das suas somas em vez de ler como
    zero. O nome do papel é o tipo de agente, então um worker e um subagente se agrupam da mesma forma.

    Só uma execução completa é registrada: uma execução que estourou o tempo, falhou ou ainda está rodando não tem
    total que valha a pena comparar com o de outro papel. A janela é aplicada pela hora de modificação
    do arquivo antes de ele ser aberto, para que uma varredura leia as execuções recentes e não o arquivo morto, e
    um registro cujos próprios timestamps são inutilizáveis é datado por essa mesma mtime em vez de por um
    carimbo que o relatório jamais poderia colocar numa janela.
    """
    rows = []
    try:
        paths = sorted(workers_dir().glob("*/status.json"))
    except OSError:
        return rows
    for path in paths:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict) or not record.get("id") or not record.get("role"):
            continue
        if record.get("status") != "completed":
            continue
        ended = stamp(record.get("finished_at") or record.get("started_at")) or stamp(mtime)
        usage = record.get("usage") if isinstance(record.get("usage"), dict) else {}
        row = {"kind": "worker", "runtime": record.get("runtime") or "claude-code",
               # Carimbado por `workers.py` quando a execução começou, para que uma varredura meses depois ainda
               # nomeie a versão que a rodou em vez da versão que lê o arquivo.
               "harness_version": record.get("harness_version"),
               # O mesmo para o perfil; uma execução de antes do campo não é atribuída.
               FINGERPRINT_KEY: record.get(FINGERPRINT_KEY),
               "session_id": record["id"], "agent_id": record["id"],
               "agent_type": record["role"], "repo": os.path.basename(str(record.get("workspace") or "").rstrip("/")),
               "model": record.get("model") or "", "effort": record.get("effort") or "",
               "tool_calls": usage.get("tool_calls"), "spawn_depth": 1, "rerouted": False,
               # Um worker é lançado por nome a partir da CLI, então não há tipo pedido nem
               # chamada de ferramenta pai para unir; null é essa ausência, não uma resposta vazia. Presente
               # para que toda linha que não é de sessão carregue as mesmas chaves.
               "requested_type": None, "tool_use_id": None,
               "status": record.get("status"), "stances": record.get("stances") or {},
               "started": stamp(record.get("started_at")) or ended, "ended": ended}
        for name, _ in FIELDS:
            row[name] = usage.get(name)
        rows.append(row)
    return rows


def backup(path):
    """Uma cópia do razão ao lado dele, tirada antes de uma revarredura reescrever ou apagar qualquer linha."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    target = path.with_name(path.name + ".bak")
    try:
        target.write_bytes(data)
    except OSError:
        return None
    return target


def rescan(days=30):
    """Relê toda transcrição na janela e reescreve o arquivo uma vez.

    Um preenchimento retroativo de um mês lê centenas de transcrições. Fazer upsert de cada uma separadamente
    tomaria a trava e reescreveria o arquivo inteiro tantas vezes, então as linhas são coletadas e
    escritas numa única passagem travada; `SessionEnd` mantém o caminho de uma-sessão.

    O Codex é lido tanto de `sessions/` quanto de `archived_sessions/`, porque o Codex move um rollout
    para o segundo diretório sem mudar um byte dele: 96 dos 131 rollouts de topo numa
    máquina viviam só ali, o que é a maior parte da lacuna de captura que esta busca fecha.
    """
    cutoff = time.time() - max(days, 0) * 86400
    prior = recorded()
    found, batch = 0, []
    codex = codex_home()
    paths = list(projects_dir().glob("*/*.jsonl"))
    for folder in ("sessions", "archived_sessions"):
        paths += list((codex / folder).rglob("*.jsonl"))
    for path in sorted(paths):
        # Uma transcrição de subagente do Claude Code é lida a partir da sua sessão, nunca como uma: ela não carrega
        # id de sessão próprio, então registrá-la aqui inventaria uma sessão que nunca rodou.
        # Um subagente do Codex é o oposto — seu próprio rollout, nomeado como qualquer outro — então é
        # percorrido aqui e distinguido por `codex_spawn` assim que sua primeira linha for lida.
        if path.name.startswith("agent-") or path.parent.name == "subagents":
            continue
        try:
            if path.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        # Uma transcrição é nomeada pela sua sessão, que é como um preenchimento retroativo encontra o registro que
        # está atualizando antes de ter lido uma linha do arquivo.
        ident = path.stem
        try:
            with path.open() as stream:
                first = json.loads(stream.readline())
            if first.get("type") == "session_meta":
                ident = first.get("payload", {}).get("id", ident)
        except (OSError, ValueError):
            pass
        records = scan_all(path, prior=prior.get(ident), rescan=True)
        # Uma transcrição não diz qual perfil a rodou. Uma sessão que o razão já guarda
        # mantém a impressão digital com que sua linha ao vivo foi escrita, e seus subagentes rodaram sob o
        # mesmo perfil; uma sessão que ele não guarda não é atribuída.
        known = (prior.get(ident) or {}).get(FINGERPRINT_KEY)
        for record in records:
            record[FINGERPRINT_KEY] = known
        if records:
            batch.extend(records)
            found += 1
    batch.extend(worker_rows(cutoff))
    children = {}
    for row in batch:
        if row.get("kind") == "subagent" and row.get("runtime") == "codex":
            children[row["session_id"]] = children.get(row["session_id"], 0) + 1
    # O Codex conta os subagentes de uma sessão a partir das suas próprias chamadas `spawn_agent`, o que perde um spawn
    # cujo rollout esta busca encontrou mas cuja chamada pai foi compactada para fora; o maior dos
    # dois é o que é sustentado por um arquivo em disco.
    for row in batch:
        if row.get("kind") == "session" and row.get("runtime") == "codex":
            row["subagents"] = max(row.get("subagents") or 0, children.get(row["session_id"], 0))
    drop = set((row["agent_id"], "codex", "session", "")
               for row in batch
               if row.get("kind") == "subagent" and row.get("runtime") == "codex")
    if batch or drop:
        backup(usage_path())
        upsert(batch, drop=drop)
    return found


def main(argv):
    if argv and argv[0] == "--worker":
        transcript, session_id, cwd = (list(argv[1:]) + ["", "", ""])[:3]
        # Workers de execução de papel não têm sessão própria para terminar, então o worker desacoplado que
        # registra esta sessão também varre os recentes para linhas.
        records = scan_all(transcript, session_id, cwd) + worker_rows(time.time() - 30 * 86400)
        # Carimbado aqui assim como em `upsert`, para que o que é oferecido ao vivo seja o que uma reprodução lê.
        records = [stamped(r) for r in records]
        if records:
            upsert(records)
            export(records)
        return 0
    if argv and argv[0] == "--rescan":
        try:
            days = int(argv[1]) if len(argv) > 1 else 30
        except ValueError:
            days = 30
        print("recorded {} session(s) from transcripts of the last {} day(s)".format(rescan(days), days))
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    # O Claude Code nomeia o arquivo `transcript_path`. O payload de SessionEnd do Codex não foi
    # observado aqui — nenhuma CLI do Codex está instalada na máquina onde isto foi medido — então os
    # dois nomes que ele plausivelmente poderia usar são aceitos e a revarredura permanece o caminho que
    # a captura do Codex de fato sabe percorrer. Veja `docs/usage.md`.
    payload = payload or {}
    transcript = (payload.get("transcript_path") or payload.get("rollout_path")
                  or payload.get("session_path") or "")
    if not transcript:
        return 0
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--worker", str(transcript),
         payload.get("session_id") or "", payload.get("cwd") or ""],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:
        record_error(exc)
        sys.exit(1)
