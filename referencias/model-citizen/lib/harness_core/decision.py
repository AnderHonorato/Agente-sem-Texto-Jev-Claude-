"""A interface compartilhada de provedor de decisão: um único contrato para "esta ação pode prosseguir, e como".

Três operações, agnósticas de transporte, para que um arquivo de política local e um plano de
controle remoto respondam às mesmas perguntas na mesma forma:

    decide(action, counterparty, context) -> Decision
    record(action_outcome) -> None
    learn(approval_stream) -> None

`Action` carrega uma classe de ação e, quando o chamador a conhece, a nota que `grade-bash.py` já
atribui a um comando (0 reversível, 3 irreversível). `counterparty` é o slug `repo:<name>/<branch>`
que `counterparty()` deriva, então uma política escrita contra um repositório e branch combina com
o que quer que faça a pergunta.

Dois provedores vêm embutidos aqui. `none` é o padrão e não governa nada: toda ação é permitida no
nível de autonomia 3. `local` lê um arquivo de política em nível de usuário e um por repositório,
os mescla, e resolve um nível a partir do resultado.
Um provedor que responde por um transporte vive em `harness_core.decisions` e é importado só
quando uma configuração o nomeia; `jev` é o que vem embutido.
Nada neste módulo alcança a rede. `grade-bash.py` consulta o provedor selecionado para cada
comando Bash que de outra forma deixaria passar, mas apenas quando `governance.provider` não é
`none`, e só importa este módulo nesse caso: sob `none` a saída do hook é exatamente o que a stance
sozinha dá. O vínculo só aperta, nunca afrouxa, então um provedor pode transformar um allow em ask
e nunca um ask em allow, e um provedor configurado que levanta pedidos em vez de permitir.
`docs/runtime-controls.md` descreve o vínculo do lado do usuário.

`Decision.outcome` tem três valores — `allow`, `ask`, `deny`. Nenhum dos dois provedores aqui nega
jamais; `deny` existe porque um provedor que pode recusar precisa ter onde dizê-lo, e um consumidor
escrito contra o contrato deveria tratá-lo desde o primeiro dia.
"""
import contextlib
import importlib.util
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]

# As classes sobre as quais um chamador pode perguntar. Fechado de propósito: um erro de digitação
# num arquivo de política que silenciosamente não governa nada é pior que um arquivo de política
# que se recusa a carregar.
ACTION_CLASSES = ("coding.shell_exec", "coding.git_commit", "coding.git_push", "coding.deploy",
                  "coding.file_write", "coding.pr_merge")
OUTCOMES = ("allow", "ask", "deny")
LEVELS = (1, 2, 3)
ACTION_OUTCOMES = ("completed", "skipped", "failed")

# O que cada variante de autonomia implica quando nenhuma política nomeia um nível para a ação. Os
# mesmos limiares sob os quais `grade-bash.py` avalia, para que um repositório sem arquivo de
# política se comporte exatamente como a stance em vigor já diz que deveria.
STANCE_LEVELS = {"execute": 3, "confirm-writes": 2, "ask": 1}
# Stance não resolvível: a variante mais estrita, para a razão de `grade-bash.py` — um portão que
# não consegue ler sua própria configuração não deve ampliar autoridade com base em não saber.
STRICTEST_LEVEL = 1
# Um deploy nunca é totalmente autônomo, seja o que for que um arquivo de política diga. Um teto
# no arquivo pode baixar isso e não pode elevar.
BUILTIN_CAPS = {"coding.deploy": 2}
# Uma ação cuja nota o chamador não conhece é julgada em 1, nunca em 3 — a regra de
# `grade-bash.py` para um comando que não consegue reconhecer, pela mesma razão.
UNKNOWN_GRADE = 1

POLICY_FILE = Path(".agent-harness") / "governance.json"
# A política em nível de usuário fica ao lado de `config.json`, no mesmo schema do arquivo de repositório.
USER_POLICY_NAME = "governance.json"
USER_LAYER = "user policy"
REPOSITORY_LAYER = "repository policy"
BUILTIN_SOURCE = "built-in"
POLICY_KEYS = ("defaults", "pairs", "caps")
# O nome de ponto que as próprias linhas de resultado de um provedor carregam no ledger de
# decisão. Deliberadamente fora de `decisions.POINTS`: essa tupla nomeia os pontos de hook cujas
# linhas o relatório espera que existam. As linhas que `grade-bash.py` escreve para cada decisão
# que pede a um provedor carregam seu próprio ponto `governance` em vez disso.
LEDGER_POINT = "decision-provider"


class PolicyError(ValueError):
    """Um arquivo de política de governança que não pode ser honrado como está escrito.

    Levantado em vez de ignorado: uma política malformada é uma pergunta de governança que
    ninguém respondeu, e lê-la como "nenhuma política" concederia silenciosamente o que ela
    pretendia negar. Todo ponto de chamada transforma isso numa única linha nomeando o arquivo e
    a falha.
    """


@dataclass(frozen=True)
class Action:
    """O que está prestes a acontecer: uma classe de ação, e sua nota quando conhecida."""

    action_class: str
    grade: Optional[int] = None

    def effective_grade(self) -> int:
        return UNKNOWN_GRADE if self.grade is None else self.grade

    def as_dict(self) -> Dict[str, Any]:
        return {"action_class": self.action_class, "grade": self.grade}


@dataclass(frozen=True)
class ActionOutcome:
    """Como uma ação sobre a qual se decidiu de fato se desenrolou."""

    action_class: str
    counterparty: str
    outcome: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    """A resposta de um provedor.

    `injected_cognition` é a parte que um runtime pode colocar diante de um agente ou de uma
    pessoa: `rule_matches` nomeia toda linha de política que influenciou a resposta, literal o
    bastante para ser citada, e as duas mensagens são texto para o agente e para o usuário, ou
    None quando não há nenhuma.
    """

    outcome: str
    autonomy_level: int
    provider: str
    reason: str
    injected_cognition: Dict[str, Any] = field(default_factory=lambda: dict(empty_cognition()))

    def as_dict(self) -> Dict[str, Any]:
        return {"outcome": self.outcome, "autonomy_level": self.autonomy_level,
                "injected_cognition": self.injected_cognition, "provider": self.provider,
                "reason": self.reason}


def empty_cognition() -> Dict[str, Any]:
    return {"rule_matches": [], "agent_message": None, "user_message": None}


# ------------------------------------------------------------------ o ledger compartilhado

_HOOK_MODULES: Dict[str, Any] = {}


def _hook_module(name: str, root: Optional[Path] = None):
    """Um módulo do diretório de hooks, carregado por arquivo, ou None quando não está lá.

    `claude/hooks` é um symlink para `policy/hooks`; ambos os nomes são tentados pela razão que
    `catalog.posture_module` dá. Carregar o próprio arquivo do hook é o que mantém um único
    escritor para o ledger de decisão e uma única derivação do slug de contraparte.
    """
    root = ROOT if root is None else Path(root)
    key = str(root) + "/" + name
    if key in _HOOK_MODULES:
        return _HOOK_MODULES[key]
    path = next((p for p in (root / "policy" / "hooks" / (name + ".py"),
                             root / "claude" / "hooks" / (name + ".py")) if p.is_file()), None)
    if path is None:
        return None
    try:
        spec = importlib.util.spec_from_file_location("harness_" + name.replace("-", "_"),
                                                      str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        return None
    _HOOK_MODULES[key] = module
    return module


UNKNOWN_COUNTERPARTY = "repo:unknown/local"


def counterparty(cwd: Optional[str] = None) -> str:
    """`repo:<name>/<branch>` para um diretório de trabalho; `locate` diz como é derivado."""
    return locate(cwd)[0]


def locate(cwd: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """`(counterparty, raiz da working tree)` para um diretório de trabalho.

    Derivado através do próprio auxiliar git de `usage-log.py`, assim como o ledger de uso deriva
    seu repositório e branch, com uma diferença: `<name>` é o do repositório, lido do diretório
    git comum, então uma worktree vinculada num diretório nomeado por sua tarefa ainda nomeia o
    repositório ao qual pertence, e uma política chaveada em `repo:<name>` governa toda worktree
    dele. O campo `repo` do ledger mantém o nome do diretório da worktree. Fora de um
    repositório, `repo:unknown/local` e nenhuma raiz: uma política não deve combinar
    silenciosamente com um diretório que apenas compartilha um nome-base com um repositório.
    """
    cwd = str(Path(cwd).expanduser()) if cwd else os.getcwd()
    module = _hook_module("usage-log")
    if module is None or not os.path.isdir(cwd):
        return UNKNOWN_COUNTERPARTY, None
    top = module.git(cwd, "rev-parse", "--show-toplevel")
    if not top:
        return UNKNOWN_COUNTERPARTY, None
    common = module.git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    branch = module.git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    return "repo:" + repository_name(top, common) + "/" + (branch or "unknown"), top


def repository_name(top: str, common: Optional[str]) -> str:
    """O nome do repositório: o diretório que guarda seu `.git` comum, ou um `<name>.git` bare.

    Recai para o nome do próprio diretório da working tree quando o diretório comum é
    desconhecido, como acontece sob um git velho demais para `--path-format`.
    """
    if common:
        common = os.path.normpath(common)
        base = os.path.basename(common)
        if base == ".git":
            name = os.path.basename(os.path.dirname(common))
        else:
            name = base[:-4] if base.endswith(".git") else base
        if name:
            return name
    return os.path.basename(top.rstrip("/")) or "unknown"


def _ledger():
    return _hook_module("decisions")


def ledger_path(target: Optional[str] = None) -> Optional[Path]:
    module = _ledger()
    if module is None:
        return None
    return Path(target) if target else module.path()


def append_outcome(action_outcome: ActionOutcome, target: Optional[str] = None) -> Optional[str]:
    """Escreve um resultado de ação no ledger de decisão. Retorna seu id, ou None.

    O `decisions.jsonl` já existente, através do escritor já existente, nunca um segundo arquivo:
    um leitor do ledger vê a atividade do provedor ao lado das decisões de hook que já contém.
    Nunca levanta exceção, pela razão que aquele módulo dá — um log que pode mudar uma resposta é
    pior que nenhum log — então um chamador recebe None e continua.
    """
    module = _ledger()
    if module is None:
        return None
    text = json.dumps({"action": action_outcome.action_class,
                       "counterparty": action_outcome.counterparty,
                       "metadata": action_outcome.metadata}, sort_keys=True)
    return module.record(LEDGER_POINT, action_outcome.outcome, text=text,
                         key=action_outcome.action_class + "|" + action_outcome.counterparty
                             + "|" + text,
                         target=str(target) if target else None)


_SUPPRESSED = []


@contextlib.contextmanager
def events_suppressed():
    """Dentro deste bloco, `append_event` não escreve nada e diz isso.

    Para um comando de relatório: `harness decide` pergunta a um provedor o que ele responderia,
    e um provedor que alcança um serviço de outra forma deixaria uma linha para trás por uma
    pergunta sobre a qual ninguém agiu. Reentrante, então aninhá-lo não pode religar o log cedo
    demais.
    """
    _SUPPRESSED.append(True)
    try:
        yield
    finally:
        _SUPPRESSED.pop()


def suppressed() -> bool:
    """Se um comando de relatório está segurando as escritas abertas. Lido por todo ledger que este módulo tem."""
    return bool(_SUPPRESSED)


def append_event(name: str, detail: Dict[str, Any], target: Optional[str] = None) -> bool:
    """Escreve uma linha `event` no ledger de decisão. Nunca levanta exceção; diz se escreveu.

    Um evento não carrega `decision_id`, então `decisions.read_rows` o pula e
    `harness usage --by decision` nunca conta a contabilidade do provedor como um julgamento que
    ninguém rotulou. `read_events` abaixo os lê de volta.
    """
    if suppressed():
        return False
    module = _ledger()
    if module is None:
        return False
    try:
        if not module.enabled():
            return False
        # O append próprio do ledger: uma linha, uma escrita, e nenhum segundo arquivo para manter em sincronia.
        module._append({"kind": "event", "point": LEDGER_POINT, "event": name,
                        "ts": module.now_ts(), "detail": detail,
                        "harness_version": module.harness_version()},
                       str(target) if target else None)
        return True
    except Exception:
        return False


def read_events(target: Optional[str] = None) -> List[Dict[str, Any]]:
    """Toda linha `event` no ledger, da mais antiga para a mais nova. Um arquivo ilegível é nenhum evento."""
    path = ledger_path(target)
    if path is None:
        return []
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    events = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("kind") == "event":
            events.append(row)
    return events


def validate_approvals(stream: Iterable[Any]) -> List[Dict[str, Any]]:
    """Os registros de aprovação em `stream`, ou um `PolicyError` nomeando o primeiro ruim.

    Apenas a forma: `{action, counterparty, approved: bool, at: iso8601}`. Nada aqui aprende com
    eles ainda — os provedores que vêm embutidos hoje não conseguem — e validar a forma é
    exatamente o que mantém a interface honesta: um chamador que entrega lixo é avisado agora em
    vez de quando algo finalmente ler o arquivo.
    """
    if isinstance(stream, (str, bytes, dict)) or stream is None:
        raise PolicyError("learn: the approval stream must be an iterable of records")
    records = []
    for index, item in enumerate(stream):
        where = "learn: record %d" % index
        if not isinstance(item, dict):
            raise PolicyError(where + " is not an object")
        for name in ("action", "counterparty", "at"):
            value = item.get(name)
            if not isinstance(value, str) or not value.strip():
                raise PolicyError(where + " needs a non-empty string `" + name + "`")
        if not isinstance(item.get("approved"), bool):
            raise PolicyError(where + " needs a boolean `approved`")
        if not _iso8601(item["at"]):
            raise PolicyError(where + " has `at` that is not an ISO 8601 timestamp: "
                              + item["at"])
        records.append(dict(item))
    return records


def _iso8601(value: str) -> bool:
    """Se `value` é um instante ISO 8601 que a stdlib deste patamar consegue ler.

    O `fromisoformat` do Python 3.9 não aceita um `Z` no final, que é a grafia que toda linha nos
    ledgers deste repositório usa, então a única substituição é feita antes do parse.
    """
    import datetime

    try:
        datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return False
    return True


# ------------------------------------------------------------------ o arquivo de política


def stance_level(variant: Optional[str] = None, root: Optional[Path] = None) -> int:
    """O nível que a stance de autonomia implica, ou o mais estrito quando nada o resolve.

    Resolvido através de `posture.py`, o mesmo arquivo que todo hook consulta, para que o
    provedor e o portão de comando não possam discordar sobre qual variante está em vigor.
    """
    if variant is None:
        module = _hook_module("posture", root)
        try:
            variant = None if module is None else module.selected("autonomy", None)
        except Exception:
            variant = None
    return STANCE_LEVELS.get(variant or "", STRICTEST_LEVEL)


def _level(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in LEVELS:
        raise PolicyError(where + " must be an autonomy level of 1, 2 or 3, not " + repr(value))
    return value


def _class_map(block: Any, where: str) -> Dict[str, int]:
    if not isinstance(block, dict):
        raise PolicyError(where + " must be an object of action class to level")
    out = {}
    for name, value in block.items():
        if name not in ACTION_CLASSES:
            raise PolicyError(where + " names an unknown action class " + repr(name)
                              + "; known classes are " + ", ".join(ACTION_CLASSES))
        out[name] = _level(value, where + "." + name)
    return out


def load_policy(path: Path) -> Dict[str, Dict[str, Any]]:
    """A política em `path`, validada, ou a política vazia quando o arquivo não está lá.

    Um arquivo ausente é um repositório que não escolheu nada, o que resolve para a stance. Um
    arquivo que existe e não pode ser honrado é um `PolicyError`.
    """
    path = Path(path)
    empty: Dict[str, Dict[str, Any]] = {"defaults": {}, "pairs": {}, "caps": {}}
    if not path.is_file():
        return empty
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PolicyError("governance policy " + str(path) + " cannot be read: " + str(exc))
    if not isinstance(raw, dict):
        raise PolicyError("governance policy " + str(path) + " must be a JSON object")
    unknown = sorted(set(raw) - set(POLICY_KEYS))
    if unknown:
        raise PolicyError("governance policy " + str(path) + " has unknown key(s) "
                          + ", ".join(unknown) + "; known keys are " + ", ".join(POLICY_KEYS))
    policy = dict(empty)
    pairs = raw.get("pairs", {})
    if not isinstance(pairs, dict):
        raise PolicyError("governance policy " + str(path) + ": pairs must be an object keyed "
                          "by counterparty")
    try:
        policy["defaults"] = _class_map(raw.get("defaults", {}), "defaults")
        policy["caps"] = _class_map(raw.get("caps", {}), "caps")
        policy["pairs"] = {slug: _class_map(block, "pairs." + str(slug))
                           for slug, block in pairs.items()}
    except PolicyError as exc:
        # Dois arquivos agora podem ser lidos, então uma falha dentro de um precisa dizer qual.
        raise PolicyError("governance policy " + str(path) + ": " + str(exc))
    return policy


def user_policy_file(env: Optional[Dict[str, str]] = None) -> Path:
    """Onde vive a política em nível de usuário: ao lado de `config.json`, encontrada como é encontrada.

    `HARNESS_HOME`, depois `HOME`, depois a home da conta, depois `.config/agent-harness` — a
    mesma busca que `bin/harness` e `posture.py` usam para `config.json`, então uma home
    temporária move os dois arquivos juntos.
    """
    env = os.environ if env is None else env
    home = env.get("HARNESS_HOME") or env.get("HOME") or str(Path.home())
    return Path(home) / ".config" / "agent-harness" / USER_POLICY_NAME


def merge_policies(layers: Iterable[Tuple[str, Path, Dict[str, Dict[str, Any]]]]
                   ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """Mescla camadas `(label, path, policy)`, precedência mais baixa primeiro, numa única política.

    Retorna `(policy, sources)`. `defaults` e as classes de cada par assumem o valor da camada
    mais recente; `caps` assumem o valor mais baixo, então nenhuma camada pode elevar um teto que
    outra baixou. `sources` mapeia o nome de regra de cada entrada (`defaults.<class>`,
    `pairs.<slug>.<class>`, `caps.<class>`) para o `"<label> <path>"` que a forneceu, para a razão
    e as correspondências de regra.
    """
    merged: Dict[str, Dict[str, Any]] = {"defaults": {}, "pairs": {}, "caps": {}}
    sources: Dict[str, str] = {}
    for label, path, policy in layers:
        where = label + " " + str(path)
        for name, level in policy.get("defaults", {}).items():
            merged["defaults"][name] = level
            sources["defaults." + name] = where
        for slug, block in policy.get("pairs", {}).items():
            target = merged["pairs"].setdefault(slug, {})
            for name, level in block.items():
                target[name] = level
                sources["pairs." + slug + "." + name] = where
        for name, level in policy.get("caps", {}).items():
            current = merged["caps"].get(name)
            if current is None or level <= current:
                merged["caps"][name] = level
                sources["caps." + name] = where
    return merged, sources


def repository_slug(counterparty: str) -> Optional[str]:
    """`repo:<name>` para um slug `repo:<name>/<branch>`, ou None quando não há parte de branch.

    O nome termina na primeira `/`, porque um nome de branch pode em si conter barras.
    """
    if not counterparty.startswith("repo:") or "/" not in counterparty:
        return None
    return counterparty.split("/", 1)[0]


def cap_for(action_class: str, policy: Dict[str, Dict[str, Any]]) -> Optional[int]:
    """O teto sobre o nível desta ação: o mais baixo entre o teto do arquivo e o embutido."""
    caps = [c for c in (policy.get("caps", {}).get(action_class),
                        BUILTIN_CAPS.get(action_class)) if c is not None]
    return min(caps) if caps else None


def outcome_for(level: int, grade: int) -> str:
    """`allow` ou `ask`, pelos limiares sob os quais `grade-bash.py` já avalia.

    Nível 3 permite toda nota; nível 2 pergunta na nota 2 e acima; nível 1 pergunta na nota 1 e acima.
    """
    if level >= 3:
        return "allow"
    return "ask" if grade >= level else "allow"


# ------------------------------------------------------------------ os provedores


class DecisionProvider(ABC):
    """O contrato que todo provedor responde, seja lá o que estiver por trás dele."""

    name = ""

    @abstractmethod
    def decide(self, action: Action, counterparty: str,
               context: Optional[Dict[str, Any]] = None) -> Decision:
        """Se esta ação pode prosseguir, e o que colocar diante do agente."""

    @abstractmethod
    def record(self, action_outcome: ActionOutcome) -> None:
        """Anota como uma ação se desenrolou. Nunca levanta exceção, nunca muda uma decisão."""

    @abstractmethod
    def learn(self, approval_stream: Iterable[Any]) -> None:
        """Recebe um fluxo de aprovações passadas. Pode ser um no-op; deve rejeitar um fluxo malformado."""


class NullProvider(DecisionProvider):
    """Não governa nada: toda ação é permitida no nível 3.

    O padrão, e o comportamento de um harness sem nenhuma governança — que é o que toda
    instalação tem hoje. Ele ainda registra resultados, então o ledger é povoado antes que
    qualquer política exista para ser medida contra ele.
    """

    name = "none"

    def __init__(self, target: Optional[str] = None):
        self.target = target

    def decide(self, action, counterparty, context=None):
        return Decision(outcome="allow", autonomy_level=3, provider=self.name,
                        reason="governance: none", injected_cognition=empty_cognition())

    def record(self, action_outcome):
        append_outcome(action_outcome, self.target)

    def learn(self, approval_stream):
        return None


class LocalProvider(DecisionProvider):
    """Um arquivo de política em nível de usuário e um por repositório, resolvidos contra a stance de autonomia.

    Ambos os arquivos compartilham um schema. `.agent-harness/governance.json` no repositório, e
    `governance.json` ao lado de `config.json` para o usuário:

        {"defaults": {"coding.git_push": 2},
         "pairs": {"repo:agent-harness/main": {"coding.git_push": 1},
                   "repo:agent-harness": {"coding.pr_merge": 2}},
         "caps": {"coding.deploy": 2}}

    O arquivo de repositório vence sobre o arquivo do usuário para `defaults` e entradas de par;
    `caps` se combinam pelo valor mais baixo. A resolução é o par exato
    `repo:<name>/<branch>`, depois o par de repositório inteiro `repo:<name>`, depois o padrão da
    classe, depois o nível que a stance de autonomia implica. Um teto é um limite que o nível
    resolvido nunca ultrapassa, e `coding.deploy` carrega um teto embutido de 2 que um arquivo
    pode baixar e não pode elevar: um deploy nunca é totalmente autônomo. A razão e cada
    correspondência de regra nomeiam o arquivo que forneceu o nível.
    """

    name = "local"

    def __init__(self, root: Optional[str] = None, policy_path: Optional[str] = None,
                 variant: Optional[str] = None, target: Optional[str] = None,
                 user_policy_path: Optional[str] = None):
        self.root = Path(root) if root else Path.cwd()
        self.policy_path = Path(policy_path) if policy_path else self.root / POLICY_FILE
        self.user_policy_path = (Path(user_policy_path) if user_policy_path
                                 else user_policy_file())
        self.variant = variant
        self.target = target
        self._policy = None
        self._sources: Dict[str, str] = {}

    def policy_files(self) -> List[Path]:
        """Os arquivos que este provedor lê, precedência mais baixa primeiro."""
        return [self.user_policy_path, self.policy_path]

    def policy(self) -> Dict[str, Dict[str, Any]]:
        if self._policy is None:
            layers = [(USER_LAYER, self.user_policy_path, load_policy(self.user_policy_path)),
                      (REPOSITORY_LAYER, self.policy_path, load_policy(self.policy_path))]
            self._policy, self._sources = merge_policies(layers)
        return self._policy

    def decide(self, action, counterparty, context=None):
        policy = self.policy()
        name = action.action_class
        matches = []
        keys = [counterparty]
        whole = repository_slug(counterparty)
        if whole is not None and whole != counterparty:
            keys.append(whole)
        source = None
        for key in keys:
            level = policy["pairs"].get(key, {}).get(name)
            if level is not None:
                source = "pairs." + key + "." + name
                break
        if source is None and policy["defaults"].get(name) is not None:
            level, source = policy["defaults"][name], "defaults." + name
        if source is None:
            level = stance_level(self.variant, self.root)
            source, origin = "autonomy stance", None
        else:
            origin = self._sources.get(source)
        matches.append(source + " = " + str(level) + (" (" + origin + ")" if origin else ""))
        cap = cap_for(name, policy)
        capped = None
        if cap is not None and level > cap:
            file_cap = policy["caps"].get(name)
            cap_origin = (self._sources.get("caps." + name)
                          if file_cap is not None and file_cap == cap else BUILTIN_SOURCE)
            capped = "caps." + name + " = " + str(cap) + " (" + cap_origin + ")"
            matches.append(capped)
            level = cap
        grade = action.effective_grade()
        outcome = outcome_for(level, grade)
        described = source + (" in " + origin if origin else "")
        if capped:
            # O nível reportado é o do teto, então a razão nomeia o teto, não só a regra que ele baixou.
            described += ", capped by " + capped
        reason = ("governance: local, level %d, grade %s -> %s (%s)"
                  % (level, "unknown" if action.grade is None else str(grade), outcome,
                     described))
        cognition = empty_cognition()
        cognition["rule_matches"] = matches
        if outcome == "ask":
            cognition["agent_message"] = (
                name + " on " + counterparty + " is level " + str(level)
                + ": state the exact command and wait for an explicit yes.")
        return Decision(outcome=outcome, autonomy_level=level, provider=self.name,
                        reason=reason, injected_cognition=cognition)

    def record(self, action_outcome):
        append_outcome(action_outcome, self.target)

    def learn(self, approval_stream):
        records = validate_approvals(approval_stream)
        append_event("learn", {"records": len(records), "provider": self.name}, self.target)
        return None


PROVIDERS = {NullProvider.name: NullProvider, LocalProvider.name: LocalProvider}
# Um provedor que responde por um transporte vive em `harness_core.decisions` e importa este
# módulo, então é nomeado aqui e carregado só quando uma configuração o pede.
TRANSPORT_PROVIDERS = {"jev": ("harness_core.decisions.jev", "JevProvider")}


def provider_class(name: str):
    """A classe que um nome de provedor seleciona, importando um provedor de transporte sob demanda."""
    if name in PROVIDERS:
        return PROVIDERS[name]
    if name in TRANSPORT_PROVIDERS:
        import importlib

        module_name, attribute = TRANSPORT_PROVIDERS[name]
        try:
            return getattr(importlib.import_module(module_name), attribute)
        except Exception as exc:
            raise PolicyError("governance.provider " + repr(name) + " cannot be loaded: "
                              + str(exc))
    raise PolicyError("governance.provider " + repr(name) + " is not a provider; known "
                      "providers are " + ", ".join(sorted(set(PROVIDERS) | set(TRANSPORT_PROVIDERS))))


def select_provider(config: Optional[Dict[str, Any]] = None, **kwargs) -> DecisionProvider:
    """O provedor que `governance.provider` nomeia, `none` por padrão.

    Um nome desconhecido é recusado em vez de assumir um padrão: uma configuração que pede uma
    governança que ninguém pode fornecer não deve voltar como governança que ninguém aplicou.
    """
    block = (config or {}).get("governance")
    name = block.get("provider") if isinstance(block, dict) else None
    name = name if isinstance(name, str) and name.strip() else NullProvider.name
    cls = provider_class(name)
    if cls is NullProvider:
        kwargs.pop("root", None)
        kwargs.pop("policy_path", None)
        kwargs.pop("user_policy_path", None)
        kwargs.pop("variant", None)
    if name in TRANSPORT_PROVIDERS:
        # Um provedor que sai da máquina lê seu próprio bloco de opt-in, então selecioná-lo nunca
        # é por si só suficiente para fazê-lo chamar qualquer coisa.
        kwargs.setdefault("config", config or {})
    return cls(**kwargs)
