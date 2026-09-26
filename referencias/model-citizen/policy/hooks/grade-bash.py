#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hook de PreToolUse: avalia todo comando Bash de 0 a 3 e restringe as notas que a stance de autonomia proíbe.

Por que um hook e não uma regra: "nunca faça force-push sem perguntar" é uma frase que o modelo
consegue ler e ainda assim pular, e o prompt de permissão nativo não consegue distinguir
`git push` de `git push --force` ou `terraform plan` de `terraform apply`. Um hook vê o comando
antes de rodar, em todo modo de permissão, e consegue colocar a consequência diante do usuário em
uma linha.

Comportamento:
  - Avalia o máximo entre os comandos simples em que a gramática somente leitura decompõe o
    comando: 0 somente leitura (`allow-readonly-bash.command_ok` prova isso), 1 escrita local, 2
    mutação remota, 3 irreversível. Um comando desconhecido recebe nota 1, nunca 3: uma nota
    baixa falsa é o prompt perdido que o nativo já dá hoje, e o corpus cresce a cada falha.
  - O texto é normalizado antes de qualquer outra coisa — continuações de barra invertida
    unidas, corpos de heredoc entre aspas e comentários removidos — para que um comentário `#`
    ou um here-document não consigam esconder o verbo ou quebrar o parse com uma aspa ou crase
    desbalanceada. Quando o texto ainda não parseia, o texto bruto é escaneado em busca de
    famílias de verbo de nota 3 em vez de receber nota 1: um comando que não parseia mas diz
    `--force` ou `rm -rf` é irreversível seja lá o que mais tenha.
  - `bash -c`, `sh -c`, `eval`, `xargs`, `find -exec` e corpos de substituição de comando recebem
    nota 3 quando seu texto interno carrega um verbo de nota 3, senão 1; o hook somente leitura
    os recusa todos de qualquer forma.
  - A stance de autonomia define o limiar: `execute` restringe a nota 3, `confirm-writes` a nota
    2 e acima, `ask` a nota 1 e acima. Abaixo do limiar o hook não imprime nada. A stance vem de
    `posture.py`; quando isso não consegue responder o hook avalia sob a variante mais estrita
    que conhece e diz que a seleção está sem resolução, porque adivinhar a permissiva
    descartaria um prompt que o usuário pediu.
  - No limiar ou acima, os modos com prompt recebem `ask` e os modos sem prompt recebem `deny`
    com o canal de confirmação na razão, porque segundo a referência de hooks do Claude Code, em
    `bypassPermissions` e no modo `auto` "a decisão 'ask' é ignorada", enquanto "um hook que
    retorna `permissionDecision: 'deny'` bloqueia a ferramenta mesmo no modo `bypassPermissions`
    ou com `--dangerously-skip-permissions`".
  - Em `bypassPermissions`, um comando prefixado com `HARNESS_CONFIRMED=1` é o canal de
    confirmação: o marcador é removido e o comando passa silenciosamente em qualquer nota. O
    marcador vai no início e confirma a linha de comando inteira, compostos incluídos, porque é
    esse o texto que foi mostrado ao usuário e ao qual ele disse sim; um marcador no meio não
    confirma nada.
  - No modo `auto` o classificador recusa esse marcador como uma tentativa de contornar este
    hook, então a negação nomeia um código de aprovação em vez disso (`approvals.py`): o usuário
    responde `approve <code>` como a mensagem inteira, e o mesmo comando, sem marcador, então
    passa uma vez naquela sessão dentro de trinta minutos. A aprovação é consumida aqui, no ponto
    em que o hook negaria. Um comando Bash que escreve no armazenamento de aprovações recebe nota
    3, para que o agente não consiga registrar uma aprovação própria.
  - Quando `governance.provider` nomeia um provedor de decisão diferente de `none`, um comando
    que a stance deixa passar também é submetido a ele (`govern`): cada comando simples é
    classificado como `coding.git_push`, `coding.git_commit`, `coding.pr_merge`,
    `coding.deploy` ou `coding.shell_exec`, sua contraparte é o repositório e branch do diretório
    em que roda (um `git -C <dir>` e um `cd <dir>` anterior o movem), e a resposta mais estrita
    entre os segmentos vale. O provedor só aperta: seu `ask` é emitido através da mesma divisão
    de modo e canal de aprovação do avaliador, e nunca é consultado sobre um comando que o
    avaliador já restringe. Um provedor configurado que levanta exceção pergunta, nomeando o
    erro, em vez de permitir, e uma escrita num arquivo de política de governança ou no
    `config.json` do usuário, ou um `harness config set governance...`, é sempre consultado,
    como uma ação de nível 1. Cada decisão é uma linha `governance` no log de decisão. Sob
    `none` nada é importado e a saída é exatamente a da stance.
  - Nunca levanta exceção: uma gramática irmã ausente e qualquer erro inesperado são uma saída
    silenciosa com 0, então uma falha aqui só pode custar um prompt que o nativo também não teria
    mostrado. A única coisa que não vai chutar é a stance, acima.

Teste: echo '{"tool_name":"Bash","tool_input":{"command":"git push --force origin main"}}' | python3 grade-bash.py
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HOOK = "grade-bash hook"
MARKER = "HARNESS_CONFIRMED=1"
DEFAULT_STANCE = "execute"
THRESHOLDS = {"execute": 3, "confirm-writes": 2, "ask": 1}
# What to grade under when the stance cannot be resolved: the variant that gates the most.
STRICTEST = min(THRESHOLDS, key=THRESHOLDS.get)
DENY_MODES = {"auto", "bypassPermissions"}
DENY_TAIL = (" Nothing can prompt in this permission mode, so the command was refused rather than"
             " asked about. Say in chat what it would change and why that is hard to undo; if the"
             " user says yes, run the same command again with " + MARKER + " in front of it.")
LABELS = {1: "local write", 2: "remote-mutating", 3: "irreversible"}
# O rótulo acima é para um log; este é o mesmo fato para quem estiver lendo o prompt.
PLAIN = {1: "this changes files on this machine",
         2: "this changes something other people can see",
         3: "this cannot be undone"}
PLACEHOLDER = "__GRADESUB__"
MAX_DEPTH = 4


def _sibling(name, alias):
    """Um módulo ao lado deste hook, ou None: um irmão quebrado deixa o hook silencioso, nunca travando."""
    try:
        spec = importlib.util.spec_from_file_location(alias, Path(__file__).resolve().with_name(name))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


ro = _sibling("allow-readonly-bash.py", "grade_bash_readonly")
approvals = _sibling("approvals.py", "grade_bash_approvals")
APPROVAL_TAIL = (" Nothing can prompt in this permission mode, so the command was refused rather than"
                 " asked about. Stop, say in chat what it would change and why that is hard to undo,"
                 " and ask the user, if they agree, to reply with exactly `approve %s` as the whole"
                 " message, since any other text in it records nothing. After that reply, run exactly"
                 " the same command again with no marker: the approval covers this command once, in"
                 " this session, for thirty minutes.")

# Uma cláusula de consequência por família de verbo, mais um fallback genérico por nota. A
# cláusula é o preview inteiro: a linha de razão é verbo, alvo, cláusula.
CLAUSES = {
    "git-history": "rewrites remote history",
    "git-discard": "discards local work with no undo",
    "merge": "merges into the shared branch",
    "delete": "deletes data that cannot be restored",
    "archive": "locks the repository read-only for everyone",
    "rename": ("moves the repository to a new name, and the old URLs redirect only while no"
               " repository takes the old name"),
    "database": "drops data that cannot be restored",
    "migration": "changes a database schema in place",
    "infra": "changes live infrastructure",
    "deploy": "ships to a live environment",
    "cluster": "changes a live cluster",
    "publish": "publishes a release that cannot be withdrawn",
    "system": "changes this machine outside the project",
    "opaque": "runs text this hook cannot inspect",
    "remote": "changes shared state",
    "remote-delete": "deletes a remote resource",
    "approvals": "records an approval only the user may give",
}
GENERIC = {1: "writes to the working tree", 2: "changes shared state", 3: "cannot be undone"}

MARKER_RE = re.compile(r"^\s*(env\s+)?" + MARKER + r"\s*;?\s*")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
DASH_C_RE = re.compile(r"^-[A-Za-z]*c$")
# Wrappers que rodam o comando em seus argumentos restantes, com as letras de opção que levam
# um valor próprio, para que `nice -n 10 git push --force` seja avaliado como o push.
WRAPPERS = {
    "timeout": ("-k", "--kill-after", "-s", "--signal"),
    "time": (),
    "nice": ("-n", "--adjustment"),
    "nohup": (),
    "stdbuf": ("-i", "-o", "-e", "--input", "--output", "--error"),
    "command": (),
    "exec": (),
    "noglob": (),
    "env": ("-u", "--unset", "--chdir", "-C"),
    "npx": ("--package", "-p"),
    "uvx": ("--from", "-p"),
}
# Runners que executam o resto da linha num ambiente gerenciado, como `npx`.
RUNNERS = {("bundle", "exec"), ("poetry", "run"), ("uv", "run"), ("pipx", "run"),
           ("pnpm", "dlx"), ("pnpm", "exec"), ("yarn", "dlx"), ("yarn", "exec"),
           ("npm", "exec"), ("rye", "run"), ("hatch", "run")}
SUDO = {"sudo": ("-u", "-g", "-U", "--user", "--group", "-p", "--prompt"),
        "doas": ("-u", "-C"),
        "su": ("-c", "-s", "--shell", "--command")}
SHELLS = {"bash", "sh", "zsh", "ksh", "dash"}
GIT_VALUE_GLOBALS = ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
                     "--config-env")
XARGS_VALUE_FLAGS = ("-I", "-i", "-n", "-P", "-L", "-s", "-d", "-a", "-E", "-e", "--replace",
                     "--max-args", "--max-procs", "--max-lines", "--delimiter", "--arg-file")
TEMP_ROOTS = ["/tmp/", "/private/tmp/", "/var/folders/", "/private/var/folders/"]
DOCKER_EXEC_VALUE_FLAGS = ("-e", "--env", "-u", "--user", "-w", "--workdir",
                           "--index", "--env-file")
SSH_VALUE_FLAGS = ("-p", "-i", "-l", "-o", "-F", "-L", "-R", "-D", "-b", "-c", "-E", "-J", "-W")
SCAN_CAP = 16384
SQL_RE = re.compile(
    r"\b(DROP\s+(?:TABLE|DATABASE|SCHEMA|INDEX|VIEW|ROLE|USER)|TRUNCATE(?:\s+TABLE)?|"
    r"DELETE\s+FROM)\s+(?:IF\s+EXISTS\s+)?([`\"\w.]+)", re.I)
ALTER_DROP_RE = re.compile(r"\bALTER\s+TABLE\s+([`\"\w.]+)[\s\S]{0,200}?\bDROP\b", re.I)
MONGO_RE = re.compile(r"\bdb(?:\.\w+)*\.(dropDatabase|drop|deleteMany|remove)\s*\(")
SQL_CLIENTS = {"psql", "mysql", "mariadb", "sqlite3", "mongosh", "mongo", "clickhouse-client"}
CLOUD = {"aws", "gcloud", "az", "doctl", "flyctl"}
CLOUD_G3 = {"delete", "terminate", "destroy", "purge", "remove"}
CLOUD_G2 = {"create", "put", "update", "start", "stop", "attach", "detach", "tag", "modify",
            "associate", "deploy", "set", "cp", "mv", "sync", "upload"}
HTTP_LONG_BODY = ("--data", "--form", "--upload-file", "--post-data", "--post-file",
                  "--body-data", "--body-file", "--json")
HTTP_BODY_LETTERS = "dFT"
HTTP_G2_METHODS = {"POST", "PUT", "PATCH"}
HTTP_G3_METHOD = "DELETE"
GH_G2_NOUNS = {"pr", "issue", "release", "repo"}
GH_G2_VERBS = {"create", "edit", "comment", "close", "reopen", "ready", "review", "merge"}
PUBLISH = {"npm": "publish", "pnpm": "publish", "yarn": "publish", "cargo": "publish",
           "twine": "upload", "gem": "push", "poetry": "publish"}

# Último recurso quando o texto não parseia: uma família de verbo de nota 3 em qualquer lugar
# nele é uma nota 3. Agulhas de substring, não regexes: o texto pode ser grande, e toda checagem
# aqui precisa continuar linear. Um chunk é uma sequência sem separador, então as agulhas de uma
# entrada precisam coocorrer num único comando.
SCAN = [
    (("force-with-lease",), "git push --force-with-lease", "git-history"),
    (("push", "--force"), "git push --force", "git-history"),
    (("push", "--mirror"), "git push --mirror", "git-history"),
    (("push", "--delete"), "git push --delete", "git-history"),
    (("push", " -f"), "git push -f", "git-history"),
    (("reset", "--hard"), "git reset --hard", "git-discard"),
    (("clean", " -f"), "git clean -f", "git-discard"),
    (("clean", "--force"), "git clean -f", "git-discard"),
    (("filter-branch",), "git filter-branch", "git-history"),
    (("filter-repo",), "git filter-repo", "git-history"),
    (("rm ", "-rf"), "rm -rf", "delete"),
    (("rm ", "-fr"), "rm -rf", "delete"),
    (("rm ", "-r "), "rm -r", "delete"),
    (("rm ", "-f "), "rm -f", "delete"),
    (("drop table",), "DROP TABLE", "database"),
    (("drop database",), "DROP DATABASE", "database"),
    (("drop schema",), "DROP SCHEMA", "database"),
    (("truncate ",), "TRUNCATE", "database"),
    (("delete from",), "DELETE FROM", "database"),
    (("dropdatabase",), "db.dropDatabase()", "database"),
    (("flushall",), "redis-cli FLUSHALL", "database"),
    (("terraform", "destroy"), "terraform destroy", "infra"),
    (("terraform", "apply"), "terraform apply", "infra"),
    (("pulumi", "destroy"), "pulumi destroy", "infra"),
    (("kubectl", "delete"), "kubectl delete", "cluster"),
    (("sudo ",), "sudo", "system"),
    (("doas ",), "doas", "system"),
    (("mkfs",), "mkfs", "system"),
    (("shutdown",), "shutdown", "system"),
    (("reboot",), "reboot", "system"),
    (("dd if=",), "dd", "system"),
]
SCAN_SPLIT = re.compile(r"[\n;&|]+")


def stance():
    """A variante de autonomia sob a qual avaliar, e o rótulo que o aviso carrega.

    Resolvida por `posture.py`, então um único arquivo responde por todo hook. Este restringe
    comandos, então falha fechado: um resolvedor que não pode ser carregado ou não consegue
    responder significa a variante mais estrita que o hook conhece, não o padrão permissivo, e
    o aviso diz que a seleção está sem resolução para que o usuário veja por que um comando
    familiar de repente pergunta."""
    module = _sibling("posture.py", "harness_posture")
    try:
        if module is None:
            raise ImportError("posture.py is not beside this hook")
        variant = module.selected("autonomy", DEFAULT_STANCE)
    except Exception:
        return STRICTEST, STRICTEST + ", unresolved: the stance resolver did not answer"
    return variant, variant


def emit(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}))


def strip_marker(cmd):
    """(comando sem um marcador de confirmação inicial, marcador visto)."""
    stripped = MARKER_RE.sub("", cmd, count=1)
    return stripped, stripped != cmd


def _split_heredocs(text):
    """Texto sem o corpo de todo here-document. Um corpo é dado: o shell expande uma variável
    num sem aspas mas nunca roda suas linhas, e um corpo entre aspas nem sequer é expandido. Os
    corpos saem antes de as continuações serem unidas, para que uma linha de corpo terminando em
    barra invertida não consiga engolir o delimitador."""
    lines = text.split("\n")
    out, bodies = [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        match = HEREDOC_RE.search(line)
        i += 1
        if not match:
            continue
        delimiter, body = match.group(2), []
        while i < len(lines) and lines[i].strip() != delimiter:
            body.append(lines[i])
            i += 1
        if i < len(lines):
            out.append(lines[i])
            i += 1
        bodies.append("\n".join(body))
    return "\n".join(out), bodies


def _strip_comments(text):
    """Texto sem seus comentários `#`, com o estado de aspas carregado através de quebras de
    linha, para que um `#` dentro de uma string entre aspas de várias linhas permaneça e um
    comentário fora de uma tome o resto da sua linha."""
    out = []
    sq = dq = False
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if sq:
            sq = c != "'"
        elif dq:
            if c == "\\":
                out.append(text[i:i + 2])
                i += 2
                continue
            dq = c != '"'
        elif c == "\\":
            out.append(text[i:i + 2])
            i += 2
            continue
        elif c == "'":
            sq = True
        elif c == '"':
            dq = True
        elif c == "#" and (i == 0 or text[i - 1] in " \t\n;|&()"):
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def normalize(cmd):
    """(texto shell, corpos de here-document). Os corpos saem primeiro, depois as continuações
    são unidas, depois os comentários são removidos, para que nada consiga esconder um verbo
    atrás de um `#`, dentro de um corpo, ou atrás de uma continuação de linha. Um corpo é dado
    para o shell; só um cliente que o interpreta — um cliente SQL — é avaliado pelo seu conteúdo."""
    text = cmd.replace("\r\n", "\n").replace("\r", "\n")
    text, bodies = _split_heredocs(text)
    text = re.sub(r"\\\n", " ", text)
    return _strip_comments(text), bodies


def _scan(text):
    """O fallback para texto que este hook não consegue decompor: uma família de verbo de nota 3
    em qualquer um dos seus chunks sem separador, ou nota 1. Linear no comprimento do texto, e o
    texto que lê é limitado, porque um hook que ultrapassa seu timeout falha aberto."""
    if len(text) > SCAN_CAP:
        return 3, "command too long to grade", "", "opaque"
    for chunk in SCAN_SPLIT.split(text.lower()):
        for needles, verb, family in SCAN:
            if all(needle in chunk for needle in needles):
                return 3, verb, "", family
    return 1, "", "", "opaque"


def _extract_subs(cmd):
    """(texto com toda substituição substituída por um placeholder, os textos internos). O texto
    é None quando uma substituição nunca fecha."""
    out, inners = [], []
    i, n = 0, len(cmd)
    sq = dq = False
    while i < n:
        c = cmd[i]
        if sq:
            out.append(c)
            if c == "'":
                sq = False
            i += 1
            continue
        if c == "'" and not dq:
            sq = True
            out.append(c)
            i += 1
            continue
        if c == '"':
            dq = not dq
            out.append(c)
            i += 1
            continue
        if c == "\\":
            out.append(cmd[i:i + 2])
            i += 2
            continue
        if c == "`":
            j = i + 1
            while j < n and cmd[j] != "`":
                j += 2 if cmd[j] == "\\" else 1
            if j >= n:
                return None, inners
            inners.append(cmd[i + 1:j])
            out.append(PLACEHOLDER)
            i = j + 1
            continue
        if cmd.startswith("$(", i):
            end = ro._match_paren(cmd, i + 1)
            if end is None:
                return None, inners
            inner = cmd[i + 2:end]
            if not inner.startswith("("):  # `$(( ))` é aritmética, não um comando
                inners.append(inner)
            out.append(PLACEHOLDER)
            i = end + 1
            continue
        if c in "<>" and not dq and cmd.startswith("(", i + 1):
            end = ro._match_paren(cmd, i + 1)
            if end is None:
                return None, inners
            inners.append(cmd[i + 2:end])
            out.append(PLACEHOLDER)
            i = end + 1
            continue
        out.append(c)
        i += 1
    return "".join(out), inners


def segments(text):
    """Os comandos simples em `text`, pela própria decomposição da gramática somente leitura:
    quebras de linha como separadores, palavras reservadas estruturais só em posição de comando.
    None quando não tokeniza."""
    text = " ; ".join(text.split("\n"))
    try:
        tokens = ro.tokenize(text)
    except ValueError:
        return None
    out, cur, skipping = [], [], False
    for token in tokens:
        if token in ro.ALWAYS_DELIM:
            if cur:
                out.append(cur)
            cur, skipping = [], False
            continue
        if skipping:
            continue
        if not cur:
            if token in ro.WORD_DROP or token in ro.WORD_COND or token == "!":
                continue
            if token in ro.WORD_HEADER:  # `for x in *` nomeia dados, não comandos
                skipping = True
                continue
        cur.append(token)
    if cur:
        out.append(cur)
    return out


def _redirects(tokens):
    """(tokens sem redirecionamentos, os alvos em que escrevem)."""
    clean, targets = [], []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if ro.PUNCTUATION_RUN.match(token):
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            if ro.WRITE_REDIRECTS.match(token):
                targets.append(target)
            i += 2
            continue
        clean.append(token)
        i += 1
    return clean, targets


def operands(args):
    out, done = [], False
    for a in args:
        if a == "--" and not done:
            done = True
        elif done or not a.startswith("-"):
            out.append(a)
    return out


def has(args, *names):
    return any(a == n or a.startswith(n + "=") for a in args for n in names)


def short(args, letters):
    """True quando um agrupamento de opções curtas carrega qualquer uma de `letters`, então `-fu` lê como `-f`."""
    for a in args:
        if a.startswith("-") and not a.startswith("--") and any(c in letters for c in a[1:]):
            return True
    return False


def strip_options(args, value_flags):
    """Argumentos além das próprias opções de um wrapper, com o valor de cada opção que leva um."""
    i = 0
    while i < len(args):
        a = args[i]
        if not a.startswith("-") or a == "-":
            break
        if a in value_flags:
            i += 2
            continue
        i += 1
    return args[i:]


def _joined(args, limit=2):
    return " ".join(operands(args)[:limit])


def _rm_flagged(tokens):
    """True quando `tokens` é um `rm` carregando uma flag recursiva ou de força."""
    return bool(tokens) and tokens[0].rpartition("/")[2] == "rm" and (
        short(tokens[1:], "rRf") or has(tokens[1:], "--recursive", "--force"))


def _inner(text, cwd, depth):
    """Um corpo que este hook não consegue modelar como um comando: nota 3 quando carrega um verbo de nota 3."""
    grade, verb, target, family = grade_text(text, cwd, depth + 1)
    if grade == 3:
        return 3, verb, target, family
    return 1, None, None, None


def _inner_tokens(tokens, cwd, depth):
    if not tokens:
        return 1, None, None, None
    if depth >= MAX_DEPTH:
        return _scan(" ".join(tokens))
    grade, verb, target, family = grade_tokens(tokens, cwd, depth + 1)
    if grade == 3:
        return 3, verb, target, family
    return 1, None, None, None


def _git(args, cwd):
    i = 0
    while i < len(args):
        a = args[i]
        if a in GIT_VALUE_GLOBALS and i + 1 < len(args):
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        break
    rest = args[i:]
    if not rest:
        return 1, "git", "", None
    sub, sargs = rest[0], rest[1:]
    ops = operands(sargs)
    dry_run = has(sargs, "--dry-run") or short(sargs, "n")
    if sub == "push":
        if dry_run:
            return 1, "git push --dry-run", " ".join(ops), None
        if has(sargs, "--force-with-lease"):
            return 3, "git push --force-with-lease", " ".join(ops), "git-history"
        if has(sargs, "--force") or has(sargs, "--mirror") or short(sargs, "f"):
            verb = "git push --force" if has(sargs, "--force") else (
                "git push --mirror" if has(sargs, "--mirror") else "git push -f")
            return 3, verb, " ".join(ops), "git-history"
        if has(sargs, "--delete") or short(sargs, "d") or any(o.startswith(":") for o in ops):
            return 3, "git push --delete", " ".join(ops), "git-history"
        if any(o.startswith("+") for o in ops):
            return 3, "git push", " ".join(ops), "git-history"
        return 2, "git push", " ".join(ops), "remote"
    if sub == "reset" and has(sargs, "--hard"):
        return 3, "git reset --hard", _joined(sargs, 1), "git-discard"
    if sub == "clean" and (has(sargs, "--force") or short(sargs, "f")) and not dry_run:
        return 3, "git clean -f", _joined(sargs, 1), "git-discard"
    if sub == "checkout":
        if "--" in sargs:
            return 3, "git checkout --", _joined(sargs, 1), "git-discard"
        if has(sargs, "--force") or short(sargs, "f"):
            return 3, "git checkout -f", _joined(sargs, 1), "git-discard"
        if ops[:1] in (["."], ["./"]):
            return 3, "git checkout", ops[0], "git-discard"
    if sub == "switch" and (has(sargs, "--discard-changes", "--force") or short(sargs, "f")):
        return 3, "git switch --discard-changes", _joined(sargs, 1), "git-discard"
    if sub == "restore" and not (has(sargs, "--staged") or short(sargs, "S")):
        return 3, "git restore", _joined(sargs, 1), "git-discard"
    if sub == "branch" and (has(sargs, "-D", "--delete") or short(sargs, "D")):
        return 3, "git branch -D", _joined(sargs, 1), "git-discard"
    if sub == "stash" and ops and ops[0] in ("drop", "clear"):
        return 3, "git stash " + ops[0], " ".join(ops[1:2]), "git-discard"
    if sub == "reflog" and ops and ops[0] in ("expire", "delete"):
        return 3, "git reflog " + ops[0], " ".join(ops[1:2]), "git-history"
    if sub in ("filter-branch", "filter-repo"):
        return 3, "git " + sub, _joined(sargs, 1), "git-history"
    return 1, "git " + sub, _joined(sargs, 1), None


def _gh(args):
    ops = operands(args)
    noun = ops[0] if ops else ""
    verb = ops[1] if len(ops) > 1 else ""
    if (noun, verb) in (("repo", "delete"), ("release", "delete"), ("gist", "delete")):
        return 3, "gh %s %s" % (noun, verb), " ".join(ops[2:3]), "delete"
    if (noun, verb) == ("repo", "archive"):
        return 3, "gh repo archive", " ".join(ops[2:3]), "archive"
    if (noun, verb) == ("repo", "rename"):
        return 3, "gh repo rename", " ".join(ops[2:3]), "rename"
    if (noun, verb) == ("pr", "merge"):
        return 2, "gh pr merge", " ".join(ops[2:3]), "merge"
    if noun == "api":
        method = ""
        for i, a in enumerate(args):
            if a in ("-X", "--method") and i + 1 < len(args):
                method = args[i + 1].upper()
            elif a.startswith("--method="):
                method = a.split("=", 1)[1].upper()
        path = " ".join([o for o in ops[1:] if o != method][:1])
        if method == HTTP_G3_METHOD:
            return 3, "gh api DELETE", path, "remote-delete"
        if method not in ("", "GET", "HEAD") or has(args, "-f", "-F", "--input", "--field",
                                                    "--raw-field"):
            return 2, "gh api " + (method or "POST"), path, "remote"
        return 1, "gh api", path, None
    if noun in GH_G2_NOUNS and verb in GH_G2_VERBS:
        return 2, "gh %s %s" % (noun, verb), " ".join(ops[2:3]), "remote"
    return 1, "gh " + noun, verb, None


def _http(prog, args):
    method, body = "", False
    for i, a in enumerate(args):
        if a in ("-X", "--request", "--method") and i + 1 < len(args):
            method = args[i + 1].upper()
        elif a.startswith(("--request=", "--method=")):
            method = a.split("=", 1)[1].upper()
        elif a.startswith("--"):
            if any(a.startswith(f) for f in HTTP_LONG_BODY):
                body = True
        elif a.startswith("-") and len(a) > 1:
            cluster = a[1:]
            if cluster.endswith("X") and i + 1 < len(args):
                method = args[i + 1].upper()
            elif "X" in cluster:
                method = cluster.split("X", 1)[1].upper()
            if any(c in HTTP_BODY_LETTERS for c in cluster):
                body = True
    ops = operands(args)
    if prog in ("http", "https", "httpie") and ops:
        verb = ops[0].upper()
        if verb == HTTP_G3_METHOD:
            return 3, "%s DELETE" % prog, " ".join(ops[1:2]), "remote-delete"
        if verb in HTTP_G2_METHODS:
            return 2, "%s %s" % (prog, verb), " ".join(ops[1:2]), "remote"
    url = " ".join([o for o in ops if o != method][:1])
    if method == HTTP_G3_METHOD:
        return 3, "%s DELETE" % prog, url, "remote-delete"
    if method in HTTP_G2_METHODS or body:
        return 2, "%s %s" % (prog, method or "with a request body"), url, "remote"
    return 1, prog, url, None


def _cloud(prog, args):
    ops = operands(args)
    for i, op in enumerate(ops):
        head = op.split("-")[0].lower()
        if op.lower() in CLOUD_G3 or head in CLOUD_G3:
            return 3, "%s %s" % (prog, " ".join(ops[:i + 1])), " ".join(ops[i + 1:i + 2]), "infra"
    if prog == "aws" and ops[:1] == ["s3"]:
        if len(ops) > 1 and ops[1] in ("rm", "rb"):
            return 3, "aws s3 " + ops[1], " ".join(ops[2:3]), "delete"
        if len(ops) > 1 and ops[1] == "sync" and has(args, "--delete"):
            return 3, "aws s3 sync --delete", " ".join(ops[2:4]), "delete"
    for i, op in enumerate(ops):
        head = op.split("-")[0].lower()
        if op.lower() in CLOUD_G2 or head in CLOUD_G2:
            return 2, "%s %s" % (prog, " ".join(ops[:i + 1])), " ".join(ops[i + 1:i + 2]), "remote"
    return 1, prog, " ".join(ops[:2]), None


def _sql(text):
    match = SQL_RE.search(text)
    if match:
        verb = re.sub(r"\s+", " ", match.group(1)).upper()
        return 3, verb, match.group(2).strip("`\""), "database"
    match = ALTER_DROP_RE.search(text)
    if match:
        return 3, "ALTER TABLE DROP", match.group(1).strip("`\""), "database"
    match = MONGO_RE.search(text)
    if match:
        return 3, "db.%s()" % match.group(1), "", "database"
    return None


def _expand(op):
    """The operand with `~`, `$HOME` and `$TMPDIR` expanded and `.`/`..` segments resolved, so
    `/tmp/../etc` is judged as `/etc` and `$HOME` as the home directory."""
    text = op.replace("${HOME}", "$HOME").replace("${TMPDIR}", "$TMPDIR")
    text = text.replace("$HOME", os.path.expanduser("~"))
    text = text.replace("$TMPDIR", (os.environ.get("TMPDIR") or "/tmp").rstrip("/"))
    if text.startswith("~"):
        text = os.path.expanduser(text)
    return os.path.normpath(text) if text else text


def _rm_risky(op, cwd):
    """True when deleting `op` recursively reaches outside the working tree, or takes the whole
    working tree, the repository metadata or a wildcard with it."""
    if "*" in op:
        return True
    path = _expand(op)
    if not path or path == "/":
        return True
    if path == ".git" or path.endswith("/.git"):
        return True
    if path.startswith("/"):
        temp_roots = list(TEMP_ROOTS)
        tmpdir = os.environ.get("TMPDIR")
        if tmpdir:
            temp_roots.append(tmpdir.rstrip("/") + "/")
        if any(path.startswith(root) for root in temp_roots):
            return False  # the system temp directories are outside cwd by design
        root = os.path.normpath(cwd) if cwd else ""
        return not (root and (path == root or path.startswith(root + "/")))
    return path == "." or path == ".." or path.startswith("../")


def _rm(args, cwd):
    if not (short(args, "rRf") or has(args, "--recursive", "--force")):
        return 1, "rm", _joined(args, 1), None
    verb = "rm -rf" if short(args, "rR") or has(args, "--recursive") else "rm -f"
    for op in operands(args):
        if _rm_risky(op, cwd):
            return 3, verb, op, "delete"
    return 1, verb, _joined(args, 1), None


G3_SUBCOMMANDS = {
    "terraform": ({"apply", "destroy"}, "infra"),
    "tofu": ({"apply", "destroy"}, "infra"),
    "pulumi": ({"up", "destroy"}, "infra"),
    "cdk": ({"deploy", "destroy"}, "infra"),
    "sam": ({"deploy"}, "deploy"),
    "serverless": ({"deploy", "remove"}, "deploy"),
    "sls": ({"deploy", "remove"}, "deploy"),
    "fly": ({"deploy"}, "deploy"),
    "railway": ({"up"}, "deploy"),
    "alembic": ({"upgrade", "downgrade"}, "migration"),
    "flyway": ({"migrate", "clean"}, "migration"),
    "goose": ({"up", "down"}, "migration"),
    "helm": ({"uninstall", "delete"}, "cluster"),
}
G2_SUBCOMMANDS = {
    "kubectl": ({"apply", "create", "patch", "scale", "rollout", "label", "annotate"}, "cluster"),
    "helm": ({"install", "upgrade"}, "cluster"),
    "docker": ({"push"}, "publish"),
}
RAILS_G3 = re.compile(r"^db:(migrate|drop|reset|schema:load|rollback)$")


def grade_tokens(tokens, cwd, depth):
    """(nota, verbo, alvo, família) para um comando simples."""
    tokens, written = _redirects(tokens)
    wrote = ""
    for target in written:
        if re.match(r"^/dev/(sd|disk|nvme|rdisk)", target):
            return 3, "redirect to", target, "system"
        if target and not target.isdigit() and target != "/dev/null":
            wrote = target
    while tokens and ASSIGN_RE.match(tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return 0, None, None, None
    if ro.segment_ok(list(tokens)):
        return (1, "redirect to", wrote, None) if wrote else (0, None, None, None)
    head = tokens[0]
    prog = head.rpartition("/")[2]
    args = tokens[1:]
    ops = operands(args)
    text = " ".join(tokens)

    if PLACEHOLDER in head or head.startswith("$"):
        return _scan(text)  # o programa vem de uma substituição ou uma variável
    if (prog, ops[0] if ops else "") in RUNNERS:
        rest = args[args.index(ops[0]) + 1:]
        while rest and (rest[0].startswith("-") or ASSIGN_RE.match(rest[0])):
            rest = rest[1:]
        if rest:
            return grade_tokens(rest, cwd, depth)
    if prog == "cargo" and ops[:1] == ["run"] and "--" in args:
        rest = args[args.index("--") + 1:]
        if rest:
            return grade_tokens(rest, cwd, depth)
    if prog == "ssh":
        rest = strip_options(args, SSH_VALUE_FLAGS)
        if len(rest) > 1:  # o primeiro operando é o host; o resto roda nele
            return _inner(" ".join(rest[1:]), cwd, depth)
    if prog == "kubectl" and ops[:1] == ["exec"] and "--" in args:
        return _inner_tokens(args[args.index("--") + 1:], cwd, depth)
    if prog in ("docker", "docker-compose") and "exec" in args:
        rest = strip_options(args[args.index("exec") + 1:], DOCKER_EXEC_VALUE_FLAGS)
        if len(rest) > 1:  # o primeiro operando é o container ou o serviço
            return _inner_tokens(rest[1:], cwd, depth)
    if prog in ("fly", "flyctl") and ops[:2] == ["ssh", "console"]:
        for i, a in enumerate(args):
            if a in ("-C", "--command") and i + 1 < len(args):
                return _inner(args[i + 1], cwd, depth)
    if prog in SUDO:
        rest = strip_options(args, SUDO[prog])
        return 3, prog, " ".join(rest[:2]) or _joined(args, 1), "system"
    if prog in SHELLS:
        for i, a in enumerate(args):
            if DASH_C_RE.match(a) and i + 1 < len(args):
                return _inner(args[i + 1], cwd, depth)
    if prog in ("eval",):
        return _inner(" ".join(args), cwd, depth)
    if prog in ("xargs", "parallel"):
        rest = strip_options(args, XARGS_VALUE_FLAGS)
        if _rm_flagged(rest):  # os operandos chegam pelo stdin, então qualquer rm -rf aqui é nota 3
            return 3, "xargs rm -rf", "", "delete"
        return _inner_tokens(rest, cwd, depth)
    if prog in WRAPPERS:
        rest = strip_options(args, WRAPPERS[prog])
        while rest and ASSIGN_RE.match(rest[0]):
            rest = rest[1:]
        if prog == "timeout" and rest:
            rest = rest[1:]  # a duração
        if rest:
            return grade_tokens(rest, cwd, depth)
        return 1, prog, "", None
    if prog == "git":
        return _git(args, cwd)
    if prog == "gh":
        return _gh(args)
    if prog in ("curl", "wget", "http", "https", "httpie"):
        return _http(prog, args)
    if prog in CLOUD:
        return _cloud(prog, args)
    if prog == "rm":
        return _rm(args, cwd)
    if prog == "find":
        if "-delete" in args:
            return 3, "find -delete", _joined(args, 1), "delete"
        for flag in ("-exec", "-execdir", "-ok", "-okdir"):
            if flag in args:
                inner = args[args.index(flag) + 1:]
                inner = [t for t in inner if t not in (";", "+", "\\;", "{}")]
                if _rm_flagged(inner):
                    return 3, "find " + flag + " rm -rf", _joined(args, 1), "delete"
                return _inner_tokens(inner, cwd, depth)
    if prog in SQL_CLIENTS:
        hit = _sql(text)
        if hit:
            return hit
        return 1, prog, _joined(args, 1), None
    if prog == "redis-cli":
        for op in ops:
            if op.upper() in ("FLUSHALL", "FLUSHDB"):
                return 3, "redis-cli " + op.upper(), "", "database"
    if SQL_RE.match(text) or ALTER_DROP_RE.match(text):  # um corpo de heredoc, no seu próprio segmento
        return _sql(text)
    if prog == "prisma" or (prog in ("npm", "pnpm", "yarn") and ops[:1] == ["prisma"]):
        rest = ops[1:] if prog != "prisma" else ops
        joined = " ".join(rest[:2])
        if joined in ("migrate deploy", "migrate reset", "db push"):
            return 3, "prisma " + joined, "", "migration"
    if prog in PUBLISH and ops[:1] == [PUBLISH[prog]]:
        return 2, "%s %s" % (prog, PUBLISH[prog]), " ".join(ops[1:2]), "publish"
    if prog in ("rails", "rake", "bin/rails") or ops[:1] == ["rails"]:
        for op in ops:
            if RAILS_G3.match(op):
                return 3, "rails " + op, "", "migration"
    if prog in ("manage.py", "./manage.py") or "manage.py" in ops:
        for op in ops:
            if op in ("migrate", "flush", "sqlflush", "reset_db"):
                return 3, "manage.py " + op, "", "migration"
    if prog == "dbmate" and ops:
        return 3, "dbmate " + ops[0], "", "migration"
    if prog in ("docker", "docker-compose"):
        compose = ops[:2] == ["compose", "down"] or (prog == "docker-compose" and ops[:1] == ["down"])
        if compose and (has(args, "--volumes") or short(args, "v")):
            return 3, "docker compose down -v", "", "delete"
        if ops[:2] == ["system", "prune"] or ops[:2] == ["volume", "prune"]:
            return 3, "docker " + " ".join(ops[:2]), "", "delete"
        if ops[:1] in (["rm"], ["rmi"]) and short(args, "f"):
            return 3, "docker %s -f" % ops[0], " ".join(ops[1:2]), "delete"
    if prog == "kubectl":
        if ops[:1] == ["delete"]:
            if any(a.startswith("--dry-run") for a in args):
                return 1, "kubectl delete --dry-run", " ".join(ops[1:2]), None
            return 3, "kubectl delete", " ".join(ops[1:2]), "cluster"
    if prog == "vercel":
        if has(args, "--prod"):
            return 3, "vercel --prod", "", "deploy"
        if ops[:1] == ["deploy"] or not ops:
            return 2, "vercel deploy", "", "remote"
    if prog == "netlify" and ops[:1] == ["deploy"]:
        if has(args, "--prod"):
            return 3, "netlify deploy --prod", "", "deploy"
        return 2, "netlify deploy", "", "remote"
    if prog in G3_SUBCOMMANDS:
        verbs, family = G3_SUBCOMMANDS[prog]
        if ops[:1] and ops[0] in verbs:
            target = " ".join(ops[1:2]) or ("." if family == "infra" else "")
            return 3, "%s %s" % (prog, ops[0]), target, family
    if prog in G2_SUBCOMMANDS:
        verbs, family = G2_SUBCOMMANDS[prog]
        if ops[:1] and ops[0] in verbs:
            return 2, "%s %s" % (prog, ops[0]), " ".join(ops[1:2]), family
    if prog in ("chmod", "chown", "chgrp") and (short(args, "R") or has(args, "--recursive")):
        for op in ops:
            if op.rstrip("/") in ("", "~"):
                return 3, "%s -R" % prog, op, "system"
    if prog.startswith("mkfs") or prog in ("dd", "shutdown", "reboot", "halt", "diskutil"):
        return 3, prog, _joined(args, 1), "system"
    if prog == "crontab" and has(args, "-r"):
        return 3, "crontab -r", "", "system"
    if prog == "launchctl" and ops[:1] and ops[0] in ("unload", "bootout"):
        return 3, "launchctl " + ops[0], " ".join(ops[1:2]), "system"
    if prog == "kill" and has(args, "-9") and has(args, "-1"):
        return 3, "kill -9 -1", "", "system"
    if prog == "history" and has(args, "-c"):
        return 3, "history -c", "", "system"
    if prog == "shred":
        return 3, "shred", _joined(args, 1), "delete"
    return 1, prog, _joined(args, 1), None


def grade_text(cmd, cwd="", depth=0):
    """(nota, verbo, alvo, família) para uma linha de comando inteira: o máximo entre suas partes.

    Um comando que não é somente leitura e nomeia o armazenamento de aprovações recebe nota 3,
    seja lá o que mais faça: uma aprovação precisa vir do prompt do usuário, nunca de uma escrita
    que o agente faz."""
    best = _grade_text(cmd, cwd, depth)
    if depth == 0 and 0 < best[0] < 3 and approvals is not None and approvals.mentions_store(cmd):
        return 3, "write to", "the approvals store", "approvals"
    return best


def _grade_text(cmd, cwd, depth):
    if depth == 0 and ro.command_ok(cmd):
        return 0, None, None, None
    if depth >= MAX_DEPTH:
        return _scan(cmd)
    text, bodies = normalize(cmd)
    stripped, inners = _extract_subs(text)
    best = (0, None, None, None)
    for inner in inners:
        hit = _inner(inner, cwd, depth)
        if hit[0] > best[0]:
            best = hit
    parts = segments(stripped) if stripped is not None else None
    if parts is None:
        return max(best, _scan(text), key=lambda h: h[0])
    if bodies and any(seg and seg[0].rpartition("/")[2] in SQL_CLIENTS for seg in parts):
        for body in bodies:  # o shell não roda um corpo, mas um cliente SQL o interpreta
            hit = _sql(body)
            if hit and hit[0] > best[0]:
                best = hit
    for tokens in parts:
        hit = grade_tokens(tokens, cwd, depth)
        if hit[0] > best[0]:
            best = hit
        if best[0] == 3:
            break
    return best


def reason(grade, verb, target, family, variant):
    clause = CLAUSES.get(family) or GENERIC[grade]
    phrase = " ".join(p for p in (verb, target) if p).strip()
    return "grade %d, %s: %s %s — %s (%s, autonomy=%s)" % (
        grade, LABELS[grade], phrase or "this command", clause, PLAIN[grade], HOOK, variant)


def approval_code(mode, session_id, command):
    """O código com o qual o usuário responde para aprovar `command`, ou None onde esse canal está fechado.

    Só o modo `auto` o tem: um modo com prompt pergunta nativamente, e `bypassPermissions` mantém
    o marcador. `command` é o texto bruto que o agente enviou, então o código nomeia exatamente
    esse comando."""
    if mode != "auto" or approvals is None or approvals.store_path(session_id) is None:
        return None
    return approvals.code_for(session_id, command)


def approved(mode, session_id, command):
    """Consome uma aprovação viva de `command` nesta sessão; True quando uma foi usada."""
    code = approval_code(mode, session_id, command)
    return code is not None and approvals.consume(session_id, code)


def deny_tail(mode, session_id, command):
    code = approval_code(mode, session_id, command)
    return APPROVAL_TAIL % code if code else DENY_TAIL


# ------------------------------------------------------------------ governance

GOVERNANCE_POINT = "governance"
NO_PROVIDER = "none"
PUSH, COMMIT, MERGE = "coding.git_push", "coding.git_commit", "coding.pr_merge"
DEPLOY, SHELL, FILE_WRITE = "coding.deploy", "coding.shell_exec", "coding.file_write"
# Um deploy é a família `deploy` do avaliador mais os deploys de preview e deploys de stack que
# avalia sob outra família, então uma política em `coding.deploy` cobre todo verbo que o
# avaliador conhece que faz deploy.
DEPLOY_VERBS = ("vercel deploy", "netlify deploy", "cdk deploy")
RANK = {"allow": 0, "ask": 1, "deny": 2}
POLICY_NAME = "governance.json"
POLICY_DIR = ".agent-harness"
# Qualquer arquivo de política nomeado num comando que não é somente leitura é uma escrita nele:
# o `.agent-harness/governance.json` do repositório e o `.config/agent-harness/governance.json`
# do usuário.
POLICY_RE = re.compile(r"agent-harness[/\\]+governance\.json")
# A configuração do usuário seleciona o provedor, então uma escrita nela pode desligar a
# governança; ela é protegida como um arquivo de política, assim como o comando que define uma
# chave `governance` nela.
CONFIG_NAME = "config.json"
CONFIG_RE = re.compile(r"\.config[/\\]+agent-harness[/\\]+config\.json")
# `citizen` é o outro nome da CLI, então ambas as grafias são o mesmo comando.
CONFIG_SET_RE = re.compile(r"(?:harness|citizen)\b[^;&|\n]*\bconfig\s+set\s+[\"']?governance\b")
# Programas cujo cada operando pode ser um caminho em que escrevem, movem ou removem.
PATH_WRITERS = {"tee", "cp", "mv", "install", "ln", "rm", "unlink", "truncate", "touch", "rsync",
                "shred", "dd"}
IN_PLACE = {"sed", "gsed", "perl", "ruby"}
POLICY_LEVEL = 1
FILE_APPROVAL_TAIL = (" Nothing can prompt in this permission mode, so the edit was refused rather"
                      " than asked about. Stop, say in chat what the edit changes, and ask the user,"
                      " if they agree, to reply with exactly `approve %s` as the whole message."
                      " After that reply, make exactly the same edit again: the approval covers it"
                      " once, in this session, for thirty minutes.")
FILE_DENY_TAIL = (" Nothing can prompt in this permission mode, so the edit was refused. Ask the"
                  " user to make this change to the policy file themselves.")


def _config():
    """A configuração do usuário, encontrada como `posture.py` a encontra; `{}` quando não pode ser lida."""
    home = os.environ.get("HARNESS_HOME") or os.environ.get("HOME") or str(Path.home())
    try:
        data = json.loads((Path(home) / ".config" / "agent-harness" / "config.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def provider_name(config):
    """O provedor que `governance.provider` nomeia, lido como `decision.select_provider` o lê."""
    block = config.get("governance")
    name = block.get("provider") if isinstance(block, dict) else None
    return name if isinstance(name, str) and name.strip() else NO_PROVIDER


def _decision_module():
    """`harness_core.decision`, importado só quando um provedor está configurado."""
    lib = str(Path(__file__).resolve().parents[2] / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    return importlib.import_module("harness_core.decision")


def _resolve(target, cwd):
    """`target` como um caminho absoluto, relativo a `cwd`, com `~` e `$HOME` expandidos; None
    quando `cwd` é desconhecido (None) e `target` é relativo."""
    path = _expand(target)
    if not path:
        return cwd
    if os.path.isabs(path):
        return path
    return None if cwd is None else os.path.normpath(os.path.join(cwd, path))


# Uma mudança de diretório só é conhecida estaticamente quando seu alvo é um caminho literal:
# nada que o shell expande em tempo de execução. `~` e `~/…` são a única expansão permitida, por
# ser a home do usuário.
DYNAMIC_CHARS = set("$`*?[{") | {"\\"}


def _static_dir(target, cwd):
    """O diretório que um `cd`, `pushd` ou `-C` para `target` alcança, ou None quando não pode
    ser conhecido sem rodar a linha: `-`, uma variável, uma substituição, `~user`, um glob."""
    if (not target or target.startswith("-") or PLACEHOLDER in target
            or any(c in DYNAMIC_CHARS for c in target)
            or (target.startswith("~") and target != "~" and not target.startswith("~/"))):
        return None
    return _resolve(target, cwd)


def _isolating(text):
    """Se a linha tem um subshell, um pipeline ou um job em segundo plano, onde um `cd` não
    carrega para os comandos depois dele."""
    try:
        for token in ro.tokenize(" ; ".join(text.split("\n"))):
            if token and set(token) <= set("();|&<>"):
                # Um operador como `)` ou `|&`, ou uma sequência entre aspas de caracteres de
                # operador: remove os dois operadores de lista e os redirecionamentos de
                # descritor, e procura o que sobrou.
                rest = token.replace("&&", "").replace("||", "")
                for redirect in (">&", "<&", "&>"):
                    rest = rest.replace(redirect, "")
                if any(c in rest for c in "()|&"):
                    return True
        return False
    except ValueError:
        return True


COMPOUND_OPEN = {"{", "if", "while", "until", "for", "select", "case"}
COMPOUND_CLOSE = {"}", "fi", "done", "esac"}
LIST_ENDS = {"&&", "||", ";", ";;", "&"}


def _unquoted_structure(text):
    """`text` com todo caractere de operador entre aspas ou escapado substituído por `_`, para
    que o tokenizador, que transforma um `|` entre aspas numa palavra soletrada como o operador,
    retorne só operadores reais. Os limites de palavra não se movem: aqueles caracteres já
    estavam dentro de uma palavra."""
    out, quote, i = [], "", 0
    while i < len(text):
        c = text[i]
        if c == "\\" and quote != "'" and i + 1 < len(text):
            nxt = text[i + 1]
            out.append(c + ("_" if nxt in ro.OPERATOR_CHARS else nxt))
            i += 2
            continue
        if quote and c == quote:
            quote = ""
        elif not quote and c in "'\"":
            quote = c
        elif quote and c in ro.OPERATOR_CHARS:
            c = "_"
        out.append(c)
        i += 1
    return "".join(out)


def _confined(text):
    """Por comando simples de `segments(text)`, se um `cd` ali é confinado a ele, ou None quando
    a varredura não consegue posicionar a estrutura da linha e cada `cd` recai para `_isolating`.

    Um pipeline se liga mais forte que `&&`, `||` e `;`, então todo elemento de um pipeline
    começa no diretório em vigor quando ele inicia: só um `cd` dentro de um elemento de
    pipeline, um subshell ou um job em segundo plano é confinado. Um `cd` dentro de um grupo de
    chaves, condicional ou loop mantém a regra da linha inteira, porque tal construção pode em
    si ser um elemento de pipeline."""
    try:
        tokens = ro.tokenize(" ; ".join(_unquoted_structure(text).split("\n")))
    except ValueError:
        return None
    # [(índice de pipeline, profundidade de parênteses, profundidade de composto)] por segmento;
    # por pipeline, se está encanado e sua lista AND-OR; por lista, se `&` a coloca em segundo
    # plano. `&` termina e coloca em segundo plano a lista inteira, `cd d && true & git push`
    # incluído; `;` termina uma sem confiná-la.
    places, piped, list_of, backgrounded = [], [False], [0], [False]
    cur, skipping, parens, compounds = [], False, 0, 0
    for token in tokens:
        if token in ro.ALWAYS_DELIM:
            if cur:
                places.append(open_at)
            cur, skipping = [], False
            if token == "(":
                parens += 1
            elif token == ")":
                parens -= 1
                if parens < 0:  # um padrão `case`, que esta varredura não posiciona
                    return None
            elif parens == 0 and compounds == 0:
                if token in ("|", "|&"):
                    piped[-1] = True
                elif token in LIST_ENDS:
                    piped.append(False)
                    if token in ("&&", "||"):
                        list_of.append(list_of[-1])
                    else:
                        backgrounded[-1] = token == "&"
                        backgrounded.append(False)
                        list_of.append(len(backgrounded) - 1)
            continue
        if skipping:
            continue
        if not cur:
            if token in COMPOUND_OPEN:
                compounds += 1
            elif token in COMPOUND_CLOSE:
                compounds -= 1
                if compounds < 0:
                    return None
            if token in ro.WORD_DROP or token in ro.WORD_COND or token == "!":
                continue
            if token in ro.WORD_HEADER:
                skipping = True
                continue
            open_at = (len(piped) - 1, parens, compounds)
        cur.append(token)
    if cur:
        places.append(open_at)
    if parens or compounds:
        return None
    return [True if in_parens else None if in_compound
            else piped[index] or backgrounded[list_of[index]]
            for index, in_parens, in_compound in places]


def _user_policy(name=POLICY_NAME):
    home = os.environ.get("HARNESS_HOME") or os.environ.get("HOME") or str(Path.home())
    return os.path.join(home, ".config", "agent-harness", name)


def is_user_config(path):
    """Se `path` é a configuração de usuário do harness, `config.json`, que seleciona o provedor."""
    try:
        return (os.path.realpath(os.path.expanduser(str(path)))
                == os.path.realpath(_user_policy(CONFIG_NAME)))
    except (OSError, ValueError):
        return False


def guarded(path):
    """O que `path` é, quando uma escrita nele é uma ação de nível 1, ou None."""
    if is_policy_file(path):
        return "the governance policy file " + str(path)
    if is_user_config(path):
        return "the harness configuration " + str(path) + ", which selects the decision provider"
    return None


def is_policy_file(path):
    """Se `path` é um arquivo de política de governança: de qualquer repositório ou do usuário."""
    try:
        real = os.path.realpath(os.path.expanduser(str(path)))
        user = os.path.realpath(_user_policy())
    except (OSError, ValueError):
        return False
    if os.path.basename(real) != POLICY_NAME:
        return False
    return real == user or os.path.basename(os.path.dirname(real)) == POLICY_DIR


def _git_dir(args, cwd):
    """(o diretório em que um comando git roda, depois de cada `-C <dir>`, e seu subcomando). O
    diretório é None quando um `-C` não é um caminho literal, ou `--git-dir` ou `--work-tree`
    aponta o comando para um repositório que seu diretório não nomeia."""
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith(("--git-dir=", "--work-tree=")):
            cwd = None
        if a in GIT_VALUE_GLOBALS and i + 1 < len(args):
            if a == "-C":
                cwd = _static_dir(args[i + 1], cwd)
            elif a in ("--git-dir", "--work-tree"):
                cwd = None
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        break
    return cwd, (args[i] if i < len(args) else "")


def _written(prog, args, targets, cwd):
    """Os caminhos que um comando simples pode escrever, mover ou remover: absolutos onde o
    diretório é conhecido, e senão o operando como escrito, para que `_policy_hits` ainda consiga
    julgá-lo pelo nome."""
    paths = [t for t in targets if t and not t.isdigit() and t != "/dev/null"]
    if prog in PATH_WRITERS:
        paths.extend(operands(args))
        paths.extend(a.split("=", 1)[1] for a in args if a.startswith("of="))
    if prog in IN_PLACE and (short(args, "i") or has(args, "--in-place")):
        paths.extend(operands(args))
    out = []
    for path in paths:
        head = os.path.dirname(path)
        resolved = None if (PLACEHOLDER in head or "$" in head) else _resolve(path, cwd)
        out.append(resolved or path)
    return out


def _governed(tokens, cwd, depth):
    """[(classe de ação, nota, diretório, caminhos escritos)] para um comando simples.

    Wrappers, runners, `sudo` e o texto `-c` de um shell são atravessados, como o avaliador os
    atravessa, e o comando interno é governado na mais alta das duas notas."""
    grade, verb, _target, family = grade_tokens(list(tokens), cwd or "", depth)
    body, targets = _redirects(list(tokens))
    while body and ASSIGN_RE.match(body[0]):
        body = body[1:]
    if not body:
        return [(SHELL, grade, cwd, _written("", [], targets, cwd))]
    prog, args = body[0].rpartition("/")[2], body[1:]
    ops = operands(args)
    written = _written(prog, args, targets, cwd)
    inner = None
    if depth < MAX_DEPTH:
        if prog in WRAPPERS:
            if prog == "env" and any(a in ("-C", "--chdir") or a.startswith("--chdir=")
                                     for a in args):
                cwd = None  # `env -C` move o comando interno; nenhum literal é confiado aqui
            rest = strip_options(args, WRAPPERS[prog])
            while rest and ASSIGN_RE.match(rest[0]):
                rest = rest[1:]
            inner = ("tokens", rest[1:] if prog == "timeout" else rest)
        elif prog in SUDO:
            inner = ("tokens", strip_options(args, SUDO[prog]))
        elif (prog, ops[0] if ops else "") in RUNNERS:
            rest = args[args.index(ops[0]) + 1:]
            while rest and (rest[0].startswith("-") or ASSIGN_RE.match(rest[0])):
                rest = rest[1:]
            inner = ("tokens", rest)
        elif prog in SHELLS:
            for i, a in enumerate(args):
                if DASH_C_RE.match(a) and i + 1 < len(args):
                    inner = ("text", args[i + 1])
                    break
        elif prog == "eval":
            inner = ("text", " ".join(args))
    if inner is not None and inner[1]:
        if inner[0] == "tokens":
            found = _governed(inner[1], cwd, depth + 1)
        else:
            found = governed_text(inner[1], cwd, depth + 1)
        if found:
            return [(c, max(g, grade), d, w + written) for c, g, d, w in found]
    if prog == "git":
        where, sub = _git_dir(args, cwd)
        return [({"push": PUSH, "commit": COMMIT}.get(sub, SHELL), grade, where, written)]
    if prog == "gh" and ops[:2] == ["pr", "merge"]:
        return [(MERGE, grade, cwd, written)]
    if family == "deploy" or verb in DEPLOY_VERBS:
        return [(DEPLOY, grade, cwd, written)]
    return [(SHELL, grade, cwd, written)]


def governed_text(cmd, cwd, depth=0, isolated=False):
    """[(classe de ação, nota, diretório, caminhos escritos)] para cada comando simples em `cmd`,
    na ordem de execução, ou None quando o texto não decompõe.

    O diretório é o que está em vigor quando o comando roda, percorrendo a linha como o shell
    faria: uma substituição é governada com o diretório do segmento em que está, então
    `cd ../other && echo "$(git push)"` faz push a partir de `../other`. Um diretório é None, que
    `govern` nomeia `repo:unknown/local`, a partir da primeira mudança que não pode ser conhecida
    sem rodar a linha: um `cd` ou `pushd` para qualquer coisa além de um caminho literal, `popd`,
    e qualquer `cd` num subshell, uma substituição, um pipeline ou um job em segundo plano, onde
    não se carrega adiante. Um pipeline depois de um `cd` começa no diretório daquele `cd`, como
    `_confined` o posiciona."""
    if depth >= MAX_DEPTH:
        return None
    text, _bodies = normalize(cmd)
    stripped, inners = _extract_subs(text)
    parts = segments(stripped) if stripped is not None else None
    if parts is None:
        return None
    line_wide = isolated or _isolating(stripped)
    confined = None if isolated else _confined(stripped)
    if confined is None or len(confined) != len(parts):
        confined = [None] * len(parts)
    queue = list(inners)
    found = []

    def substitutions(count, where):
        for _ in range(min(count, len(queue))):
            inner = queue.pop(0)
            found.extend(governed_text(inner, where, depth + 1, isolated=True)
                         or [(SHELL, _scan(inner)[0], where, [])])

    here = cwd
    for tokens, alone in zip(parts, confined):
        substitutions(sum(t.count(PLACEHOLDER) for t in tokens), here)
        body, _targets = _redirects(list(tokens))
        while body and ASSIGN_RE.match(body[0]):
            body = body[1:]
        head = body[0].rpartition("/")[2] if body else ""
        if head in ("cd", "pushd", "popd"):
            # Uma mudança de diretório que também escreve, através de um redirecionamento, é governada onde roda.
            moved_grade = grade_tokens(list(tokens), here or "", depth)[0]
            if moved_grade > 0:
                found.append((SHELL, moved_grade, here, _written(head, [], _targets, here)))
            args = body[1:]
            if alone is None:
                alone = line_wide
            # Um `cd` confinado deixa o diretório desconhecido, não inalterado: o zsh roda o
            # último elemento de um pipeline no shell atual, então `x | cd d` o move para lá.
            if alone or head == "popd" or any(a.startswith("-") for a in args) or len(args) > 1:
                here = None
            elif head == "pushd" and not args:
                here = None  # troca com a pilha de diretórios, que esta varredura não mantém
            else:
                here = _static_dir(args[0] if args else "~", here)
            continue
        found.extend(_governed(tokens, here, depth))
    substitutions(len(queue), None)  # qualquer um que os segmentos não contabilizaram: falha fechado
    return found


_LEDGER = []


def _log(action_class, slug, level, grade, outcome, provider, event, runtime,
         error=None):
    """Uma linha `governance`: a classe, contraparte, nível, nota e resultado, nunca o texto."""
    if not _LEDGER:
        _LEDGER.append(_sibling("decisions.py", "grade_bash_decisions"))
    module = _LEDGER[0]
    if module is None:
        return
    detail = {"action": action_class, "counterparty": slug, "level": level, "grade": grade,
              "outcome": outcome, "provider": provider}
    if error:
        detail["error"] = error
    module.record(GOVERNANCE_POINT, outcome, json.dumps(detail, sort_keys=True), event or {},
                  runtime)


def unresolved(operand):
    """O que um operando de escrita cujo diretório é desconhecido pode ser, julgado só pelo nome.

    Um operando sob um `cd` que a varredura não consegue seguir, ou com uma variável ou
    substituição em seu diretório, não tem caminho para checar, então um nome terminando em
    `governance.json` ou `config.json` é tomado como o arquivo que nomeia. Um operando que é em
    si uma variável não é julgado aqui."""
    name = operand.strip("\"'")
    for suffix, what in ((POLICY_NAME, "a governance policy file"),
                         (CONFIG_NAME, "the harness configuration")):
        if name.endswith(suffix):
            return what + ", " + name + ", in a directory that cannot be known before it runs"
    return None


def _policy_hits(command, found):
    """O que um comando muda que é uma ação de nível 1: um arquivo de política, a configuração do
    usuário ou uma chave `governance` definida através de `harness config set`."""
    hits = sorted(set(filter(None, (guarded(p) if os.path.isabs(p) else unresolved(p)
                                    for entry in found for p in entry[3]))))
    if not hits:
        match = POLICY_RE.search(command)
        if match:
            hits = ["the governance policy file " + match.group(0)]
        else:
            match = CONFIG_RE.search(command)
            if match:
                hits = ["the harness configuration " + match.group(0)
                        + ", which selects the decision provider"]
    if CONFIG_SET_RE.search(command):
        hits.append("the governance configuration, through `harness config set`")
    return hits


def govern(command, cwd, grade, variant, event=None, runtime=""):
    """O que o provedor de decisão acrescenta a um comando que o avaliador deixa passar.

    None quando nada é acrescentado: provedor `none`, um comando de nota 0, ou um provedor que
    permite. Senão `(outcome, sentence)`, `ask` ou `deny`, a frase nomeando a classe, contraparte,
    nível e sua fonte. Só aperta por construção: o chamador só pergunta isso quando sua própria
    resposta é deixar o comando passar. Um provedor configurado que não consegue responder é um
    ask nomeando o erro, nunca um allow."""
    config = _config()
    name = provider_name(config)
    if name == NO_PROVIDER or not grade:
        return None
    cwd = cwd or os.getcwd()
    try:
        found = governed_text(command, cwd)
    except Exception:
        found = None
    if not found or max(entry[1] for entry in found) <= 0:
        # O avaliador deu à linha uma nota acima de 0, mas nenhum segmento carrega essa nota:
        # governa a linha inteira na sua nota em vez de deixar a varredura não encontrar nada
        # sobre o que perguntar.
        found = (found or []) + [(SHELL, grade, cwd, [])]
    hits = _policy_hits(command, found)
    if hits:
        _log(FILE_WRITE, None, POLICY_LEVEL, grade, "ask", name, event, runtime)
        return "ask", ("Governance: this changes %s, which is level %d: every change to it"
                       " needs the user's explicit yes." % ("; ".join(hits), POLICY_LEVEL))
    worst = None
    try:
        decision = _decision_module()
        places, providers = {}, {}
        # O provedor é selecionado, carregado e sua política lida para o próprio diretório do
        # comando antes de qualquer segmento ser examinado. Um provedor que não pode ser usado
        # então pergunta pelo comando inteiro, seja qual for a nota dos seus segmentos: uma linha
        # cuja única parte avaliada fica escondida da varredura de segmentos, como
        # `cd $(cat x)`, não pode passar por falta de um segmento sobre o qual perguntar.
        places[cwd] = decision.locate(cwd)
        home_root = places[cwd][1] or cwd
        providers[home_root] = decision.select_provider(config, root=home_root, variant=variant)
        load = getattr(providers[home_root], "policy", None)
        if callable(load):
            load()
        for action_class, level_grade, where, _written_paths in found:
            if level_grade <= 0:
                continue
            if where is None:
                # Um diretório que a varredura não conseguiu conhecer: nenhum par nomeia esta
                # contraparte, então o padrão da classe governa, lido das políticas que o próprio
                # diretório do hook enxerga.
                slug, root = decision.UNKNOWN_COUNTERPARTY, home_root
            else:
                if where not in places:
                    places[where] = decision.locate(where)
                slug, top = places[where]
                root = top or where
            if root not in providers:
                providers[root] = decision.select_provider(config, root=root, variant=variant)
            answer = providers[root].decide(decision.Action(action_class, level_grade), slug)
            if answer.outcome not in RANK:
                raise decision.PolicyError("provider %s answered %r, not allow, ask or deny"
                                           % (name, answer.outcome))
            _log(action_class, slug, answer.autonomy_level, level_grade, answer.outcome,
                 answer.provider, event, runtime)
            if answer.outcome != "allow" and (worst is None
                                              or RANK[answer.outcome] > RANK[worst[0]]):
                worst = (answer.outcome, "Governance: %s on %s is level %d (%s)."
                         % (action_class, slug, answer.autonomy_level, answer.reason))
    except Exception as exc:
        error = "%s: %s" % (type(exc).__name__, exc)
        _log(None, None, None, grade, "ask", name, event, runtime, error=type(exc).__name__)
        return "ask", ("Governance: provider %s could not answer, so this asks rather than runs"
                       " (%s)." % (name, error))
    return worst


def govern_file(tool, tool_input, paths, event=None, runtime=""):
    """`(subject, sentence)` para uma escrita de ferramenta de arquivo num arquivo de política ou na config do usuário, ou None.

    Só quando um provedor diferente de `none` está configurado. `subject` é o que um código de
    aprovação nomeia: a ferramenta e sua entrada exata, para que uma aprovação cubra aquela edição."""
    name = provider_name(_config())
    if name == NO_PROVIDER:
        return None
    hits = sorted(set(filter(None, (guarded(p) for p in paths))))
    if not hits:
        return None
    _log(FILE_WRITE, None, POLICY_LEVEL, 1, "ask", name, event, runtime)
    subject = tool + "\n" + json.dumps(tool_input, sort_keys=True)
    return subject, ("Governance: this edits %s, which is level %d: every change to it needs"
                     " the user's explicit yes." % ("; ".join(hits), POLICY_LEVEL))


def main():
    if ro is None:
        return  # sem gramática, sem avaliação: cai no fluxo de permissão normal
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return
    raw = command
    command, confirmed = strip_marker(command)
    if confirmed:
        return
    variant, label = stance()
    threshold = THRESHOLDS.get(variant, THRESHOLDS[DEFAULT_STANCE])
    grade, verb, target, family = grade_text(command, payload.get("cwd") or "")
    if grade == 0:
        return
    text = reason(grade, verb, target, family, label)
    decision = "ask"
    if grade < threshold:
        governed = govern(command, payload.get("cwd") or "", grade, variant, payload)
        if governed is None:
            return
        decision, sentence = governed
        text = text + " " + sentence
    mode, session_id = payload.get("permission_mode"), payload.get("session_id")
    if decision == "deny":
        emit("deny", text)
    elif mode in DENY_MODES:
        if approved(mode, session_id, raw):
            return
        emit("deny", text + deny_tail(mode, session_id, raw))
    else:
        emit("ask", text)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # falha aberta: um bug aqui custa um prompt, nunca um bloqueio
