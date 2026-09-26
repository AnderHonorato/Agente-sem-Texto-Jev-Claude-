#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""O pacote de regras deste repositório, sobre o motor de medição `ruleprobe` vendorizado.

O motor — o schema de eventos, a decomposição de shell, o registro e `run()` — é `ruleprobe`,
vendorizado como um wheel em `lib/vendor` ao lado de `tomlkit` e importado abaixo. Seis
detectores genéricos vêm com ele (`transcript-hygiene/whole-file-cat`,
`transcript-hygiene/unfiltered-find`, `verification/no-verify`, `secrets/secret-in-write`,
`cache-hygiene/compact`, `cache-hygiene/model-switch`); este arquivo guarda os onze que são sobre
*estas* regras, as isenções, e o registro que `bin/harness` e `usage-log.py` leem.

Isto não é um hook: não tem `main()` nem evento de ciclo de vida. `usage-log.py` constrói a lista
de eventos na passagem que já faz sobre um transcript e chama `run()`; `bin/harness lint`
importa `DETECTORS` e `OPT_OUT`, para checar que toda regra é medida ou tem uma isenção com um
motivo, e pega `SECRET_PATTERNS` daqui. Ambos carregam este arquivo por caminho a partir do
checkout, por isso o wheel vendorizado está sempre alcançável.

Schema de eventos, hits, custo e as falhas conhecidas do parse de shell: `ruleprobe.events`,
`ruleprobe.registry` e `ruleprobe.shell`. Os dois fatos que um leitor deste arquivo precisa são
que `run()` retorna `{detector_id: [Hit, ...]}` com os detectores vazios omitidos, e que um hit
nunca carrega um trecho — o transcript é a evidência, e `usage.jsonl` não guarda texto de
comando algum (decisão 3 do plano).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent
                       / "lib" / "vendor" / "ruleprobe-0.1.0-py3-none-any.whl"))
from ruleprobe import Registry, analyse, counts, run as _run  # noqa: E402,F401
from ruleprobe.detectors import common as generic  # noqa: E402
from ruleprobe.events import hit, input_of, text_of  # noqa: E402
from ruleprobe.registry import Detector as _Detector  # noqa: E402
from ruleprobe.shell import (MAX_COMMAND, MARKER_RE, SUB_PLACEHOLDER, git_calls,  # noqa: E402
                             has_redirect, normalise, operands, pipelines, strip_heredocs)

# O lint faz grep na árvore por essas formas e o próprio detector `secret-in-write` do motor lê a
# mesma lista, então há uma única fonte de verdade para os dois e ela é a do wheel.
SECRET_PATTERNS = generic.SECRET_PATTERNS

# Os três abridores e a frase de fechamento são lidos de `claude/output-styles/scannable.md`
# (seções 1 e 9) no momento do build e congelados aqui; este módulo nunca lê um arquivo em tempo de execução.
BANNED_OPENERS = ("I started by", "After investigating", "Great question")
BANNED_CLOSER = "Let me know if"

# As duas formas que `decisions-and-plans` prescreve — um bloco "Decisions" em lote, ou uma
# linha de recomendação — e os marcadores que mostram que outro caminho foi nomeado ao lado
# deles. O gatilho é uma linha que *abre* com a palavra; um "I recommend" inline em prosa
# corrida não é um bloco de decisão e não dispara.
DECISION_RE = re.compile(
    r"^[\s*_>#|-]*recommend(?:ation|ed|ing|s)?\b"
    r"|\brecommendation:"
    r"|^[\s*_>#|-]*decisions?\b[\s*_:-]*$",
    re.I | re.M,
)
ALTERNATIVE_RE = re.compile(
    r"\balternativ|^[\s*_>#|-]*alt\b|\bagainst:|\bhonest case\b|^[\s*_>#|-]*option\s",
    re.I | re.M,
)

# `WebSearch` é limitado por sessão por claude/rules/research-and-verification.md.
SEARCH_CAP = 200

# Agentes cuja própria definição carrega o limite de palavras, para que um brief não precise repeti-lo.
CAPPED_AGENTS = frozenset(("log-compressor", "gatherer", "reviewer", "spec-reviewer", "design-judge"))

CONVENTIONAL_RE = re.compile(r"^(feat|fix|chore|docs|refactor|test|perf|build|ci|style|revert)(\([^)]+\))?!?: \S")
# Toda forma em que um limite de palavras é escrito: "at most 400 words", "400 words max",
# "400 words or fewer", "within 400 words", "a 400-word cap", "cap the return at 400 words". Um
# limite sempre carrega um número, então "keep it short" ainda é uma falha.
WORD_CAP_RE = re.compile(
    r"(?i)(?:(?:at most|no more than|under|within|max(?:imum)?|≤|<=)\s*\d+\s*[- ]?words?"
    r"|\d+\s*[- ]?words?\s*(?:or (?:fewer|less)|max(?:imum)?|cap)"
    r"|\d+\s*[- ]?word\s+cap"
    r"|cap[^.\n]{0,40}?\d+\s*[- ]?words?"
    r"|word\s+cap\s*(?:of\s+)?\d+)"
)
# Um brief que já se precifica sozinho: a frase que `brief-guard` escreve, ou um gasto que o
# autor escreveu com suas próprias palavras ("under 20k output tokens", "at most 30 tool calls").
# Um gasto é três coisas juntas — uma palavra limitante, uma quantidade e uma das duas unidades —
# porque qualquer uma delas sozinha é prosa comum: "fix the 3 tool calls in parser.py" não conta
# nada, e "the budget of the project" também não.
_BUDGET_LIMIT = (r"(?:at most|no more than|not more than|fewer than|less than|up to|under|within"
                 r"|about|around|approx(?:\.|imately)?|expected|expect|spend|budget(?:ed)?|cap(?:ped)?"
                 r"|limit(?:ed)?|max(?:imum)?|≤|<=|<|~)")
_BUDGET_UNIT = r"(?:(?:output|completion)[- ]tokens?|tool[- ]?calls?)"
BUDGET_RE = re.compile(
    r"(?i)(?:expected spend:"
    r"|" + _BUDGET_LIMIT + r"(?:\s+[\w,'’-]+){0,3}\s*"
    r"\d[\d,._]*\s*[kKmM]?\s*(?:of\s+)?" + _BUDGET_UNIT + r")"
)
# As duas marcas do portão de autonomia: o prefixo atrás do qual o modelo re-roda um comando
# negado, e a assinatura que o hook de avaliação escreve na razão com que nega. O padrão de
# marcador espelha o próprio `MARKER_RE` de `grade-bash.py`, então o que o portão deixa passar é
# o que isto conta; um valor entre aspas (`HARNESS_CONFIRMED="1"`) não é o marcador lá e não é um aqui.
_COMMENT_RE = re.compile(r"^(?:\s*(?:#[^\n]*)?\n)+")
_CONFIRMED_RE = re.compile(r"^\s*(?:env\s+)?HARNESS_CONFIRMED=1\s*;?\s*")
GRADE_SIGNATURE = "(grade-bash hook,"
# Um caminho cujo próprio nome diz que guarda uma credencial, pelo nome-base; veja `_is_secret_path`.
ENV_EXAMPLES = frozenset(("example", "sample", "template", "dist"))
KEY_SUFFIXES = (".pem", ".p12", ".pfx")
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,})(.*)$")


class Detector(_Detector):
    """O `Detector` do motor sob os dois nomes de campo que o registro deste repositório usa.

    `kind` é o `event` do motor e `stance` é seu `gate`; ambos são lidos pelos testes e por
    `check_detectors`, e nenhum vale a pena renomear através de um ledger armazenado.
    """

    __slots__ = ()

    @property
    def kind(self):
        return self.event

    @property
    def stance(self):
        return self.gate


# --- auxiliares ------------------------------------------------------------------------


def _messages_of(parsed, args):
    """Todo valor `-m` de um `git commit`, em ordem, com marcadores resolvidos para seu corpo.

    `git commit` sem `-m` — `--amend --no-edit`, `-F file`, `-C <commit>` — não carrega
    mensagem alguma aqui: um heredoc em outro lugar do comando pertence a esse outro comando, não
    ao commit. Nem um commit cuja mensagem é uma substituição que o parse não conseguiu abrir
    (`-m "$(cat msg.txt)"`): uma mensagem não lida não é uma ruim, então o commit inteiro
    produz nenhuma mensagem em vez de um assunto vazio.
    """
    out = []
    i = 0
    while i < len(args):
        token = args[i]
        value = None
        if token == "--message":
            value = args[i + 1] if i + 1 < len(args) else ""
            i += 2
        elif token.startswith("--message="):
            value = token.split("=", 1)[1]
            i += 1
        elif token.startswith("-") and not token.startswith("--") and "m" in token[1:]:
            # Um agrupamento curto: tudo depois do primeiro `m` é o valor, como o git o lê,
            # então `-am`, `-sm` e `-mfeat: x` caem todos aqui.
            rest = token[1:].split("m", 1)[1]
            if rest:
                value = rest
                i += 1
            else:
                value = args[i + 1] if i + 1 < len(args) else ""
                i += 2
        else:
            i += 1
            continue
        value = text_of(value)
        match = MARKER_RE.match(value)
        if match:
            index = int(match.group(1))
            value = parsed.heredocs[index] if index < len(parsed.heredocs) else ""
        if not value.strip() or SUB_PLACEHOLDER in value or "$(" in value:
            return []
        out.append(value)
    return out


def _commit_messages(parsed):
    """Os valores `-m` de cada `git commit` num comando parseado, commit por commit."""
    return [_messages_of(parsed, args) for _, sub, args in git_calls(parsed, ("commit",))]


def _is_secret_path(path):
    """Um caminho cujo próprio nome diz que guarda uma credencial."""
    base = path.rstrip("/").rsplit("/", 1)[-1]
    if base == ".env":
        return True
    if base.startswith(".env."):
        return base.split(".", 2)[2].lower() not in ENV_EXAMPLES
    if base.lower().endswith(KEY_SUFFIXES):
        return True
    if "id_rsa" in base or "id_ed25519" in base:
        return True
    return base.split(".", 1)[0] == "credentials"


def _unmarked(text):
    """`text` com trechos entre aspas e crases apagados, para que uma frase em discussão não
    seja lida como uma frase em uso."""
    return re.sub(r"`[^`]*`|'[^'\n]*'|\"[^\"\n]*\"", " ", text)


def _fenced_lines(text):
    """Toda linha dentro de um bloco de código cercado, pela regra de fechamento do
    CommonMark: uma cerca de fechamento carrega ao menos tantas crases quanto o abridor e
    nenhuma string de informação."""
    out, opener = [], None
    for line in (text or "").split("\n"):
        match = _FENCE_RE.match(line)
        if opener is None:
            if match:
                opener = len(match.group(1))
            continue
        if match and len(match.group(1)) >= opener and not match.group(2).strip():
            opener = None
            continue
        out.append(line)
    return out


# --- detectores ---------------------------------------------------------------------


def model_wrote_no_cap(events, ctx):
    """Um brief de `Agent` que o modelo escreveu sem limite de palavras, para um agente cuja
    definição não carrega nenhum.

    Isto mede o brief como foi escrito, nunca como foi entregue. O Claude Code escreve o bloco
    `tool_use` com a entrada que o modelo produziu; o `updatedInput` de um hook de `PreToolUse` é
    registrado separadamente, numa linha `attachment` do tipo `hook_success`, que o construtor de
    eventos não lê. Então todo brief que `brief-guard` limitou ainda é um hit aqui, e a contagem
    é uma medida de conformidade do orquestrador — do mesmo jeito que `usage-log.mark_reroutes`
    mede o trabalho do hook de disparo pelo que aconteceu em vez de pelo que o hook anunciou.

    O id diz isso desde #324: o antigo `transcript-hygiene/brief-without-cap` lia como uma
    contagem de briefs sem limite alcançando um subagente, o que, com o hook instalado, é um
    número que este módulo não consegue ver e é muito próximo de zero. `promote?` neste detector
    significa que o orquestrador não escreve limites e o hook está carregando a regra.
    """
    hits = []
    for event in events:
        if event.get("kind") != "tool_use" or event.get("name") != "Agent":
            continue
        data = input_of(event)
        if text_of(data.get("subagent_type")) in CAPPED_AGENTS:
            continue
        if not WORD_CAP_RE.search(text_of(data.get("prompt"))):
            hits.append(hit(event))
    return hits


def executed_from_summary(events, ctx):
    """Um comando Bash cuja primeira aparição na sessão foi dentro de um retorno de `Agent`.

    Um comando que a sessão já rodou, e que um subagente depois citou de volta, não é um hit: a
    regra é sobre agir sobre texto que chegou de um subagente, não sobre repetição.
    """
    origin, hits = {}, []
    for event in events:
        kind = event.get("kind")
        if kind == "tool_result" and event.get("tool_name") == "Agent":
            for line in _fenced_lines(text_of(event.get("text"))):
                text = " ".join(line.split())
                if text:
                    origin.setdefault(text, "agent")
        elif kind == "tool_use" and event.get("name") == "Bash":
            command = text_of(input_of(event).get("command"))
            if not command:
                continue
            text = normalise(command)
            if origin.setdefault(text, "bash") == "agent":
                hits.append(hit(event))
    return hits


def git_add_secret_file(events, ctx):
    """`git add` de um caminho cujo nome diz que guarda uma credencial."""
    hits = []
    for parsed in ctx.bash:
        for _, _, args in git_calls(parsed, ("add",)):
            if any(_is_secret_path(a) for a in args if not a.startswith("-")):
                hits.append(hit(parsed.event))
                break
    return hits


def search_over_cap(events, ctx):
    """Um único hit na busca que leva a sessão além do teto por sessão."""
    seen = 0
    for event in events:
        if event.get("kind") == "tool_use" and event.get("name") == "WebSearch":
            seen += 1
            if seen == SEARCH_CAP + 1:
                return [hit(event)]
    return []


def banned_opener(events, ctx):
    hits = []
    for event in ctx.finals:
        text = text_of(event.get("text"))
        opener = re.sub(r"^[\s*#>_\-]+", "", text)
        if opener.startswith(BANNED_OPENERS) or BANNED_CLOSER in _unmarked(text):
            hits.append(hit(event, tool_use_id=False))
    return hits


def second_table(events, ctx):
    """Dois ou mais blocos de tabela numa mensagem final; um bloco é duas ou mais linhas
    consecutivas começando com `|`."""
    hits = []
    for event in ctx.finals:
        blocks, run_len = 0, 0
        for line in text_of(event.get("text")).split("\n"):
            if line.lstrip().startswith("|"):
                run_len += 1
                if run_len == 2:
                    blocks += 1
            else:
                run_len = 0
        if blocks >= 2:
            hits.append(hit(event, tool_use_id=False))
    return hits


# A voz `concise` proíbe o esqueleto que outras vozes usavam: os rótulos de seção de um template
# de resposta. Palavras de status não estão na lista, porque a stance as permite ao reportar uma
# correção. Um rótulo só conta em posição de rótulo: fechado por dois-pontos (depois de negrito
# fechado ou não), embrulhado inteiro em negrito, ou como um cabeçalho. Uma palavra nua no fim de
# uma linha é um item de lista ou prosa.
_SCAFFOLD_LABELS = (r"(?:What changed|What you need to know|What you need to do|Still open|"
                    r"Verification|Why|The catch|Catch|Alternatives)")
_LIST_MARKER = r"^\s{0,3}(?:(?:[-*+]|\d+[.)])\s+)?"
SCAFFOLD_LABEL_RE = re.compile(
    _LIST_MARKER + _SCAFFOLD_LABELS + r"\s*:"
    r"|" + _LIST_MARKER + r"(\*\*|__)\s*" + _SCAFFOLD_LABELS + r"\s*:?\s*\1"
    r"|^\s{0,3}#{1,6}\s+(?:\*\*|__)?" + _SCAFFOLD_LABELS + r"\s*:?\s*(?:\*\*|__)?\s*:?\s*#*\s*$",
    re.IGNORECASE)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")


# Cercas de crase e til, só para `_unfenced_lines`; `_fenced_lines` mantém `_FENCE_RE` para que
# os detectores que leem comandos cercados mantenham seu comportamento medido.
_ANY_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")


def _unfenced_lines(text):
    """Toda linha fora de um bloco de código cercado, crase ou til, pela regra de fechamento do
    CommonMark: o mesmo caractere de cerca, ao menos tantos dele, e nenhuma string de informação."""
    out, opener = [], None
    for line in (text or "").split("\n"):
        match = _ANY_FENCE_RE.match(line)
        if opener is None:
            if match:
                opener = match.group(1)
            else:
                out.append(line)
        elif (match and match.group(1)[0] == opener[0] and len(match.group(1)) >= len(opener)
              and not match.group(2).strip()):
            opener = None
    return out


def scaffold_leak(events, ctx):
    """Uma mensagem final que usa os rótulos de seção de um template de resposta, fora de cercas
    de código; uma menção entre crases ou aspas não é um rótulo. Um hit por mensagem."""
    hits = []
    for event in ctx.finals:
        for line in _unfenced_lines(text_of(event.get("text"))):
            line = _unmarked(line)
            if SCAFFOLD_LABEL_RE.search(line):
                hits.append(hit(event, tool_use_id=False))
                break
    return hits


def heading_first(events, ctx):
    """Uma mensagem final cuja primeira linha não vazia é um cabeçalho markdown."""
    hits = []
    for event in ctx.finals:
        lines = [l for l in text_of(event.get("text")).split("\n") if l.strip()]
        if lines and HEADING_RE.match(lines[0]):
            hits.append(hit(event, tool_use_id=False))
    return hits


def recommendation_without_alternative(events, ctx):
    """Uma mensagem final que decide entre caminhos e nomeia só um. A regra pede "as
    alternativas com seu caso honesto", então um bloco `Decisions` em lote ou uma linha de
    recomendação isolada é a forma que ela proíbe. Marcadores são lidos do texto bruto em vez do
    texto sem marcas, para que uma alternativa nomeada dentro de uma citação ainda conte como nomeada."""
    hits = []
    for event in ctx.finals:
        text = text_of(event.get("text"))
        if DECISION_RE.search(_unmarked(text)) and not ALTERNATIVE_RE.search(text):
            hits.append(hit(event, tool_use_id=False))
    return hits


def non_conventional(events, ctx):
    """Um assunto de commit que não é uma linha de Conventional Commit."""
    hits = []
    for parsed in ctx.bash:
        for messages in _commit_messages(parsed):
            if not messages:
                continue
            subject = messages[0].strip().split("\n")[0].strip()
            if subject and not CONVENTIONAL_RE.match(subject):
                hits.append(hit(parsed.event))
                break
    return hits


def missing_trailer(events, ctx):
    """Um commit cuja mensagem não carrega linha `Co-Authored-By:` nenhuma, em nenhum `-m`."""
    hits = []
    for parsed in ctx.bash:
        for messages in _commit_messages(parsed):
            if not messages:
                continue
            if not re.search(r"(?im)^\s*Co-Authored-By:", "\n".join(messages)):
                hits.append(hit(parsed.event))
                break
    return hits


def confirmed_irreversible(events, ctx):
    """Um comando re-rodado atrás do marcador, que é uma ação de nota 3 à qual o usuário disse sim.

    `env` pode carregar a atribuição, como o shell permite, e linhas em branco ou de comentário
    no início não são nada que o shell roda; qualquer outra coisa antes do marcador significa que
    o portão viu um comando diferente deste, então um marcador enterrado no meio do comando não
    confirma nada e não conta nada.
    """
    return [hit(p.event) for p in ctx.bash
            if _CONFIRMED_RE.match(_COMMENT_RE.sub("", p.command))]


def denied_by_grade(events, ctx):
    """Um resultado de Bash carregando a assinatura do hook de avaliação: o portão disparou e o
    comando nunca rodou. O hook assina sua própria razão de negação, então a string é a
    evidência — o detector nunca a importa, e não lê a saída de nenhum outro hook como uma negação."""
    hits = []
    for event in events:
        if event.get("kind") != "tool_result" or event.get("tool_name") != "Bash":
            continue
        if GRADE_SIGNATURE in text_of(event.get("text")):
            hits.append((event.get("turn", 0), event.get("tool_use_id") or None))
    return hits


# --- o registro -------------------------------------------------------------------

_COMMITS_ON = ("commits", None)  # qualquer variante menos `off`
_VOICE_ON = ("voice", None)  # a forma é da stance; `off` não impõe nenhuma
_VOICE_CONCISE = ("voice", ("concise",))  # formas que só a voz `concise` proíbe
_COMMITS_ATTRIBUTED = ("commits", ("conventional-attributed",))

# Uma variante de custo cujo switch `compaction` é `compact-allowed` levanta o "not compaction"
# de `cache-hygiene.md`, então uma compactação ali é a stance funcionando, não uma falha.
# Congelado aqui porque este módulo não lê arquivo nenhum em tempo de execução; um teste o
# mantém igual aos sidecars embutidos.
COMPACTION_ALLOWED = frozenset(("max",))
_GATES = {"cache-hygiene/compact": lambda stances: stances.get("cost") not in COMPACTION_ALLOWED}

# Os seis que o motor traz, re-registrados sob o `Detector` deste arquivo para que toda entrada
# no registro responda aos mesmos nomes de campo. As funções são as do wheel, não uma segunda cópia.
_GENERIC = [Detector(d.id, d.rule, d.event, d.fn, _GATES.get(d.id, d.gate))
            for d in generic.DETECTORS]

_REGISTRY = _GENERIC + [
    Detector("transcript-hygiene/model-wrote-no-cap", "transcript-hygiene", "agent-brief",
             model_wrote_no_cap),
    Detector("delegation/executed-from-summary", "delegation", "bash", executed_from_summary),
    Detector("secrets/git-add-secret-file", "secrets", "bash", git_add_secret_file),
    Detector("research/search-over-cap", "research-and-verification", "session", search_over_cap),
    Detector("voice/banned-opener", "voice-and-format", "assistant-final", banned_opener, _VOICE_ON),
    Detector("voice/second-table", "voice-and-format", "assistant-final", second_table, _VOICE_ON),
    Detector("voice/scaffold-leak", "voice-and-format", "assistant-final", scaffold_leak,
             _VOICE_CONCISE),
    Detector("voice/heading-first", "voice-and-format", "assistant-final", heading_first,
             _VOICE_CONCISE),
    Detector("decisions/no-alternatives", "decisions-and-plans", "assistant-final",
             recommendation_without_alternative),
    Detector("autonomy/confirmed-irreversible", "autonomy", "bash", confirmed_irreversible),
    Detector("autonomy/denied-by-grade", "autonomy", "bash", denied_by_grade),
    Detector("commits/non-conventional", "commits", "bash", non_conventional, _COMMITS_ON),
    Detector("commits/missing-trailer", "commits", "bash", missing_trailer, _COMMITS_ATTRIBUTED),
]

DETECTORS = dict((d.id, d) for d in _REGISTRY)

# Um detector que foi renomeado, id antigo → novo. Uma linha de ledger escrita sob o id antigo
# nunca é reescrita; `harness usage --rules` dobra este mapa a cada leitura em vez disso, então
# uma medição continua sendo uma linha e uma série através da renomeação. Renomear ainda é um último recurso.
RENAMED = {"transcript-hygiene/brief-without-cap": "transcript-hygiene/model-wrote-no-cap"}

# Regras sobre as quais um transcript não pode decidir nada. O motivo é o que o lint imprime.
OPT_OUT = {
    "conciseness": "a comment's redundancy is a judgment over the codebase, not a transcript pattern",
    "working-style": "\"verify before you claim\" needs a semantic link between a claim and a command",
}


def run(events, stances=None, strict=False, errors=None):
    """Todo detector sobre os eventos de uma sessão; detectores sem hits são omitidos.

    O registro é construído por chamada a partir de `_REGISTRY`, que é uma lista para que um
    teste possa adicionar um detector a ela e retirá-lo de novo; o custo é uma vez por sessão,
    não uma vez por evento.
    """
    return _run(events, stances, registry=Registry(_REGISTRY), strict=strict, errors=errors)
