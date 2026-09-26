"""Controles de opt-in para um provedor de decisão que sai da máquina: modos, um interruptor de
emergência, uma allowlist.

Três perguntas separadas, deliberadamente não um único switch:

* **Este ponto pode sequer ser julgado, e até que ponto?** `governance.jev.mode` define um
  padrão e `governance.jev.modes` nomeia um ponto de decisão: `off` não chama nada, `shadow`
  chama e registra a resposta onde só o ledger a vê, `advise` acrescenta uma linha à decisão,
  `act` deixa um julgamento apertá-la. Todo modo tem padrão `off`, então uma configuração
  existente que nunca ouviu falar deste provedor não faz nenhuma requisição.
* **Algo pode sair agora mesmo?** Um arquivo sentinela desativa toda chamada enquanto existir,
  sem mudança de configuração e sem reinício: `touch ~/.local/state/agent-harness/jev-disabled`
  é o interruptor de emergência, e `mode_for` o lê por decisão em vez de na construção.
* **O que pode sair?** `governance.jev.state_fields` é uma allowlist sobre `STATE_FIELDS`,
  vazia por padrão. Um campo não listado nunca é construído dentro da requisição, e nenhuma
  chave fora de `BASE_FIELDS` mais as listadas pode alcançar a rede — `check_outbound` recusa a
  requisição em vez de recortá-la.

Uma requisição real precisa que as três concordem, além de uma credencial no ambiente; o harness
nunca lê um arquivo de chave. `SessionSpend` fica ao lado delas para o orçamento que o provedor
cobra: um hook é um processo novo por evento, então contadores que vivem em um não limitam nada;
o gasto de uma sessão é mantido no diretório de estado sob o lock em vez disso. Nada aqui tem
efeito até que uma configuração peça por um.
"""
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .. import decision
from .. import reconcile

# Os pontos de hook que um modo pode nomear. Uma cópia em vez de um import:
# `policy/hooks/decisions.py` é alcançado por arquivo a partir de um diretório de hooks, não por
# caminho de módulo, e uma configuração precisa validar num processo que nunca o carrega.
# `test_jev_outbound_controls.py` garante que as duas listas concordam, então um ponto
# adicionado ali e esquecido aqui é uma falha de teste.
POINTS = ("grade-bash", "stop-gate", "tier-agent-spawns", "brief-guard", "evasion-deny")

MODES = ("off", "shadow", "advise", "act")
DEFAULT_MODE = "off"

# Os campos de estado que o contexto de um chamador pode contribuir, e os que toda requisição
# carrega seja o que for que a configuração diga. Fechado de propósito: um ponto de decisão que
# toca permissões pode descrever o comando que está julgando e nada mais, então saída de
# ferramenta, prosa do assistente, conteúdo de arquivo e valores de ambiente não têm campo por
# onde viajar.
STATE_FIELDS = ("command", "summary")
BASE_FIELDS = ("action_class", "counterparty", "grade", "grade_scale")

SENTINEL_NAME = "jev-disabled"
# Onde o gasto de uma sessão é mantido, para que um teto limite uma sessão em vez de um
# processo: todo hook é um processo novo, e um contador que vive em um não limita nada.
SPEND_NAME = "jev-spend.json"
# A linha de uma sessão é descartada um dia após sua última requisição. Longo o bastante para
# que uma sessão não consiga sobreviver ao próprio teto, curto o bastante para que o arquivo
# continue sendo um arquivo que uma pessoa consegue ler.
SPEND_RETENTION_SECONDS = 24 * 60 * 60
SPEND_LOCK_ATTEMPTS = 5
SPEND_LOCK_PAUSE = 0.01
SESSION_VARIABLES = ("HARNESS_SESSION_ID", "CLAUDE_SESSION_ID")
# O balde do qual um processo sem id de sessão gasta. Compartilhado em vez de por processo, que
# é a direção conservadora: um chamador não identificado pode não ter um teto recém-atribuído.
UNKNOWN_SESSION = "unknown-session"
# Lido apenas do ambiente. O harness nunca lê um arquivo de chave, e um valor nunca é impresso:
# o que um relatório pode dizer é qual desses nomes está definido.
KEY_VARIABLES = ("TYPESAFE_API_KEY", "JEV_API_KEY")
# Dois segundos, dentro dos dez que um hook tem: um julgamento que não chegou até lá vale menos
# que o turno que está segurando, e a resposta determinística já está em mãos.
DEFAULT_TIMEOUT = 2
DEFAULT_MAX_REQUESTS = 50
DEFAULT_MAX_TOKENS = 200000
KEYS = ("mode", "modes", "state_fields", "sentinel", "timeout", "max_requests", "max_tokens")


def state_dir() -> Path:
    """`~/.local/state/agent-harness`, o diretório onde os ledgers já vivem."""
    home = os.environ.get("HARNESS_HOME") or os.environ.get("HOME")
    return (Path(home) if home else Path.home()) / ".local" / "state" / "agent-harness"


def _where(key: str) -> str:
    return "governance.jev." + key


def _mode(value: Any, key: str) -> str:
    if value not in MODES:
        # O valor ofensor nunca é citado de volta. Um valor de configuração pode conter qualquer
        # coisa que um usuário colou, e uma mensagem de erro é impressa, registrada e rolada.
        raise decision.PolicyError(_where(key) + " must be one of " + ", ".join(MODES))
    return value


def _count(value: Any, key: str, fallback: int) -> int:
    if value is None:
        return fallback
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise decision.PolicyError(_where(key) + " must be a non-negative integer")
    return value


class Controls:
    """Uma resposta resolvida para cada uma das três perguntas acima.

    Construída a partir de uma configuração com `from_config`, que dá padrão `off` a todo modo e
    lista vazia à allowlist. `acting()` é o outro construtor: todo ponto em `act` e ambos os
    campos opcionais permitidos, para um chamador que montou um provedor à mão e forneceu seu
    próprio cliente. Só controles configurados podem colocar um cliente na rede — um provedor
    construído num teste ou script é inerte não importa como seus modos leiam.
    """

    def __init__(self, default_mode=DEFAULT_MODE, modes=None, state_fields=(), sentinel=None,
                 timeout=DEFAULT_TIMEOUT, max_requests=DEFAULT_MAX_REQUESTS,
                 max_tokens=DEFAULT_MAX_TOKENS, configured=False):
        self.default_mode = _mode(default_mode, "mode")
        self.modes = {}
        for name in sorted(modes or {}):
            if name not in POINTS:
                raise decision.PolicyError(
                    _where("modes") + " names an unknown decision point " + repr(name)
                    + "; known points are " + ", ".join(POINTS))
            self.modes[name] = _mode((modes or {})[name], "modes." + name)
        self.state_fields = []
        for name in state_fields or ():
            if name not in STATE_FIELDS:
                raise decision.PolicyError(
                    _where("state_fields") + " names a field a decision point may not send; "
                    "it may send " + ", ".join(STATE_FIELDS) + " and nothing else")
            if name not in self.state_fields:
                self.state_fields.append(name)
        if sentinel is not None and (not isinstance(sentinel, str) or not sentinel.strip()
                                     or "\x00" in sentinel or "\n" in sentinel):
            raise decision.PolicyError(_where("sentinel") + " must be a path")
        self.sentinel = sentinel.strip() if sentinel else None
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) \
                or not 0 < timeout <= 10:
            raise decision.PolicyError(_where("timeout")
                                       + " must be a number of seconds in (0, 10]")
        self.timeout = timeout
        self.max_requests = _count(max_requests, "max_requests", DEFAULT_MAX_REQUESTS)
        self.max_tokens = _count(max_tokens, "max_tokens", DEFAULT_MAX_TOKENS)
        self.configured = bool(configured)

    @classmethod
    def from_config(cls, config: Optional[Dict[str, Any]]) -> "Controls":
        """O bloco `governance.jev`, validado, ou todo ponto `off` quando não há nenhum."""
        block = (config or {}).get("governance")
        block = block.get("jev") if isinstance(block, dict) else None
        if block is None:
            return cls(configured=True)
        if not isinstance(block, dict):
            raise decision.PolicyError("governance.jev must be an object of "
                                       + ", ".join(KEYS))
        unknown = sorted(set(block) - set(KEYS))
        if unknown:
            raise decision.PolicyError("governance.jev has unknown key(s) "
                                       + ", ".join(unknown) + "; known keys are "
                                       + ", ".join(KEYS))
        modes = block.get("modes", {})
        if not isinstance(modes, dict):
            raise decision.PolicyError(_where("modes")
                                       + " must be an object of decision point to mode")
        fields = block.get("state_fields", [])
        if not isinstance(fields, list):
            raise decision.PolicyError(_where("state_fields") + " must be an array of field "
                                       "names; known fields are " + ", ".join(STATE_FIELDS))
        return cls(default_mode=block.get("mode", DEFAULT_MODE), modes=modes,
                   state_fields=fields, sentinel=block.get("sentinel"),
                   timeout=block.get("timeout", DEFAULT_TIMEOUT),
                   max_requests=block.get("max_requests"),
                   max_tokens=block.get("max_tokens"), configured=True)

    @classmethod
    def acting(cls) -> "Controls":
        return cls(default_mode="act", modes=dict((point, "act") for point in POINTS),
                   state_fields=STATE_FIELDS)

    def sentinel_path(self) -> Path:
        """Onde vive o interruptor de emergência. Um caminho relativo é resolvido contra o diretório de estado.

        Nunca contra o diretório de trabalho: um interruptor cujo significado depende de onde um
        hook foi invocado é um que fica ligado para algumas decisões e desligado para outras.
        """
        if not self.sentinel:
            return state_dir() / SENTINEL_NAME
        path = Path(self.sentinel).expanduser()
        return path if path.is_absolute() else state_dir() / path

    def disabled(self) -> bool:
        """Se o interruptor de emergência está acionado. Lido por decisão, nunca em cache."""
        try:
            return self.sentinel_path().exists()
        except OSError:
            # Um caminho que nem sequer pode ser stat'ado não é motivo para começar a chamar.
            return True

    def mode_for(self, point: Optional[str] = None) -> str:
        """O modo para um ponto de decisão, o sentinela e um nome desconhecido incluídos.

        Um ponto que este harness não conhece lê `off`, nunca o padrão: um chamador que nomeia
        um ponto que ninguém configurou é um chamador sobre o qual ninguém decidiu.
        """
        if self.disabled():
            return "off"
        if point is not None and point not in POINTS:
            return "off"
        if point is not None and point in self.modes:
            return self.modes[point]
        return self.default_mode

    def selected(self) -> Dict[str, str]:
        """Todo ponto conhecido e o modo para o qual resolve, o sentinela incluído."""
        return dict((point, self.mode_for(point)) for point in POINTS)

    def enabled(self) -> bool:
        """Se algum modo configurado pede uma chamada, o interruptor de emergência deixado de fora disso.

        O que um cliente é construído com, porque o interruptor de emergência é respondido por
        decisão por `mode_for`: um cliente construído enquanto o sentinela existia ainda precisa
        funcionar no momento em que é removido, sem reinício.
        """
        if not self.configured:
            return False
        modes = [self.modes.get(point, self.default_mode) for point in POINTS]
        return any(mode != "off" for mode in modes)

    def live(self) -> bool:
        """Se uma chamada poderia ser feita agora mesmo: habilitado, e não desligado."""
        return self.enabled() and not self.disabled()

    def allowed_fields(self) -> List[str]:
        return list(BASE_FIELDS) + list(self.state_fields)

    def outbound(self, context: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """Os campos listados de `context` que são seguros para enviar, e nada mais.

        Um campo cujo texto combina com uma forma de segredo conhecida é descartado por
        inteiro em vez de mascarado: a correspondência diz onde uma credencial está, não quão
        longa ela é, e um resto mascarado ainda carregaria o que quer que estivesse ao lado dela.
        """
        patterns = secret_patterns()
        out = {}
        for name in self.state_fields:
            value = (context or {}).get(name)
            if not isinstance(value, str) or not value.strip():
                continue
            if patterns is None or any(rx.search(value) for rx in patterns):
                continue
            out[name] = value
        return out

    def check_outbound(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """`state`, ou um `PolicyError` nomeando a primeira chave que nenhuma configuração permitiu sair."""
        allowed = set(self.allowed_fields())
        extra = sorted(set(state) - allowed)
        if extra:
            raise decision.PolicyError(
                "jev: " + ", ".join(extra) + " is not a field this configuration allows out; "
                "allowed fields are " + ", ".join(sorted(allowed)))
        return state

    def status(self, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """O que `harness doctor` imprime: modos, o interruptor, e se uma chave existe.

        A credencial é reportada apenas pelo nome da variável. Um valor é uma credencial e nunca
        é impresso, aqui ou em qualquer lugar.
        """
        try:
            path = str(self.sentinel_path())
        except (OSError, RuntimeError):
            path = "unresolved"
        return {"default_mode": self.default_mode, "modes": self.selected(),
                "sentinel": path, "sentinel_present": self.disabled(),
                "state_fields": list(self.state_fields),
                "credential": credential_variable(env), "live": self.live(),
                "timeout": self.timeout, "max_requests": self.max_requests,
                "max_tokens": self.max_tokens}


class SessionSpend:
    """As requisições e tokens de uma sessão, compartilhados por todo processo que responde por ela.

    Um hook é um processo novo por evento, então um teto contado em memória limita uma única
    decisão e nada mais. Os contadores vivem no diretório de estado chaveados pelo id de sessão,
    lidos antes de cada checagem e somados após cada cobrança, sob o mesmo lock que o resto do
    harness usa para um arquivo que dois processos podem escrever.

    Nada aqui pode falhar uma decisão. Um lock que fica preso, um arquivo ilegível ou um disco
    cheio deixa a contagem local ao processo como estava, o que é a mesma direção conservadora do
    resto deste provedor: um julgamento nunca vale mais que um turno.
    """

    def __init__(self, session: Optional[str] = None, path=None,
                 env: Optional[Dict[str, str]] = None):
        env = os.environ if env is None else env
        named = session or next((env[name] for name in SESSION_VARIABLES if env.get(name)), None)
        self.session = named if _session_key(named) else UNKNOWN_SESSION
        self.path = Path(path) if path else state_dir() / SPEND_NAME

    def read(self) -> Tuple[int, int]:
        """`(requests, tokens)` já gastos nesta sessão. Ilegível é zero."""
        row = self._rows().get(self.session) or {}
        return (_nonnegative(row.get("requests")), _nonnegative(row.get("tokens")))

    def add(self, requests: int, tokens: int) -> bool:
        """Soma ao gasto desta sessão; diz se o arquivo aceitou."""
        for attempt in range(SPEND_LOCK_ATTEMPTS):
            try:
                with reconcile.lock(self.path.parent):
                    rows = self._prune(self._rows())
                    row = rows.get(self.session) or {}
                    rows[self.session] = {
                        "requests": _nonnegative(row.get("requests")) + int(requests),
                        "tokens": max(0, _nonnegative(row.get("tokens")) + int(tokens)),
                        "updated": int(time.time())}
                    reconcile.atomic_text(self.path, json.dumps(rows, sort_keys=True) + "\n")
                return True
            except ValueError:
                # Outro processo segura o lock. Ele o segura por uma escrita pequena.
                time.sleep(SPEND_LOCK_PAUSE * (attempt + 1))
            except OSError:
                return False
        return False

    def _rows(self) -> Dict[str, Any]:
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return dict((k, v) for k, v in rows.items() if isinstance(v, dict)) \
            if isinstance(rows, dict) else {}

    def _prune(self, rows: Dict[str, Any]) -> Dict[str, Any]:
        cutoff = time.time() - SPEND_RETENTION_SECONDS
        return dict((name, row) for name, row in rows.items()
                    if name == self.session or _nonnegative(row.get("updated")) >= cutoff)


def _session_key(value: Any) -> bool:
    """Um id de sessão seguro para chavear uma linha por ele: ASCII, limitado, sem separador e sem travessia."""
    return (isinstance(value, str) and value.isascii() and 0 < len(value) <= 128
            and value[0].isalnum() and all(c.isalnum() or c in "._-" for c in value))


def _nonnegative(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def credential_variables() -> List[str]:
    return list(KEY_VARIABLES)


def credential_variable(env: Optional[Dict[str, str]] = None) -> Optional[str]:
    """O nome da variável de ambiente que guarda uma chave, ou None. Nunca o valor."""
    env = os.environ if env is None else env
    return next((name for name in KEY_VARIABLES if env.get(name)), None)


def secret_patterns():
    """As formas de segredo compartilhadas, compiladas, ou None quando a lista não pode ser carregada.

    Uma única lista para o lint, o detector `secret-in-write` e este filtro. None não é "nenhum
    segredo": um chamador o lê como "varredura indisponível" e não envia texto livre nenhum,
    porque um redator que falhou ao carregar não deve ser confundido com um que não encontrou nada.
    """
    module = decision._hook_module("rule-detectors")
    patterns = getattr(module, "SECRET_PATTERNS", None) if module else None
    if not patterns:
        return None
    try:
        return [re.compile(pattern) for pattern in patterns]
    except re.error:
        return None
