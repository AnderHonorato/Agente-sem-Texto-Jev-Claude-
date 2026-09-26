#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exportação OTLP/HTTP opcional de linhas do ledger de uso. Desligado a menos que `config.json` a ligue.

O ledger é o registro e um backend é uma cópia reconstruível dele: toda linha é escrita primeiro
em `usage.jsonl`, e só então oferecida a um endpoint a partir do worker desacoplado, onde um
coletor lento ou morto não consegue alcançar a sessão. A entrega é ao-menos-uma-vez por design,
então um leitor deduplica por `harness.row_key` e mantém o maior `harness.exported_at`;
`harness usage export --since` reproduz uma janela.

Este módulo fica ao lado de `usage-log.py` em vez de em `lib/harness_core` porque o hook também é
um script standalone: é alcançado através de `~/.claude/hooks/harness`, que resolve para o
diretório de hooks do checkout e para nada acima dele. `usage-log.py` o carrega com o mesmo
resolvedor `sibling()` com que carrega os detectores, e uma cópia rodando longe dele não exporta
nada em vez de fazer a sessão falhar.

Nada aqui jamais registra, imprime ou grava um valor de cabeçalho. Veja docs/telemetry.md.
"""
import calendar
import importlib.util
import json
import os
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# O SessionEnd já rodou no momento em que o worker exporta, então o orçamento aqui é a paciência
# do usuário no próximo comando, não a do hook. Uma tentativa, sem retry: o ledger ainda guarda a
# linha, e `harness usage export --since` é o caminho de recuperação.
TIMEOUT = 2.0

# Um lote é limitado duas vezes: por linhas, para que uma reprodução de um mês seja muitas
# requisições modestas em vez de uma enorme, e por bytes, porque uma única linha carregando um
# mapa `rules` grande pode ter dezenas de kilobytes e coletores recusam corpos grandes demais.
MAX_ROWS = 100
MAX_BYTES = 1 << 20

SERVICE_NAME = "agent-harness"
# Uma linha de decisão mede uma chamada de provedor, não uma sessão, e carrega `input`, `output`
# e um preço sob os mesmos nomes que uma linha de sessão. Exportadas nuas cairiam nas mesmas
# colunas, e um backend somando `input` contaria a pergunta de um hook como gasto de sessão.
# Então os próprios campos de uma linha de decisão viajam sob um namespace próprio; veja `attributes`.
DECISION_KIND = "decision"
DECISION_PREFIX = "harness.decision."
SEVERITY_NUMBER = 9  # INFO, segundo o modelo de dados de logs OTLP.

# `native` é validado aqui e usado por `harness sync`, nunca por este exportador: o
# pass-through de runtime escreve as próprias configurações de telemetria de um runtime e não
# envia nada por si.
KNOWN_KEYS = ("export", "endpoint", "headers_env", "headers_file", "labels", "native",
              "decisions", "completion_claim", "allow_sample_rate")

# Os runtimes que o pass-through nativo pode configurar. `native` é `true` para todos eles,
# `false` para nenhum, ou a lista dos que nomeia: o Codex só aceita valores de cabeçalho como
# literais em `config.toml`, que o harness não vai escrever, então um coletor que autentica só
# pode ser alimentado nativamente a partir do Claude Code. Veja docs/telemetry.md.
NATIVE_RUNTIMES = ("claude-code", "codex")
DEFAULT_ENDPOINT = "http://localhost:4318"
# A amostra de comandos permitidos, mantida em sincronia com
# `decisions.DEFAULT_SAMPLE_RATE`, que este módulo não importa: a validação aqui não pode
# depender de um hook irmão ser carregável.
DEFAULT_SAMPLE_RATE = 20


def home():
    return Path(os.environ.get("HARNESS_HOME") or os.environ.get("HOME") or Path.home())


def config_path():
    return home() / ".config" / "agent-harness" / "config.json"


def read_config(path=None):
    try:
        with open(str(path or config_path()), encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def settings(cfg=None, path=None):
    """O bloco `telemetry` validado, ou `{"export": "off"}` quando não há nenhum.

    Levanta `ValueError` para um bloco que não pode ser honrado, para que a CLI possa recusar em
    voz alta enquanto o hook fica silencioso: um endpoint mal digitado deve parar uma
    sincronização, nunca uma sessão.
    """
    cfg = read_config(path) if cfg is None else cfg
    block = cfg.get("telemetry") if isinstance(cfg, dict) else None
    if block is None:
        return {"export": "off"}
    if not isinstance(block, dict):
        raise ValueError("telemetry must be an object")
    unknown = sorted(set(block) - set(KNOWN_KEYS))
    if unknown:
        # Um valor de cabeçalho na config é o único erro de digitação que vale a pena nomear:
        # colocaria uma credencial num arquivo que é backupeado, sincronizado e lido por toda
        # ferramenta que lê a config.
        if any(k in ("headers", "header", "authorization") for k in unknown):
            raise ValueError(
                "telemetry headers must be read from headers_env or headers_file; a header "
                "value in config.json is a credential in a configuration file")
        raise ValueError("telemetry does not take " + ", ".join(unknown))
    mode = block.get("export", "off")
    if mode not in ("off", "otlp"):
        raise ValueError("telemetry.export must be \"off\" or \"otlp\"; got " + repr(mode))
    endpoint = block.get("endpoint") or DEFAULT_ENDPOINT
    if not isinstance(endpoint, str) or not endpoint.startswith(("http://", "https://")):
        raise ValueError("telemetry.endpoint must be an http:// or https:// URL")
    headers_env = block.get("headers_env") or ""
    if not isinstance(headers_env, str):
        raise ValueError("telemetry.headers_env must be the name of an environment variable")
    if "=" in headers_env:
        raise ValueError(
            "telemetry.headers_env names an environment variable to read headers from; it is "
            "not the headers themselves")
    headers_file = block.get("headers_file") or ""
    if not isinstance(headers_file, str):
        raise ValueError("telemetry.headers_file must be a path")
    labels = block.get("labels") or {}
    if not isinstance(labels, dict) or any(not isinstance(v, (str, int, float, bool)) for v in labels.values()):
        raise ValueError("telemetry.labels must be an object of scalar values")
    native = native_runtimes(block.get("native", False))
    # O log de decisão local, que nunca sai da máquina e não faz parte de `export`: veja
    # `decisions.py`. Validado aqui porque é uma chave `telemetry` e uma chave desconhecida
    # naquele bloco para uma sincronização; o próprio exportador nunca a lê.
    decisions = block.get("decisions", True)
    if not isinstance(decisions, bool):
        raise ValueError("telemetry.decisions must be true or false; got " + repr(decisions))
    # A alegação de conclusão numa linha de stop-gate, desligada por padrão: `decisions.claim_enabled`.
    claim = block.get("completion_claim", False)
    if not isinstance(claim, bool):
        raise ValueError("telemetry.completion_claim must be true or false; got " + repr(claim))
    # Um em quantos comandos Bash permitidos é mantido como um negativo não avaliado:
    # `decisions.sample_rate`, 20 por padrão, 0 para nenhum.
    rate = block.get("allow_sample_rate", DEFAULT_SAMPLE_RATE)
    if isinstance(rate, bool) or not isinstance(rate, int) or rate < 0:
        raise ValueError("telemetry.allow_sample_rate must be a whole number of commands, one "
                         "of which is logged, or 0 for none; got " + repr(rate))
    return {"export": mode, "endpoint": endpoint.rstrip("/"), "headers_env": headers_env,
            "headers_file": headers_file, "labels": dict(labels), "native": native,
            "decisions": decisions, "completion_claim": claim, "allow_sample_rate": rate}


def native_runtimes(value):
    """`telemetry.native` como a lista de runtimes que nomeia, numa ordem estável.

    `true` é todo runtime e `false` é nenhum, então uma config escrita antes de a chave aceitar
    uma lista mantém seu significado. Um nome desconhecido é recusado em vez de ignorado: um erro
    de digitação de outra forma deixaria um runtime silenciosamente sem configuração e nada dito
    sobre isso.
    """
    if isinstance(value, bool):
        return list(NATIVE_RUNTIMES) if value else []
    if not isinstance(value, (list, tuple)) or any(not isinstance(n, str) for n in value):
        raise ValueError(
            "telemetry.native must be true, false, or a list of runtime names ("
            + ", ".join(NATIVE_RUNTIMES) + "); got " + repr(value))
    unknown = sorted(set(value) - set(NATIVE_RUNTIMES))
    if unknown:
        raise ValueError(
            "telemetry.native does not know the runtime " + ", ".join(repr(n) for n in unknown)
            + "; the runtimes are " + ", ".join(NATIVE_RUNTIMES))
    return [name for name in NATIVE_RUNTIMES if name in set(value)]


def parse_headers(text):
    """`name=value` por linha, ou a forma separada por vírgulas que `OTEL_EXPORTER_OTLP_HEADERS` usa."""
    out = {}
    for line in str(text or "").replace(",", "\n").splitlines():
        item = line.strip()
        if not item:
            continue
        name, sep, value = item.partition("=")
        name, value = name.strip(), value.strip()
        if not sep or not name or any(c.isspace() for c in name):
            raise ValueError("a telemetry header must read name=value")
        out[name] = value
    return out


def _in_git_work_tree(path):
    for parent in Path(path).resolve().parents:
        if (parent / ".git").exists():
            return True
    return False


def headers_from_file(path):
    """Cabeçalhos de um arquivo que está fora de toda árvore de trabalho e ilegível por outros usuários.

    Uma credencial dentro de um repositório está a um `git add -A` de ser publicada, e uma que
    qualquer conta na máquina consegue ler não é um segredo. Nem o valor nem o texto do arquivo
    aparece na recusa.
    """
    target = Path(path).expanduser()
    try:
        mode = target.stat().st_mode
    except OSError:
        raise ValueError("telemetry.headers_file {} cannot be read".format(target))
    if not stat.S_ISREG(mode):
        raise ValueError("telemetry.headers_file {} is not a regular file".format(target))
    if _in_git_work_tree(target):
        raise ValueError(
            "telemetry.headers_file {} is inside a git work tree; keep the credential outside "
            "every repository".format(target))
    if stat.S_IMODE(mode) & 0o007:
        raise ValueError(
            "telemetry.headers_file {} is readable by other users; `chmod 600` it".format(target))
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        raise ValueError("telemetry.headers_file {} cannot be read".format(target))
    return parse_headers(text)


def headers(config, env=None):
    """Os cabeçalhos da requisição, da variável de ambiente e do arquivo nomeados e de nenhum outro lugar."""
    env = os.environ if env is None else env
    out = {}
    name = config.get("headers_env") or ""
    if name:
        raw = env.get(name)
        if raw is None:
            raise ValueError("telemetry.headers_env names ${}, which is not set".format(name))
        out.update(parse_headers(raw))
    if config.get("headers_file"):
        out.update(headers_from_file(config["headers_file"]))
    return out


# ------------------------------------------------------------------ preços

# Carregado uma vez por processo: o exportador roda num worker desacoplado que envia um lote e
# sai, e reler o arquivo de preços por linha seria a coisa mais cara que faria.
_PRICING = []


def pricing():
    """O módulo de preços irmão, ou None quando esta cópia está rodando longe dele.

    O mesmo resolvedor que `usage-log.py` usa para os detectores, e a mesma consequência: uma
    cópia desses arquivos em outro lugar exporta linhas sem dólares em vez de falhar.
    """
    if not _PRICING:
        module = None
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pricing.py")
            spec = importlib.util.spec_from_file_location("harness_pricing", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            module = None
        _PRICING.append(module)
    return _PRICING[0]


def price_table(cfg=None):
    """A tabela de preços mesclada, ou `{}` quando preço algum pode ser obtido.

    Nunca levanta exceção. Um arquivo de preços ausente, um override `prices` malformado ou um
    irmão ausente custam a uma linha exportada seus dois atributos de dólar e nada mais: a linha
    ainda viaja, com seus tokens, exatamente como antes de preços existirem para exportar.
    """
    module = pricing()
    if module is None:
        return {}
    try:
        return module.load_prices(read_config() if cfg is None else cfg)
    except Exception:
        return {}


def row_prices(rows, table):
    """`(usd, as_of)` por linha, em ordem, ou `(None, "")` para cada uma quando preços não estão disponíveis.

    Precificado sobre o conjunto inteiro em vez de linha por linha, porque uma sessão do Claude
    Code é precificada com suas linhas de subagente em mãos — a cifra na linha de sessão já as inclui.
    """
    module = pricing()
    if module is not None and table:
        try:
            return module.priced(rows, table)
        except Exception:
            pass
    return [(None, "")] * len(rows)


# ------------------------------------------------------------------ o payload OTLP/JSON


def row_key(row):
    """A identidade estável de uma linha: a tupla sobre a qual o `row_key` de `usage-log.py` faz upsert, como texto.

    Uma reprodução reenvia a mesma string para a mesma linha, que é o que permite a um backend
    deduplicar um fluxo ao-menos-uma-vez.
    """
    return "|".join(str(row.get(k) or d) for k, d in (
        ("session_id", ""), ("runtime", "claude-code"), ("kind", "session"), ("agent_id", "")))


def _nanos(stamp):
    """Nanossegundos de epoch para um timestamp de ledger, ou None quando não parseia."""
    if not isinstance(stamp, str) or not stamp:
        return None
    text = stamp.replace("Z", "").split(".")[0]
    try:
        parsed = time.strptime(text, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    try:
        return int(calendar.timegm(parsed)) * 1000000000
    except (OverflowError, ValueError):
        return None


def exported_at(now=None):
    """O horário de exportação como uma string RFC 3339 UTC de largura fixa: `2026-09-21T18:04:05.123456Z`.

    Largura fixa, sempre seis dígitos fracionários e sempre `Z`, porque um backend que pousa
    atributos num mapa de string — o `otel_logs` do ClickHouse guarda `LogAttributes` como
    `Map(String, String)` — compara isso lexicamente, e só uma forma de largura fixa faz a ordem
    lexical igualar a ordem temporal. É o que distingue dois registros para um `harness.row_key`:
    o horário observado do OTLP não sobrevive a essa ingestão.
    """
    stamp = time.time() if now is None else float(now)
    whole = int(stamp // 1)
    micros = int((stamp - whole) * 1000000)
    if micros >= 1000000:  # só alcançável através de arredondamento de float numa fronteira de segundo
        whole, micros = whole + 1, 0
    return "{}.{:06d}Z".format(time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(whole)), micros)


def any_value(value):
    """Um `AnyValue` do OTLP. Ints viajam como strings decimais, que o mapeamento JSON exige."""
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    return {"stringValue": str(value)}


def attributes(row, config=None, version="", price=None, exported=None):
    """Os escalares planos da linha, suas stances, sua chave, seu preço, seu horário de exportação e os rótulos.

    Um mapa aninhado — `days`, `by_model`, `rules`, `counts` — viaja só no corpo: conjuntos de
    atributos são planos, e achatar cem fatias por dia em nomes de atributo tornaria toda linha
    uma coluna nova num backend. `stances` é a exceção, porque uma stance é uma dimensão pela
    qual um relatório agrupa: achata para um `harness.<dimension>` cada, e só aqui, que é por
    que `body_row` retira o mapa de volta do corpo.

    `price` é o `(usd, as_of)` no qual esta linha foi precificada. Uma linha sem preço não
    carrega nenhum atributo: um zero diria que a execução foi de graça em vez de que ninguém
    sabe quanto custou.

    `exported` é o carimbo `harness.exported_at`; veja essa função para saber por que todo
    registro carrega um. Linhas num único lote podem compartilhar um carimbo, o que é inofensivo:
    são chaves distintas.

    Uma linha `kind: "decision"` é uma chamada de provedor em vez de uma sessão, e seus campos
    viajam sob `harness.decision.*` — seu preço incluído — para que um backend que soma `input`
    ou `usd` sobre seus logs conte o que as sessões gastaram e não o que o harness gastou perguntando.
    """
    out = {}
    prefix = DECISION_PREFIX if row.get("kind") == DECISION_KIND else ""
    for key, value in sorted(row.items()):
        if value is None or key == "stances":
            continue
        if isinstance(value, (str, int, float, bool)):
            out[prefix + key] = value
    for dimension, variant in sorted((row.get("stances") or {}).items()):
        if isinstance(variant, (str, int, float, bool)):
            out["harness." + str(dimension)] = variant
    out["harness.row_key"] = row_key(row)
    out["harness.exported_at"] = exported or exported_at()
    usd, as_of = price or (None, "")
    if usd is not None:
        out[(prefix or "harness.") + "usd"] = float(usd)
        if as_of:
            out[(prefix or "harness.") + "price_as_of"] = str(as_of)
    stamped = row.get("harness_version") or version
    if stamped:
        out["harness.version"] = stamped
    for key, value in sorted(((config or {}).get("labels") or {}).items()):
        out[str(key)] = value
    return [{"key": k, "value": any_value(v)} for k, v in sorted(out.items())]


def body_row(row):
    """A linha como viaja no corpo: tudo que o ledger guarda menos o mapa `stances`.

    Um backend que faz parse de um corpo JSON achata um mapa aninhado nas suas próprias chaves
    com pontos, então um corpo carregando `stances` pousaria uma segunda cópia de toda stance ao
    lado dos atributos `harness.<dimension>` acima. Uma stance, um atributo: o mapa sai aqui e
    mais nada sai, porque nenhum outro campo aninhado também é exportado como atributos.
    """
    return dict((k, v) for k, v in row.items() if k != "stances")


def log_record(row, config=None, version="", now=None, price=None):
    seconds = time.time() if now is None else now
    now_nanos = int(seconds * 1000000000)
    return {
        "timeUnixNano": str(_nanos(row.get("ended")) or now_nanos),
        "observedTimeUnixNano": str(now_nanos),
        "severityNumber": SEVERITY_NUMBER,
        "severityText": "INFO",
        "body": {"stringValue": json.dumps(body_row(row), sort_keys=True)},
        # O mesmo instante do horário observado acima, na forma que sobrevive à ingestão.
        "attributes": attributes(row, config, version, price, exported_at(seconds)),
    }


def payload(rows, config=None, version="", now=None, prices=None):
    """Um corpo de requisição OTLP. `prices` é o `(usd, as_of)` por linha, na ordem dada."""
    prices = list(prices or []) + [None] * max(len(rows) - len(prices or []), 0)
    resource = [{"key": "service.name", "value": {"stringValue": SERVICE_NAME}}]
    if version:
        resource.append({"key": "service.version", "value": {"stringValue": version}})
    return {"resourceLogs": [{
        "resource": {"attributes": resource},
        "scopeLogs": [{"scope": {"name": SERVICE_NAME},
                       "logRecords": [log_record(r, config, version, now, p)
                                      for r, p in zip(rows, prices)]}],
    }]}


def batches(rows, max_rows=MAX_ROWS, max_bytes=MAX_BYTES):
    """Linhas agrupadas em requisições, limitadas por contagem e por tamanho codificado."""
    batch, size = [], 0
    for row in rows:
        cost = len(json.dumps(row)) + 2048  # o corpo da linha mais espaço para seus atributos
        if batch and (len(batch) >= max_rows or size + cost > max_bytes):
            yield batch
            batch, size = [], 0
        batch.append(row)
        size += cost
    if batch:
        yield batch


# ------------------------------------------------------------------ entrega


def endpoint_label(endpoint):
    """Só esquema e host. Um caminho ou uma query podem carregar um token; nenhum é jamais registrado."""
    try:
        parts = urllib.parse.urlsplit(endpoint)
        host = parts.hostname or ""
        if parts.port:
            host = "{}:{}".format(host, parts.port)
        return "{}://{}".format(parts.scheme, host)
    except Exception:
        return ""


def post(rows, config, request_headers, version="", timeout=TIMEOUT, opener=None, prices=None):
    """Faz POST de um lote. Levanta exceção em falha de transporte ou status; o chamador registra a classe."""
    url = config["endpoint"]
    if not url.endswith("/v1/logs"):
        url = url + "/v1/logs"
    body = json.dumps(payload(rows, config, version, None, prices)).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for name, value in request_headers.items():
        request.add_header(name, value)
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=timeout) as response:
            status = getattr(response, "status", None) or response.getcode()
            response.read()
    except urllib.error.HTTPError as exc:
        # Um HTTPError também é a resposta, e segura um socket até ser fechado.
        exc.close()
        raise
    if not 200 <= int(status) < 300:
        raise urllib.error.HTTPError(url, int(status), "OTLP export rejected", None, None)
    return len(rows)


def record_failure(path, endpoint, error, rows):
    """Uma linha no arquivo de erros já existente: quando, qual classe, quantas linhas, qual host."""
    if not path:
        return
    entry = {"time": time.time(), "error": type(error).__name__, "action": "otlp-export",
             "endpoint": endpoint_label(endpoint), "rows": rows}
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            stream.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def export_rows(rows, config=None, env=None, version="", errors_path=None,
                timeout=TIMEOUT, opener=None, dry_run=False, prices=None):
    """Envia linhas para o endpoint configurado. Retorna `(sent, failed)` e nunca levanta exceção.

    Com exportação desligada isso não abre socket nenhum e não lê credencial nenhuma: a primeira
    checagem é o modo, então uma máquina que não ligou a exportação se comporta exatamente como
    antes de ela existir.

    `prices` é a tabela de preços com que carimbar as linhas; sem uma dada é lida do arquivo de
    preços e dos próprios overrides `prices` do chamador, que é o que o hook faz. A precificação
    roda depois da checagem de modo e não pode fazer a exportação falhar: uma linha sem preço
    ainda viaja.
    """
    rows = [r for r in rows if isinstance(r, dict)]
    cfg = None
    try:
        if config is None:
            # Uma leitura do arquivo de config para tanto o endpoint quanto os overrides `prices`.
            cfg = read_config()
            config = settings(cfg)
    except ValueError as exc:
        record_failure(errors_path, "", exc, len(rows))
        return 0, len(rows)
    if config.get("export") != "otlp" or not rows:
        return 0, 0
    try:
        request_headers = headers(config, env)
    except ValueError as exc:
        record_failure(errors_path, config.get("endpoint", ""), exc, len(rows))
        return 0, len(rows)
    # Por identidade, porque um lote é uma fatia destes mesmos objetos de linha e uma linha não
    # tem chave própria até `row_key` construir uma.
    priced = {}
    if not dry_run:
        table = price_table(cfg) if prices is None else prices
        priced = dict((id(row), price) for row, price in zip(rows, row_prices(rows, table)))
    sent = failed = 0
    for batch in batches(rows):
        if dry_run:
            sent += len(batch)
            continue
        try:
            sent += post(batch, config, request_headers, version, timeout, opener,
                         [priced.get(id(row)) for row in batch])
        except Exception as exc:
            failed += len(batch)
            record_failure(errors_path, config.get("endpoint", ""), exc, len(batch))
    return sent, failed
