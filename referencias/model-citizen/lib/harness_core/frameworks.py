"""A qual framework um disparo nativo pertence, lido a partir de um descritor de integração declarado.

Um framework que dirige uma sessão de agente dispara subagentes próprios, e o nome que dá a eles
é seja lá o que o modelo do cliente escrever na chamada. O confinamento não pode ser construído
sobre esse nome: a instrução roteada para rodar um papel restrito através de `harness role run` é
um pedido num prompt, e um cliente que parafraseia o brief e não nomeia nenhum papel passa direto
por uma proteção que só lê `subagent_type` (#291).

Então um framework se declara em vez disso. `policy/integrations/<id>.json` nomeia o framework, a
versão à qual está fixado, como seus disparos são reconhecidos, para qual papel do harness cada
disparo mapeia, e as raízes de entrada de que um worker confinado precisa. O hook de disparo
classifica a partir desse mapeamento, e uma linha `harness-role:` no brief continua sendo o que
sempre foi: uma otimização que poupa o trabalho do classificador, não aquilo de que a imposição depende.

O reconhecimento é corroborado, porque uma recusa falsa não é um erro menor do que uma perdida:
um brief classificado erroneamente é trabalho que a sessão não consegue realizar, e o classificador
não tem como ouvir que estava errado.

* **agents** — um disparo cujo `subagent_type` é um dos próprios nomes de camada do framework. Só
  o framework coloca esse nome ali, então isso sozinho já basta.
* **identifiers** — um literal que só o texto roteado do framework carrega, como o caminho de um
  dos seus arquivos de prompt. Nunca basta sozinho: um brief que edita os templates de override,
  ou que pede a um worker para ler um desses arquivos, cita o mesmo caminho. Um identificador
  precisa de uma frase ao lado, ou de uma diretiva.
* **directed identifiers** — um identificador numa frase que instrui o subagente a segui-lo ou
  aplicá-lo: "read the instructions at <path> and follow them exactly". Um cliente que escreve o
  próprio brief mantém o arquivo de prompt, porque o subagente precisa lê-lo, e descarta toda
  frase do texto próprio do framework (#739). A diretiva é o que separa isso de um brief que edita
  o arquivo ou o lê por outro motivo, então basta sozinha. Ela precisa governar o arquivo: antes
  dele e ininterrupta por uma cláusula, ou depois dele com um pronome apontando de volta ("and
  follow them", "follow it" numa frase posterior enquanto as intermediárias ainda falam do
  arquivo). Uma diretiva negada, uma diretiva apontada para outra coisa, e uma frase que edita,
  atualiza ou reescreve o próprio arquivo não são diretivas; "update your findings" edita outra
  coisa e deixa a diretiva de pé. O caminho precisa terminar onde o declarado termina, então
  `<path>.bak` é outro arquivo, e um "follow the instructions in <other>" no final nomeia seu
  próprio arquivo.
* **phrases** — frases inteiras do próprio texto de prompt do framework, distintas o bastante para
  que citar uma seja coincidência e citar `corroboration` delas não seja. Substantivos genéricos
  isolados não são frases: "unified diff" e "list of findings" são o que um brief comum de
  correção diz depois de uma revisão, e recusar esses foi o primeiro erro deste classificador.

A linha `harness-role:` não é um sinal aqui: é uma linha isolada que a proteção de marcador já lê,
e reafirmá-la como texto solto recusaria prosa que apenas a cita.

Raízes de entrada são declaração, nunca um sinal: `_bmad/` nomeia o framework mas aparece em
qualquer brief sobre editá-lo. Elas viajam para dentro da recusa em vez disso, então a frase que
recusa um disparo também diz quais raízes o worker isolado precisa receber.

Um bloco opcional `install` carrega o resto do que um framework custa ao harness: onde os
templates de override vivem, onde são instalados, qual diretório diz que o framework está
presente, e onde suas skills declaram a superfície da qual esses templates dependem.
`harness integration check|apply <id>` o lê, então a CLI também não guarda nome de framework
nenhum, e a sondagem de presença do hook de sessão é o caminho `detect` do bloco em vez de um
literal no hook.

Um descritor que não vai parsear ou não vai validar não é imposição que silenciosamente parou: o
carregador guarda por que foi ignorado, e o hook de disparo diz isso uma vez por sessão.
"""
import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
DESCRIPTORS = ROOT / "policy" / "integrations"
SCHEMA_VERSION = 1
# Um brief é normalizado antes de ser pesquisado, e só sua cabeça é pesquisada: as próprias
# instruções do framework estão no topo de todo brief roteado, e um hook roda numa chamada de ferramenta.
CLASSIFY_MAX = 20000
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]*\Z")
# O que um sinal precisa ser antes de poder contribuir para uma recusa. Uma string curta ou de
# uma palavra é algo que um brief não relacionado diz por acidente, e o autor do descritor não
# descobre isso; o carregador descobre, aqui.
MIN_IDENTIFIER = (12, 1)
MIN_PHRASE = (24, 4)
_CACHE = []


def normalise(text):
    """Um brief reduzido ao que a variação de redação não consegue esconder: espaço, caixa e comprimento."""
    return " ".join(text.split()).casefold()[:CLASSIFY_MAX] if isinstance(text, str) else ""


def _too_slight(value, limits):
    characters, words = limits
    return len(value.strip()) < characters or len(value.split()) < words


def _signal_problems(where, spawn, roots):
    """O que há de errado com os sinais de uma entrada de disparo: forma, peso, e sobreposição com raízes de entrada."""
    found = []
    for field, limits in (("agents", (2, 1)), ("identifiers", MIN_IDENTIFIER), ("phrases", MIN_PHRASE)):
        values = spawn.get(field, [])
        if not isinstance(values, list) or not all(isinstance(v, str) and v.strip() for v in values):
            found.append(where + "." + field + " must be a list of non-empty strings")
            continue
        for value in values:
            if _too_slight(value, limits):
                found.append(where + "." + field + ": `" + value + "` is too slight to identify a "
                             "spawn; " + field + " need at least " + str(limits[0]) + " characters "
                             "and " + str(limits[1]) + " word(s)")
            if field == "identifiers" and any(_covers(root, value) for root in roots):
                found.append(where + ".identifiers: `" + value + "` is an input root or a bare "
                             "directory under one, which any brief about the framework quotes")
    if not spawn.get("phrases"):
        found.append(where + " declares no phrases: agents and identifiers alone cannot tell the "
                     "framework's own work from a brief that quotes one of its paths")
    return found


def _covers(root, value):
    """Se `value` é uma raiz de entrada, ou um diretório puro dentro de uma em vez de um arquivo nela."""
    root, value = root.strip().strip("/").casefold(), value.strip().strip("/").casefold()
    if not root or not value:
        return False
    if value == root or not (value.startswith(root + "/") or root.startswith(value + "/")):
        return value == root
    tail = value[len(root) + 1:] if value.startswith(root + "/") else ""
    return "." not in tail.rsplit("/", 1)[-1]


def problems(data, role_check=None):
    """Tudo o que há de errado com um descritor, como frases. Vazio significa que é utilizável.

    A validação vive aqui em vez de no manipulador de exceção do carregador para que os
    descritores embutidos possam ser conferidos por um teste, e para que o carregador possa dizer
    qual descritor ignorou e por quê.

    `role_check` responde se um papel é um que um worker isolado precisa rodar; por padrão é a
    própria resposta do ciclo de vida, porque um descritor que mapeia um disparo para um papel que
    a proteção de disparo não restringiria é um mapeamento que nunca pode recusar nada.
    """
    found = []
    if not isinstance(data, dict):
        return ["descriptor is not an object"]
    if data.get("schema_version") != SCHEMA_VERSION:
        found.append("schema_version must be " + str(SCHEMA_VERSION))
    for field in ("id", "name"):
        value = data.get(field)
        if not (isinstance(value, str) and value.strip()):
            found.append(field + " must be a non-empty string")
    if not IDENTIFIER.match(str(data.get("id", ""))):
        found.append("id must be lowercase, starting with a letter")
    version = data.get("version")
    if not (isinstance(version, dict) and isinstance(version.get("pinned"), str) and version["pinned"].strip()):
        found.append("version.pinned must name the framework release this descriptor was read from")
    roots = data.get("input_roots", [])
    if not (isinstance(roots, list) and all(isinstance(r, str) and r.strip() for r in roots)):
        found.append("input_roots must be a list of paths")
        roots = []
    corroboration = data.get("corroboration", 2)
    if not (isinstance(corroboration, int) and not isinstance(corroboration, bool) and corroboration >= 2):
        found.append("corroboration must be an integer of at least 2")
    if "install" in data:
        found += _install_problems(data["install"])
    spawns = data.get("spawns")
    if not (isinstance(spawns, list) and spawns):
        return found + ["spawns must be a non-empty list"]
    if role_check is None:
        role_check = _constrained
    for index, spawn in enumerate(spawns):
        where = "spawns[" + str(index) + "]"
        if not isinstance(spawn, dict):
            found.append(where + " is not an object")
            continue
        for field in ("id", "role"):
            if not IDENTIFIER.match(str(spawn.get(field, ""))):
                found.append(where + "." + field + " must be a lowercase identifier")
        if IDENTIFIER.match(str(spawn.get("role", ""))) and not role_check(spawn["role"]):
            found.append(where + ".role `" + spawn["role"] + "` is not a role an isolated worker "
                         "must run, so this mapping could never refuse anything")
        found += _signal_problems(where, spawn, roots)
    return found


INSTALL_STRINGS = ("detect", "templates", "destination", "suffix", "skill_surface")
# Os três que são resolvidos contra uma raiz de repositório ou contra este checkout. `apply`
# escreve sob um deles, então um caminho absoluto ou um segmento `..` num descritor é uma escrita
# fora do repositório que o operador nomeou, e o descritor é o lugar errado para descobrir isso.
INSTALL_PATHS = ("detect", "templates", "destination")


def _outside(value):
    """Se um caminho declarado sairia da raiz contra a qual é resolvido."""
    parts = PurePosixPath(value.strip()).parts
    return value.strip().startswith("/") or ".." in parts or (parts and parts[0].endswith(":"))


def _install_problems(install):
    """O que há de errado com o bloco opcional install que `harness integration check|apply` lê."""
    if not isinstance(install, dict):
        return ["install must be an object"]
    found = []
    for field in INSTALL_STRINGS:
        value = install.get(field)
        if not (isinstance(value, str) and value.strip()):
            found.append("install." + field + " must be a non-empty string")
        elif field in INSTALL_PATHS and _outside(value):
            found.append("install." + field + " must be a relative path inside the repository, "
                         "with no `..` segment")
    roots = install.get("skill_roots")
    if not (isinstance(roots, list) and roots
            and all(isinstance(r, str) and r.strip() for r in roots)):
        found.append("install.skill_roots must be a non-empty list of paths")
    elif [r for r in roots if _outside(r)]:
        found.append("install.skill_roots must all be relative paths inside the repository, "
                     "with no `..` segment")
    return found


def installable(name, directory=None):
    """O descritor `name`, ou None. Usado pela CLI, que também precisa do seu bloco install."""
    for data in descriptors(directory):
        if data["id"] == name:
            return data
    return None


def _constrained(role):
    """Se a proteção de disparo restringe `role` a um worker isolado. False quando não pode ser perguntado."""
    try:
        from . import lifecycle
        return lifecycle.constrained_role(role) is not None
    except Exception:
        return False


def _read(directory):
    """`(usable, ignored)` para um diretório. `ignored` é `(path, reason)` para tudo que foi pulado."""
    try:
        paths = sorted(directory.glob("*.json"))
        stats = [p.stat() for p in paths]
    except OSError:
        return [], [], ()
    signature = tuple((str(p), st.st_mtime_ns, st.st_size) for p, st in zip(paths, stats))
    usable, ignored = [], []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            ignored.append((path.name, type(exc).__name__ + ": " + str(exc)))
            continue
        found = problems(data)
        if found:
            ignored.append((path.name, found[0] if len(found) == 1
                            else found[0] + " (and " + str(len(found) - 1) + " more)"))
        else:
            usable.append(data)
    return usable, ignored, signature


def _loaded(directory=None):
    """O `(usable, ignored)` em cache para um diretório, relido quando os bytes de algum descritor mudam."""
    directory = Path(directory) if directory else DESCRIPTORS
    usable, ignored, signature = _read(directory)
    if _CACHE and _CACHE[0][0] == signature:
        return _CACHE[0][1]
    del _CACHE[:]
    _CACHE.append((signature, (usable, ignored)))
    return usable, ignored


def descriptors(directory=None):
    """Todo descritor utilizável. Um quebrado é deixado de fora, e `ignored` diz qual e por quê."""
    return _loaded(directory)[0]


def ignored(directory=None):
    """`(file, reason)` para todo descritor que o carregador não conseguiu usar."""
    return _loaded(directory)[1]


# O que uma frase diz, antes do arquivo, para adotá-lo como as próprias instruções do subagente,
# na forma base ou -ing que uma instrução assume. Um "follows" ou "applied" na terceira pessoa
# descreve, não direciona. Ele governa o arquivo só através de uma lacuna curta sem quebra de cláusula.
DIRECTIVE = re.compile(
    r"\b(?:follow(?:ing)?|apply(?:ing)?|obey(?:ing)?|adher(?:e|ing) to|comply(?:ing)? with"
    r"|abid(?:e|ing) by|carry(?:ing)? out|according to|as (?:instructed|directed|specified|"
    r"described|set out|laid out) (?:in|by)|per (?:the|those|these|its|that|this|their)\b"
    r"|your (?:\w+ ){0,2}(?:instructions|methodology|guidelines|checklist|rubric|procedure))\b")
LEAD_GAP = 6
CLAUSE_BREAK = re.compile(r"[,:()]|\b(?:and|then|but|or|while|after|before)\b")
# A diretiva depois do arquivo, mais adiante na mesma frase ou na próxima, que só conta quando
# aponta de volta para o arquivo: "read <path> and follow it", não "read <path> and use it as a
# fixture".
DIRECTIVE_BACK = re.compile(
    r"\b(?:(?:follow(?:ing)?|apply(?:ing)?|obey(?:ing)?) (?:it|them|that file|this file"
    r"|those instructions|these instructions|its instructions|the instructions)"
    r"|use (?:those|these|its|the) instructions|as (?:your |the )?(?:\w+ ){0,2}instructions)\b")
# Trabalho no arquivo em vez de trabalho sob ele, quando o verbo governa o arquivo como uma
# diretiva faria: "update <path>", ou "update it" depois dele. "Update your findings" edita outra
# coisa. Negado ("do not edit it") ainda é uma diretiva.
EDIT_VERB = (r"(?:edit(?:s|ed|ing)?|modif(?:y|ies|ied|ying)|updat(?:e|es|ed|ing)"
             r"|rewrit(?:e|es|ing|ten)|rewrote|renam(?:e|es|ed|ing)|delet(?:e|es|ed|ing)"
             r"|remov(?:e|es|ed|ing)|reword(?:s|ed|ing)?|refactor(?:s|ed|ing)?|lint(?:s|ed|ing)?"
             r"|amend(?:s|ed|ing)?)")
EDIT = re.compile(r"\b" + EDIT_VERB + r"\b")
EDIT_BACK = re.compile(r"\b" + EDIT_VERB + r" (?:it|them|that file|this file)\b")
NEGATION = re.compile(r"\b(?:not|never|no|without|don't|do not)\s+(?:\w+\s+){0,2}\Z")
SENTENCE = re.compile(r"(?<=[.!?;])\s+|\s+(?:—|–|-{2})\s+")


def _unnegated(pattern, text):
    """As correspondências de `pattern` em `text` não anuladas por um "not", "never" ou "without" antes."""
    return [found for found in pattern.finditer(text) if not NEGATION.search(text[:found.start()])]


def _governs(pattern, before):
    """Se um verbo de `pattern` termina perto o bastante antes do arquivo, sem quebra de cláusula, para governá-lo."""
    for found in _unnegated(pattern, before):
        gap = before[found.end():]
        if len(gap.split()) <= LEAD_GAP and not CLAUSE_BREAK.search(gap):
            return True
    return False


# Uma diretiva numa frase posterior ainda aponta de volta para o arquivo enquanto cada frase
# intermediária continua falando dele: "Read <path>. These instructions define the layer. Follow
# them precisely."
FOLLOW_REACH = 3
ANAPHOR = re.compile(r"\b(?:(?:these|those|its|the) instructions|(?:that|this|the) file)\b")
# Um "the instructions" no final seguido de onde elas vivem nomeia seu próprio arquivo, não este.
OWN_TARGET = re.compile(r"\s+(?:in|at|from|of|under|inside)\b")
# O caminho declarado termina onde um nome de arquivo mais longo continuaria: `<path>.bak` é outro arquivo.
PATH_END = r"(?![\w/-]|\.\w)"


def _points_back(after):
    """Se `after` contém uma diretiva não negada apontando de volta para o arquivo antes dela."""
    return any(not _names_its_own(found, after) for found in _unnegated(DIRECTIVE_BACK, after))


def _names_its_own(found, after):
    """Se um "follow the instructions" no final diz onde elas vivem, então não são as nossas."""
    said = found.group(0)
    return said.endswith("instructions") and not said.startswith("as ") and bool(
        OWN_TARGET.match(after, found.end()))


def _directed(value, text):
    """Se `text` instrui o subagente a seguir ou aplicar o arquivo nomeado `value`."""
    path = re.compile(re.escape(normalise(value)) + PATH_END)
    sentences = SENTENCE.split(text)
    for index, sentence in enumerate(sentences):
        if not path.search(sentence):
            continue
        parts = path.split(sentence)
        pairs = [(parts[at - 1], parts[at]) for at in range(1, len(parts))]
        if any(_governs(EDIT, before) or _unnegated(EDIT_BACK, after) for before, after in pairs):
            continue
        if any(_governs(DIRECTIVE, before) or _points_back(after) for before, after in pairs):
            return True
        for following in sentences[index + 1:index + 1 + FOLLOW_REACH]:
            if _points_back(following) and not _unnegated(EDIT_BACK, following):
                return True
            if not ANAPHOR.search(following):
                break
    return False


def _score(spawn, text, agent):
    """`(agents, directed, identifiers, phrases)` que esta entrada de disparo combinou."""
    agents = 1 if agent and agent in [a.casefold() for a in spawn.get("agents", [])] else 0
    named = [value for value in spawn.get("identifiers", []) if normalise(value) in text]
    directed = sum(1 for value in named if _directed(value, text))
    phrases = sum(1 for value in spawn.get("phrases", []) if normalise(value) in text)
    return agents, directed, len(named), phrases


def _recognised(score, corroboration):
    """Se esta quantidade de evidência recusa um disparo. A regra, num único lugar, para o único chamador."""
    agents, directed, identifiers, phrases = score
    if agents or directed:
        return True
    if identifiers and phrases:
        return True
    return phrases >= corroboration


def classify(prompt, subagent_type=None, directory=None, accept=None):
    """O disparo de framework que esta chamada é, ou None.

    `accept` filtra os papéis para os quais uma correspondência pode mapear, então um disparo que
    a proteção acabaria permitindo de qualquer forma não pode superar em pontuação um que ela
    recusaria. A entrada sobrevivente de maior pontuação vence, que é o que classifica um brief
    que carrega tanto a redação geral de revisão de um framework quanto sua redação específica de
    auditoria como a auditoria.
    """
    text = normalise(prompt)
    agent = subagent_type.strip().casefold() if isinstance(subagent_type, str) else ""
    best = None
    for data in descriptors(directory):
        for spawn in data["spawns"]:
            if accept is not None and not accept(spawn["role"]):
                continue
            score = _score(spawn, text, agent)
            if not _recognised(score, data.get("corroboration", 2)):
                continue
            if best is None or score > best[0]:
                best = (score, {"framework": data["id"], "framework_name": data["name"],
                                "spawn": spawn["id"], "role": spawn["role"],
                                "version": data["version"]["pinned"],
                                "input_roots": list(data.get("input_roots", []))})
    return best[1] if best else None


def origin(match):
    """As frases com as quais uma recusa abre: o que foi reconhecido, e do que o worker vai precisar."""
    said = ("This spawn carries the " + match["framework_name"] + " " + match["version"] + " `"
            + match["spawn"] + "` work, which this installation runs as the constrained `"
            + match["role"] + "` role whatever the spawn called itself.")
    roots = match.get("input_roots") or []
    if roots:
        said += (" The isolated worker needs the framework's input roots as read roots: "
                 + ", ".join(roots) + ".")
    return said
