#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Alimenta o gasto medido de volta ao orquestrador: uma linha de turno, uma linha por subagente terminado.

Quatro eventos, todos na thread pai. `SubagentStart` e `SubagentStop` registram quando um agente
começou e o que custou. `PostToolUse` em `Agent` reporta um retorno síncrono no momento em que chega,
e diz quantos agentes estão rodando quando isso passa da largura da postura. `UserPromptSubmit`
reporta o turno e cada subagente que terminou desde o prompt anterior — o que é como um
spawn em segundo plano, cujo `PostToolUse` dispara no lançamento sem totais, é reportado de qualquer forma.

Sete fatos moldam o arquivo inteiro:

- **O número de tokens da resposta de uma ferramenta descreve só a última resposta do subagente.** Medido num
  retorno ao vivo: `tool_response.usage.output_tokens` dizia 3.143 contra 10.575 realmente gastos em
  dezenove respostas. O número real é somado a partir da própria transcrição do subagente, uma vez por
  id de mensagem no máximo campo a campo, pela função de linha por agente de `usage-log.py` e não por uma
  segunda cópia dessa lógica aqui.
- **Estes hooks rodam concorrentemente, como processos separados.** Então o estado é dividido em dois. Um evento
  de subagente é uma linha abaixo de 4 KB anexada a `<session>.events.jsonl` através de um descritor
  `O_APPEND`, que nenhum manipulador jamais reescreve e que portanto não pode perder um registro. Tudo
  que a thread principal lê-modifica-escreve mora em `<session>.json`, sob um `flock` exclusivo em
  `<session>.lock` com uma espera limitada. Sem trava, sem escrita, e nada emitido.
- **Nada lento acontece sob a trava.** `SubagentStart` e `SubagentStop` nunca a tomam de jeito
  nenhum, e os dois eventos de thread principal somam a transcrição de um subagente antes de adquiri-la. Um stop
  que levasse quatro segundos para ler enquanto segura a trava faria o prompt esperando atrás
  dele passar fome, e esse prompt silenciosamente perderia sua linha.
- **Um registro que não pode ser calculado ainda é um registro.** Um stop é registrado no diário num `finally`,
  com totais nulos quando a soma falhou e `partial` quando um orçamento o cortou pela metade. Um agente cujo
  stop se perdesse contaria como rodando pelo resto da sessão e a linha de
  largura dispararia falsamente para sempre; um start sem stop também decai depois de três horas.
- **O gasto de um subagente é somado quando é reportado, não quando ele para.** Medido ao vivo: um
  `SubagentStop` disparou enquanto a transcrição do agente ainda mantinha nada além de registros `user`, o
  stop foi registrado no diário com totais nulos, e a única linha que a sessão jamais imprimiu para aquele agente
  dizia `spend unknown` — enquanto reproduzir a mesma carga um momento depois rendeu 297. Então um stop
  que não carrega número, ou um em que uma resposta ainda estava sendo escrita, é somado de novo no
  momento em que está prestes a ser nomeado, antes da trava, dentro de um orçamento de relógio de parede compartilhado por todo
  agente que esse evento reporta. O retorno também espera um momento limitado pela última resposta
  terminar de ser escrita, diz `(so far)` quando isso nunca acontece, e o stop que o diário traz depois
  levanta os totais da sessão sem o agente ser anunciado uma segunda vez.
- **Uma linha vale a pena ser dita uma vez.** `spend unknown` nomeia seu agente e é dita uma vez, porque nenhum
  evento posterior pode colocar um número nele e uma sessão que a repete ensina o orquestrador a
  pular o feed. O que os números medem também é dito uma vez, antes do primeiro deles. Um agente
  retomado com uma mensagem de acompanhamento, por outro lado, para uma vez por rodada contra um id de agente,
  e cada uma dessas rodadas é uma conclusão que o feed deve uma linha — cumulativa, porque uma
  transcrição cobre todas elas. Se tal rodada chegou não é uma pergunta que a forma da transcrição
  pode responder: ela termina na resposta concluída da rodada anterior de qualquer forma. Então uma rodada
  posterior é resolvida por seu número ultrapassar o já reportado, e é re-somada a cada
  evento, silenciosamente, até que o faça.
- **Leituras são limitadas em todo lugar.** A transcrição pai é lida a partir de um offset salvo, confiável
  só enquanto o inode e o hash do primeiro registro ainda combinam, e a partir de 8 MiB antes do
  fim num início a frio. O diário é lido a partir do seu próprio offset salvo, então os totais de uma sessão longa
  só podem crescer. A transcrição de um subagente é limitada por bytes e pelo relógio.

Nenhum orçamento, limiar, nome de modelo ou nome de papel mora aqui: todo número vem da tabela de
custo, todo switch de `switches.turn_feed`, `switches.nudge_at`, `switches.session_nudge_at`
e `switches.max_parallel`.
Uma variante que não define nenhum deles não alimenta nada. Qualquer falha, seja qual for, não emite nada e sai com 0,
e nenhuma linha que o feed emite é jamais uma decisão. O empurrão de sessão nova é uma recomendação, então
dizê-lo também registra um evento de adesão, que `adherence.py` responde depois.
"""
import errno
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - a platform with no advisory locking
    fcntl = None

HOOKS = Path(__file__).resolve().parent
PREFIX = "usage-feed: "
# Uma linha de diário é um `os.write`. Bem abaixo de PIPE_BUF, o que é o que torna um append atômico.
MAX_LINE = 4096
# Quantos ids de mensagem ficam abertos para uma linha posterior levantar, mais novo mantido e mais velho descartado. Uma
# resposta de API é escrita como várias linhas repetindo seu id, e uma resposta cujo id é descartado
# antes do seu número final, maior, chegar seria contada duas vezes; uma cauda deste tamanho está bem além
# dessa janela.
OPEN_TAIL = 64
MAX_LISTED = 5
# Stops esperando por uma linha, e ids cujo gasto já está nos totais. Ambos limitam até onde o arquivo de
# estado de uma sessão pode crescer, e ambos estão bem além de qualquer fan-out real.
MAX_PENDING = 200
MAX_COUNTED = 1000
# Um início a frio lê essa quantidade da cauda da transcrição, não o arquivo inteiro.
COLD_TAIL = 8 * 1024 * 1024
READ_BUDGET = 3.0
# O que a transcrição de um subagente pode custar a um hook que tem dez segundos para tudo.
AGENT_BUDGET = 4.0
AGENT_BYTES = 8 * 1024 * 1024
# Quanto tempo um retorno síncrono pode esperar pela última resposta do subagente terminar de ser
# escrita, e com que frequência ele olha. Ambos estão bem dentro do timeout do hook, e a espera é sobre
# uma cauda de 256 KB em vez da transcrição.
SETTLE_BUDGET = 1.0
SETTLE_STEP = 0.15
SETTLE_TAIL = 256 * 1024
# O que somar no momento do relatório pode custar a um evento, compartilhado por todo agente que esse evento nomeia. Com
# vários agentes pendentes, os que ele não alcança mantêm seu lugar e são somados na próxima vez.
REPORT_BUDGET = 4.0
# O mínimo desse orçamento com que um agente é tentado. Abaixo disso o agente espera pelo
# próximo evento em vez de ser somado numa fração de tempo e reportado como sem número.
REPORT_SLICE = 0.5
# Quantos eventos podem tentar somar um stop que ainda não tem resposta nenhuma. Uma transcrição que nunca
# ganha uma é um fato, não uma corrida, e tentar de novo para sempre gastaria o orçamento à toa.
UNSUMMED_TRIES = 3
LOCK_WAIT = 2.0
# Um start sem stop desta idade não está rodando; algo o terminou sem dizer isso.
RUNNING_TTL = 3 * 3600
FEED_TTL = 14 * 86400
PRUNE_EVERY = 86400
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
# Como um tipo de agente pode se parecer antes de ser permitido em texto injetado ou no diário.
AGENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
UNNAMED = "other"
MODES = ("off", "thresholds", "every-turn")


def sibling(name):
    """Um módulo ao lado deste hook, ou None. Um feed nunca falha ruidosamente por causa de uma importação."""
    try:
        spec = importlib.util.spec_from_file_location(
            "harness_" + name.replace("-", "_"), str(HOOKS / (name + ".py")))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def _open(path):
    """O único lugar onde a transcrição pai é aberta, para que um teste possa medir o que uma leitura custa."""
    return open(str(path), "rb")


def plural(number, noun):
    """`1 tool call`, `15 tool calls`, `135,000 output tokens`. Todo número emitido faz sentido lido."""
    return "{:,}".format(number) + " " + noun + ("" if number == 1 else "s")


# --------------------------------------------------------------------------- paths


def home(env):
    return Path(env.get("HARNESS_HOME") or env.get("HOME") or Path.home())


def feed_dir(env):
    return home(env) / ".local" / "state" / "agent-harness" / "feed"


def paths(session_id, env):
    """`(state, journal, lock)` para uma sessão, ou None quando o id não é um nome que escreveríamos."""
    if not isinstance(session_id, str) or not IDENTIFIER.match(session_id):
        return None
    directory = feed_dir(env)
    return (directory / (session_id + ".json"), directory / (session_id + ".events.jsonl"),
            directory / (session_id + ".lock"))


def ensure_dir(directory):
    try:
        if not directory.is_dir():
            os.makedirs(str(directory), 0o700)
        return True
    except OSError:
        return directory.is_dir()


# --------------------------------------------------------------------------- the journal


def journal_append(path, record):
    """Uma linha, um `os.write`, num descritor `O_APPEND`. Nunca lê-modifica-escreve."""
    data = (json.dumps(record, ensure_ascii=True) + "\n").encode("utf-8")
    if len(data) > MAX_LINE or not ensure_dir(path.parent):
        return False
    try:
        handle = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    except OSError:
        return False
    try:
        written = os.write(handle, data)
        if written == len(data):
            return True
        # Uma escrita curta deixa um fragmento. Terminá-la é tudo o que se deve: o leitor descarta
        # uma linha que não parseia, e o próximo registro então começa numa linha própria.
        if not data[:written].endswith(b"\n"):
            os.write(handle, b"\n")
        return False
    except OSError:
        return False
    finally:
        os.close(handle)


# --------------------------------------------------------------------------- the reader's state


def new_state():
    return {"version": 3, "offset": 0, "size": 0, "inode": None, "head": None, "partial": False,
            "session": {"output": 0, "tool_calls": 0},
            "turn": {"output": 0, "tool_calls": 0},
            "previous_turn": {"output": 0, "tool_calls": 0},
            "subagents": {"output": 0, "tool_calls": 0, "count": 0, "unknown": 0},
            "journal_offset": 0, "running": {}, "pending": [], "counted": [],
            "figures": {}, "unsummed": {}, "open": [], "pruned": 0, "said_turn": None,
            "rounds": {}, "said_unknown": [], "said_measure": False,
            "context": None, "said_nudge": [], "turns": 0}


def load_state(path):
    """O estado da sessão, ou um novo. Um arquivo que não conseguimos ler é um arquivo do qual recomeçamos."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return new_state()
    if not isinstance(data, dict) or data.get("version") != 3:
        return new_state()
    state = new_state()
    state.update(data)
    for key in ("session", "turn", "previous_turn", "subagents"):
        value = state.get(key)
        state[key] = value if isinstance(value, dict) else new_state()[key]
        for name, blank in new_state()[key].items():
            if not isinstance(state[key].get(name), int) or isinstance(state[key].get(name), bool):
                state[key][name] = blank
    for key in ("offset", "size", "journal_offset", "pruned", "turns"):
        if not isinstance(state.get(key), int) or isinstance(state.get(key), bool):
            state[key] = 0
    if not isinstance(state.get("running"), dict):
        state["running"] = {}
    figures = state.get("figures")
    state["figures"] = figures if isinstance(figures, dict) else {}
    for agent, pair in list(state["figures"].items()):
        if not (isinstance(pair, list) and len(pair) == 2
                and all(isinstance(v, int) and not isinstance(v, bool) for v in pair)):
            del state["figures"][agent]
    unsummed = state.get("unsummed")
    state["unsummed"] = unsummed if isinstance(unsummed, dict) else {}
    for agent, entry in list(state["unsummed"].items()):
        # `[caminho registrado, tentativas até agora]`. Uma forma que isto não reconhece é uma tentativa que
        # não pode fazer, e descartá-la só deixa o agente contado como desconhecido.
        if not (isinstance(entry, list) and len(entry) == 2 and isinstance(entry[0], str)
                and isinstance(entry[1], int) and not isinstance(entry[1], bool)):
            del state["unsummed"][agent]
    rounds = state.get("rounds")
    state["rounds"] = rounds if isinstance(rounds, dict) else {}
    for agent, value in list(state["rounds"].items()):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            del state["rounds"][agent]
    state["said_measure"] = bool(state.get("said_measure"))
    for key in ("pending", "counted", "open", "said_unknown", "said_nudge"):
        if not isinstance(state.get(key), list):
            state[key] = []
    state["said_unknown"] = [v for v in state["said_unknown"] if isinstance(v, str)]
    state["said_nudge"] = [v for v in state["said_nudge"]
                           if isinstance(v, int) and not isinstance(v, bool) and v > 0]
    size = state.get("context")
    if not (isinstance(size, int) and not isinstance(size, bool) and size > 0):
        state["context"] = None
    return state


def save_state(path, state):
    """Atômico e privado. Chamado antes da leitura lenta assim como depois dela."""
    state["pending"] = state.get("pending", [])[-MAX_PENDING:]
    state["counted"] = state.get("counted", [])[-MAX_COUNTED:]
    state["said_unknown"] = state.get("said_unknown", [])[-MAX_COUNTED:]
    for stale in list(state.get("rounds", {}))[:max(0, len(state.get("rounds", {}))
                                                    - MAX_COUNTED)]:
        del state["rounds"][stale]
    for stale in list(state.get("unsummed", {}))[:max(0, len(state.get("unsummed", {}))
                                                      - MAX_PENDING)]:
        del state["unsummed"][stale]
    if not ensure_dir(path.parent):
        return
    tmp = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    try:
        handle = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(handle, json.dumps(state).encode("utf-8"))
        finally:
            os.close(handle)
        os.replace(str(tmp), str(path))
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


class Lock(object):
    """Um `flock` exclusivo com uma espera limitada. Indisponível ou disputado significa não emitir nada.

    Todo escritor do estado do leitor é um processo de hook com dez segundos para tudo, e
    nada lento é feito enquanto isto é mantido. Esperar mais de alguns segundos por um
    número que o próximo prompt vai recalcular de qualquer forma é pior que pular a linha.
    """

    def __init__(self, path, wait=LOCK_WAIT):
        self.path = path
        self.wait = wait
        self.handle = None

    def __enter__(self):
        if fcntl is None or not ensure_dir(self.path.parent):
            return False
        try:
            self.handle = os.open(str(self.path), os.O_WRONLY | os.O_CREAT, 0o600)
        except OSError:
            return False
        deadline = time.monotonic() + self.wait
        while True:
            try:
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Um arquivo de trava nunca é escrito, então sem isto sua idade é a de sua criação e a
                # varredura abaixo acabaria apagando o arquivo que uma sessão ativa está segurando.
                try:
                    os.utime(str(self.path), None)
                except OSError:
                    pass
                return True
            except (IOError, OSError) as exc:
                if getattr(exc, "errno", None) not in (errno.EACCES, errno.EAGAIN):
                    break
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.01)
        os.close(self.handle)
        self.handle = None
        return False

    def __exit__(self, *exc):
        if self.handle is not None:
            try:
                fcntl.flock(self.handle, fcntl.LOCK_UN)
            finally:
                os.close(self.handle)
                self.handle = None
        return False


def prune(directory, state, keep, now=None):
    """No máximo uma vez por dia, descarta os arquivos de sessões que nada tocou em duas semanas.

    Os três arquivos de uma sessão vão juntos ou nenhum, julgados pelo mais novo deles: um arquivo
    de estado reescrito a cada prompt ao lado de um diário em que ninguém anexou por um mês ainda é uma sessão
    ativa. `keep` é esta sessão, que nunca é candidata por mais velhos que seus arquivos pareçam.
    """
    now = time.time() if now is None else now
    if now - state.get("pruned", 0) < PRUNE_EVERY:
        return
    state["pruned"] = int(now)
    sessions = {}
    try:
        entries = list(directory.iterdir())
    except OSError:
        return
    for entry in entries:
        stem = entry.name.split(".", 1)[0]
        if stem == keep:
            continue
        try:
            if not entry.is_file():
                continue
            sessions.setdefault(stem, []).append((entry, entry.stat().st_mtime))
        except OSError:
            continue
    for files in sessions.values():
        if now - max(mtime for _, mtime in files) <= FEED_TTL:
            continue
        for entry, _ in files:
            try:
                entry.unlink()
            except OSError:
                continue


# --------------------------------------------------------------------------- the parent transcript


def _slot(state, mid):
    """O máximo aberto para um id de mensagem, mais novo por último, mais velho descartado após a cauda."""
    entries = state["open"]
    if mid:
        for item in entries:
            if item[0] == mid:
                return item
    item = [mid, 0, []]
    entries.append(item)
    del entries[:max(0, len(entries) - OPEN_TAIL)]
    return item


def _whole(value):
    """Um número de tokens como um inteiro, ou 0. Nada que uma transcrição possa conter levanta exceção daqui para fora.

    `OverflowError` é a que importa: JSON admite `1e400`, Python o lê como um infinito,
    e `int()` nisso levanta exceção. Um registro é lido uma vez, o offset após ele é salvo, e uma
    exceção não capturada ali silenciaria o feed pelo resto da sessão.
    """
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


#: O que uma resposta leu, através dos três campos em que é reportada. Eles não se sobrepõem:
#: `input_tokens` é o que foi enviado sem cache, e os outros dois são o prefixo lido do
#: cache e o prefixo escrito nele, então o contexto é a soma deles e não qualquer um isolado.
CONTEXT_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def _context(usage):
    """O tamanho de contexto de uma resposta. Zero quando os campos estão ausentes, o que não é um tamanho."""
    total = 0
    for key in CONTEXT_KEYS:
        total += max(0, _whole(usage.get(key)))
    return total


def _apply(state, entry):
    """Uma linha de transcrição contra os totais correntes. Linhas de sidechain pertencem a um subagente."""
    if not isinstance(entry, dict) or entry.get("isSidechain"):
        return
    kind = entry.get("type")
    message = entry.get("message")
    message = message if isinstance(message, dict) else {}
    if kind == "user":
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
            return
        if entry.get("isMeta") or entry.get("isCompactSummary"):
            return
        # Um prompt real fecha o turno. Um vazio não é um turno que valha a pena lembrar, então ele
        # nunca desloca o último turno que gastou algo.
        if state["turn"]["output"] or state["turn"]["tool_calls"]:
            state["previous_turn"] = state["turn"]
        state["turn"] = {"output": 0, "tool_calls": 0}
        return
    if kind != "assistant":
        return
    mid = message.get("id") if isinstance(message.get("id"), str) else ""
    usage = message.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    context = _context(usage)
    if context:
        # O que a próxima resposta vai reler, conforme a resposta mais nova registrada. Não somado
        # e não um máximo: um contexto que encolheu porque a sessão foi compactada de fato
        # encolheu, e o número mais velho e maior descreve uma sessão que não existe mais.
        state["context"] = context
    slot = _slot(state, mid)
    output = _whole(usage.get("output_tokens"))
    if output > slot[1]:
        # Só o aumento é somado, então uma contagem parcial de streaming seguida do número
        # verdadeiro é uma mensagem contada uma vez no seu maior valor.
        for name in ("session", "turn"):
            state[name]["output"] += output - slot[1]
        slot[1] = output
    for index, block in enumerate(message.get("content") or []):
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        key = block.get("id") or str(block.get("apiBlockIndex", index))
        if key in slot[2]:
            continue
        slot[2].append(key)
        for name in ("session", "turn"):
            state[name]["tool_calls"] += 1


def _align(handle, offset, size):
    """O início da próxima linha em ou após `offset`. Um offset salvo no meio de uma linha se realinha para frente."""
    if offset <= 0:
        return 0
    if offset >= size:
        return size
    handle.seek(offset - 1)
    if handle.read(1) == b"\n":
        return offset
    handle.seek(offset)
    raw = handle.readline()
    return size if not raw.endswith(b"\n") else offset + len(raw)


def _identity(handle):
    """`(inode, hash da cabeça, tamanho)`. Uma transcrição substituída de qualquer tamanho falha nisto, não só uma mais curta.

    O hash cobre a primeira linha da transcrição em vez de 512 bytes fixos, porque um arquivo
    jovem mais curto que isso ainda está sendo anexado dentro da janela que uma fatia fixa
    cobriria, e sua identidade mudaria sob ela a cada turno. Um primeiro registro é escrito uma vez.
    """
    stat = os.fstat(handle.fileno())
    handle.seek(0)
    head = handle.read(512)
    cut = head.find(b"\n")
    if cut >= 0:
        head = head[:cut]
    return stat.st_ino, hashlib.sha256(head).hexdigest()[:16], stat.st_size


def advance(state, transcript, save=None, budget=READ_BUDGET):
    """Lê do offset estabelecido até o EOF, limitado por `COLD_TAIL` e pelo relógio.

    `save` é chamado assim que o offset e a identidade do arquivo estão estabelecidos e antes de uma única linha
    ser parseada: um hook morto no seu timeout não deve deixar o próximo repetir o mesmo trabalho
    para sempre. `timed_out` no estado retornado diz que a leitura desistiu, e o chamador fica quieto.
    """
    path = Path(os.path.expanduser(str(transcript)))
    try:
        handle = _open(path)
    except OSError:
        if save:
            save(state)
        return state
    with handle:
        try:
            inode, head, size = _identity(handle)
        except OSError:
            return state
        if (state.get("inode") != inode or state.get("head") != head
                or state["offset"] > size or size < state["size"]):
            # Compactação, uma rotação, uma substituição — de qualquer tamanho. O que veio antes é incognoscível
            # sobre a transcrição; o que o diário registrou ainda é verdade e permanece, assim como
            # o que já foi dito. Um reset que de fato encolheu o contexto rearma o empurrão
            # de sessão através do próprio tamanho, não esquecendo que a linha foi alimentada.
            seen = state.get("inode") is not None
            kept = {key: state[key] for key in
                    ("journal_offset", "running", "pending", "counted", "figures", "unsummed",
                     "subagents", "pruned", "rounds", "said_unknown", "said_nudge", "turns")}
            state = dict(new_state(), **kept)
            state["inode"], state["head"] = inode, head
            state["offset"] = max(0, size - COLD_TAIL)
            state["partial"] = seen or state["offset"] > 0
        try:
            state["offset"] = _align(handle, state["offset"], size)
        except OSError:
            return state
        state["size"] = size
        if save:
            save(state)
        if state["offset"] >= size:
            return state
        position = state["offset"]
        deadline = time.monotonic() + budget
        handle.seek(position)
        for counted, raw in enumerate(handle):
            # Uma linha ainda sendo escrita não é uma linha; deixá-la não consumida é o que faz a
            # próxima leitura pegá-la inteira.
            if not raw.endswith(b"\n"):
                break
            position += len(raw)
            try:
                _apply(state, json.loads(raw.decode("utf-8", "replace")))
            except ValueError:
                pass
            if not counted % 256 and time.monotonic() > deadline:
                state["partial"] = True
                state["timed_out"] = True
                break
    state["offset"] = position
    return state


# --------------------------------------------------------------------------- subagents


def agent_transcript(transcript_path, session_id, agent_id):
    """`<dirname(transcript)>/<session>/subagents/agent-<id>.jsonl`, ou None.

    Um agente da ferramenta Workflow fica um nível mais fundo, sob `subagents/workflows/wf_*/`. Ambos os lugares
    são nomeados, em vez de percorridos: uma busca recursiva de toda a árvore de subagentes de uma sessão é
    trabalho ilimitado para uma pergunta com duas respostas possíveis.
    """
    if not (isinstance(agent_id, str) and IDENTIFIER.match(agent_id)):
        return None
    if not (isinstance(session_id, str) and IDENTIFIER.match(session_id)):
        return None
    if not transcript_path:
        return None
    base = Path(os.path.expanduser(str(transcript_path))).parent / session_id / "subagents"
    name = "agent-" + agent_id + ".jsonl"
    try:
        if (base / name).is_file():
            return base / name
        found = sorted(base.glob("workflows/*/" + name))
    except OSError:
        return None
    return found[0] if found else None


def readable(path):
    """Se uma transcrição de subagente está lá para ser somada, ponto final.

    A única coisa que separa `spend unknown` de `spend not yet recorded`: um arquivo que não
    está lá nunca vai render um número, enquanto um arquivo que está lá e ainda não tem resposta
    é um flush dentro do qual este hook disparou.
    """
    if not path:
        return False
    try:
        return os.path.isfile(str(path)) and os.access(str(path), os.R_OK)
    except OSError:
        return False


def redact(path, env):
    """Um caminho de transcrição de subagente pronto para o diário: o prefixo home vira `~`, ou nada.

    O diário é um registro de contagens, e um caminho sob o home do usuário carrega o nome da
    conta dele. Um caminho que não está sob este home não é gravado; o leitor o rederiva do
    id de sessão em vez disso, que é o que `agent_transcript` já faz.
    """
    if not path:
        return ""
    text, root = str(path), str(home(env))
    return "~" + text[len(root):] if text.startswith(root + os.sep) else ""


def expand(value, env, agent_id):
    """O caminho que um `~/…` registrado no diário nomeia, quando ainda nomeia a própria transcrição deste agente.

    O nome é checado contra o próprio id do registro para que uma linha do diário, seja lá quem a escreveu,
    só possa apontar este hook para o arquivo que ela alega ser.
    """
    if not (isinstance(value, str) and value.startswith("~/")
            and isinstance(agent_id, str) and IDENTIFIER.match(agent_id)):
        return None
    path = home(env) / value[2:]
    return path if path.name == "agent-" + agent_id + ".jsonl" else None


def agent_totals(path, budget=None):
    """`{output, tool_calls, agent_type, partial}` a partir da própria transcrição do subagente, ou None.

    A soma é a função de linha por agente de `usage-log.py`, reutilizada em vez de reimplementada: é
    o código que já conta um id de mensagem uma vez no seu maior valor, que é a única
    forma de passar do número da última resposta que uma resposta de ferramenta reporta. Recebe um teto de bytes e um
    relógio aqui, porque isto roda dentro de um timeout de hook e um agente muito grande de outra forma
    derrubaria o processo inteiro junto com ele.
    """
    module = sibling("usage-log")
    if module is None or not path:
        return None
    budget = AGENT_BUDGET if budget is None else budget
    try:
        row = module._agent_row(Path(path), budget=budget, max_bytes=AGENT_BYTES)
    except Exception:
        return None
    if not isinstance(row, dict):
        return None
    return {"output": int(row.get("output") or 0), "tool_calls": int(row.get("tool_calls") or 0),
            "agent_type": agent_name(row.get("agent_type")), "partial": bool(row.get("partial"))}


def tail_state(path, max_bytes=SETTLE_TAIL):
    """`(há uma resposta, ela terminou de ser escrita)` a partir da cauda da transcrição.

    O Claude Code escreve uma resposta de API como vários registros repetindo seu id de mensagem. Os
    primeiros carregam `stop_reason: null` e um `output_tokens` parcial de streaming; o registro que encerra
    a resposta carrega um motivo. Contado em 1.418 ids de mensagem em transcrições reais de subagente,
    o registro que carregava um motivo tinha o maior número daquele id todas as vezes, e os arquivos
    cujo último registro não carregava nenhum eram execuções que tinham sido interrompidas — então um motivo no último
    registro é a resposta estar completa, e sua ausência é uma resposta ainda chegando.

    Um registro sem chave `stop_reason` nenhuma veio de um escritor cujo streaming isto não consegue
    julgar, e é tomado como está em vez de esperado. Só a cauda é lida, então perguntar
    custa o mesmo numa transcrição grande e numa pequena.

    A primeira metade do par é a que a corrida de flush depende: uma transcrição contendo só
    registros `user` e `attachment` não tem resposta para julgar, o que não é o mesmo fato que uma
    resposta que terminou. Um arquivo ilegível não reporta nenhum dos dois — seu chamador pergunta a `readable`.
    """
    try:
        with open(str(path), "rb") as handle:
            size = os.fstat(handle.fileno()).st_size
            if size > max_bytes:
                handle.seek(size - max_bytes)
                handle.readline()
            lines = handle.read().splitlines()
    except OSError:
        return False, True
    for raw in reversed(lines):
        try:
            entry = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            continue  # Uma linha ainda sendo escrita não é uma linha.
        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        message = message if isinstance(message, dict) else {}
        if "stop_reason" not in message:
            return True, True
        return True, bool(message.get("stop_reason"))
    return False, True


def tail_settled(path, max_bytes=SETTLE_TAIL):
    """Se a transcrição de um subagente termina numa resposta que terminou de ser escrita."""
    return tail_state(path, max_bytes)[1]


def settled_totals(path, budget=None, step=None, clock=None, sleep=None, read_budget=None):
    """`agent_totals` com `settled`, depois de uma espera limitada por uma resposta terminada chegar.

    Só a cauda barata é consultada enquanto se espera; a transcrição é somada uma vez, depois, então
    a espera inteira custa uma leitura e no máximo `budget` segundos por quantas vezes olhou. Um
    número que para de se mover não é tomado como o fim da resposta — uma contagem parcial de streaming
    pode repetir — então o fim da resposta é a única coisa que interrompe a espera antecipadamente, e uma espera
    que se esgota deixa ao chamador um número para marcar `(so far)`.

    Nenhuma resposta ainda também é esperada da mesma forma, e é para isso que a espera serve principalmente: um stop
    dispara enquanto a transcrição do agente ainda mantém só os registros que o pai escreveu nela.
    Uma transcrição que não está lá não é esperada — nenhuma espera faz um arquivo faltando aparecer — e
    uma legível que nunca ganha uma resposta retorna None, que seu chamador reporta como gasto
    ainda não registrado em vez de gasto desconhecido.
    """
    if not readable(path):
        return None
    clock = time.monotonic if clock is None else clock
    sleep = time.sleep if sleep is None else sleep
    budget = SETTLE_BUDGET if budget is None else budget
    step = SETTLE_STEP if step is None else step
    seen, settled = tail_state(path)
    deadline = clock() + budget
    while not (seen and settled) and clock() + step <= deadline:
        sleep(step)
        seen, settled = tail_state(path)
    totals = agent_totals(path, budget=read_budget)
    if totals is not None:
        totals["settled"] = settled
    return totals


#: A que a soma de um agente no momento do relatório chegou. Um dict de totais é um número; estes dois não são.
PENDING = "pending"
ABSENT = "absent"


def settle_many(items, budget=None, clock=None, sleep=None):
    """`{agent id: totals | PENDING | ABSENT}` para quantos de `items` um orçamento permitir.

    Este é o custo inteiro de somar no momento do relatório, e é gasto uma vez por evento em vez de
    uma vez por agente: um turno que finaliza oito subagentes não deve esperar oito vezes. A cada agente é
    dado o que resta do orçamento, e um agente que o orçamento nunca alcança está simplesmente ausente do
    resultado — seu stop mantém seu lugar e é somado no próximo evento em vez deste
    estourar o timeout do hook. Chamado antes da trava ser tomada, nunca sob ela.
    """
    clock = time.monotonic if clock is None else clock
    budget = REPORT_BUDGET if budget is None else budget
    deadline = clock() + budget
    out = {}
    for agent_id, path in items:
        if agent_id in out:
            continue
        if not readable(path):
            out[agent_id] = ABSENT
            continue
        left = deadline - clock()
        # A um agente é dado no máximo metade do que resta para esperar e metade para ler, então a passagem
        # inteira cabe dentro do orçamento seja qual for a ordem em que os agentes vieram. Abaixo do piso não
        # é sequer tentado: uma soma cortada depois de um décimo de segundo reportaria um número
        # que existe como um que ainda não chegou, o que é pior que reportá-lo depois.
        if left < REPORT_SLICE and out:
            break
        slice_ = max(left, REPORT_SLICE) / 2.0
        totals = settled_totals(path, budget=min(SETTLE_BUDGET, slice_), clock=clock, sleep=sleep,
                                read_budget=min(AGENT_BUDGET, slice_))
        out[agent_id] = PENDING if totals is None else totals
    return out


def agent_name(value, fallback="unknown"):
    """Um tipo de agente pronto para injetar e para o diário. Texto livre vira `other`, nunca ele mesmo."""
    if value is None or value == "":
        return fallback
    if isinstance(value, str) and AGENT_NAME.match(value):
        return value
    return UNNAMED


# --------------------------------------------------------------------------- the journal, ingested


def journal_records(journal_file, offset):
    """Cada registro inteiro após `offset`, lido e nada mais.

    `ingest` dobra os mesmos bytes para dentro do estado travado. Esta é a leitura que acontece antes
    da trava, então o evento sabe quais stops está prestes a nomear e pode somá-los enquanto ninguém
    está esperando por isso.
    """
    out = []
    try:
        handle = open(str(journal_file), "rb")
    except OSError:
        return out
    with handle:
        handle.seek(offset if offset > 0 else 0)
        for raw in handle:
            if not raw.endswith(b"\n"):
                break
            try:
                record = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if isinstance(record, dict) and isinstance(record.get("id"), str):
                out.append(record)
    return out


def needs_sum(record):
    """Se o número de um stop registrado no diário é um a se tomar como final.

    Dois stops não são: aquele cuja soma não pôde ser feita quando disparou — a corrida de flush, onde
    nenhuma resposta tinha sido escrita ainda — e aquele cujo número foi lido de uma resposta ainda
    sendo escrita ou de uma transcrição que um teto cortou pela metade. Ambos são somados de novo quando o agente
    é reportado.
    """
    if record.get("t") != "stop":
        return False
    return not record.get("summed") or bool(record.get("partial"))


def record_path(record, payload, env):
    """Onde está a transcrição de um stop registrado no diário: o que ele anotou, ou onde estaria."""
    agent_id = record.get("id")
    return expand(record.get("path"), env, agent_id) or agent_transcript(
        payload.get("transcript_path"), payload.get("session_id"), agent_id)


def to_settle(state, journal_file, payload, env, first=None):
    """`[(agent id, path)]` que valem a pena somar antes deste evento tomar a trava, `first` à frente.

    Três fontes, na ordem em que valem o orçamento: o agente que este evento está retornando,
    os stops de eventos anteriores que ainda estão sem número, e os stops que este evento está
    prestes a ingerir. Uma tentativa que já esgotou suas chances é descartada em vez de perguntada de novo.
    """
    items = [first] if first and first[0] else []
    seen = {agent for agent, _ in items}
    for record in state.get("pending") or []:
        agent_id = record.get("id")
        if (not record.get("awaiting") or agent_id in seen
                or record.get("tries", 0) >= UNSUMMED_TRIES):
            continue
        seen.add(agent_id)
        items.append((agent_id, record_path(record, payload, env)))
    for agent_id, entry in (state.get("unsummed") or {}).items():
        if agent_id in seen or entry[1] >= UNSUMMED_TRIES:
            continue
        seen.add(agent_id)
        items.append((agent_id, expand(entry[0], env, agent_id) or agent_transcript(
            payload.get("transcript_path"), payload.get("session_id"), agent_id)))
    rounds = dict(state.get("rounds") or {})
    for record in journal_records(journal_file, state.get("journal_offset", 0)):
        agent_id = record["id"]
        repeat = False
        if record.get("t") == "stop":
            rounds[agent_id] = rounds.get(agent_id, 0) + 1
            repeat = rounds[agent_id] > 1
        if agent_id in seen or not (needs_sum(record) or repeat):
            continue
        seen.add(agent_id)
        items.append((agent_id, record_path(record, payload, env)))
    return items


def settle_before_lock(state_file, journal_file, payload, env, first=None):
    """A totalidade do trabalho lento que um evento de thread principal faz, feito sem nenhuma trava mantida."""
    return settle_many(to_settle(load_state(state_file), journal_file, payload, env, first))


def apply_settled(record, outcome):
    """Uma soma no momento do relatório sobre o stop a que pertence. Um número substitui um número; nada
    tira um — um parcial registrado no diário é melhor que nenhum número."""
    if isinstance(outcome, dict):
        record["output"], record["tool_calls"] = outcome["output"], outcome["tool_calls"]
        record["partial"] = bool(outcome.get("partial"))
        record["so_far"] = not outcome.get("settled", True)
        record["summed"] = True
        record.pop("not_yet", None)
        return record
    if record.get("output") is None and record.get("tool_calls") is None:
        # Uma transcrição que não está lá é o único desfecho que é final. Legível e ainda
        # sem resposta, e um agente que o orçamento nunca alcançou, ambos valem a pena perguntar de novo.
        record["not_yet"] = outcome != ABSENT
    return record


def ingest(state, journal_file, resolved=None):
    """Dobra os novos bytes do diário para dentro do estado travado: running, pending e os totais.

    Só bytes novos, a partir de um offset salvo, porque uma sessão longa o bastante para superar uma
    leitura é exatamente a sessão cujos totais não devem começar a diminuir. Uma última linha
    escrita pela metade é deixada não consumida e lida inteira na próxima vez.

    `resolved` é o que `settle_before_lock` somou para este evento. Um stop que precisava de soma
    carrega esse número para dentro dos totais e para dentro da linha; um que ainda está sem número é
    contado como desconhecido e lembrado, para que um evento posterior possa reconciliá-lo sem nomeá-lo duas vezes.
    """
    resolved = resolved or {}
    try:
        size = journal_file.stat().st_size
        handle = open(str(journal_file), "rb")
    except OSError:
        return state
    offset = state["journal_offset"]
    if offset > size:
        # Um diário substituído debaixo de nós: relê em vez de confiar num offset para dentro de outro arquivo.
        offset = 0
    position = offset
    with handle:
        handle.seek(offset)
        for raw in handle:
            if not raw.endswith(b"\n"):
                break
            position += len(raw)
            try:
                record = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                continue
            agent_id = record["id"]
            if record.get("t") == "start":
                state["running"][agent_id] = int(record.get("at") or 0)
                continue
            if record.get("t") != "stop":
                continue
            state["running"].pop(agent_id, None)
            round_number = bump_round(state, agent_id)
            # O stop de uma rodada posterior nunca é tomado no número com que foi registrado no diário. A
            # transcrição de onde foi lido ainda termina na resposta terminada da rodada anterior,
            # então `summed` diz final sobre uma rodada cujas próprias respostas ainda não estão em disco.
            if needs_sum(record) or round_number > 1:
                apply_settled(record, resolved.get(agent_id))
            if agent_id in state["counted"]:
                if agent_id in state["unsummed"] and record.get("output") is not None:
                    # Anunciado sem número, e o diário trouxe um: os totais o assumem
                    # e o agente não é nomeado de novo.
                    resolve_unknown(state, agent_id, figures_of(record))
                    del state["unsummed"][agent_id]
                elif round_number < 2:
                    reconcile(state, record)
                if round_number > 1:
                    open_round(state, record, round_number)
                continue
            if agent_id in (state.get("said_unknown") or []):
                # O registro do leitor sobre este agente se perdeu, não o fato em si: ele foi
                # contado uma vez e nomeado uma vez, e nenhum dos dois é devido uma segunda vez.
                state["counted"].append(agent_id)
                if has_figure(record):
                    resolve_unknown(state, agent_id, figures_of(record))
                continue
            state["counted"].append(agent_id)
            count(state, record)
            if record.get("not_yet"):
                remember_unsummed(state, agent_id, record.get("path"))
            state["pending"].append(record)
    state["journal_offset"] = position
    return state


def figures_of(record):
    """`[output, tool_calls]` como inteiros, seja lá o que o registro colocou ali."""
    out = []
    for key in ("output", "tool_calls"):
        try:
            out.append(int(record.get(key) or 0))
        except (TypeError, ValueError):
            out.append(0)
    return out


def risen(record):
    """Se o número cumulativo de uma rodada posterior ultrapassou o já reportado.

    É a única coisa que diz que a rodada de um agente retomado está em disco. A soma cobre toda
    rodada que o agente rodou, e a transcrição termina numa resposta terminada de qualquer forma, então um
    total que não se moveu é uma rodada cujas respostas ainda não foram gravadas.
    """
    return has_figure(record) and figures_of(record)[0] > record.get("floor", 0)


def open_round(state, record, round_number):
    """Uma conclusão de um agente retomado: mantida até seu próprio gasto chegar, então nomeada.

    Até que chegue, o registro é re-somado a cada evento e nada é dito sobre ele —
    uma linha repetindo o número da rodada anterior seria pior que uma linha um prompt depois.
    """
    record["round"] = round_number
    record["floor"] = (state["figures"].get(record.get("id")) or [0, 0])[0]
    record["tries"] = 0
    if risen(record):
        reconcile(state, record)
    else:
        record["awaiting"] = True
    state["pending"].append(record)


def reconcile_rounds(state, resolved):
    """Dobra as somas deste evento nas rodadas posteriores cujo próprio gasto ainda não tinha chegado.

    Uma rodada é aceita no momento em que seu número ultrapassa o já reportado, e é nomeada a partir da
    lista pending como qualquer outra. Uma transcrição que sumiu, e uma rodada que já esgotou suas
    tentativas, são descartadas: nada foi jamais dito sobre nenhuma delas, então nada precisa ser retirado.
    """
    for record in list(state.get("pending") or []):
        if not record.get("awaiting"):
            continue
        outcome = resolved.get(record.get("id"))
        if isinstance(outcome, dict) and outcome["output"] > record.get("floor", 0):
            apply_settled(record, outcome)
            record.pop("awaiting", None)
            reconcile(state, record)
        elif outcome == ABSENT or record.get("tries", 0) >= UNSUMMED_TRIES:
            state["pending"].remove(record)
        elif outcome is not None:
            record["tries"] = record.get("tries", 0) + 1


def has_figure(record):
    """Se um stop carrega número nenhum, ponto final. Contagens nulas são uma soma que não pôde ser feita."""
    return not (record.get("output") is None and record.get("tool_calls") is None)


def bump_round(state, agent_id):
    """Qual conclusão deste agente um stop registrado no diário é, contando a partir de um.

    Um agente retomado com uma mensagem de acompanhamento para uma vez por rodada, contra um id de agente e uma
    transcrição, então toda rodada depois da primeira foi dobrada para dentro dos totais e nunca nomeada: só
    a primeira conclusão dele alimentou uma linha. A contagem de stops é o que distingue uma rodada retomada da
    cópia estabelecida de uma rodada já reportada — essa ainda é o mesmo, primeiro, stop.
    """
    rounds = state.setdefault("rounds", {})
    number = rounds.get(agent_id)
    number = number + 1 if isinstance(number, int) and not isinstance(number, bool) else 1
    rounds[agent_id] = number
    return number


def count(state, record):
    """Um agente terminado contra os totais de subagente da sessão, exatamente uma vez."""
    totals = state["subagents"]
    totals["count"] += 1
    if record.get("output") is None and record.get("tool_calls") is None:
        totals["unknown"] += 1
        return
    figures = figures_of(record)
    totals["output"] += figures[0]
    totals["tool_calls"] += figures[1]
    agent_id = record.get("id")
    if isinstance(agent_id, str):
        state["figures"][agent_id] = figures
        for stale in list(state["figures"])[:max(0, len(state["figures"]) - MAX_COUNTED)]:
            del state["figures"][stale]


def reconcile(state, record):
    """Eleva os totais quando um número posterior, estabelecido, para um agente já reportado é maior.

    Um retorno síncrono é reportado no momento em que chega, o que pode ser antes da última
    resposta do subagente ter sido totalmente escrita. O stop do diário, calculado depois, é o número
    estabelecido: dizer a linha do agente de novo custaria contexto do orquestrador por um número que ele já
    tem, então só a diferença é adicionada, e o total da sessão portanto nunca fica abaixo da soma
    dos números finais.
    """
    agent_id = record.get("id")
    before = state["figures"].get(agent_id)
    if not isinstance(before, list) or len(before) != 2:
        return
    settled = figures_of(record)
    for index, key in enumerate(("output", "tool_calls")):
        value = settled[index]
        if value > before[index]:
            state["subagents"][key] += value - before[index]
            before[index] = value


def remember_unsummed(state, agent_id, path):
    """Mantém um agente reportado sem número na lista que um evento posterior tenta de novo.

    Ele foi contado — como desconhecido, então a linha da sessão diz `(partial)` — e foi
    nomeado, então nunca deve ser nomeado de novo. O que resta é seu número, e a nova tentativa existe para
    que uma transcrição que ganha sua resposta um segundo depois ainda chegue aos totais da sessão.
    """
    entry = state["unsummed"].get(agent_id)
    tries = entry[1] + 1 if isinstance(entry, list) else 1
    state["unsummed"][agent_id] = [path if isinstance(path, str) else "", tries]


def resolve_unknown(state, agent_id, figures):
    """Um número que chegou depois que seu agente foi contado como desconhecido. Os totais sobem; nada é dito."""
    totals = state["subagents"]
    if totals["unknown"] > 0:
        totals["unknown"] -= 1
    totals["output"] += figures[0]
    totals["tool_calls"] += figures[1]
    state["figures"][agent_id] = list(figures)


def reconcile_unsummed(state, resolved):
    """Dobra as somas deste evento nos agentes em que eventos anteriores não conseguiram colocar um número.

    Nenhum deles é nomeado de novo: foram anunciados quando terminaram. Uma transcrição que se
    revelou inexistente para de ser perguntada, e o mesmo vale para uma que já foi perguntada
    `UNSUMMED_TRIES` vezes; ambas permanecem contadas como desconhecidas, que é para o que o `(partial)` na
    linha da sessão serve.
    """
    for agent_id, entry in list(state["unsummed"].items()):
        outcome = resolved.get(agent_id)
        if isinstance(outcome, dict):
            resolve_unknown(state, agent_id, [outcome["output"], outcome["tool_calls"]])
            for record in state["pending"]:
                if record.get("id") == agent_id:
                    apply_settled(record, outcome)
            del state["unsummed"][agent_id]
        elif outcome == ABSENT or entry[1] >= UNSUMMED_TRIES:
            del state["unsummed"][agent_id]
        elif outcome == PENDING:
            entry[1] += 1


def running_now(state, now=None):
    """Os agentes ainda em voo, esquecendo um start cujo stop nunca chegou."""
    now = time.time() if now is None else now
    stale = [agent for agent, at in state["running"].items() if now - (at or 0) > RUNNING_TTL]
    for agent in stale:
        del state["running"][agent]
    return list(state["running"])


# --------------------------------------------------------------------------- the lines


def settings(env):
    """`(table, mode, nudges, width)` a partir da variante de custo ativa, ou o padrão silencioso."""
    module = sibling("posture")
    if module is None:
        return None, "off", [], None
    try:
        table = module.cost_table(env)
    except Exception:
        return None, "off", [], None
    switches = table.get("switches") if isinstance(table, dict) else None
    switches = switches if isinstance(switches, dict) else {}
    mode = switches.get("turn_feed")
    mode = mode if mode in MODES else "off"
    nudges = sorted(v for v in switches.get("nudge_at") or []
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0)
    width = switches.get("max_parallel")
    width = width if isinstance(width, int) and not isinstance(width, bool) and width > 0 else None
    return table, mode, nudges, width


def session_nudges(table):
    """Os tamanhos de contexto que a postura chama de sessão cheia, menor primeiro; vazio significa silencioso."""
    switches = table.get("switches") if isinstance(table, dict) else None
    switches = switches if isinstance(switches, dict) else {}
    return sorted(v for v in switches.get("session_nudge_at") or []
                  if isinstance(v, int) and not isinstance(v, bool) and v > 0)


def budgets(row):
    """Os dois orçamentos suaves da linha, cada um só quando é um número inteiro positivo."""
    if not isinstance(row, dict):
        return None, None
    out = []
    for key in ("budget_output_tokens", "budget_tool_calls"):
        value = row.get(key)
        out.append(value if isinstance(value, int) and not isinstance(value, bool) and value > 0
                   else None)
    return out[0], out[1]


def agent_line(agent_type, output, calls, row, nudges, partial=False, provisional=False,
               not_yet=False, agent_id=None, round_number=1):
    """`(line, ratio)` para um subagente terminado; ratio é None quando não há nada para comparar.

    Contagens nulas são o que uma soma que não pôde ser calculada deixa para trás, e a linha diz isso:
    um agente reportado em zero se leria como um agente que não fez nada. Qual das duas coisas
    ela diz é a diferença entre uma transcrição que não está lá — `spend unknown`, final —
    e uma que está lá e ainda não teve resposta escrita nela, cujo número um turno posterior ainda pode
    reconciliar nos totais da sessão. Uma linha que orça só
    metade da unidade nomeia essa metade, porque `n / None` se leria como um número para agir sobre.
    `provisional` é o número de uma resposta ainda sendo escrita: `(so far)`, nunca um número
    apresentado como exato. `(partial)` o inclui — uma soma que foi cortada pela metade é a ressalva maior.

    `spend unknown` nomeia o agente sobre o qual fala, porque é a única linha que não carrega número
    para distinguir duas: uma sessão que a emitiu uma vez por hora e uma sessão emitindo-a
    a cada turno pareceriam idênticas até o id estar nela.

    Uma rodada além da primeira é uma conclusão de um agente retomado, e seu número é sua transcrição
    inteira em vez de só aquela rodada, então a linha diz `(cumulative)`.
    """
    if output is None and calls is None:
        if not_yet:
            return PREFIX + agent_type + " finished, spend not yet recorded", None
        named = (", no transcript found for agent " + agent_id) if agent_id else ""
        return PREFIX + agent_type + " finished, spend unknown" + named, None
    text = (PREFIX + agent_type + " finished" + ("" if round_number < 2 else
            " round " + "{:,}".format(round_number)) + " at " + plural(output or 0, "output token")
            + " and " + plural(calls or 0, "tool call"))
    marks = ["cumulative"] if round_number > 1 else []
    if partial:
        marks.append("partial")
    elif provisional:
        marks.append("so far")
    if marks:
        text += " (" + ", ".join(marks) + ")"
    budget_out, budget_calls = budgets(row)
    ratios, halves = [], []
    if budget_out:
        ratios.append((output or 0) / float(budget_out))
        halves.append(plural(budget_out, "output token"))
    if budget_calls:
        ratios.append((calls or 0) / float(budget_calls))
        halves.append(plural(budget_calls, "tool call"))
    if not ratios:
        return text, None
    ratio = max(ratios)
    if budget_out and budget_calls:
        halves = ["{:,}".format(budget_out) + " / " + "{:,}".format(budget_calls)]
    clause = "{:.1f}".format(ratio) + "× its budget of " + " and ".join(halves)
    if any(ratio >= level for level in nudges):
        clause = "over budget " + clause
    return text + " — " + clause, ratio


def width_line(running, width):
    """Uma linha quando mais agentes estão em voo do que a largura da postura. Nunca uma decisão."""
    if width is None or len(running) <= width:
        return None
    return (PREFIX + plural(len(running), "subagent") + " running against a posture width of "
            + "{:,}".format(width))


def turn_line(state):
    """O turno e a sessão até agora, ou None quando não diria nada novo.

    O primeiro prompt de uma sessão não tem turno atrás dele, e a conclusão de um agente em segundo
    plano chega como um prompt próprio — vários em fileira, todos reportando o turno antes deles. Repetir uma
    linha que o orquestrador já leu custa contexto e o ensina a pular o feed, então os
    números impressos por último são lembrados e um turno inalterado é silêncio.
    """
    last = state["turn"] if (state["turn"]["output"] or state["turn"]["tool_calls"]) \
        else state["previous_turn"]
    figures = [last["output"], last["tool_calls"]]
    if not any(figures) or state.get("said_turn") == figures:
        return None
    state["said_turn"] = figures
    totals = state["subagents"]
    text = (PREFIX + "last turn " + plural(last["output"], "output token") + ", "
            + plural(last["tool_calls"], "tool call") + " · session "
            + "{:,}".format(state["session"]["output"] + totals["output"]) + " output, "
            + plural(state["session"]["tool_calls"] + totals["tool_calls"], "tool call") + ", "
            + plural(totals["count"], "subagent"))
    if totals["unknown"] or state.get("partial"):
        text += " (partial)"
    return text


def session_line(state, thresholds):
    """Uma linha na primeira vez que o contexto da sessão passa de um limiar, ou None.

    A linha de turno reporta o que um turno produziu. O que uma sessão longa custa é sobretudo o contexto
    que todo turno seguinte relê, o que nenhum número no feed mostra, então esta é a única linha que
    diz que continuar aqui é a escolha cara. É suave: nada é bloqueado.

    Uma vez por limiar, nunca uma vez por turno. Todo limiar em ou abaixo do tamanho atual é
    marcado como dito, então uma sessão que fica acima de um fica silenciosa até alcançar o próximo, e um
    resume lê as mesmas marcas do mesmo arquivo de estado. Um limiar sob o qual o contexto desde então
    voltou é desmarcado, porque uma compactação que reduziu a sessão pela metade e uma hora de
    trabalho que a encheu de novo é uma travessia sobre a qual o orquestrador não foi informado.

    Um tamanho que nenhuma linha de transcrição ainda forneceu não é uma travessia: a linha nomearia um
    limiar contra o qual nada foi medido, e reportar o contexto de uma transcrição não lida
    como zero seria uma mentira de qualquer forma.
    """
    size = state.get("context")
    if not thresholds or not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        return None
    said = state.setdefault("said_nudge", [])
    said[:] = [level for level in said if level <= size]
    fresh = [level for level in thresholds if size >= level and level not in said]
    if not fresh:
        return None
    said.extend(fresh)
    # O maior dos recém-atravessados, que não é o maior ultrapassado: um limiar
    # já dito não é novidade, e nomeá-lo se leria como uma linha se repetindo.
    return (PREFIX + "session context " + plural(size, "token") + ", past the fresh-session "
            "threshold of " + "{:,}".format(fresh[-1]) + " — finish the task, write the "
            "handoff, start a fresh session")


def record_adherence(recommendation, session_id, turn, env):
    """Registra uma recomendação que este feed emitiu. Nada que faz pode mudar o que o feed diz."""
    module = sibling("adherence")
    if module is None:
        return
    try:
        module.emit(recommendation, session_id, turn, env)
    except Exception:
        pass


def shows(mode, ratio, nudges):
    """Se a linha de um subagente vale uma linha. `thresholds` quer o menor empurrão atendido."""
    if mode == "every-turn":
        return True
    if mode != "thresholds" or not nudges or ratio is None:
        return False
    return ratio >= nudges[0]


def row_for(table, agent_type):
    module = sibling("posture")
    try:
        return module.row_for(table, agent_type) if module else None
    except Exception:
        return None


def stop_line(table, nudges, record):
    agent_id = record.get("id")
    round_number = record.get("round")
    return agent_line(agent_name(record.get("type")), record.get("output"),
                      record.get("tool_calls"), row_for(table, record.get("type")), nudges,
                      bool(record.get("partial")), bool(record.get("so_far")),
                      bool(record.get("not_yet")),
                      agent_id if isinstance(agent_id, str) else None,
                      round_number if isinstance(round_number, int) else 1)


def unknown_final(record):
    """Um stop cujo gasto nada vai recuperar: `spend unknown`, não `not yet recorded`."""
    return not has_figure(record) and not record.get("not_yet")


def said_unknown(state, record):
    """Se o `spend unknown` deste agente já foi alimentado, para que nunca seja alimentado duas vezes.

    A linha não carrega número e não pode ser reconciliada, então nada sobre o agente jamais a
    mudará. Repeti-la turno após turno — o que uma sessão cujo estado do leitor foi reconstruído costumava
    fazer — gasta o contexto do orquestrador num fato que ele leu na primeira vez.
    """
    return unknown_final(record) and record.get("id") in (state.get("said_unknown") or [])


def note_unknown(state, record):
    """Lembra um `spend unknown` que acabou de ser alimentado, limitado como toda outra lista aqui."""
    if not unknown_final(record) or not isinstance(record.get("id"), str):
        return
    already = state.setdefault("said_unknown", [])
    if record["id"] not in already:
        already.append(record["id"])


#: O que os números do feed são, dito uma vez por sessão para que não sejam lidos como outra medida.
#: Reportado ao vivo: a linha de um agente dizia 31.121 tokens de saída ao lado do `subagent_tokens
#: 102398` de uma notificação de tarefa, e ambos estavam certos sobre coisas diferentes.
MEASURE = (PREFIX + "figures above are output tokens and tool calls summed from each agent's own "
           "transcript — not the task notification's subagent_tokens, which is another measure.")


def legend(state):
    """A linha de medida, na primeira vez que esta sessão alimenta um número, e nunca mais."""
    if state.get("said_measure"):
        return None
    state["said_measure"] = True
    return MEASURE


# --------------------------------------------------------------------------- the events


def on_subagent_event(payload, env, kind):
    """Registra um evento de ciclo de vida de subagente no diário. Nunca emite e nunca toma a trava.

    O próprio `additionalContext` de `SubagentStop` chegaria ao agente que acabou de terminar, então
    não há nada a dizer aqui mesmo quando há algo a registrar. O stop é escrito num
    `finally`: um agente cujo stop nunca chegou seria contado como rodando pelo resto
    da sessão, então um stop sem nada nele vence nenhum stop.

    Nada aqui espera. Um stop dispara no instante em que o agente termina, o que pode ser antes de sequer
    uma das suas respostas ter sido gravada em sua transcrição, e este evento não tem a quem contar. Então
    o número que consegue ver é registrado como o número que consegue ver, e `summed` diz se isso é
    um número em que confiar: uma leitura vazia, ou uma tirada de uma resposta ainda sendo escrita, é
    registrada no diário como ainda não somada e a soma no momento do relatório a torna boa. A transcrição é
    anotada com o prefixo home ofuscado para que o repórter possa encontrá-la de novo.
    """
    if payload.get("stop_hook_active"):
        return None
    agent_id = payload.get("agent_id")
    if not (isinstance(agent_id, str) and IDENTIFIER.match(agent_id)):
        return None
    _, mode, _, _ = settings(env)
    if mode == "off":
        return None
    found = paths(payload.get("session_id"), env)
    if found is None:
        return None
    record = {"t": kind, "id": agent_id, "type": agent_name(payload.get("agent_type")),
              "at": int(time.time())}
    if kind == "start":
        journal_append(found[1], record)
        return None
    record["output"], record["tool_calls"], record["partial"] = None, None, False
    record["summed"], record["path"] = False, ""
    try:
        path = payload.get("agent_transcript_path") or agent_transcript(
            payload.get("transcript_path"), payload.get("session_id"), agent_id)
        record["path"] = redact(path, env)
        totals = agent_totals(path)
        if totals is not None:
            record["type"] = agent_name(payload.get("agent_type"), totals["agent_type"])
            record["output"], record["tool_calls"] = totals["output"], totals["tool_calls"]
            record["partial"] = totals["partial"]
            record["summed"] = tail_settled(path) and not totals["partial"]
    finally:
        journal_append(found[1], record)
    return None


def emit(state, lines, record, line):
    """Adiciona a linha de um subagente, a menos que seja um `spend unknown` que esta sessão já disse.

    Retorna se a linha carregava um número, que é para o que a linha de medida é devida.
    """
    if said_unknown(state, record):
        return False
    note_unknown(state, record)
    lines.append(line)
    return has_figure(record)


def refresh(state_file, journal_file, resolved):
    """O estado da sessão com as somas deste evento dobradas: as tentativas primeiro, depois o diário.

    Nessa ordem porque as duas listas não devem tocar no trabalho uma da outra. Uma tentativa pertence a um
    agente que um evento anterior já nomeou; um stop que o diário traz agora nunca foi nomeado.
    Dobrar o diário primeiro entregaria a entrada de tentativa nova em folha de um stop direto para a passagem
    de tentativa, que contaria sua única tentativa duas vezes.
    """
    state = load_state(state_file)
    reconcile_unsummed(state, resolved)
    reconcile_rounds(state, resolved)
    return ingest(state, journal_file, resolved)


def fresh_record(agent_id, response, outcome):
    """O registro de stop que um retorno síncrono faz para si mesmo, ou None quando não há nada a dizer.

    `ABSENT` é o None: o retorno deriva o caminho da transcrição a partir do id de sessão, enquanto o
    stop que o segue recebe o caminho diretamente, então um arquivo que este não consegue encontrar é um arquivo
    que o diário bem pode encontrar. Dizer `spend unknown` aqui aposentaria o agente e jogaria isso
    fora.
    """
    record = {"id": agent_id, "output": None, "tool_calls": None, "partial": False,
              "type": agent_name(response.get("agentType"))}
    if isinstance(outcome, dict):
        record["type"] = agent_name(response.get("agentType"), outcome["agent_type"])
        return apply_settled(record, outcome)
    if outcome == ABSENT or outcome is None:
        return None
    return apply_settled(record, outcome)


def on_agent_return(payload, env):
    """Uma conclusão síncrona de `Agent`, reportada uma vez, mais a nota de largura em qualquer chamada Agent."""
    response = payload.get("tool_response")
    response = response if isinstance(response, dict) else {}
    table, mode, nudges, width = settings(env)
    if mode == "off":
        return None
    found = paths(payload.get("session_id"), env)
    if found is None:
        return None
    state_file, journal_file, lock_file = found
    agent_id = response.get("agentId")
    # O PostToolUse de um spawn em segundo plano dispara no lançamento sem totais nenhum; só a nota
    # de largura se aplica a ele.
    synchronous = (not response.get("isAsync") and response.get("status") == "completed"
                   and isinstance(agent_id, str) and IDENTIFIER.match(agent_id))
    # Antes da trava, sempre: esta é a única coisa lenta que qualquer evento de thread principal faz, e um
    # prompt esperando atrás dele esgotaria sua espera e perderia sua linha. O agente retornando vai
    # primeiro, e o que sobra do orçamento soma os stops que este evento está prestes a nomear. Um
    # lançamento não nomeia nenhum deles — sua única linha é a nota de largura — então não soma nada e permanece
    # tão rápido quanto era; o que ele ingere nesse meio tempo é reconciliado pelo prompt que o reporta.
    first, resolved = None, {}
    if synchronous:
        first = (agent_id, agent_transcript(payload.get("transcript_path"),
                                            payload.get("session_id"), agent_id))
        resolved = settle_before_lock(state_file, journal_file, payload, env, first)
    with Lock(lock_file) as held:
        if not held:
            return None
        state = refresh(state_file, journal_file, resolved)
        lines, figured = [], False
        if synchronous:
            record = next((r for r in state["pending"]
                           if r.get("id") == agent_id and not r.get("awaiting")), None)
            if record is not None:
                line, ratio = stop_line(table, nudges, record)
                if shows(mode, ratio, nudges):
                    state["pending"].remove(record)
                    figured = emit(state, lines, record, line)
            elif agent_id not in state["counted"]:
                # O stop ainda não foi registrado no diário. Reportá-lo agora significa contá-lo agora,
                # então a cópia do diário é pulada quando chegar. Um desfecho de `ABSENT` é
                # deixado para aquela cópia em vez disso: é ela que recebeu o caminho da transcrição.
                fresh = fresh_record(agent_id, response, resolved.get(agent_id))
                line, ratio = stop_line(table, nudges, fresh) if fresh else (None, None)
                if fresh and shows(mode, ratio, nudges):
                    state["counted"].append(agent_id)
                    count(state, fresh)
                    if fresh.get("not_yet"):
                        remember_unsummed(state, agent_id, redact(first[1], env))
                    state["running"].pop(agent_id, None)
                    figured = emit(state, lines, fresh, line)
        note = width_line(running_now(state), width)
        if note:
            lines.append(note)
        if figured:
            measure = legend(state)
            if measure:
                lines.append(measure)
        save_state(state_file, state)
        return lines or None


def on_prompt(payload, env):
    """A linha de turno, o empurrão de sessão, a nota de largura, e então os subagentes que terminaram."""
    table, mode, nudges, width = settings(env)
    if mode == "off":
        return None
    found = paths(payload.get("session_id"), env)
    if found is None:
        return None
    state_file, journal_file, lock_file = found
    # Fora da trava, como o do retorno: os agentes que este prompt está prestes a nomear são somados
    # antes de qualquer coisa ser mantida, dentro de um orçamento para o lote inteiro.
    resolved = settle_before_lock(state_file, journal_file, payload, env)
    with Lock(lock_file) as held:
        if not held:
            return None
        state = refresh(state_file, journal_file, resolved)
        # A contagem de prompts da sessão, que um evento de adesão nomeia como seu turno. Antes da
        # leitura, para que uma leitura que desiste ainda conte o prompt em que desistiu.
        state["turns"] += 1
        prune(state_file.parent, state, state_file.name.split(".", 1)[0])
        state = advance(state, payload.get("transcript_path"),
                        save=lambda current: save_state(state_file, current))
        if state.get("timed_out"):
            save_state(state_file, state)
            return None
        turn = turn_line(state) if mode == "every-turn" else None
        lines = [turn] if turn else []
        # Não é a linha de um subagente e não é um número para comparar: também é dita sob `thresholds`.
        nudge = session_line(state, session_nudges(table))
        if nudge:
            lines.append(nudge)
            record_adherence("fresh-session", payload.get("session_id"), state["turns"], env)
        note = width_line(running_now(state), width)
        if note:
            lines.append(note)
        said = []
        for record in list(state["pending"]):
            if record.get("awaiting"):
                continue     # uma rodada retomada cujo próprio gasto ainda não chegou
            line, ratio = stop_line(table, nudges, record)
            if not shows(mode, ratio, nudges):
                continue
            if said_unknown(state, record):
                # Nada jamais colocará um número nisso e o orquestrador já o leu uma vez.
                state["pending"].remove(record)
                continue
            said.append((record, line))
        # Só os agentes que este turno de fato nomeia são aposentados. O teto limita quanto é dito
        # de uma vez, então o resto é nomeado no próximo prompt em vez de descartado sem ser dito.
        figured = False
        for record, line in said[:MAX_LISTED]:
            state["pending"].remove(record)
            figured = emit(state, lines, record, line) or figured
        if len(said) > MAX_LISTED:
            lines.append("… and " + "{:,}".format(len(said) - MAX_LISTED) + " more")
        if figured:
            measure = legend(state)
            if measure:
                lines.append(measure)
        save_state(state_file, state)
    return lines or None


def run(payload, env=None):
    """As linhas que um evento produz, ou None. A thread pai é o único lugar onde um feed roda."""
    env = os.environ if env is None else env
    kind = payload.get("hook_event_name") or ""
    if kind in ("SubagentStop", "SubagentStart"):
        # Os únicos eventos cujo `agent_id` nomeia outra pessoa: eles disparam nos hooks do pai.
        return on_subagent_event(payload, env, "stop" if kind == "SubagentStop" else "start")
    if payload.get("agent_id"):
        return None
    if kind == "UserPromptSubmit":
        return on_prompt(payload, env)
    if kind == "PostToolUse" and payload.get("tool_name") == "Agent":
        return on_agent_return(payload, env)
    return None


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return
        lines = run(payload)
    except Exception:
        return
    if lines:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": payload.get("hook_event_name") or "",
            "additionalContext": "\n".join(lines)}}))


if __name__ == "__main__":
    main()
