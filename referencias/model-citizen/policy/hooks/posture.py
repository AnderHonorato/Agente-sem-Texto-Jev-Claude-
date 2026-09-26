#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""O único lugar onde uma stance e a escada de modelos são resolvidas.

Não é um hook: nada o registra, e não lê evento algum. Fica ao lado dos hooks porque eles são
scripts standalone rodados como subprocessos e compartilham código carregando um arquivo irmão
(`rule-detectors.py` é o precedente); `lifecycle.py` carrega este mesmo arquivo por caminho, para
que o dispatcher e os hooks não consigam divergir em duas respostas para uma pergunta.

`selection(env)` resolve toda unidade de todo tipo sobre a escada de seleção que
`docs/preferences.md` documenta: padrões embutidos, o modo selecionado, a config do usuário sob
`HARNESS_HOME` ou `$HOME`, o arquivo que `HARNESS_PROJECT_CONFIG` nomeia, o arquivo que
`HARNESS_SESSION_CONFIG` nomeia, depois o `HARNESS_MODE` e `HARNESS_STANCE_*` da sessão.
`resolve(env)` e `selected()` leem a mesma escada só para stances. `strict` diz o que um arquivo
inutilizável significa: o dispatcher quer o erro, um hook quer que o disparo rode de qualquer
forma, então passa `strict=False` e usa as camadas que conseguiu ler.

`cost_table(env)`, e `resolve(env, table=True)`, resolvem adicionalmente o sidecar JSON da
variante `cost` ativa — switches, linhas por papel e por banda, a banda padrão — sobre sua cadeia
`extends`. Schema e autoria: `docs/primitive-authoring.md`. É opt-in porque lê mais arquivos do
que uma pergunta de stance precisa. Nenhum número vive aqui: um sidecar inutilizável produz a
tabela da variante base e um aviso, nunca um padrão chutado.

`fingerprint(env)` faz o digest da seleção resolvida na fingerprint de perfil que toda nova
linha de ledger carrega; veja `FINGERPRINT_KEY`.

Barato de importar de propósito: nenhum trabalho na importação, só leituras de JSON, porque o
dispatcher carrega isto em toda chamada de ferramenta.
"""
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "HARNESS_STANCE_"
# Por quanto tempo vale a pena manter um registro de sessão. Uma sessão que não começou em duas
# semanas nunca mais vai disparar, e seu registro são três campos que ninguém lê.
SESSION_TTL_DAYS = 14
SESSION_ID_MAX = 128
# O quão obsoleto um registro pode ficar antes de um disparo que o leu mover seu mtime para fora do caminho da varredura.
SESSION_REFRESH_SECONDS = 86400
# O anexo de transcript que uma sessão escreve quando o conjunto de tipos que resolve muda, e
# quanto do final do transcript é lido para encontrar um. Um recarregamento é anunciado no turno
# em que é notado, então fica no fim do arquivo, e uma leitura limitada mantém o custo de um hook
# de disparo constante.
AGENT_LISTING = "agent_listing_delta"
TRANSCRIPT_TAIL_BYTES = 256 * 1024
# A chave de config do usuário que nomeia globs de nome de ferramenta que o modo plano pode usar,
# e as posturas sob as quais uma autoridade de modo plano alargada é o que o usuário já pediu em
# todo outro lugar.
PLAN_TOOLS_KEY = "plan_allow_tools"
OPEN_POSTURES = ("bypass", "auto")

# As dimensões que `bin/harness` resolve e a variante para a qual cada uma recai, que é a de
# `config.example.json` — o arquivo sobre o qual a CLI sobrepõe a config do usuário, e um teste
# mantém os dois juntos.
DEFAULT_STANCES = {
    "licensing": "permissive-commercial",
    "build-vs-buy": "capability-ceiling",
    "commits": "conventional-attributed",
    "plan-ceremony": "review-card",
    "delegation": "tiered",
    "testing": "required",
    "autonomy": "execute",
    "cost": "balanced", "voice": "scannable",
}
# Classes de capacidade, mais forte primeiro; um teste mantém isto igual a `catalog.TIER_CLASSES`,
# que é a definição. Nomeado aqui para que um hook possa ordenar a tabela de um adaptador sem
# importar a biblioteca: um hook de política é um subprocesso sem pacote algum no seu path.
TIER_CLASSES = ("frontier", "strong", "standard", "light")
EFFORTS = ("low", "medium", "high")
BANDS = ("A", "B", "C")
# O papel que a linha de uma banda renderiza e para o qual reroteia. Uma banda classifica o
# *trabalho*, então precisa de uma definição de agente para carregar sua classe e esforço para um
# disparo nativo; estas três são essas definições, e este mapa é o único lugar onde a nomeação é escrita.
BAND_ROLES = {band: "worker-" + band.lower() for band in BANDS}
# A variante para a qual toda outra recai, e aquela para a qual uma variante sem sidecar resolve.
BASE_COST_VARIANT = DEFAULT_STANCES["cost"]
SIDECAR_SCHEMA_VERSION = 1
MAX_EXTENDS_DEPTH = 5
SWITCH_VALUES = {
    "session_effort": ("low", "medium", "high", "default"),
    "fast_mode": ("never", "off-unless-asked", "allowed"),
    "compaction": ("clear-only", "clear-at-task-end", "compact-allowed"),
    "turn_feed": ("off", "thresholds", "every-turn"),
}
BUDGET_KEYS = ("budget_output_tokens", "budget_tool_calls")
# A unidade em que cada chave de orçamento é declarada, na ordem em que a frase as declara.
BUDGET_UNITS = dict(zip(BUDGET_KEYS, ("output tokens", "tool calls")))
# Tetos que só descartam um número que máquina nenhuma poderia significar. Um orçamento é leve,
# então o limite é sobre aritmética que permanece finita, não sobre uma opinião de quanto é demais.
MAX_MULTIPLIER = 100
MAX_BUDGET = 10 ** 9
MAX_NUDGES = 8
SIDECAR_KEYS = ("schema_version", "extends", "switches", "default_band", "rows")
# O documento de seleção: `mode`, depois um objeto por tipo em `catalog.KINDS`. `sources` e
# `shadowed` são o que `harness selection --json` imprime ao lado deles; não selecionam nada, e
# são aceitos para que a saída se releia inalterada como um arquivo de sessão. Forma e
# precedência: `docs/preferences.md`.
SELECTION_EXTRA_KEYS = ("mode", "sources", "shadowed")
SWITCH_STATES = ("on", "off")
MODE_VARIABLE = "HARNESS_MODE"
# Um arquivo de modo carrega estas ao lado das suas chaves de seleção. Contrato e modos
# embutidos: `docs/modes.md`.
MODE_KEYS = ("schema_version", "description")
# Hooks que uma camada, um modo incluído, só pode desligar quando a configuração do usuário
# define `CORE_ACK` como true (`core_refusals`). Os mesmos quatro ids de `catalog.CORE_HOOKS`,
# mantidos aqui também porque um hook copiado para fora do seu checkout não tem catálogo; um
# teste mantém os dois iguais.
CORE_HOOKS = ("brief-guard", "grade-bash", "neutralize-tool-output", "stop-gate")
CORE_ACK = "core_switches_acknowledged"
# A chave de configuração do usuário que nomeia, por tipo, as unidades que `harness init`
# escreveu como padrões em vez de escolhidas pelo usuário. Essas resolvem abaixo do modo (AD-2);
# toda outra chave do usuário acima dele.
INIT_DEFAULTS = "init_defaults"
_KINDS = {}
# O manifesto de um módulo (AD-22): o que alega mudar, onde alcança o modelo, o que mede, o
# único slot exclusivo que ocupa, e os módulos que precisa ou com os quais colide. Contrato de
# autoria e vocabulário: `docs/primitive-authoring.md`.
MANIFEST_FIELDS = ("claims", "surface", "instruments", "slot", "dependencies", "conflicts")
MANIFEST_FILE = "manifests.json"
SURFACES = ("resident-context", "on-demand-context", "hook-events")


def home(env=None):
    env = os.environ if env is None else env
    return Path(env.get("HARNESS_HOME") or env.get("HOME") or Path.home())


def config_path(env=None):
    return home(env) / ".config" / "agent-harness" / "config.json"


def user_agents_dir(env=None):
    """Onde a ferramenta resolve uma definição de agente em nível de usuário; `CLAUDE_CONFIG_DIR` a move.

    O único lugar onde essa regra é escrita, para que o hook que reroteia um disparo e o hook que
    registra o que uma sessão consegue resolver nunca estejam olhando para dois diretórios diferentes.
    """
    env = os.environ if env is None else env
    config = env.get("CLAUDE_CONFIG_DIR")
    return (Path(config) if config else Path(env.get("HOME") or Path.home()) / ".claude") / "agents"


def installed_agents(env=None):
    """As definições de agente em nível de usuário em disco agora, ordenadas; `[]` quando o diretório é ilegível."""
    try:
        return sorted(path.stem for path in user_agents_dir(env).glob("*.md") if path.is_file())
    except OSError:
        return []


def transcript_agents(transcript_path, limit=TRANSCRIPT_TAIL_BYTES):
    """Os tipos que um recarregamento anunciou a esta sessão depois que começou, ou None quando nenhum anunciou.

    O Claude Code anexa um registro `agent_listing_delta` ao transcript sempre que o conjunto de
    tipos que consegue resolver muda: um com `isInitial` true no início da sessão, e mais um a
    cada vez que o observador pega uma definição. Um registro posterior é a própria declaração do
    runtime de que esta sessão resolve os nomes que adiciona, o que nenhuma listagem de diretório
    consegue dar — uma sessão headless não recarrega nada e não escreve registro posterior algum,
    então isto responde pela sessão que perguntou em vez de pela máquina. Medido em
    `docs/spikes/2026-09-22-registry-reload.md`.

    Só o final é lido, então uma sessão longa custa o que uma curta custa, e uma listagem que
    caiu para fora dele lê como None: desconhecido, que não roteia nada.
    """
    if not transcript_path:
        return None
    try:
        with open(str(transcript_path), "rb") as stream:
            try:
                stream.seek(-limit, os.SEEK_END)
            except OSError:
                stream.seek(0)
            tail = stream.read().decode("utf-8", "replace")
    except OSError:
        return None
    names = None
    # Um registro por linha, então só `\n` termina um: um corpo guardando um separador de linha
    # próprio não deve ser lido como dois meio-registros.
    for line in tail.split("\n"):
        if AGENT_LISTING not in line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict) or record.get("type") != "attachment" or record.get("isSidechain"):
            continue
        listing = record.get("attachment")
        if not isinstance(listing, dict) or listing.get("type") != AGENT_LISTING:
            continue
        if listing.get("isInitial"):
            # Uma listagem da qual uma sessão parte substitui tudo antes dela, exatamente como um
            # `startup` substitui o registro: o que uma sessão anterior resolvia não é desta.
            names = None
            continue
        names = set() if names is None else names
        for key, apply in (("addedTypes", names.add), ("removedTypes", names.discard)):
            value = listing.get(key)
            if isinstance(value, list):
                for name in value:
                    if isinstance(name, str):
                        apply(name)
    return sorted(names) if names is not None else None


def state_dir(env=None):
    return home(env) / ".local" / "state" / "agent-harness"


def sessions_dir(env=None):
    """O registro de sessões: um registro por sessão, escrito quando seu processo começou.

    Uma definição em disco não é evidência de que uma sessão em execução consegue resolver o tipo
    que nomeia: uma sessão interativa pega uma segundos depois de aparecer, uma headless nunca
    pega, e rerotear para um tipo que a sessão não consegue resolver transforma um disparo que
    teria funcionado num que falha. A política de SessionStart escreve o que o registro guardava;
    o hook de disparo reroteia para um nome que encontra lá, ou para um que `transcript_agents`
    mostra que a sessão foi avisada depois.
    """
    return state_dir(env) / "sessions"


def _session_id(value):
    """Um identificador de sessão seguro para virar um nome de arquivo: sem separador, sem travessia, limitado."""
    return (isinstance(value, str) and value.isascii() and 0 < len(value) <= SESSION_ID_MAX
            and value[0].isalnum() and all(c.isalnum() or c in "._-" for c in value))


def session_record_path(session_id, env=None):
    return sessions_dir(env) / (session_id + ".json") if _session_id(session_id) else None


def read_session_record(session_id, env=None):
    """O registro de uma sessão, ou None para nenhum registro, um ilegível, ou qualquer coisa que não seja um objeto."""
    path = session_record_path(session_id, env)
    if path is None:
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def write_session_record(session_id, record, env=None):
    """Substitui o registro de uma sessão atomicamente; `True` quando foi escrito.

    O diretório é assunto só da sessão e de mais ninguém, então é 0700 e o arquivo é 0600 desde o
    momento em que existe em vez de depois de um chmod com o qual um leitor poderia competir.
    """
    path = session_record_path(session_id, env)
    if path is None or not isinstance(record, dict):
        return False
    temp = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(str(path.parent), 0o700)
        with os.fdopen(os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
                       "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        os.replace(str(temp), str(path))
        return True
    except OSError:
        try:
            os.unlink(str(temp))
        except OSError:
            pass
        return False


def session_agents(session_id, env=None):
    """Os nomes de agente que o registro desta sessão guardava, ou None quando nada os registrou.

    Uma chave `agents` ausente ou inutilizável é None, que todo chamador lê como desconhecido, e
    desconhecido nunca é roteável. É isso que permite que um registro exista puramente para
    lembrar um aviso sem jamais autorizar um reroteamento.
    """
    record = read_session_record(session_id, env)
    names = record.get("agents") if record else None
    return [name for name in names if isinstance(name, str)] if isinstance(names, list) else None


def session_announced(session_id, env=None):
    """Os tipos sobre os quais um recarregamento avisou esta sessão num disparo anterior; `[]` quando nenhum avisou."""
    record = read_session_record(session_id, env)
    names = record.get("announced") if record else None
    return [name for name in names if isinstance(name, str)] if isinstance(names, list) else []


def remember_agents(session_id, names, env=None):
    """Guarda o que um recarregamento anunciou, para que o roteamento sobreviva ao final do transcript. `True` quando escrito.

    O transcript é onde um anúncio é descoberto e sua leitura é limitada, então uma sessão longa
    empurra o delta para fora do final; roteamento que se desligasse ali seria o mesmo defeito de
    novo num relógio mais lento. O conjunto lembrado é substituído em vez de mesclado, porque a
    resposta do leitor já contabiliza todo `removedTypes` no final, e uma mesclagem reinstauraria
    um worker que a sessão já foi avisada que não resolve mais.
    """
    wanted = sorted({name for name in names if isinstance(name, str)}) if names else []
    record = read_session_record(session_id, env)
    record = {} if record is None else record
    if record.get("announced") == wanted:
        return False
    return write_session_record(session_id, dict(record, announced=wanted, at=int(time.time())), env)


def refresh_session_record(session_id, env=None, older_than=SESSION_REFRESH_SECONDS):
    """Mantém uma sessão em uso fora da varredura de outra sessão. `True` quando o mtime foi movido.

    Uma sessão aberta por mais tempo que o TTL de outra forma teria seu registro podado debaixo
    dela e pararia de rotear na metade, então ler o registro é evidência de que a sessão está
    viva. Granularidade de um dia, porque isto roda num disparo e a varredura mede duas semanas.
    """
    path = session_record_path(session_id, env)
    try:
        if path is not None and time.time() - path.stat().st_mtime > older_than:
            os.utime(str(path), None)
            return True
    except OSError:
        pass
    return False


def note_once(session_id, key, env=None):
    """`True` na primeira vez que esta sessão é avisada de `key`; `False` assim que algo o lembra.

    Uma sessão sem registro é exatamente a sessão para a qual esses avisos existem, então um é
    criado para guardar a memória — sem chave `agents`, que lê como desconhecido e nunca pode
    autorizar um reroteamento. Um hook é um processo por evento, então nada além do registro
    lembra: quando não pode ser escrito isto não diz nada de forma alguma, porque um aviso
    repetido a cada disparo é uma falha pior do que um nunca dado.
    """
    record = read_session_record(session_id, env)
    if record is None:
        return write_session_record(session_id, {"notified": [key], "at": int(time.time())}, env)
    seen = record.get("notified")
    seen = sorted({name for name in seen if isinstance(name, str)}) if isinstance(seen, list) else []
    if key in seen:
        return False
    return write_session_record(session_id, dict(record, notified=sorted(seen + [key])), env)


def prune_session_records(keep=None, days=SESSION_TTL_DAYS, env=None):
    """Descarta registros mais antigos que `days`, nunca o de `keep`. Melhor esforço: uma varredura nunca falha uma sessão."""
    cutoff, removed = time.time() - days * 86400, 0
    try:
        paths = sorted(sessions_dir(env).glob("*.json"))
    except OSError:
        return 0
    for path in paths:
        if keep is not None and path.stem == keep:
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def _stances_of(data):
    """Os pares `{dimension: variant}` utilizáveis de uma camada; qualquer outra coisa não é uma seleção."""
    stances = data.get("stances") if isinstance(data, dict) else None
    if not isinstance(stances, dict):
        return {}
    return {name: value.strip() for name, value in stances.items()
            if isinstance(value, str) and value.strip()}


def _user_config(env, strict):
    """A configuração do usuário. Nenhum arquivo são os padrões; um arquivo que não pode ser lido não é.

    Uma config que existe mas não abre ou não parseia é uma seleção que ninguém consegue ver,
    então chamadores estritos ouvem falar disso em vez de rodar sob padrões que o usuário não escolheu.
    """
    path = config_path(env)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, NotADirectoryError):
        return {}
    except (OSError, ValueError):
        if strict:
            raise
        return {}


def selection_kinds(root=None):
    """`{kind: catalog entry}` para todo tipo selecionável, lido de `catalog.KINDS` por arquivo.

    O catálogo é a única definição de um tipo, então um tipo novo é uma entrada nova lá e nada
    aqui. Um hook copiado para fora do seu checkout não tem catálogo ao lado e conhece só
    `stances`, que é o único tipo cujos padrões este arquivo carrega.
    """
    key = str(root or ROOT)
    if key not in _KINDS:
        kinds = {"stances": {"directory": "stances", "pattern": "*/*.md", "value": "variant"}}
        path = Path(key) / "lib" / "harness_core" / "catalog.py"
        if path.is_file():
            try:
                spec = importlib.util.spec_from_file_location("harness_catalog_kinds", str(path))
                loaded = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(loaded)
                kinds = {name: dict(entry) for name, entry in loaded.KINDS.items()
                         if entry.get("value") in ("variant", "switch")}
            except Exception:
                pass
        _KINDS[key] = kinds
    return _KINDS[key]


def _selection_file(env, variable, strict, root=None):
    """O documento de seleção que uma variável de ambiente nomeia; `{}` quando não nomeia nenhum.

    Carrega só chaves de seleção. Identidade, permissões, flags de runtime, `primitive_roots` e
    telemetria mantêm sua própria validação na configuração do usuário, então uma chave fora da
    seleção é recusada pelo nome em vez de ignorada.
    """
    named = env.get(variable)
    if not named:
        return {}
    try:
        data = json.loads(Path(named).expanduser().read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(variable + " names " + named + ", which is not a JSON object")
        refused(data, variable + " file " + named, root)
        # Um tipo cujo valor não é um objeto é recusado por `selection()` quando estrito e não
        # seleciona nada nos demais casos; só uma chave que o arquivo não pode definir descarta o arquivo inteiro.
        return data
    except (OSError, ValueError):
        if strict:
            raise
        return {}


def refused(data, where, root=None):
    """Levanta `ValueError` nomeando toda chave de `data` que um documento de seleção não pode carregar."""
    extra = sorted(set(data) - set(SELECTION_EXTRA_KEYS) - set(selection_kinds(root)))
    if extra:
        raise ValueError(where + " may carry selection keys only, not " +
                         ", ".join("'" + key + "'" for key in extra) +
                         "; identity, permissions, runtime flags, primitive_roots and telemetry "
                         "stay in the user configuration")


def _project_config(env, strict, root=None):
    return _selection_file(env, "HARNESS_PROJECT_CONFIG", strict, root)


def _session_config(env, strict, root=None):
    return _selection_file(env, "HARNESS_SESSION_CONFIG", strict, root)


def overrides(env=None):
    """O `{dimension: variant}` que uma sessão define através de `HARNESS_STANCE_*`."""
    env = os.environ if env is None else env
    return {key[len(PREFIX):].lower().replace("_", "-"): value.strip()
            for key, value in env.items()
            if key.startswith(PREFIX) and isinstance(value, str) and value.strip()}


def _identifier(value):
    return (isinstance(value, str) and value and value[0].isalpha() and value.islower()
            and all(c.isalnum() or c == "-" for c in value) and value.isascii())


def _number(value, low, high, integer=False):
    """Um número finito dentro do intervalo. `True` não é 1 aqui, e nem NaN nem um infinito é um valor.

    O JSON admite `Infinity` e `NaN`, e o `json` do Python os lê, então um multiplicador chegando
    de um arquivo pode ser qualquer um dos dois; ambos levantariam exceção fora da aritmética
    abaixo em vez de apenas avisar.
    """
    if isinstance(value, bool) or not isinstance(value, int if integer else (int, float)):
        return False
    if value != value or value in (float("inf"), float("-inf")):
        return False
    return low <= value <= high


def _sizes(value):
    """None quando `value` é uma lista utilizável de tamanhos de contexto, senão a regra que quebra.

    Específico, onde todo outro switch reporta "um valor inutilizável", porque este é uma lista:
    um autor a quem se diz que oito números são inutilizáveis precisa descobrir quais, contra
    uma regra escrita em lugar nenhum.
    """
    if not isinstance(value, list):
        return "is a list of whole positive token counts, smallest first"
    if len(value) > MAX_NUDGES:
        return "has " + str(len(value)) + " entries and at most " + str(MAX_NUDGES) + " are read"
    previous = None
    for item in value:
        shown = json.dumps(item, default=str)
        if not (_number(item, 0, MAX_BUDGET, integer=True) and item > 0):
            return "entry " + shown + " is not a whole positive token count"
        if previous is not None and item <= previous:
            return ("entry " + shown + " does not follow " + json.dumps(previous) +
                    "; the sizes ascend and none repeats")
        previous = item
    return None


def validate_sidecar(data, roles=None):
    """`(cópia utilizável, achados)` para um objeto de sidecar; todo achado descarta o valor que nomeia.

    Achados são avisos para o resolvedor e falhas para o lint, que é todo o ponto: um switch
    adicionado num lançamento posterior nunca deve quebrar uma variante que outra pessoa
    escreveu, enquanto uma variante embutida com uma chave desconhecida é um erro que ninguém
    deveria ter que descobrir em tempo de execução.

    `roles` é o catálogo de papéis quando o chamador tem um, para que uma linha que não nomeia
    papel nem banda seja reportada em vez de aplicar-se silenciosamente a nada.
    """
    findings, clean = [], {}
    for key in sorted(data):
        if key not in SIDECAR_KEYS:
            findings.append("unknown key '" + key + "'")
    version = data.get("schema_version")
    if version != SIDECAR_SCHEMA_VERSION:
        findings.append("schema_version must be " + str(SIDECAR_SCHEMA_VERSION))
    extends = data.get("extends")
    if extends is not None:
        if _identifier(extends):
            clean["extends"] = extends
        else:
            findings.append("extends names a cost variant or is null")
    band = data.get("default_band")
    if band is not None:
        if band in BANDS:
            clean["default_band"] = band
        else:
            findings.append("default_band is one of " + ", ".join(BANDS))
    switches = data.get("switches", {})
    if "switches" in data and not isinstance(switches, dict):
        findings.append("switches is an object")
        switches = {}
    kept = {}
    for key in sorted(switches):
        value = switches[key]
        if key in SWITCH_VALUES:
            ok = value in SWITCH_VALUES[key]
        elif key == "max_parallel":
            ok = value is None or _number(value, 1, MAX_BUDGET, integer=True)
        elif key == "budget_multiplier":
            ok = _number(value, 0, MAX_MULTIPLIER) and value > 0
        elif key == "nudge_at":
            ok = (isinstance(value, list) and len(value) <= MAX_NUDGES
                  and all(_number(v, 0, MAX_MULTIPLIER) and v > 0 for v in value))
        elif key == "session_nudge_at":
            # Tamanhos de contexto, não múltiplos: tokens inteiros, porque é isso que um
            # transcript conta e um token fracionário é um número que ninguém mediu.
            problem = _sizes(value)
            if problem:
                findings.append("switch 'session_nudge_at' " + problem)
                continue
            ok = True
        else:
            findings.append("unknown switch '" + key + "'")
            continue
        if ok:
            kept[key] = value
        else:
            findings.append("switch '" + key + "' has an unusable value")
    if kept:
        clean["switches"] = kept
    rows = data.get("rows", {})
    if "rows" in data and not isinstance(rows, dict):
        findings.append("rows is an object")
        rows = {}
    resolved_rows = {}
    for name in sorted(rows):
        row = rows[name]
        if not (name in BANDS or _identifier(name)):
            findings.append("row '" + str(name) + "' is a role name or a band")
            continue
        if roles is not None and name not in BANDS and name not in roles:
            # Uma linha que não nomeia nada se aplica a nada, que é um erro de digitação que ninguém veria.
            findings.append("row '" + name + "' names no role and no band")
            continue
        if not isinstance(row, dict):
            findings.append("row '" + name + "' is an object")
            continue
        cells = {}
        for key in sorted(row):
            value = row[key]
            if key == "class":
                # `frontier` nunca é alcançável por pedido; a stance de delegação decide isso, e
                # uma variante é um pedido.
                ok = value in TIER_CLASSES[1:]
            elif key == "effort":
                ok = value in EFFORTS
            elif key in BUDGET_KEYS:
                ok = value is None or _number(value, 0, MAX_BUDGET, integer=True)
            else:
                findings.append("row '" + name + "' has an unknown key '" + str(key) + "'")
                continue
            if ok:
                cells[key] = value
            else:
                findings.append("row '" + name + "' cell '" + key + "' has an unusable value")
        resolved_rows[name] = cells
    if resolved_rows:
        clean["rows"] = resolved_rows
    return clean, findings


def stance_roots(config=None, root=None):
    """Os diretórios de stance a pesquisar, o embutido primeiro, depois os `primitive_roots` de um usuário."""
    roots = [(root or ROOT) / "primitives" / "stances"]
    entries = config.get("primitive_roots") if isinstance(config, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, str) and entry.strip():
            path = Path(entry).expanduser()
            if path.is_absolute():
                roots.append(path / "stances")
    return roots


def primitive_roots(config=None, root=None, kind="stances"):
    """Os diretórios de primitivas de um tipo, o embutido primeiro, depois as raízes de um usuário."""
    roots = [(root or ROOT) / "primitives" / kind]
    entries = config.get("primitive_roots") if isinstance(config, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, str) and entry.strip():
            path = Path(entry).expanduser()
            if path.is_absolute():
                roots.append(path / kind)
    return roots


def stance_roots(config=None, root=None):
    return primitive_roots(config, root, "stances")


def sidecar_path(variant, roots):
    """A primeira raiz guardando `cost/<variant>.json`, ou None. Nunca lê fora de uma raiz.

    O nome da variante chega de um arquivo de config ou `HARNESS_STANCE_COST`, então é mantido à
    mesma regra de identificador que o `.md` que acompanha, e o arquivo que nomeia ainda precisa
    resolver dentro da raiz em que foi encontrado: um symlink para fora da árvore é uma leitura
    que ninguém pediu.
    """
    if not _identifier(variant):
        return None
    for source in roots:
        path = source / "cost" / (variant + ".json")
        if not path.is_file():
            continue
        try:
            real, base = path.resolve(), source.resolve()
        except OSError:
            continue
        if real == base or base in real.parents:
            return path
    return None


def _load_sidecar(path, strict, warnings):
    """O objeto do sidecar, ou None com um aviso; ilegível é um erro só no modo estrito."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        if strict:
            raise
        warnings.append(str(path) + " is not readable JSON: " + str(exc))
        return None
    if not isinstance(data, dict):
        if strict:
            raise ValueError(str(path) + " is not a JSON object")
        warnings.append(str(path) + " is not a JSON object")
        return None
    return data


def _frontmatter(path):
    """Os campos de frontmatter de um arquivo de papel, ou `{}`; a mesma forma `key: value` que `catalog` parseia."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---\n") or text.count("---") < 2:
        return {}
    fields = {}
    for line in text.split("---", 2)[1].strip().splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def role_catalog(config=None, root=None):
    """`(todo nome de papel, os nomes cujo frontmatter diz `posture: fixed`)`.

    A classe e o esforço de um verificador são seu contrato, então uma linha de variante pode
    orçá-lo mas nunca rebaixar sua classe, e o arquivo de papel é o único lugar que diz isso.
    Papéis que um usuário adicionou através de `primitive_roots` contam igual aos embutidos; um
    catálogo ausente são dois conjuntos vazios, que é como um hook instalado sem checkout ao
    lado se comporta.
    """
    names, fixed = set(), set()
    for directory in primitive_roots(config, root, "roles"):
        for path in sorted(directory.glob("*.md")) if directory.is_dir() else []:
            fields = _frontmatter(path)
            if not fields:
                continue
            names.add(path.stem)
            if fields.get("posture") == "fixed":
                fixed.add(path.stem)
    return names, fixed


def fixed_roles(config=None, root=None):
    return role_catalog(config, root)[1]


def _merge(base, layer):
    """`layer` sobre `base`, um nível dentro de `switches` e dois dentro de `rows`."""
    merged = dict(base)
    for key in ("extends", "default_band"):
        if key in layer:
            merged[key] = layer[key]
    merged["switches"] = dict(base.get("switches", {}), **layer.get("switches", {}))
    rows = {name: dict(cells) for name, cells in base.get("rows", {}).items()}
    for name, cells in layer.get("rows", {}).items():
        rows[name] = dict(rows.get(name, {}), **cells)
    merged["rows"] = rows
    return merged


def _round_to(value, step):
    return int((value + step / 2) // step) * step


def table_for(stances=None, config=None, strict=True, root=None):
    """A variante de custo ativa resolvida: switches, linhas, banda padrão, cadeia e avisos.

    Orçamentos carregam ambas as cifras: `base_*` é o que a variante escreveu e `budget_*` é isso
    vezes o `budget_multiplier` resolvido, para que um leitor nunca multiplique duas vezes. Um
    link que não pode ser seguido — nenhum sidecar, ilegível, um schema que este lançamento não
    conhece, um nome que não é um identificador — resolve para a variante base em vez de para
    uma tabela vazia.
    """
    stances = dict(DEFAULT_STANCES) if stances is None else stances
    variant = stances.get("cost") or BASE_COST_VARIANT
    roots = stance_roots(config, root)
    roles, fixed = role_catalog(config, root)
    warnings, chain, layers, seen = [], [], [], set()
    name = variant
    while name:
        if name in seen:
            warnings.append("extends cycle at cost variant '" + str(name) + "'")
            break
        if len(chain) >= MAX_EXTENDS_DEPTH:
            warnings.append("extends chain deeper than " + str(MAX_EXTENDS_DEPTH) +
                            " variants, stopped at '" + str(name) + "'")
            break
        seen.add(name)
        data = None
        if not _identifier(name):
            warnings.append("cost variant '" + str(name) + "' is not a primitive identifier")
        else:
            path = sidecar_path(name, roots)
            if path is None:
                warnings.append("cost variant '" + name + "' has no sidecar")
            else:
                data = _load_sidecar(path, strict, warnings)
                version = data.get("schema_version") if data is not None else None
                if data is not None and version != SIDECAR_SCHEMA_VERSION:
                    warnings.append(name + ".json: schema_version " + json.dumps(version) +
                                    " is not one this release reads")
                    data = None
        if data is None:
            if name != BASE_COST_VARIANT and BASE_COST_VARIANT not in seen:
                # Um link inutilizável é a tabela da variante base, não uma vazia.
                name = BASE_COST_VARIANT
                continue
            break
        clean, findings = validate_sidecar(data, roles or None)
        warnings.extend(name + ".json: " + finding for finding in findings)
        chain.append({"variant": name, "source": str(path)})
        layers.append(clean)
        name = clean.get("extends")
    resolved = {}
    for layer in reversed(layers):
        resolved = _merge(resolved, layer)
    switches = resolved.get("switches", {})
    multiplier = switches.get("budget_multiplier", 1)
    rows = {}
    for row_name, cells in sorted(resolved.get("rows", {}).items()):
        row = {"class": cells.get("class"), "effort": cells.get("effort")}
        if row_name in fixed:
            # O papel mantém seu nível de frontmatter e seu esforço de bindings; só orçamentos se aplicam.
            row["class"], row["effort"], row["posture"] = None, None, "fixed"
        for key, step in zip(BUDGET_KEYS, (100, 1)):
            base = cells.get(key)
            row["base_" + key] = base
            row[key] = None if base is None else _round_to(base * multiplier, step)
        rows[row_name] = row
    return {"cost_variant": variant, "switches": switches, "rows": rows,
            "default_band": resolved.get("default_band"), "extends_chain": chain,
            "class_applies": stances.get("delegation") == "tiered", "warnings": warnings}


def _mode_of(data):
    value = data.get("mode") if isinstance(data, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def modes(config=None, root=None):
    """`({name: path}, [refusal])`: cada `modes/<name>.json` nas raízes primitivas.

    Um nome que duas raízes definem é uma recusa em vez de primeiro-vence, para que uma raiz de usuário não
    substitua silenciosamente um modo distribuído; a primeira definição ainda é retornada para um hook.
    """
    found, errors = {}, []
    for directory in primitive_roots(config, root, "modes"):
        for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
            name = path.stem
            if not _identifier(name):
                errors.append("mode file " + str(path) + " is not named with lowercase letters, digits and hyphens")
            elif name in found:
                errors.append("mode '" + name + "' is defined in both " + str(found[name]) + " and " + str(path))
            else:
                found[name] = path
    return found, errors


def validate_mode(name, data, config, root=None):
    """Toda recusa que o arquivo de modo `data` ganha, como mensagens; vazio quando é sólido.

    Um modo carrega `schema_version` 1, uma `description`, e chaves de seleção nomeando apenas
    unidades instaladas; uma variante de postura é checada onde a de toda camada é, por `sync`. Um hook central
    que ele desliga é recusado onde o de toda camada é, por `core_refusals`.
    """
    where = "mode file " + name
    if not isinstance(data, dict):
        return [where + " is not a JSON object"]
    kinds = selection_kinds(root)
    errors = []
    extra = sorted(set(data) - set(MODE_KEYS) - set(kinds))
    if extra:
        errors.append(where + " may carry schema_version, description and selection keys only, not " +
                      ", ".join("'" + key + "'" for key in extra))
    if data.get("schema_version") != 1:
        errors.append(where + " needs \"schema_version\": 1")
    if not (isinstance(data.get("description"), str) and data["description"].strip()):
        errors.append(where + " needs a nonempty \"description\"")
    declared = None
    for kind in sorted(set(data) & set(kinds)):
        chosen, entry = data[kind], kinds[kind]
        if not isinstance(chosen, dict):
            errors.append(where + " sets " + kind + " to " + json.dumps(chosen) + "; a kind is an object of unit to value")
            continue
        if entry.get("directory"):
            known = set(_units(kind, entry, config, root))
        else:
            if declared is None:
                declared = manifests(config, root)[0]
            known = set(declared.get(kind, {})) | (set(CORE_HOOKS) if kind == "hooks" else set())
        for unit, value in sorted(chosen.items()):
            label = where + " sets " + kind + "." + unit
            if unit not in known:
                errors.append(label + ", which is not an installed " + kind + " unit")
            elif entry.get("value") == "switch" and value not in SWITCH_STATES:
                errors.append(label + " to " + json.dumps(value) + "; a " + kind + " unit is on or off")
            elif entry.get("value") == "variant" and not (isinstance(value, str) and value.strip()):
                errors.append(label + " to " + json.dumps(value) + "; a " + kind + " unit names a variant")
    return errors


def _mode_file(name, config, strict, root=None):
    """As chaves de seleção do modo `name`, validadas; `{}` quando um hook não pode usá-lo.

    Chamadores estritos ouvem sobre um modo desconhecido, um nome duplicado, ou um arquivo de modo que falha
    em `validate_mode`, antes de qualquer coisa agir sobre a seleção. Um hook roda sem um modo que não pode
    usar, e usa a definição da primeira raiz para um nome duplicado.
    """
    found, errors = modes(config, root)
    path = found.get(name)
    if errors and strict:
        raise ValueError("\n".join(errors))
    try:
        if path is None:
            raise ValueError("unknown mode '" + name + "'; installed modes: " + (", ".join(sorted(found)) or "none"))
        data = json.loads(path.read_text(encoding="utf-8"))
        problems = validate_mode(name, data, config, root)
        if problems:
            raise ValueError("\n".join(problems))
    except (OSError, ValueError):
        if strict:
            raise
        return {}
    return {key: value for key, value in data.items() if key not in MODE_KEYS}


def _init_split(config):
    """`(typed, defaults)`: a configuração do usuário sem, e só com, o que o init definiu por padrão.

    Uma unidade conta como padrão do init só enquanto ainda mantém o valor que o init registrou para ela, então
    um valor editado em `config.json` depois fica tipado e permanece acima do modo.
    """
    listed = config.get(INIT_DEFAULTS)
    if not isinstance(listed, dict):
        return config, {}
    typed, defaults = dict(config), {}
    for kind, names in listed.items():
        chosen = config.get(kind)
        if not isinstance(chosen, dict) or not isinstance(names, dict):
            continue
        moved = {unit: chosen[unit] for unit, recorded in names.items()
                 if unit in chosen and chosen[unit] == recorded}
        if moved:
            defaults[kind] = moved
            typed[kind] = {unit: value for unit, value in chosen.items() if unit not in moved}
    return typed, defaults


def layers(config, env, strict, root=None):
    """`(mode, [(source, document)])`, menor precedência primeiro: a única escada de seleção.

    O que `harness init` gravou como padrão (`init`), o modo, a configuração do usuário, o arquivo de
    projeto, o arquivo de sessão, e então o açúcar de ambiente da sessão: `HARNESS_MODE` e
    `HARNESS_STANCE_*` resolvem como a última palavra da camada de sessão. O modo é o que qualquer camada nomeou
    por último, e seu arquivo fica abaixo de toda camada explícita mas acima dos padrões do init.
    """
    project = _project_config(env, strict, root)
    session = _session_config(env, strict, root)
    sugar = {"stances": overrides(env)}
    if (env.get(MODE_VARIABLE) or "").strip():
        sugar["mode"] = env[MODE_VARIABLE]
    user, defaults = _init_split(config if isinstance(config, dict) else {})
    explicit = [("user", user), ("project", project),
                ("session", session), ("session", sugar)]
    mode = None
    for source, data in explicit:
        if _mode_of(data):
            mode = (_mode_of(data), source)
    ladder = [("init", defaults)] if defaults else []
    if mode:
        ladder.append(("mode:" + mode[0], _mode_file(mode[0], config, strict, root)))
    return mode, ladder + explicit


def _selection(config, env, strict, root=None):
    """A variante de cada postura em vigor: a escada lida só para `stances`, sem percorrer unidades."""
    stances = dict(DEFAULT_STANCES)
    for _, data in layers(config, env, strict, root)[1]:
        stances.update(_stances_of(data))
    return stances


def _units(kind, entry, config, root=None):
    """As unidades instaladas de um tipo, ordenadas: dimensões de postura, nomes de regra, skill ou papel.

    Um tipo que o catálogo enumera, `hooks`, conta cada id listado cujo módulo está neste checkout.
    """
    if entry.get("units"):
        base = (root or ROOT) / "policy" / "hooks"
        return sorted(unit for unit in entry["units"] if (base / (unit + ".py")).is_file())
    directory, pattern = entry.get("directory"), entry.get("pattern")
    if not directory or not pattern:
        return []
    names = set()
    for source in primitive_roots(config, root, directory):
        names.update(_units_in(source, pattern))
    return sorted(names)


def _units_in(source, pattern):
    return {path.parent.name if "/" in pattern else path.stem
            for path in (source.glob(pattern) if source.is_dir() else [])}


def _manifest_files(config, root=None):
    """`[(path, shipped)]`: os arquivos do catálogo e do núcleo de hooks, então os de cada raiz de usuário."""
    base = root or ROOT
    files = [(base / "primitives" / MANIFEST_FILE, True), (base / "policy" / "hooks" / MANIFEST_FILE, True)]
    for source in primitive_roots(config, root, "rules")[1:]:
        files.append((source.parent / MANIFEST_FILE, False))
    return files


def _reference(value, kinds):
    kind, sep, unit = value.partition("/") if isinstance(value, str) else ("", "", "")
    return bool(sep) and kind in kinds and _identifier(unit)


def validate_manifest(kind, unit, entry, kinds):
    """A única mensagem que `entry` ganha como manifesto de `kind/unit`, ou None quando é sólido.

    `kinds` são os tipos de switch que uma dependência ou conflito pode nomear, como `kind/unit`.
    """
    name = kind + "/" + unit
    if not isinstance(entry, dict):
        return name + " manifest is not an object"
    unknown = sorted(set(entry) - set(MANIFEST_FIELDS))
    if unknown:
        return name + " manifest has unknown field(s): " + ", ".join(unknown)
    for field in MANIFEST_FIELDS:
        if field not in entry:
            return name + " manifest is missing '" + field + "'"
    strings = lambda value: isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)
    if not strings(entry["claims"]) or not entry["claims"]:
        return name + " manifest 'claims' is a nonempty list of what the module is for"
    if not strings(entry["surface"]) or not entry["surface"] or set(entry["surface"]) - set(SURFACES):
        return name + " manifest 'surface' is a nonempty list drawn from " + ", ".join(SURFACES)
    if not strings(entry["instruments"]):
        return name + " manifest 'instruments' is a list of instrument ids, empty when nothing measures it"
    slot = entry["slot"]
    if slot is not None and not (isinstance(slot, dict) and set(slot) == {"id", "cedes"}
                                 and _identifier(slot["id"]) and isinstance(slot["cedes"], bool)):
        return name + " manifest 'slot' is null or {\"id\": <identifier>, \"cedes\": true|false}"
    for field in ("dependencies", "conflicts"):
        refs = entry[field]
        if not isinstance(refs, list) or not all(_reference(v, kinds) for v in refs):
            return name + " manifest '" + field + "' is a list of kind/unit, kind one of " + ", ".join(kinds)
        if name in refs:
            return name + " manifest '" + field + "' names the module itself"
    return None


def manifests(config=None, root=None, kinds=None):
    """`({kind: {unit: manifest}}, [refusal])` a partir de cada arquivo de manifesto, cada entrada validada.

    Um arquivo distribuído precisa parsear; uma raiz de usuário pode não carregar nenhum. Um módulo declarado em dois
    arquivos é uma recusa, para que uma raiz de usuário não reescreva do que um módulo distribuído precisa nem com o que colide.
    """
    kinds = [k for k, e in selection_kinds(root).items() if e.get("value") == "switch"] if kinds is None else kinds
    declared, origin, errors = {kind: {} for kind in kinds}, {}, []
    for path, shipped in _manifest_files(config, root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError):
            continue
        except (OSError, ValueError) as exc:
            errors.append(str(path) + " is not readable JSON: " + str(exc))
            continue
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            errors.append(str(path) + " is not a schema_version 1 manifest file")
            continue
        for kind, units in data.items():
            if kind == "schema_version":
                continue
            if kind not in kinds or not isinstance(units, dict):
                errors.append(str(path) + " declares '" + kind + "', which is not a switch kind")
                continue
            for unit, entry in sorted(units.items()):
                problem = validate_manifest(kind, unit, entry, kinds)
                if problem:
                    errors.append(problem)
                elif unit in declared[kind]:
                    errors.append(kind + "/" + unit + " has a manifest in both " + origin[kind, unit] +
                                  " and " + str(path))
                else:
                    declared[kind][unit], origin[kind, unit] = entry, str(path)
    return declared, errors


def manifest_refusals(document, declared, required, installed=None):
    """Toda recusa que uma seleção resolvida ganha dos manifestos dos seus módulos, como mensagens.

    `required` é `{kind: units}` que precisa declarar um manifesto: os distribuídos. `installed` é
    `{kind: units}` que existe, para os tipos que têm um diretório de módulo; um tipo sem um,
    como hooks, conta uma unidade como presente quando ela declara um manifesto. Só módulos ligados
    ocupam um slot, precisam de uma dependência ou colidem; um módulo desligado não pede nada.
    """
    installed = {} if installed is None else installed
    errors = []
    for kind in sorted(required):
        for unit in sorted(required[kind]):
            if unit not in declared.get(kind, {}):
                errors.append(kind + "/" + unit + " has no manifest; declare " +
                              ", ".join(MANIFEST_FIELDS) + " in " + MANIFEST_FILE)
    on = {kind + "/" + unit: declared[kind][unit] for kind in sorted(declared)
          for unit in sorted(declared[kind]) if (document.get(kind) or {}).get(unit) == "on"}
    slots = {}
    for name, entry in on.items():
        for needed in entry["dependencies"]:
            kind, _, unit = needed.partition("/")
            if unit not in installed.get(kind, declared.get(kind, {})):
                errors.append(name + " depends on " + needed + ", which is not installed")
            elif (document.get(kind) or {}).get(unit) != "on":
                errors.append(name + " depends on " + needed + ", which is not switched on")
        for other in entry["conflicts"]:
            if other in on and (other < name or name not in on[other]["conflicts"]):
                errors.append(name + " conflicts with " + other + "; switch one of them off")
        if entry["slot"]:
            slots.setdefault(entry["slot"]["id"], []).append(name)
    for slot, names in sorted(slots.items()):
        # Um reivindicante que cede se retira; o slot é recusado enquanto dois ou mais ainda o detêm.
        holders = [name for name in names if not on[name]["slot"]["cedes"]]
        if len(holders) > 1:
            errors.append(", ".join(holders) + " each claim the slot '" + slot +
                          "'; switch one off, or have one declare that it cedes the slot")
    return errors


def core_refusals(document, sources, config):
    """Uma mensagem por hook central que `document` desliga enquanto o usuário não o reconheceu.

    O reconhecimento é lido só da configuração do usuário: um arquivo de projeto, sessão ou modo
    não pode carregá-lo, para que nenhum arquivo que um repositório distribua possa desligar a aplicação por autoridade própria.
    """
    if isinstance(config, dict) and config.get(CORE_ACK) is True:
        return []
    hooks = document.get("hooks") or {}
    return [(sources.get("hooks") or {}).get(unit, "a layer") + " switches the core hook " + unit +
            " off; set " + CORE_ACK + " true in the user configuration to allow it"
            for unit in CORE_HOOKS if hooks.get(unit) == "off"]


def measurement(manifest):
    """Como um relatório mostra um módulo: seus instrumentos, ou `unmeasured`, nunca `no effect`."""
    instruments = (manifest or {}).get("instruments") or []
    return "measured by " + ", ".join(instruments) if instruments else "unmeasured"


def selection(env=None, strict=True, config=None, root=None):
    """Cada unidade de cada tipo com seu valor, e a fonte que o definiu.

    Retorna o documento de seleção — `mode`, então `{kind: {unit: value}}` para cada tipo em
    `catalog.KINDS` — mais `sources` na mesma forma, cada um `default`, `init`,
    `mode:<name>`, `user`, `project` ou `session`, nessa precedência, e `shadowed`,
    `{kind: {unit: source}}` para cada chave de modo que uma camada superior sobrescreveu. O padrão de um tipo variante é a
    postura embutida ou null; o de um tipo switch é `on`. `config` é a configuração do usuário quando o chamador
    já a leu. Um tipo que não é um objeto, ou um valor de switch diferente de `on` ou `off`,
    é um erro quando estrito e não seleciona nada caso contrário; uma unidade que uma camada nomeia mas que nada instala ainda é reportada.
    O mesmo vale para um hook central desligado sem `core_switches_acknowledged` verdadeiro na configuração
    do usuário, que resolve para `on` quando não estrito (`core_refusals`).
    A resolução estrita também aplica os manifestos dos tipos switch (AD-22): um módulo distribuído sem
    um, um campo faltando ou malformado, um módulo ligado cuja dependência não está ligada, dois que
    conflitam, ou dois que reivindicam um slot sem que nenhum ceda, é um `ValueError` nomeando-os.
    """
    env = os.environ if env is None else env
    config = _user_config(env, strict) if config is None else config
    kinds = selection_kinds(root)
    if strict:
        duplicates = modes(config, root)[1]
        if duplicates:
            raise ValueError("\n".join(duplicates))
    mode, ladder = layers(config, env, strict, root)
    result, sources = {"mode": mode[0] if mode else None}, {"mode": mode[1] if mode else "default"}
    shadowed = {}  # {kind: unidades que a camada de modo definiu}
    for kind, entry in kinds.items():
        switch = entry.get("value") == "switch"
        result[kind] = {unit: ("on" if switch else DEFAULT_STANCES.get(unit))
                        for unit in _units(kind, entry, config, root)}
        if not switch:
            result[kind].update(DEFAULT_STANCES)
        sources[kind] = {unit: "default" for unit in result[kind]}
        for source, data in ladder:
            if not isinstance(data, dict) or kind not in data:
                continue
            chosen = data[kind]
            if not isinstance(chosen, dict):
                if strict:
                    raise ValueError(source + " sets " + kind + " to " + json.dumps(chosen) +
                                     "; a kind is an object of unit to value")
                continue
            for unit, value in chosen.items():
                value = value.strip() if isinstance(value, str) else value
                if switch and value not in SWITCH_STATES:
                    if strict:
                        shown = "'" + value + "'" if isinstance(value, str) else json.dumps(value)
                        raise ValueError(source + " sets " + kind + "." + unit + " to " + shown +
                                         "; a " + kind + " unit is on or off")
                    continue
                if not isinstance(value, str) or not value:
                    continue
                if source.startswith("mode:"):
                    shadowed.setdefault(kind, set()).add(unit)
                result[kind][unit], sources[kind][unit] = value, source
    refusals = core_refusals(result, sources, config)
    if refusals and strict:
        raise ValueError("\n".join(refusals))
    if refusals:
        # Um hook resolvendo de forma não estrita continua aplicando: um `off` não reconhecido não é um.
        for unit in CORE_HOOKS:
            if result.get("hooks", {}).get(unit) == "off":
                result["hooks"][unit], sources["hooks"][unit] = "on", "default"
    for kind in kinds:
        result[kind] = dict(sorted(result[kind].items()))
        sources[kind] = dict(sorted(sources[kind].items()))
    if strict:
        switches = [kind for kind, entry in kinds.items() if entry.get("value") == "switch"]
        declared, errors = manifests(config, root, switches)
        base = (root or ROOT) / "primitives"
        required = {kind: _units_in(base / kinds[kind]["directory"], kinds[kind]["pattern"])
                    for kind in switches if kinds[kind].get("directory") and kinds[kind].get("pattern")}
        installed = {kind: set(_units(kind, kinds[kind], config, root)) for kind in required}
        # Hooks não têm diretório de módulo, então `installed` continua contando um como presente quando ele
        # declara um manifesto; cada hook que este checkout distribui precisa declarar um.
        required.update({kind: set(_units(kind, kinds[kind], config, root))
                         for kind in switches if kinds[kind].get("units")})
        errors += manifest_refusals(result, declared, required, installed)
        if errors:
            raise ValueError("module manifest: " + "\nmodule manifest: ".join(errors))
    result["sources"] = sources
    # Uma chave de modo é ofuscada quando uma camada acima do modo define a mesma unidade, qualquer que seja seu valor.
    shadowed = {kind: {unit: sources[kind][unit] for unit in sorted(units)
                       if not sources[kind][unit].startswith("mode:")} for kind, units in sorted(shadowed.items())}
    result["shadowed"] = {kind: units for kind, units in shadowed.items() if units}
    return result


# A impressão digital de perfil (AD-22, AD-23): qual perfil escreveu uma linha do razão. A configuração que
# ela cobre são as chaves de usuário que chegam ao modelo ou a um hook; switches do instalador, controle remoto e
# integrações não alteram nenhuma. `primitive_roots` fica de fora porque os módulos que ela adiciona são
# hasheados por conteúdo, então um perfil em duas máquinas combina. Uma linha anterior ao campo é
# não atribuída, e o braço nu de uma repetição, que não carrega harness nenhum, é `BARE_FINGERPRINT`.
FINGERPRINT_KEY = "profile_fingerprint"
FINGERPRINT_CONFIG_KEYS = ("identity", "permissions", "permissions_bypass_acknowledged",
                           "plan_allow_tools", "telemetry", "governance")
BARE_FINGERPRINT = "bare"
_FINGERPRINTS = {}


def _unit_files(entry, unit, value, config, root=None):
    """`[(label, path)]` para os arquivos que são o conteúdo de uma unidade, em cada raiz primitiva.

    O rótulo é a posição da raiz e o caminho dentro dela, para que a localização própria de um checkout nunca
    chegue ao digest. Uma skill é seu diretório inteiro; uma postura é sua variante selecionada e o
    sidecar ao seu lado; qualquer outro tipo é seu único arquivo.
    """
    directory, pattern = entry.get("directory"), entry.get("pattern")
    if not directory or not pattern or not _identifier(unit):
        return []
    files = []
    for index, source in enumerate(primitive_roots(config, root, directory)):
        if pattern == "*/*.md":
            if not _identifier(value):
                continue
            found = [source / unit / (value + suffix) for suffix in (".md", ".json")]
        elif "/" in pattern:
            base = source / unit
            found = sorted(path for path in base.rglob("*") if path.is_file() and not any(
                part.startswith(".") or part == "__pycache__" for part in path.relative_to(base).parts)) \
                if base.is_dir() else []
        else:
            found = [source / pattern.replace("*", unit)]
        files += [(str(index) + "/" + path.relative_to(source).as_posix(), path)
                  for path in found if path.is_file()]
    return files


def _content_digest(files):
    """O sha256 dos bytes dos arquivos rotulados, ou None quando a unidade não tem arquivo em lugar nenhum."""
    if not files:
        return None
    digest = hashlib.sha256()
    for label, path in files:
        try:
            data = path.read_bytes()
        except OSError:
            data = b"\0unreadable"
        digest.update(label.encode("utf-8") + b"\0" + str(len(data)).encode("ascii") + b"\0" + data)
    return digest.hexdigest()


def _version(root=None):
    try:
        return ((root or ROOT) / "VERSION").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def profile(env=None, config=None, root=None):
    """O documento que a impressão digital de perfil resume, resolvido de forma não estrita a partir da única escada.

    Cada módulo ligado com seu digest de conteúdo, cada postura com sua variante e o digest
    dessa variante, os valores de configuração que `FINGERPRINT_CONFIG_KEYS` nomeia, e a versão do
    harness. Um módulo desligado está ausente, assim como da sessão. Um modo não é nomeado:
    o que ele seleciona é.
    """
    env = os.environ if env is None else env
    config = _user_config(env, False) if config is None else config
    document = selection(env, strict=False, config=config, root=root)
    modules, stances = {}, {}
    for kind, entry in selection_kinds(root).items():
        units = document.get(kind) or {}
        if entry.get("value") == "switch":
            on = {unit: _content_digest(_unit_files(entry, unit, None, config, root))
                  for unit, value in units.items() if value == "on"}
            if on:
                modules[kind] = on
        else:
            stances.update({unit: {"variant": value,
                                   "digest": _content_digest(_unit_files(entry, unit, value, config, root))}
                            for unit, value in units.items() if value})
    settings = config if isinstance(config, dict) else {}
    return {"harness_version": _version(root), "modules": modules, "stances": stances,
            "config": {key: settings[key] for key in FINGERPRINT_CONFIG_KEYS if key in settings}}


def _file_state(path):
    """`(mtime_ns, size)` de um arquivo, ou None quando não pode ser lido: a chave do cache de impressão digital."""
    try:
        state = path.stat()
    except OSError:
        return None
    return (state.st_mtime_ns, state.st_size)


def fingerprint(env=None, config=None, root=None):
    """A impressão digital de perfil: o sha256 de `profile()` como JSON canônico. Veja `FINGERPRINT_KEY`.

    Entradas idênticas dão uma impressão digital em cada execução e máquina, e qualquer módulo, postura ou
    configuração diferente dá outra. Lembrada por processo para um ambiente e um estado
    dos arquivos de configuração, já que um hook a carimba em cada linha que escreve: reescrever a
    configuração do usuário ou um arquivo de seleção nomeado dá um digest novo. Um módulo editado sob um
    processo em execução não é visto até o próximo, que é onde as edições do checkout chegam.
    """
    env = os.environ if env is None else env
    files = [config_path(env)] + [Path(env[name]).expanduser() for name in
                                  ("HARNESS_PROJECT_CONFIG", "HARNESS_SESSION_CONFIG") if env.get(name)]
    key = (str(root or ROOT), tuple(sorted((name, value) for name, value in env.items()
                                           if name in ("HOME", "HARNESS_HOME", MODE_VARIABLE,
                                                       "HARNESS_PROJECT_CONFIG", "HARNESS_SESSION_CONFIG")
                                           or name.startswith(PREFIX))),
           tuple(_file_state(path) for path in files))
    if config is None and key in _FINGERPRINTS:
        return _FINGERPRINTS[key]
    text = json.dumps(profile(env, config, root), sort_keys=True, separators=(",", ":"))
    value = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if config is None:
        _FINGERPRINTS[key] = value
    return value


# Atribuição por módulo de tokens de contexto (AD-23). O contexto é compartilhado, então o que cada módulo pôs
# lá é estimado, nunca medido, e carrega o rótulo de estimativa suave do AD-12 e seu método.
# A estimativa é só de texto residente: o que é carregado antes do primeiro prompt. Um tipo listado
# é residente como sua entrada de listagem, seu nome e descrição, e seu corpo carrega sob demanda; o
# contexto de um hook chega por evento em tempo de execução e não é estimado aqui.
ATTRIBUTION_KEY = "context_attribution"
SOFT_ESTIMATE = "soft estimate"
CHARS_PER_TOKEN = 4.0
ATTRIBUTION_METHOD = ("chars/4 of resident text: a rule or stance variant whole; a skill, role or "
                      "workflow its name and description")
LISTED_KINDS = ("skills", "roles", "workflows")


def _listed_description(path):
    """A `description` do frontmatter que uma sessão lista, dobrada e com linhas de continuação
    literal incluídas, lida da forma como `scripts/cost_bench.py` a conta para a camada estática."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return ""
    if not lines or lines[0].strip() != "---":
        return ""
    out, taking = [], False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("description:"):
            out.append(line.split(":", 1)[1].strip())
            taking = True
        elif taking and line[:1] in (" ", "\t"):
            out.append(line.strip())
        else:
            taking = False
    return " ".join(part for part in out if part and part not in (">", "|", ">-", "|-", ">+", "|+"))


def _resident_text(kind, entry, unit, value, config, root=None):
    """O texto que uma unidade mantém residente, da primeira raiz primitiva que a contém, ou None."""
    directory, pattern = entry.get("directory"), entry.get("pattern")
    if not directory or not pattern or not _identifier(unit):
        return None
    if pattern == "*/*.md" and not _identifier(value):
        return None
    for source in primitive_roots(config, root, directory):
        if pattern == "*/*.md":
            path = source / unit / (value + ".md")
        else:
            path = source / pattern.replace("*", unit)
        if not path.is_file():
            continue
        if kind in LISTED_KINDS:
            return (_frontmatter(path).get("name") or unit) + ": " + _listed_description(path)
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, ValueError):
            return None
    return None


def context_attribution(env=None, config=None, root=None):
    """`{"estimand", "method", "modules": {"kind/unit": tokens}}` para a seleção em vigor.

    Resolvido de forma não estrita a partir da escada que `profile()` lê, então um módulo desligado remove
    a entrada desse módulo e não muda nenhuma outra. Cada módulo ligado e cada postura com
    texto residente tem uma entrada; uma unidade instalada em lugar nenhum, e um hook, não têm nenhuma.
    """
    env = os.environ if env is None else env
    config = _user_config(env, False) if config is None else config
    document = selection(env, strict=False, config=config, root=root)
    modules = {}
    for kind, entry in selection_kinds(root).items():
        switch = entry.get("value") == "switch"
        for unit, value in sorted((document.get(kind) or {}).items()):
            if (switch and value != "on") or not value:
                continue
            text = _resident_text(kind, entry, unit, None if switch else value, config, root)
            if text is not None:
                modules[kind + "/" + unit] = int(round(len(text) / CHARS_PER_TOKEN))
    return {"estimand": SOFT_ESTIMATE, "method": ATTRIBUTION_METHOD, "modules": modules}


def resolve(env=None, strict=True, table=False):
    """A postura em vigor: `{"stances": {dimension: variant}}`, cada dimensão presente.

    Um arquivo de configuração ausente é o conjunto padrão e nunca um mapa vazio, o que se leria como
    "nenhuma postura em vigor". A tabela de custo é opt-in com `table=True`, porque a maioria dos chamadores são
    hooks de caminho crítico respondendo uma pergunta, e percorrer sidecars para eles seria custo puro.
    """
    env = os.environ if env is None else env
    config = _user_config(env, strict)
    stances = _selection(config, env, strict)
    if not table:
        return {"stances": stances}
    return dict(table_for(stances, config, strict=strict), stances=stances)


def cost_table(env=None, strict=False, root=None):
    """A tabela da variante de custo ativa para um chamador que só tem um ambiente.

    Não estrita por padrão: um sidecar inutilizável em algum ponto da cadeia é um aviso na tabela,
    nunca um motivo para o trabalho em mãos parar.
    """
    env = os.environ if env is None else env
    config = _user_config(env, strict)
    return table_for(_selection(config, env, strict, root), config, strict=strict, root=root)


def selected(name, fallback=None, env=None, strict=True):
    """A variante de uma dimensão, ou `fallback` quando nada na escada a nomeia.

    Lê só a escada de posturas: um hook fazendo uma pergunta não deveria pagar pela tabela de custo.
    """
    env = os.environ if env is None else env
    return _selection(_user_config(env, strict), env, strict).get(name) or fallback


def permissions(env=None, strict=False):
    """A postura de permissão que o usuário selecionou, ou `inherit` quando a config não nomeia nenhuma.

    Não estrita por padrão: uma postura que ninguém consegue ler não é uma postura que o usuário escolheu, e um
    chamador que amplia autoridade com base nela estaria fazendo isso com base em um arquivo que não pôde abrir.
    """
    env = os.environ if env is None else env
    value = _user_config(env, strict).get("permissions")
    return value.strip() if isinstance(value, str) and value.strip() else "inherit"


def plan_allow_tools(env=None, strict=False):
    """Os globs de nome de ferramenta que o usuário permite durante o modo plano, estilo `fnmatch`. Vazio por padrão.

    Nada é inferido: um payload de PreToolUse não carrega dica de somente-leitura para uma ferramenta MCP, então a
    única coisa que pode dizer que uma ferramenta é segura para investigar com ela é o usuário a nomeando. Um valor
    que não é uma lista de strings não vazias não nomeia nada.
    """
    env = os.environ if env is None else env
    value = _user_config(env, strict).get(PLAN_TOOLS_KEY)
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def row_for(table, role):
    """A linha que governa um papel: a própria, ou a da sua banda quando é um trabalhador de banda.

    As bandas existem para que uma variante possa precificar trabalho para o qual não consegue nomear um papel, e os trabalhadores de banda
    são os papéis que carregam uma banda para dentro de um spawn. Uma linha indexada pelo papel vence a da banda,
    porque nomear o papel é a coisa mais específica que uma variante pode dizer.
    """
    rows = table.get("rows") if isinstance(table, dict) else None
    rows = rows if isinstance(rows, dict) else {}
    if role in rows:
        return rows[role]
    for band, name in BAND_ROLES.items():
        if name == role:
            return rows.get(band)
    return None


def _sibling(name):
    """Um módulo ao lado deste arquivo, ou None. Resolver uma postura nunca deve levantar exceção numa importação."""
    try:
        spec = importlib.util.spec_from_file_location(
            "harness_" + name.replace("-", "_"), str(Path(__file__).resolve().parent / (name + ".py")))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def budget_figures(row):
    """As metades do orçamento suave de uma linha que valem a pena ser ditas, indexadas como a linha as indexa.

    Uma metade nula é deixada de fora em vez de escrita como "sem orçamento", o que se leria como permissão para
    gastar sem limite, e uma metade abaixo de uma unidade vai junto: "cerca de 0 tokens de saída" se
    leria como uma instrução para não fazer nada, o que é um orçamento que ninguém escreveu.
    """
    if not isinstance(row, dict):
        return {}
    return {key: row[key] for key in BUDGET_KEYS
            if isinstance(row.get(key), int) and not isinstance(row[key], bool) and row[key] >= 1}


def budget_sentence(row):
    """A frase em que o orçamento suave de uma linha é declarado, ou None quando a linha não precifica nada.

    A única redação para todo brief que o harness escreve: o de um spawn nativo, anexado por
    `brief-guard`, e o de um trabalhador de papel isolado, anexado por `harness role run`. Um agente não pode
    ver a variante de custo que o precificou, então os números da linha são declarados no brief — todo
    número da tabela e nenhuma das palavras. É suave, porque um teto rígido truncaria
    o trabalho em vez do gasto.
    """
    parts = ["about {:,} {}".format(value, BUDGET_UNITS[key])
             for key, value in budget_figures(row).items()]
    if not parts:
        return None
    return ("\n\nExpected spend: " + " and ".join(parts) + ". Past that, finish if you are "
            "close; otherwise return what you have and say why.")


def budget_stated(text, detectors=None):
    """True quando este brief já se precifica sozinho, ou quando nada aqui consegue dizer.

    O que conta como um orçamento declarado pertence a `rule-detectors.py` e não a uma segunda cópia por
    chamador: uma frase que o detector ainda lê como ausente seria anexada para sempre e o
    número nunca se moveria. Um registro que não carrega, ou um sem o padrão, é
    "não é possível dizer", o que não anexa nada.
    """
    module = _sibling("rule-detectors") if detectors is None else detectors
    pattern = getattr(module, "BUDGET_RE", None)
    return pattern is None or bool(pattern.search(text or ""))


def tier_models(runtime="claude-code", root=None):
    """O `{class: native model}` do adaptador, classe mais forte primeiro, ou `{}` quando ilegível.

    Nomes de modelo pertencem a `adapters/<runtime>/bindings.json`, nunca ao código do hook: uma mudança
    de alinhamento é uma edição de dados, e um chamador que não obtém nada diz isso em vez de adivinhar.
    """
    path = (root or ROOT) / "adapters" / runtime / "bindings.json"
    try:
        tiers = json.loads(path.read_text(encoding="utf-8"))["tiers"]
        return {name: tiers[name] for name in TIER_CLASSES
                if isinstance(tiers.get(name), str) and tiers[name].strip()}
    except Exception:
        return {}


def ladder(runtime="claude-code", root=None):
    """Os modelos nativos do adaptador, classe mais forte primeiro, ou `[]` quando não pode ser lido."""
    return list(tier_models(runtime, root).values())
