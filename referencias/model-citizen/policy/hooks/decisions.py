#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""O log de decisão: um registro local, somente para acréscimo, por julgamento que um hook do harness faz.

`~/.local/state/agent-harness/decisions.jsonl`, ao lado de `usage.jsonl`. O ledger diz o que uma
sessão gastou; este diz o que o harness decidiu e, onde a sessão depois mostrou, como a decisão
se desenrolou. Nada aqui alcança a rede, nada aqui é visível ao modelo, e nenhuma linha é jamais
reescrita: um resultado é um segundo registro unido ao primeiro por `decision_id`, então um
leitor do arquivo vê a decisão exatamente como o hook a fez.

    {"kind": "decision", "decision_id": "…", "point": "grade-bash", "session_id": "…",
     "ts": "2026-09-21T18:04:05Z", "input_sha256": "…", "input": "git push --force",
     "deterministic_answer": "ask", "outcome": null, "runtime": "claude-code",
     "harness_version": "0.12.0", "profile_fingerprint": "…", "module": "hooks/grade-bash",
     "schema_version": 1}
    {"kind": "outcome", "decision_id": "…", "point": "grade-bash", "session_id": "…",
     "ts": "…", "outcome": "ran", "harness_version": "0.12.0", "profile_fingerprint": "…",
     "module": "hooks/grade-bash", "schema_version": 1}

`input` é o texto que o hook julgou, limitado a MAX_INPUT (2 KiB) — um comando ou um brief, nunca
saída de ferramenta e nunca prosa do assistente. `input_sha256` é sobre o texto **sem o limite**,
então duas linhas cujo texto limitado é idêntico ainda são diferenciadas, e um comando longo pode
ser comparado contra seus próprios eventos posteriores.

`telemetry.completion_claim`, desligado por padrão, acrescenta `completion_claim` e seu hash a
uma linha de stop-gate: o final da última mensagem do assistente no turno, lido do transcript que
o evento Stop nomeia, ou uma alegação nula ao lado do motivo de não haver nenhuma. É o único
lugar onde este arquivo guarda prosa do assistente, por isso é um switch próprio e por isso está
desligado. Veja `claim_fields`.

Este módulo fica ao lado dos hooks em vez de em `lib/harness_core`, pela razão que `telemetry.py`
dá: um hook é alcançado através de `~/.claude/hooks/harness` e nada acima daquele diretório
resolve a partir dele. `lifecycle.py` o carrega com seu próprio `load()`.

Toda escrita é envolvida: uma falha de registro conta em `errors()` e não muda a decisão, saída
ou status de saída de nenhum hook. Veja docs/usage.md para o relatório e docs/telemetry.md para o switch.
"""
import hashlib
import importlib.util
import json
import os
import re
import time
import uuid
from pathlib import Path

# Os pontos que escrevem. Nomeados aqui para que o relatório possa listar um ponto que ainda não
# disparou, e para que um erro de digitação num ponto de chamada seja uma falha de teste em vez
# de um novo grupo silencioso.
POINTS = ("grade-bash", "stop-gate", "tier-agent-spawns", "brief-guard", "evasion-deny")

# O módulo que possui a decisão de cada ponto (AD-23): o id de hook cuja lógica a fez, nomeado
# como uma referência de seleção, `hooks/<id>`. O aviso de integração roda no caminho de disparo
# que `tier-agent-spawns` possui. Recusas de confinamento de papel, de framework e de evasão e a
# proteção de lançamento de Workflow não têm id, já que nenhum switch os desliga, então nomeiam
# `null`, assim como qualquer outro ponto que nenhum hook possui, como `decision-provider`, em
# vez de um chute.
MODULE_KEY = "module"
POINT_MODULES = {
    "grade-bash": "hooks/grade-bash",
    "stop-gate": "hooks/stop-gate",
    "tier-agent-spawns": "hooks/tier-agent-spawns",
    "brief-guard": "hooks/brief-guard",
    "evasion-deny": None,
    "role-confinement": None,
    "framework-spawn": None,
    "workflow-launch": None,
    "integration-descriptor": "hooks/tier-agent-spawns",
    # Uma linha por decisão que `grade-bash` pede ao provedor de decisão configurado.
    "governance": "hooks/grade-bash",
}

# 2 KiB. Muito além de qualquer comando ou do início de um brief, e pequeno o bastante para que
# as linhas de uma sessão continuem sendo um arquivo que uma pessoa consegue ler. O hash é sobre
# o texto sem o limite, então o limite perde evidência, nunca identidade.
MAX_INPUT = 2048

# Um ask de Bash sem PostToolUse correspondente até o fim da sessão. Não "negado": um usuário que
# recusou, um usuário que interrompeu o turno e uma sessão que travou parecem todos iguais aqui,
# e nomear um deles colocaria um rótulo no arquivo que ninguém mediu.
NOT_RUN = "not_run"
RAN = "ran"

# Os allows amostrados: uma fração dos comandos Bash que o harness deixou passar sem um prompt,
# escritos como linhas de `grade-bash` com `deterministic_answer: allow` e `sampled: true`. São
# negativos para avaliação em shadow — um check que só pode apertar um allow para um ask não tem
# nada contra o que medir seus alarmes falsos de outra forma — e não carregam resultado algum:
# "rodou" não diz nada sobre se optar por não interromper foi certo. Um em cada
# DEFAULT_SAMPLE_RATE por padrão, `telemetry.allow_sample_rate` para mudar isso e 0 para parar.
# A escolha é o próprio hash do comando, então uma nova execução do mesmo corpus amostra os
# mesmos comandos, e a linha nomeia a taxa em que foi tirada para que um leitor conheça o denominador.
DEFAULT_SAMPLE_RATE = 20

# Uma linha amostrada é o único lugar onde este log escreve texto sobre o qual ninguém foi
# consultado, então o texto é redigido primeiro e a linha guarda só o texto redigido: o valor de
# toda atribuição e de toda flag de credencial, toda forma que os detectores de regra combinam, e
# o diretório home como `~` para que nenhum nome de usuário alcance a linha. Essas formas são
# lidas do motor de medição vendorizado — veja `secret_shapes` — então há uma única lista e este
# arquivo não guarda cópia dela. `input_sha256` numa linha amostrada é sobre o texto **redigido**,
# diferente de toda outra linha: o hash de um original ao lado do texto redigido é um ataque de
# dicionário contra um segredo curto, que é a única forma de um valor poder ser recuperado da
# linha da qual foi tirado. A identidade dentro da amostra sobrevive, porque duas linhas que
# redigem de forma parecida são parecidas em tudo o que esta linha guardou.
REDACTED = "<redacted>"
# O motor de onde as formas vêm, na versão que `rule-detectors.py` fixa: uma lista, um arquivo,
# uma fixação. `tests/test_allow_sampling.py` falha quando este nome e aquele import se afastam.
ENGINE_WHEEL = "ruleprobe-0.1.0-py3-none-any.whl"
SHAPES_MODULE = "ruleprobe/detectors/common.py"
SHAPES_NAME = "SECRET_PATTERNS"
# Um valor é uma string entre aspas ou uma palavra pura, então `API_TOKEN="abc def"` perde tudo dela.
VALUE = r'''"[^"]*"|'[^']*'|\S+'''
# Uma atribuição começa uma palavra — depois de nada, depois de espaço em branco, ou depois do
# `;`, `&&`, `|` ou `(` que inicia o próximo comando — então `FOO=secret cmd` perde seu valor
# onde o `value` de `cmd --flag=value` é mantido. Uma flag de credencial é a outra forma de um
# segredo alcançar uma linha de comando, longa ou curta, com ou sem espaço depois dela.
ASSIGNMENT_RE = re.compile(r"(^|[\s;&|(])([A-Za-z_][A-Za-z0-9_]*)=(" + VALUE + ")")
CREDENTIAL_FLAGS = ("password", "passwd", "pass", "username", "user", "token", "api-key",
                    "api_key", "apikey", "secret", "key")
FLAG_RE = re.compile(r"(--(?:" + "|".join(CREDENTIAL_FLAGS) + r")(?:=|\s+))(" + VALUE + ")",
                     re.IGNORECASE)
# A forma curta leva seu valor anexado, como `-phunter2` faz; `-p` com um espaço depois é
# `mkdir -p dir` muito mais frequentemente do que uma senha, e esse valor é mantido.
SHORT_FLAG_RE = re.compile(r"(^|[\s;&|(])(-[pu])(" + VALUE + ")")

_SHAPES = []

# A alegação de conclusão: o final da última mensagem do assistente no turno, numa linha de
# stop-gate e em nenhum outro lugar. É o único lugar onde este log guarda prosa do modelo, então
# tem seu próprio switch e esse switch está desligado. 2 KiB dela, medidos em bytes como `input`
# é, hasheados sobre o todo.
MAX_CLAIM = 2048
# A leitura são os últimos CLAIM_TAIL_BYTES do arquivo, então custa o mesmo em um transcript de
# qualquer tamanho, e um arquivo além de MAX_TRANSCRIPT não é aberto de forma alguma — nada tão
# grande é um transcript cuja última linha este hook deveria estar buscando dentro do orçamento
# de um hook Stop.
CLAIM_TAIL_BYTES = 256 * 1024
MAX_TRANSCRIPT = 256 * 1024 * 1024
# Por que uma linha não carrega alegação nenhuma, registrado na própria linha. `no_transcript_path`
# é a lacuna do runtime e o resto é do arquivo; `error` é o leitor levantando exceção, o que nunca
# se viu acontecer. Um leitor do log distingue uma alegação que ninguém fez de uma alegação que
# não pôde ser lida.
CLAIM_MISSES = ("no_transcript_path", "unreadable", "oversized", "no_claim", "error")

_CONFIG = []
_ERRORS = [0]


def home():
    return Path(os.environ.get("HARNESS_HOME") or os.environ.get("HOME") or Path.home())


def state_dir():
    return home() / ".local" / "state" / "agent-harness"


def path():
    return state_dir() / "decisions.jsonl"


def config_path():
    return home() / ".config" / "agent-harness" / "config.json"


def read_config():
    """A config do usuário, lida no máximo uma vez por processo. `{}` quando não há nenhuma para ler."""
    if not _CONFIG:
        try:
            with open(str(config_path()), encoding="utf-8") as stream:
                data = json.load(stream)
        except (OSError, ValueError):
            data = {}
        _CONFIG.append(data if isinstance(data, dict) else {})
    return _CONFIG[0]


def enabled(cfg=None):
    """Se decisões são registradas: `telemetry.decisions`, que tem padrão ligado.

    A coleta é local e ligada por padrão, como o ledger de uso ao lado dela, porque os rótulos
    só valem a pena ter a partir do dia em que o hook começa a escrevê-los. `false` a desliga e o
    harness não escreve nada — nenhum arquivo, nenhum diretório. Um bloco `telemetry` que não é
    um objeto é uma configuração que ninguém consegue honrar, e também não escreve nada.
    """
    cfg = read_config() if cfg is None else cfg
    block = cfg.get("telemetry") if isinstance(cfg, dict) else None
    if block is None:
        return True
    if not isinstance(block, dict):
        return False
    return block.get("decisions", True) is True


def claim_enabled(cfg=None):
    """Se uma linha de stop-gate carrega a alegação de conclusão: `telemetry.completion_claim`.

    Desligado por padrão, ao contrário de `decisions` ao lado, porque este é o único campo no log
    que guarda prosa do assistente: uma linha que cita as últimas palavras do turno é uma coisa
    diferente de manter numa máquina compartilhada do que uma linha guardando um comando. Também
    não faz parte de `export` — uma linha de decisão não alcança endpoint nenhum seja lá o que
    `export` diga.
    """
    cfg = read_config() if cfg is None else cfg
    block = cfg.get("telemetry") if isinstance(cfg, dict) else None
    if not isinstance(block, dict):
        return False
    return block.get("completion_claim", False) is True


def sample_rate(cfg=None):
    """Um em quantos comandos permitidos é registrado: `telemetry.allow_sample_rate`, 20 por padrão.

    0 para a amostragem e não escreve linha de allow nenhuma. Um valor que este módulo não
    consegue honrar é lido como 0 em vez do padrão: `telemetry.settings` o recusa por nome quando
    a CLI lê o mesmo bloco, e um hook que não consegue ler sua própria configuração não deve
    registrar mais do que o usuário pediu. `telemetry.decisions: false` desliga isso junto com tudo o mais.
    """
    cfg = read_config() if cfg is None else cfg
    block = cfg.get("telemetry") if isinstance(cfg, dict) else None
    if block is None:
        return DEFAULT_SAMPLE_RATE
    if not isinstance(block, dict):
        return 0
    rate = block.get("allow_sample_rate", DEFAULT_SAMPLE_RATE)
    if isinstance(rate, bool) or not isinstance(rate, int) or rate < 0:
        return 0
    return rate


def in_sample(text, rate):
    """Se este comando é um dos um-em-`rate` que são registrados.

    O próprio hash do comando, nunca uma tiragem aleatória e nunca um relógio: o mesmo corpus
    reproduzido através desta função amostra os mesmos comandos, que é o que torna reproduzível
    uma medição feita contra essas linhas.
    """
    if not rate or not text:
        return False
    return int(digest(text)[:8], 16) % rate == 0


def secret_shapes():
    """As formas que os detectores de regra combinam, compiladas, ou None quando não podem ser lidas.

    Lidas de dentro do wheel vendorizado `ruleprobe` em vez de importadas dele: importar o motor
    dentro de um hook de PreToolUse custa um quinto de segundo, e uma cópia da lista neste
    arquivo seria tanto uma segunda fonte de verdade quanto, para o `harness lint`, um padrão de
    segredo escrito num arquivo commitado. `rule-detectors.py` pega a mesma lista do mesmo wheel,
    na mesma versão fixada. None para a amostragem, que é a direção segura: nenhuma linha em vez
    de uma não redigida.
    """
    if not _SHAPES:
        _SHAPES.append(_read_shapes())
    return _SHAPES[0]


def _read_shapes(root=None):
    """`SHAPES_NAME` de dentro de `SHAPES_MODULE` no wheel fixado, compilado, ou None.

    None para toda forma que isso pode falhar — nenhum checkout, nenhum wheel, um wheel que não
    é um zip, um módulo que foi renomeado, uma lista que não é literal — porque cada um deles
    significa a mesma coisa para o chamador: o texto não pode ser redigido, então não é escrito.
    """
    import ast
    import zipfile

    root = checkout_root() if root is None else Path(root)
    if root is None:
        return None
    wheel = root / "lib" / "vendor" / ENGINE_WHEEL
    if not wheel.is_file():
        return None
    try:
        with zipfile.ZipFile(str(wheel)) as archive:
            source = archive.read(SHAPES_MODULE).decode("utf-8")
        for node in ast.parse(source).body:
            if not isinstance(node, ast.Assign):
                continue
            if any(getattr(target, "id", "") == SHAPES_NAME for target in node.targets):
                return [re.compile(pattern) for pattern in ast.literal_eval(node.value)]
    except Exception:
        return None
    return None


def _value(match, keep):
    """Uma correspondência com seu valor substituído por REDACTED, mantendo os primeiros `keep` grupos."""
    return "".join(match.group(index + 1) for index in range(keep)) + REDACTED


def redact(text, shapes, home_dir=None):
    """`text` com todo valor em que um segredo pode se esconder substituído por REDACTED. Veja SHAPES_MODULE.

    Atribuições e flags de credencial perdem seus valores, entre aspas ou não; toda forma em
    `shapes` é substituída onde quer que apareça; e o diretório home é escrito `~`, para que uma
    linha não carregue nome de usuário mesmo quando um caminho nomeia um.
    """
    text = ASSIGNMENT_RE.sub(lambda m: m.group(1) + m.group(2) + "=" + REDACTED, text)
    text = FLAG_RE.sub(lambda m: _value(m, 1), text)
    text = SHORT_FLAG_RE.sub(lambda m: _value(m, 2), text)
    for shape in shapes:
        text = shape.sub(REDACTED, text)
    root = str(home() if home_dir is None else home_dir).rstrip("/")
    return text.replace(root, "~") if root and root != "/" else text


def errors():
    """Quantas escritas este processo engoliu. A decisão de um hook nunca depende disso."""
    return _ERRORS[0]


def now_ts(now=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if now is None else now))


def digest(text):
    return hashlib.sha256((text or "").encode("utf-8", "replace")).hexdigest()


def checkout_root():
    """A raiz do checkout ao qual este arquivo pertence, ou None quando roda fora de um.

    A mesma busca que `usage-log.py` faz, e pela mesma razão: um hook é um script, não um
    import da CLI.
    """
    here = Path(os.path.realpath(__file__)).parent
    for parent in [here] + list(here.parents):
        if (parent / "VERSION").is_file() and (parent / "bin" / "harness").exists():
            return parent
    return None


def harness_version():
    """A versão no arquivo `VERSION` na raiz deste checkout, ou None fora de um.

    Uma cópia rodando fora de um checkout carimba nenhuma versão em vez de um chute.
    """
    root = checkout_root()
    if root is None:
        return None
    try:
        return (root / "VERSION").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def match_key(event, text):
    """A identidade que um evento posterior re-deriva para encontrar esta decisão de novo.

    O id de uso de ferramenta quando o payload do runtime carrega um — nenhum dos dois
    adaptadores carrega hoje, e ambos passam o payload por `lifecycle.normalize()` intocado,
    então se um começar a carregá-lo os dois lados da junção o ganham de uma vez — e senão a
    sessão e o hash do texto que o hook julgou. Dois comandos idênticos numa sessão compartilham
    uma chave, o que une o mesmo resultado a ambos em vez de a nenhum.
    """
    event = event if isinstance(event, dict) else {}
    for name in ("tool_use_id", "call_id"):
        value = event.get(name)
        if isinstance(value, str) and value:
            return value
    return str(event.get("session_id") or "") + ":" + digest(text)


def decision_id(point, key):
    """O id reproduzível de uma decisão em `point` sobre `key`. Veja `match_key`."""
    return digest(point + "|" + key)[:32]


# Quanto do final um evento que chega lê para descobrir se sua decisão foi registrada. Uma
# decisão feita segundos atrás está no fim do arquivo, e uma leitura limitada é o que mantém o
# custo de um hook de PostToolUse constante à medida que o log cresce.
TAIL_BYTES = 256 * 1024


def tail_text(target=None, limit=TAIL_BYTES):
    """Os últimos `limit` bytes do log como texto, ou "" quando não há nada para ler."""
    target = Path(target) if target else path()
    try:
        with open(str(target), "rb") as stream:
            try:
                stream.seek(-limit, os.SEEK_END)
            except OSError:
                stream.seek(0)
            return stream.read().decode("utf-8", "replace")
    except OSError:
        return ""


def _message_of(record):
    """O objeto de mensagem num registro de transcript, ou None para um registro que não guarda nenhum.

    Ambos os runtimes numa única forma: o Claude Code guarda a mensagem sob `message`, um
    rollout do Codex embrulha o mesmo objeto num `response_item`, e cada um carrega seu próprio
    `role`. Um registro de sidechain é o turno de um subagente e nunca parte do turno próprio da sessão.
    """
    if not isinstance(record, dict) or record.get("isSidechain"):
        return None
    if record.get("type") in ("assistant", "user"):
        message = record.get("message")
    elif record.get("type") == "response_item":
        message = record.get("payload")
    else:
        message = record
    return message if isinstance(message, dict) else None


def _message_text(message):
    """A prosa de uma mensagem: todo bloco de texto, unido, e nada mais.

    Um bloco sem `text` é uma chamada de ferramenta, um pensamento ou uma imagem, nenhum dos
    quais é uma alegação.
    """
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = [b["text"] for b in content
             if isinstance(b, dict) and isinstance(b.get("text"), str) and b["text"]]
    return "\n".join(parts).strip()


def _starts_the_turn(message):
    """Se esta mensagem são as próprias palavras do usuário, e portanto a borda distante do turno atual.

    O Claude Code escreve um resultado de ferramenta como um registro `user`, então uma varredura
    que parasse em todo registro `user` pararia no meio do turno que está lendo; uma que não
    parasse em nenhum pegaria uma alegação do turno anterior quando este turno terminou numa
    chamada de ferramenta.
    """
    if message.get("role") != "user":
        return False
    content = message.get("content")
    if isinstance(content, list):
        return not any(isinstance(b, dict)
                       and b.get("type") in ("tool_result", "function_call_output")
                       for b in content)
    return True


def _claim_in(tail):
    """A alegação num final de transcript, ou None quando este turno terminou sem uma.

    Mais nova primeiro, voltando até a mensagem do usuário que abriu o turno. As linhas são
    divididas só por `\n`: uma string JSON pode carregar U+2028, U+2029, U+0085 e os outros
    caracteres em que `splitlines` quebra, e dividir ali rasgaria um registro ao meio e leria
    silenciosamente um turno mais antigo. A primeira linha da janela costuma ser um fragmento,
    que falha ao parsear e é descartado.
    """
    for line in reversed(tail.split("\n")):
        if '"assistant"' not in line and '"user"' not in line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        message = _message_of(record)
        if message is None:
            continue
        if _starts_the_turn(message):
            return None
        if message.get("role") != "assistant":
            continue
        text = _message_text(message)
        if text:
            return text
    return None


def read_claim(transcript):
    """`(claim, miss)`: a alegação do turno e por que não há nenhuma, exatamente um dos dois definido.

    O miss é um motivo sobre o qual um leitor do log pode agir. `no_transcript_path` é um
    runtime que não nomeou nenhum arquivo — uma lacuna no que o evento carrega, não na sessão —
    onde `unreadable`, `oversized` e `no_claim` são todos sobre um arquivo que foi nomeado. A
    leitura é limitada dos dois lados, veja MAX_TRANSCRIPT e CLAIM_TAIL_BYTES, então custa o
    mesmo em qualquer comprimento de sessão.
    """
    if not transcript:
        return None, "no_transcript_path"
    target = os.path.expanduser(str(transcript))
    try:
        if os.path.getsize(target) > MAX_TRANSCRIPT:
            return None, "oversized"
        with open(target, "rb") as stream:
            try:
                stream.seek(-CLAIM_TAIL_BYTES, os.SEEK_END)
            except OSError:
                stream.seek(0)
            tail = stream.read().decode("utf-8", "replace")
    except OSError:
        return None, "unreadable"
    text = _claim_in(tail)
    return (text, None) if text else (None, "no_claim")


def _capped(text):
    """Os últimos MAX_CLAIM **bytes** da alegação, cortados de volta a um limite de caractere.

    Bytes em vez de caracteres porque o limite existe para restringir o arquivo em disco, e um
    emoji são quatro deles.
    """
    raw = text.encode("utf-8")
    return text if len(raw) <= MAX_CLAIM else raw[-MAX_CLAIM:].decode("utf-8", "ignore")


def claim_fields(transcript, cfg=None):
    """Os campos de alegação de conclusão para uma linha de decisão, ou `{}` quando não há nenhum a adicionar.

    `{}` sempre que o switch está desligado, então a linha é byte a byte a linha escrita antes
    disso existir. Com ele ligado a linha sempre diz algo: a alegação e seu hash, ou uma alegação
    nula ao lado do motivo de não haver nenhuma. Evidência ausente é registrada, nunca um motivo
    para perder a decisão para a qual era evidência, então nada aqui levanta exceção.
    """
    if not claim_enabled(cfg):
        return {}
    try:
        text, miss = read_claim(transcript)
    except Exception:
        text, miss = None, "error"
    if text is None:
        return {"completion_claim": None, "completion_claim_miss": miss}
    return {"completion_claim": _capped(text), "completion_claim_sha256": digest(text)}


# O log cresce compativelmente, sob a regra que `usage-log.py` declara para o ledger de uso: uma
# mudança acrescenta um campo, uma renomeação vem com uma dobra (`nome antigo: nome novo`), nada
# é removido no lugar e nenhuma linha antiga é reescrita. Uma linha sem SCHEMA_KEY é anterior à
# versão e lê como versão 0.
SCHEMA_KEY = "schema_version"
# A versão 1 é lançada pela primeira vez na v0.14.0 e carrega `profile_fingerprint`; veja `usage-log.py`.
SCHEMA_VERSION = 1
FIELD_FOLDS = {}
FINGERPRINT_KEY = "profile_fingerprint"
_POSTURE = []


def profile_fingerprint():
    """A fingerprint do perfil em vigor, a partir do `posture.py` ao lado deste arquivo, ou None.

    Carregado por caminho, como `lifecycle.py` carrega este arquivo, e lembrado pelo processo.
    Uma cópia rodando longe do seu resolvedor, ou um resolvedor que falha, carimba nulo em vez de um chute.
    """
    if not _POSTURE:
        location = Path(os.path.realpath(__file__)).parent / "posture.py"
        try:
            spec = importlib.util.spec_from_file_location("harness_decisions_posture", str(location))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            module = None
        _POSTURE.append(module)
    try:
        return _POSTURE[0].fingerprint() if _POSTURE[0] else None
    except Exception:
        return None


def module_of(point):
    """O `hooks/<id>` que possui decisões em `point`, ou None para um ponto que nenhum hook possui."""
    return POINT_MODULES.get(point) if isinstance(point, str) else None


def fold(row, folds=None):
    """Uma cópia de `row` com todo campo renomeado sob seu nome atual; veja o `fold` do usage-log."""
    folds = FIELD_FOLDS if folds is None else folds
    out = dict(row)
    for old, new in folds.items():
        if old in out:
            value = out.pop(old)
            out.setdefault(new, value)
    return out


def _append(row, target=None):
    """Uma linha, um `write`. Acrescentar é a única forma pela qual este arquivo já é mudado."""
    row = dict(row, **{SCHEMA_KEY: SCHEMA_VERSION})
    if FINGERPRINT_KEY not in row:
        row[FINGERPRINT_KEY] = profile_fingerprint()
    if MODULE_KEY not in row:
        row[MODULE_KEY] = module_of(row.get("point"))
    target = Path(target) if target else path()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(target.parent), 0o700)
    except OSError:
        pass
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (json.dumps(row, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    return target


def _decision_row(point, answer, text, event, runtime, key, now, written=None):
    """A própria linha de decisão, com `written` substituindo `text` quando está redigido."""
    return {"kind": "decision",
            "decision_id": uuid.uuid4().hex if key is None else decision_id(point, key),
            "point": point,
            "session_id": str((event or {}).get("session_id") or "") if event else "",
            "ts": now_ts(now), "input_sha256": digest(text),
            "input": (text if written is None else written)[:MAX_INPUT],
            "deterministic_answer": answer, "outcome": None,
            "runtime": runtime or os.environ.get("HARNESS_RUNTIME", ""),
            "harness_version": harness_version()}


def record(point, answer, text="", event=None, runtime="", key=None, target=None, now=None,
           transcript=None):
    """Registra um julgamento. Retorna seu `decision_id`, ou None quando nada foi escrito.

    Nunca levanta exceção. Uma escrita falha é contada e o chamador continua com a decisão que já
    tinha feito: um log que pode mudar uma resposta de permissão é pior que nenhum log.

    `key` torna o id reproduzível, então um evento que chega depois pode nomear esta decisão sem
    ter lido o arquivo; sem uma, o id é novo e ninguém vai uni-lo a nada.

    `transcript` é o arquivo do qual uma alegação de conclusão é lida, e não acrescenta nada à
    linha a menos que o chamador passe um e o switch esteja ligado: veja `claim_fields`.
    """
    try:
        if not enabled():
            return None
        text = text if isinstance(text, str) else ""
        row = _decision_row(point, answer, text, event, runtime, key, now)
        row.update(claim_fields(transcript))
        identity = row["decision_id"]
        _append(row, target)
        return identity
    except Exception:
        _ERRORS[0] += 1
        return None


def record_allowed(command, event=None, runtime="", target=None, now=None, cfg=None):
    """Registra um comando permitido, se estiver na amostra. Retorna seu id, ou None. Nunca levanta exceção.

    Os negativos para avaliação em shadow: `deterministic_answer: allow`, `sampled: true` e a
    taxa em que foi tirado. Só um comando que o próprio harness permitiu chega aqui — um comando
    sobre o qual não disse nada é responsabilidade do runtime e ainda pode receber prompt ou ser
    recusado, então não é evidência de um allow. A linha não carrega resultado nem chave de
    correspondência, porque não há julgamento aqui para rotular e um allow que depois "rodou" não
    avalia nada; nada se une a ele, `close_session` o ignora e `usage --by decision` o conta
    separado das linhas avaliadas. O texto é redigido antes de ser limitado, ao contrário do
    texto de um prompt que o usuário viu. Veja DEFAULT_SAMPLE_RATE.
    """
    try:
        if not isinstance(command, str) or not command.strip() or not enabled(cfg):
            return None
        rate = sample_rate(cfg)
        if not in_sample(command, rate):
            return None
        shapes = secret_shapes()
        if shapes is None:
            return None
        written = redact(command, shapes)
        row = _decision_row("grade-bash", "allow", command, event, runtime, None, now,
                            written=written)
        # O hash de uma linha amostrada é sobre o texto redigido, não o original: veja REDACTED.
        row.update({"input_sha256": digest(written), "sampled": True, "sample_rate": rate})
        _append(row, target)
        return row["decision_id"]
    except Exception:
        _ERRORS[0] += 1
        return None


def observe(decision_id, outcome, point="", session_id="", target=None, now=None):
    """Registra o resultado de uma decisão anterior. Nunca levanta exceção; retorna se uma linha foi escrita.

    A linha de decisão mantém seu `null`. Um resultado é seu próprio registro, e um leitor os une.
    """
    try:
        if not decision_id or not enabled():
            return False
        _append({"kind": "outcome", "decision_id": decision_id, "point": point,
                 "session_id": str(session_id or ""), "ts": now_ts(now), "outcome": outcome,
                 "harness_version": harness_version()}, target)
        return True
    except Exception:
        _ERRORS[0] += 1
        return False


def observe_if_logged(identity, outcome, point="", session_id="", target=None, now=None):
    """Registra um resultado só para uma decisão que este log de fato guarda. Nunca levanta exceção.

    A maioria dos eventos que poderiam carregar um resultado não segue decisão nenhuma — o
    harness responde à pergunta de permissão numa pequena minoria de chamadas Bash — e um
    resultado sem nada a que se unir seria tanto uma contagem errada quanto um arquivo que cresce
    a cada chamada de ferramenta. A leitura do final é limitada; uma decisão mais antiga que o
    final fica sem rótulo, o que o relatório mostra como tal.
    """
    try:
        if not identity or not enabled():
            return False
        if identity not in tail_text(target):
            return False
    except Exception:
        _ERRORS[0] += 1
        return False
    return observe(identity, outcome, point, session_id, target, now)


def read_rows(target=None, folds=None):
    """Todo registro bem formado no log, dobrado, mais antigo primeiro. Um arquivo ilegível é nenhuma linha.

    Um campo ou versão de schema que este leitor não conhece é carregado, nunca recusado.
    """
    target = Path(target) if target else path()
    rows = []
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rows
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            row = fold(row, folds)
            if row.get("decision_id"):
                rows.append(row)
    return rows


def joined(rows):
    """Linhas de decisão com seu resultado preenchido, mais antigas primeiro.

    O primeiro resultado registrado para um `decision_id` é o que vale: um segundo registro para
    a mesma decisão é um evento duplicado, não uma mudança de ideia, e um arquivo só-para-acréscimo
    não tem como dizer que o anterior estava errado.
    """
    outcomes = {}
    for row in rows:
        if row.get("kind") == "outcome" and row["decision_id"] not in outcomes:
            outcomes[row["decision_id"]] = row.get("outcome")
    out = []
    for row in rows:
        if row.get("kind") == "outcome":
            continue
        result = row.get("outcome")
        if result is None:
            result = outcomes.get(row["decision_id"])
        out.append(dict(row, outcome=result))
    return out


def close_session(session_id, points=("grade-bash",), outcome=NOT_RUN, target=None, now=None):
    """Rotula as decisões sem resposta desta sessão no SessionEnd. Retorna quantas foram rotuladas.

    Um ask de Bash cujo PostToolUse nunca chegou é a resposta da sessão a ele, e a sessão acabou:
    nada mais jamais vai chegar. Só os pontos cujo resultado é observado dessa forma são
    fechados, então uma decisão que simplesmente ainda não foi rotulada continua sem rótulo e
    aparece na fração não rotulada do relatório em vez de como um resultado fabricado. Um allow
    amostrado é ignorado: ninguém foi consultado sobre ele, então "não rodou" seria um rótulo
    sobre um prompt que nunca existiu.
    """
    try:
        if not session_id or not enabled():
            return 0
        rows = read_rows(target)
        answered = set(r["decision_id"] for r in rows if r.get("kind") == "outcome")
        closed = 0
        for row in rows:
            if row.get("kind") == "outcome" or row.get("session_id") != session_id:
                continue
            if row.get("point") not in points or row["decision_id"] in answered:
                continue
            if row.get("sampled"):
                continue
            answered.add(row["decision_id"])
            if observe(row["decision_id"], outcome, row.get("point") or "", session_id,
                       target, now):
                closed += 1
        return closed
    except Exception:
        _ERRORS[0] += 1
        return 0
