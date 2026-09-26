"""Qual classe de capacidade executa um alvo de qualificação, e qual classe lê o que ele escreveu.

Todo caso obrigatório agora é um script (#336): o worker de um alvo roda um script, lê
JSON e escreve achados, o que não é trabalho que precise do nível forte. O que precisa dele é a
avaliação — o procedimento publicado exige que um revisor avalie as observações, e um worker mais
barato que produziu a evidência nunca pode ser o único leitor dela.

Então uma rodada carrega duas classes por alvo, não uma: uma classe de execução, `standard` por
padrão, e uma classe de avaliação, `strong`, que é um piso e não uma preferência. O par é resolvido
através do `adapters/<runtime>/bindings.json` do runtime do alvo e escrito no registro de
evidência, então o registro diz qual classe produziu uma observação e qual classe deve lê-la.
Uma classe de execução barata que resolve para o próprio modelo da classe de avaliação é recusada
em vez de registrada: uma rodada cujo executor é seu próprio leitor compra a economia removendo o
revisor.

A resolução lê a própria tabela do adaptador. Um override pessoal de `tiers.<runtime>` na
configuração de um usuário não é aplicado, porque uma rodada roda a partir de um clone congelado
e o registro nomeia a classe ao lado do modelo do adaptador para ela; passe `tiers` para colocar
uma sobreposição em cima.
"""
import importlib.util
import re
from pathlib import Path

from . import catalog

TIER_CLASSES = catalog.TIER_CLASSES
EXECUTION_DEFAULT = "standard"
ASSESSMENT_DEFAULT = "strong"
# A classe mais fraca autorizada a avaliar as observações de uma rodada. `docs/compatibility.md`
# exige um revisor; a decisão 6 da #340 mantém esse revisor na classe strong enquanto o executor
# fica mais barato.
ASSESSMENT_FLOOR = "strong"
UNMAPPED = ("the %s adapter maps no %s class, so the %s worker inherits the session model; "
            "the record names the class, not a model")
_RELEASE_SUFFIX = re.compile(r"(?:[-@](?:20\d{6}|20\d{2}-\d{2}-\d{2})|-v\d+(?::\d+)?)$")
_NORMALISERS = {}


def _normaliser(root):
    """`pricing.normalise_model` do checkout, ou o fallback abaixo.

    Uma grafia de id de modelo já tem uma definição, no hook de pricing; uma segunda cópia dela
    divergiria da do ledger. O hook vive sob dois nomes, `policy/hooks` sendo o real e
    `claude/hooks` a projeção, e uma árvore que carrega só a projeção ainda resolve. Uma árvore
    que não carrega nenhum dos dois recai para o fallback, porque um hook ausente não deve
    desligar a recusa de mesmo modelo.
    """
    key = str(root)
    if key not in _NORMALISERS:
        _NORMALISERS[key] = _loaded(root) or _normalise_model
    return _NORMALISERS[key]


def _loaded(root):
    path = next((p for p in (Path(root) / "policy" / "hooks" / "pricing.py",
                             Path(root) / "claude" / "hooks" / "pricing.py") if p.is_file()), None)
    if path is None:
        return None
    try:
        spec = importlib.util.spec_from_file_location("harness_pricing", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.normalise_model
    except Exception:
        return None


def _normalise_model(model):
    """A grafia de fallback: minúsculas, sem colchete de janela, sem prefixo de fornecedor, sem sufixo de lançamento."""
    name = re.sub(r"\[[^\]]*\]", "", (model or "").strip().lower()).split("/")[-1]
    while True:
        head, dot, rest = name.partition(".")
        if not (dot and rest and head.isalpha()):
            break
        name = rest
    while True:
        trimmed = _RELEASE_SUFFIX.sub("", name)
        if trimmed == name:
            break
        name = trimmed
    return name.strip("-").strip()


def _words(name):
    return [part for part in re.split(r"[^a-z0-9]+", name) if part]


def same_model(first, second, normalise=_normalise_model):
    """Se duas entradas de adaptador nomeiam um único modelo, uma vez consideradas grafia e aliasing.

    Duas classes mapeadas para `opus` e para um `claude-opus-4-5-20260101` datado são um modelo
    comprado duas vezes, e comparar as strings perderia isso. Então os ids são normalizados do
    jeito que o ledger os normaliza, e um alias — cada palavra de um id aparecendo, em ordem e
    adjacente, no outro — conta como o mesmo modelo. A comparação protege uma recusa, então erra
    a favor de recusar: `gpt-5` e `gpt-5.6-terra` são tratados como um único modelo, e um operador
    que quer dizer dois escreve dois ids que não são prefixo um do outro.
    """
    left, right = normalise(first), normalise(second)
    if left == right:
        return True
    if not left or not right:
        return False
    short, long = sorted((_words(left), _words(right)), key=len)
    return any(long[i:i + len(short)] == short for i in range(len(long) - len(short) + 1))


def _rank(name):
    return TIER_CLASSES.index(name)


def _checked(name, what):
    if name not in TIER_CLASSES:
        raise ValueError("%s class must be one of %s: %s" % (what, ", ".join(TIER_CLASSES), name))
    return name


def parse_class_map(values, targets, default, flag="--execution-class", known=None):
    """Argumentos `CLASS` ou `TARGET=CLASS`, os mais recentes vencendo, como uma classe por alvo.

    Uma classe nua move todo alvo que a rodada está rodando; uma qualificada move o alvo que
    nomeia, então uma rodada Codex pode ser executada numa classe diferente de uma Claude Code
    sem duas invocações. `known` é todo alvo que este executor possui, o que é o que diferencia um
    cliente deixado de fora de `--targets` de um cliente que não existe: o primeiro é uma rodada
    que o operador não pediu, o segundo é um erro de digitação, e são erros diferentes.
    """
    chosen = dict((target, default) for target in targets)
    for value in values or []:
        target, sign, name = str(value).partition("=")
        target, name = target.strip(), name.strip()
        if not sign:
            target, name = None, target
        if target is not None:
            if not target:
                raise ValueError("%s: no target named before '=': %s" % (flag, value))
            if target not in chosen:
                raise ValueError("%s: %s" % (flag, (
                    "%s is not in this round's --targets" % target if target in (known or ())
                    else "unknown qualification target: " + target)))
            if not name:
                raise ValueError("%s: no class given for target %s" % (flag, target))
        if not name:
            raise ValueError("%s: no class given" % flag)
        try:
            _checked(name, "worker")
        except ValueError as error:
            raise ValueError("%s: %s" % (flag, error))
        for key in ([target] if target is not None else list(chosen)):
            chosen[key] = name
    return chosen


def resolve(root, runtime, execution=EXECUTION_DEFAULT, assessment=ASSESSMENT_DEFAULT,
            tiers=None):
    """O roteamento da rodada para um alvo, ou `ValueError` nomeando por que é recusado.

    A recusa é uma classe de execução barata que pousa no próprio modelo da classe de avaliação,
    seja lá como isso aconteça — uma tabela de adaptador mapeando duas classes para um
    identificador, duas grafias de um modelo, ou uma classe barata que a tabela não mapeia de jeito
    nenhum, o que resolve para cima. Um avaliador que a tabela não mapeia enquanto o executor está
    fixado também é recusado: o leitor herdaria seja lá qual modelo a sessão estiver rodando por
    acaso, que não é leitor nomeado nenhum. O que continua sendo uma divulgação em vez de uma
    recusa é um *executor* não mapeado ao lado de um avaliador mapeado, que é o que pedir uma
    classe mais forte que a do avaliador faz.
    """
    _checked(execution, "execution")
    _checked(assessment, "assessment")
    if _rank(assessment) > _rank(ASSESSMENT_FLOOR):
        raise ValueError(
            "assessment class %s is weaker than %s: a cheaper tier may execute the scripted "
            "cases, but the round's observations are assessed by a %s-class reader"
            % (assessment, ASSESSMENT_FLOOR, ASSESSMENT_FLOOR))
    table = catalog.adapter_tiers(root, runtime, tiers)[1]
    executor = catalog.native_model(table, execution)
    assessor = catalog.native_model(table, assessment)
    if _rank(execution) > _rank(ASSESSMENT_FLOOR):
        if assessor is None:
            raise ValueError(
                "the %s adapter maps no %s class, so the reader of what a %s worker produced "
                "would be whatever model the session is running: name a mapped assessment class"
                % (runtime, assessment, executor or "session-model"))
        if same_model(executor, assessor, _normaliser(root)):
            raise ValueError(
                "execution class %s and assessment class %s both resolve to %s on %s: a cheaper "
                "worker may produce the evidence, but it may not be the only reader of it"
                % (execution, assessment, assessor, runtime))
    notes = []
    for name, model, what in ((execution, executor, "execution"),
                              (assessment, assessor, "assessment")):
        if model is None:
            notes.append(UNMAPPED % (runtime, name, what))
    routing = {"execution_class": execution, "execution_model": executor,
               "assessment_class": assessment, "assessment_model": assessor}
    if notes:
        routing["notes"] = notes
    return routing


def describe(routing):
    """Uma linha que um operador lê num plano ou num resumo de rodada."""
    return "execution %s (%s), assessment %s (%s)" % (
        routing["execution_class"], routing["execution_model"] or "session model",
        routing["assessment_class"], routing["assessment_model"] or "session model")
