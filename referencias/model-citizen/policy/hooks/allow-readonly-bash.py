#!/usr/bin/env python3
"""Hook de PreToolUse: aprova comandos Bash somente leitura que o conjunto somente-leitura
embutido do Claude Code não pega, para que o modo plano e o modo Manual parem de pedir
confirmação para eles.

Por que um hook e não regras de allow: `git -C <dir> status`, `gh repo view`, `npm view`
e afins não podem ser expressos como uma regra de prefixo sem um wildcard antes do
subcomando, sobre o qual o Claude Code avisa e que também combinaria com escritas.

Comportamento:
  - Aprova só quando TODO comando que rodaria é somente leitura sob a gramática
    abaixo. Comandos compostos são decompostos primeiro: pipelines e sequências
    `;`/`&&`/`||`, quebras de linha, blocos `for`/`while`/`until`/`if`, subshell `( ... )` e
    grupo `{ ...; }`, e substituições de comando `$(...)` / crase / `<(...)` são
    cada uma verificada, recursivamente, e o conjunto todo só é aprovado se cada parte
    for. Qualquer coisa que a gramática não consiga provar somente leitura não retorna
    decisão nenhuma e cai no fluxo de permissão normal. Este hook nunca nega.
  - Redirecionamentos de saída para um arquivo (`>`, `>>`, `>|`, `&>`, `>&`, `<>`) nunca
    são aprovados aqui; `/dev/null` e duplicação de fd (`2>&1`) são. Heredocs e
    continuações de barra invertida não são modelados e caem no fluxo normal. Um comentário `#`
    termina na sua linha, como faz para o bash, então nada depois de um comentário fica escondido
    da checagem.
  - Subshells que rodam uma escrita, `bash -c`, `eval`, `xargs`, `sudo`, `find -exec`
    e `find -delete`, e um comando construído a partir da saída de uma substituição nunca são
    aprovados aqui; nem as flags de escrita ou execução de ferramentas de outra forma somente
    leitura (`sort -o`, `fd -x`, `rg --pre`, `sed w`, o `system()` do awk), um programa rodado
    por caminho fora dos diretórios bin do sistema, ou uma atribuição de ambiente que
    direciona um comando posterior (`PATH`, `GIT_*`, `NODE_OPTIONS` e afins).

Teste: echo '{"tool_name":"Bash","tool_input":{"command":"git -C /x status"}}' | python3 allow-readonly-bash.py
"""
import json
import re
import sys

# Comandos que são somente leitura independentemente dos argumentos. O Claude Code ainda checa
# os alvos de redirecionamento por conta própria; recusamos redirecionamentos de arquivo abaixo de qualquer forma.
PLAIN = {
    "ls", "cat", "head", "tail", "wc", "grep", "egrep", "fgrep", "find",
    "stat", "du", "df", "pwd", "echo", "printf", "true", "false",
    "test", "[", "which", "type", "whoami", "id", "uname", "sw_vers",
    "printenv", "basename", "dirname", "realpath", "readlink", "uniq", "cut",
    "tr", "jq", "column", "nl", "od", "strings", "md5", "md5sum",
    "shasum", "sha256sum", "diff", "cmp", "comm", "tac", "rev", "seq", "expr",
    "cd", "arch", "nproc", "lsof", "ps", "top", "uptime",
    "read", "fold", "paste", "join", "look", "hexdump", "base64", "cksum",
}

# Somente leitura a menos que uma dessas flags apareça: uma opção longa combinada por prefixo, ou
# uma letra em qualquer lugar num agrupamento de opções curtas, então `-Hx` é pego do mesmo jeito que `-x`.
FLAGGED = {
    "sort": (("--output", "--compress-program"), "o"),
    "tree": ((), "o"),
    "yq": (("--inplace", "--split-exp"), "is"),
    "fd": (("--exec", "--exec-batch"), "xX"),
    "rg": (("--pre",), ""),
    "file": (("--compile",), "C"),
    "date": (("--set",), "s"),  # plus: no operand other than a +FORMAT
    "sysctl": (("--write",), "w"),
    "hostname": (("--file",), "F"),
    "xxd": ((), ""),
}
# Operandos além dessa contagem nomeiam um arquivo de saída (`xxd in out`) ou definem estado (`hostname x`).
POSITIONAL_MAX = {"xxd": 1, "hostname": 0}

# Comandos somente leitura só quando os argumentos combinam com o regex dado
# (comparado contra a string de argumento depois do nome do programa).
PREFIXED = [
    ("gh", r"^(auth status|repo view|repo list|pr view|pr list|pr diff|pr checks|pr status|"
           r"issue view|issue list|run list|run view|release list|release view|label list|"
           r"search \S+|api (-X GET |--method GET )?\S+$|--version)"),
    ("npm", r"^(view|info|show|ls|list|outdated|why|explain|--version|-v)(\s|$)"),
    ("pnpm", r"^(ls|list|why|outdated|--version|-v)(\s|$)"),
    ("yarn", r"^(info|why|--version|-v)(\s|$)"),
    ("cargo", r"^(metadata|tree|--version|-V)(\s|$)"),
    ("uv", r"^(pip list|pip show|tree|--version|-V)(\s|$)"),
    ("python3", r"^--version$"),
    ("python", r"^--version$"),
    ("node", r"^--version$"),
    ("claude", r"^--version$"),
    ("rustc", r"^--version$"),
    ("brew", r"^(list|info|--version|--prefix)(\s|$)"),
    ("aws", r"^sts get-caller-identity(\s|$)"),
]

# Variáveis que mudam qual programa roda ou o que ele executa: atribuir a uma, mesmo
# sem `export`, é uma forma de direcionar um comando aprovado. `PAGER=cat` é o único
# idioma que vale a pena manter.
DANGEROUS_ENV = re.compile(
    r"^(PATH|LD_|DYLD_|GIT_|PAGER|LESS|EDITOR|VISUAL|NODE_OPTIONS|PYTHON|PERL|RUBY|BASH_ENV|"
    r"ENV$|IFS|CDPATH|GLOBIGNORE|HOME|SHELL|TMPDIR|PS4|PROMPT_COMMAND|AWKPATH|AWKLIBPATH|"
    r"GREP_OPTIONS|BROWSER|MANPATH|GH_|NPM_|CARGO|RUSTC|GOFLAGS|GOENV|UV_|HOMEBREW|SSH_|"
    r"PYENV|NVM|JAVA|_JAVA|CLASSPATH|JQ_)"
)
PAGER_OK = re.compile(r"^(PAGER|GIT_PAGER)=(cat)?$")

# Um programa nomeado por caminho absoluto só é aprovado a partir desses diretórios; um
# repositório pode trazer um `bin/cat` próprio.
SAFE_BIN_DIRS = {"/bin", "/usr/bin", "/usr/local/bin", "/opt/homebrew/bin", "/sbin", "/usr/sbin"}

# Subcomandos git que são somente leitura com quaisquer argumentos.
GIT_ANY = {
    "status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree", "check-ignore",
    "blame", "describe", "shortlog", "cat-file", "rev-list", "name-rev", "merge-base",
    "count-objects", "for-each-ref", "show-ref", "var", "diff-tree", "diff-index",
    "diff-files", "grep", "whatchanged", "version", "--version", "help",
}

GIT_ARGS_WRITE = re.compile(r"^(--output|--open-files-in-pager|-O)")

# awk: escapes de shell, saída para arquivo, arquivos de script e carregamento de extensão.
AWK_FORBIDDEN = re.compile(r"system\s*\(|getline|[|>]|@load|@include|^-[filE]|^--(file|include|load|exec)")

FIND_FORBIDDEN = {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls"}
NEVER = {"sudo", "eval", "exec", "bash", "sh", "zsh", "xargs", "source", "."}

# Metacaracteres que separam comandos onde quer que apareçam.
ALWAYS_DELIM = {";", "&&", "||", "|", "|&", "&", "(", ")", ";;"}
# Palavras reservadas são estruturais só em posição de comando (veja command_ok). Como um
# argumento, ex. `grep -q done`, a mesma palavra é dado comum.
#   WORD_DROP    separa comandos mas não carrega nenhum para checar.
#   WORD_COND    introduz um comando de condição cujo restante precisa ser checado.
#   WORD_HEADER  introduz um cabeçalho de loop/case cujas palavras são dados, não comandos.
WORD_DROP = {"do", "done", "then", "fi", "else", "esac", "{", "}"}
WORD_COND = {"while", "until", "if", "elif"}
WORD_HEADER = {"for", "select", "case"}

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PLACEHOLDER = "__ROSUB__"  # representa uma substituição verificada; nunca um comando real

# Tokens de redirecionamento que são seguros por conta própria: redirecionamentos de entrada (seu
# operando é lido, nunca escrito) e duplicação de fd.
READ_REDIRECTS = {"<", "<<", "<<<", "<&"}
WRITE_REDIRECTS = re.compile(r"^\d*(>|>>|&>|>&)$")
PUNCTUATION_RUN = re.compile(r"^\d*[<>&|]+$")


# Caracteres que iniciam um operador fora de aspas, e os operadores que eles soletram, o mais
# longo primeiro. `;&` e `;;&` não estão listados, então se dividem em delimitadores e falham fechados.
OPERATOR_CHARS = "();<>|&"
OPERATORS = ("&>>", "<<<", "&&", "||", ";;", "|&", "&>", ">>", ">&", ">|", "<<", "<&", "<>",
             ";", "&", "|", "(", ")", "<", ">")
_WHITESPACE = " \t\r\n"


def _operators(run):
    """Uma sequência sem aspas de caracteres de operador como os operadores que o bash lê nela: o
    operador mais longo em cada posição, da esquerda para a direita, então `);` é `)` depois `;`."""
    out, i = [], 0
    while i < len(run):
        op = next(o for o in OPERATORS if run.startswith(o, i))
        out.append(op)
        i += len(op)
    return out


def tokenize(cmd):
    """As palavras e operadores de `cmd`, como o POSIX `shlex` com `punctuation_chars` os divide,
    exceto que uma sequência sem aspas de caracteres de operador é dividida em seus operadores.
    `shlex` retorna tal sequência como um único token, então `(true);` terminava em `);`, que não
    é um delimitador. Um caractere de operador entre aspas ou escapado é parte de uma palavra.
    Levanta ValueError numa aspa não fechada ou uma barra invertida no final, como `shlex` faz."""
    tokens = []
    word = None  # None: nenhuma palavra em progresso; "" é uma palavra entre aspas vazia
    i, n = 0, len(cmd)
    while i < n:
        c = cmd[i]
        if c in _WHITESPACE or c in OPERATOR_CHARS:
            if word is not None:
                tokens.append(word)
                word = None
            if c in _WHITESPACE:
                i += 1
                continue
            j = i
            while j < n and cmd[j] in OPERATOR_CHARS:
                j += 1
            tokens.extend(_operators(cmd[i:j]))
            i = j
        elif c == "\\":
            if i + 1 >= n:
                raise ValueError("No escaped character")
            word = (word or "") + cmd[i + 1]
            i += 2
        elif c == "'":
            end = cmd.find("'", i + 1)
            if end < 0:
                raise ValueError("No closing quotation")
            word = (word or "") + cmd[i + 1:end]
            i = end + 1
        elif c == '"':
            buf, j = [], i + 1
            while j < n and cmd[j] != '"':
                if cmd[j] == "\\" and j + 1 < n:
                    if cmd[j + 1] not in '"\\':
                        buf.append("\\")  # só uma aspa ou uma barra invertida é escapada aqui
                    buf.append(cmd[j + 1])
                    j += 2
                    continue
                buf.append(cmd[j])
                j += 1
            if j >= n:
                raise ValueError("No closing quotation")
            word = (word or "") + "".join(buf)
            i = j + 1
        else:
            word = (word or "") + c
            i += 1
    if word is not None:
        tokens.append(word)
    return tokens


def assignment_ok(token):
    """`NAME=value` pode preceder um comando, ou ficar sozinho, só quando NAME não
    consegue direcionar o que um comando aprovado posterior roda."""
    return PAGER_OK.match(token) is not None or DANGEROUS_ENV.match(token) is None


def flags_hit(args, longs, shorts):
    for a in args:
        if a == "--":
            break
        if a.startswith("--"):
            if any(a.startswith(l) for l in longs):
                return True
        elif a.startswith("-") and len(a) > 1:
            if any(ch in shorts for ch in a[1:]):
                return True
    return False


def positionals(args):
    out, opts_done = [], False
    for a in args:
        if a == "--":
            opts_done = True
        elif opts_done or not a.startswith("-"):
            out.append(a)
    return out


def _skip_delimited(s, i, delim):
    """Índice logo após o próximo `delim` não escapado a partir de s[i], respeitando expressões
    de colchete; None quando a seção nunca fecha."""
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "[":
            j = i + 1
            if j < n and s[j] == "^":
                j += 1
            if j < n and s[j] == "]":
                j += 1
            while j < n and s[j] != "]":
                j += 1
            if j >= n:
                return None
            i = j + 1
            continue
        if c == delim:
            return i + 1
        i += 1
    return None


def sed_script_ok(s):
    """True when a sed script only prints, edits the pattern space, branches or
    quits — never `w`, `W`, `e` or the `w`/`e` flags of `s`."""
    n = len(s)
    i = 0
    while i < n:
        c = s[i]
        if c in " \t\n;":
            i += 1
            continue
        if c == "#":
            while i < n and s[i] != "\n":
                i += 1
            continue
        # Addresses: N, $, /re/, \cREc, optional ~step, I/M flags, a comma and a second one.
        while i < n:
            c = s[i]
            if c.isdigit() or c in "$+~":
                while i < n and (s[i].isdigit() or s[i] in "$~+"):
                    i += 1
            elif c == "/":
                i = _skip_delimited(s, i + 1, "/")
            elif c == "\\" and i + 1 < n:
                i = _skip_delimited(s, i + 2, s[i + 1])
            else:
                break
            if i is None:
                return False
            while i < n and s[i] in "IM":
                i += 1
            while i < n and s[i] in " \t":
                i += 1
            if i < n and s[i] == ",":
                i += 1
                while i < n and s[i] in " \t":
                    i += 1
                continue
            break
        while i < n and s[i] in " \t!":
            i += 1
        if i >= n:
            return True
        cmd = s[i]
        i += 1
        if cmd in "wWe":
            return False
        if cmd in "{}pPnNdDhHgGxz=F":
            continue
        if cmd in ":btT" or cmd in "rR" or cmd in "aic":
            while i < n and s[i] != "\n":
                i += 1
            continue
        if cmd in "qQlLv":
            while i < n and s[i].isdigit():
                i += 1
            continue
        if cmd in "sy":
            if i >= n:
                return False
            delim = s[i]
            i = _skip_delimited(s, i + 1, delim)
            if i is None:
                return False
            i = _skip_delimited(s, i, delim)
            if i is None:
                return False
            if cmd == "s":
                while i < n and s[i] in "gpImM0123456789":
                    i += 1
                if i < n and s[i] not in " \t\n;}":
                    return False  # `e`, `w file`, or a flag this parser does not know
            continue
        return False
    return True


def sed_ok(args):
    """`sed -n` with inline scripts that never write or execute: no -i, no -f, no w/e."""
    scripts, files, i, saw_n = [], [], 0, False
    while i < len(args):
        a = args[i]
        if a == "--":
            files.extend(args[i + 1:])
            break
        if a.startswith("--"):
            name, eq, value = a.partition("=")
            if name in ("--quiet", "--silent"):
                saw_n = True
            elif name == "--expression":
                if eq:
                    scripts.append(value)
                elif i + 1 < len(args):
                    scripts.append(args[i + 1])
                    i += 1
                else:
                    return False
            elif name in ("--regexp-extended", "--separate", "--unbuffered", "--null-data",
                          "--posix", "--debug", "--sandbox", "--line-length"):
                if name == "--line-length" and not eq:
                    i += 1
            else:
                return False
        elif a.startswith("-") and len(a) > 1:
            letters = a[1:]
            for k, ch in enumerate(letters):
                if ch == "n":
                    saw_n = True
                elif ch in "Ersuz":
                    pass
                elif ch == "e":
                    rest = letters[k + 1:]
                    if rest:
                        scripts.append(rest)
                    elif i + 1 < len(args):
                        scripts.append(args[i + 1])
                        i += 1
                    else:
                        return False
                    break
                elif ch == "l":
                    if not letters[k + 1:]:
                        i += 1
                    break
                else:
                    return False  # -i, -f, and anything unknown
        else:
            (files if scripts else scripts).append(a)
        i += 1
    return saw_n and bool(scripts) and all(sed_script_ok(s) for s in scripts)


def git_ok(args):
    """args: list of tokens after `git`. Strips -C <dir>, --no-pager, -P."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-C" and i + 1 < len(args):
            i += 2
            continue
        if a in ("--no-pager", "-P"):
            i += 1
            continue
        if a.startswith("-"):
            return False  # -c key=val and unknown globals are not approved
        break
    rest = args[i:]
    if not rest:
        return False
    sub, sargs = rest[0], rest[1:]
    if any(GIT_ARGS_WRITE.match(s) for s in sargs):
        return False
    if sub in GIT_ANY:
        return True
    if sub == "branch":
        ro = {"-a", "-r", "-v", "-vv", "--all", "--remotes", "--list", "-l", "--show-current",
              "--contains", "--no-contains", "--merged", "--no-merged", "--points-at", "--verbose"}
        listing = any(s in ("--list", "-l") for s in sargs)
        for s in sargs:
            if s.startswith("--format=") or s.startswith("--sort="):
                continue
            if s in ro:
                continue
            if not s.startswith("-") and listing:
                continue
            return False
        return True
    if sub == "remote":
        return not sargs or sargs[0] in ("-v", "--verbose", "show", "get-url")
    if sub == "tag":
        return not sargs or sargs[0] in ("-l", "--list", "-n", "--contains", "--points-at")
    if sub == "stash":
        return bool(sargs) and sargs[0] in ("list", "show")
    if sub == "worktree":
        return bool(sargs) and sargs[0] == "list"
    if sub == "submodule":
        return bool(sargs) and sargs[0] == "status"
    if sub == "reflog":
        return not sargs or sargs[0] not in ("expire", "delete")
    if sub == "config":
        getters = {"--get", "--get-all", "--get-regexp", "--list", "-l"}
        writers = {"--unset", "--unset-all", "--add", "--replace-all", "--edit", "-e",
                   "--remove-section", "--rename-section"}
        if any(s in writers for s in sargs) or not any(s in getters for s in sargs):
            return False
        positional = [s for s in sargs if not s.startswith("-")]
        return len(positional) <= 1
    if sub == "symbolic-ref":
        return len([s for s in sargs if not s.startswith("-")]) <= 1
    return False


def strip_redirects(tokens):
    """Tokens with safe redirections removed; None when any redirection writes a file."""
    cleaned = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if not PUNCTUATION_RUN.match(t):
            cleaned.append(t)
            i += 1
            continue
        target = tokens[i + 1] if i + 1 < len(tokens) else ""
        if t in READ_REDIRECTS:
            i += 2
        elif re.match(r"^\d*>&$", t) and re.match(r"^\d+$", target):
            i += 2  # 2>&1
        elif WRITE_REDIRECTS.match(t) and target == "/dev/null":
            i += 2
        else:
            return None  # a file is written, or an operator this hook does not model
    return cleaned


def segment_ok(tokens):
    """True when a single simple command (already free of substitutions and of the
    structural keywords) is read-only."""
    tokens = strip_redirects(tokens)
    if not tokens:
        return False
    # Strip leading assignments (LANG=C, S=/path, NAME=value cmd ...). A segment
    # that is nothing but assignments runs no command, so it is read-only — unless
    # the variable steers a command that runs later in the same call.
    while tokens and ASSIGN_RE.match(tokens[0]):
        if not assignment_ok(tokens[0]):
            return False
        tokens = tokens[1:]
    if not tokens:
        return True
    for t in tokens:
        if "$(" in t or "`" in t or "<(" in t or ">(" in t:
            return False  # an unextracted substitution: fail closed
    head = tokens[0]
    if "/" in head:
        base, _, prog = head.rpartition("/")
        if base not in SAFE_BIN_DIRS:
            return False  # a relative path, or a binary outside the system directories
    else:
        prog = head
    args = tokens[1:]
    if prog in NEVER:
        return False
    if prog in ("timeout", "time", "nice", "nohup", "stdbuf", "command", "noglob"):
        return segment_ok(args[1:] if prog == "timeout" and args else args)
    if prog == "env":
        while args and ASSIGN_RE.match(args[0]):
            if not assignment_ok(args[0]):
                return False
            args = args[1:]
        if not args:
            return True
        return not args[0].startswith("-") and segment_ok(args)
    if prog == "export":
        return bool(args) and all(
            NAME_RE.match(a.split("=", 1)[0]) is not None and assignment_ok(a) for a in args)
    if prog == "find":
        return not any(a in FIND_FORBIDDEN for a in args)
    if prog in PLAIN:
        return True
    if prog in FLAGGED:
        longs, shorts = FLAGGED[prog]
        if flags_hit(args, longs, shorts):
            return False
        if prog in POSITIONAL_MAX and len(positionals(args)) > POSITIONAL_MAX[prog]:
            return False
        if prog == "sysctl" and any("=" in a for a in args):
            return False
        if prog == "date" and any(not a.startswith("+") for a in positionals(args)):
            return False  # a bare MMDDhhmm operand sets the clock
        return True
    if prog == "awk":
        return not any(AWK_FORBIDDEN.search(a) for a in args)
    if prog == "sed":
        return sed_ok(args)
    if prog == "git":
        return git_ok(args)
    if prog == "go":
        return bool(args) and (args[0] == "version" or (args[0] == "env" and not flags_hit(args[1:], (), "wu")))
    for name, pattern in PREFIXED:
        if prog == name:
            return re.match(pattern, " ".join(args)) is not None
    if args == ["--version"] and "/" not in head:
        return True
    return False


def _match_paren(s, start):
    """s[start] == '('. Return the index of the matching ')', or None. Quote-aware."""
    depth = 0
    i = start
    n = len(s)
    sq = dq = False
    while i < n:
        c = s[i]
        if sq:
            if c == "'":
                sq = False
        elif dq:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                dq = False
        else:
            if c == "'":
                sq = True
            elif c == '"':
                dq = True
            elif c == "\\":
                i += 2
                continue
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return None


def _strip_subs(cmd, depth):
    """Replace every command/process/arithmetic substitution in `cmd` with a
    placeholder, verifying each command substitution is itself read-only. Returns
    the rewritten string, or None if any substitution is not read-only or the text
    does not parse."""
    out = []
    i = 0
    n = len(cmd)
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
                return None
            inner = cmd[i + 1:j].replace("\\`", "`").replace("\\$", "$")
            if not command_ok(inner, depth + 1):
                return None
            out.append(_PLACEHOLDER)
            i = j + 1
            continue
        if cmd.startswith("$(", i):
            end = _match_paren(cmd, i + 1)
            if end is None:
                return None
            inner = cmd[i + 2:end]
            if not inner.startswith("("):  # a plain '(' opener is arithmetic $(( )), no command
                if not command_ok(inner, depth + 1):
                    return None
            out.append(_PLACEHOLDER)
            i = end + 1
            continue
        if c in "<>" and not dq and cmd.startswith("(", i + 1):
            end = _match_paren(cmd, i + 1)
            if end is None:
                return None
            inner = cmd[i + 2:end]
            if not command_ok(inner, depth + 1):
                return None
            out.append(_PLACEHOLDER)
            i = end + 1
            continue
        out.append(c)
        i += 1
    if sq or dq:
        return None
    return "".join(out)


def _strip_comment(line):
    """`line` without its trailing bash comment: an unquoted `#` at the start of a
    word. Substitutions are already placeholders, so only quotes need tracking."""
    sq = dq = False
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if sq:
            sq = c != "'"
        elif dq:
            if c == "\\":
                i += 1
            elif c == '"':
                dq = False
        elif c == "\\":
            i += 1
        elif c == "'":
            sq = True
        elif c == '"':
            dq = True
        elif c == "#" and (i == 0 or line[i - 1] in " \t;|&()"):
            return line[:i]
        i += 1
    return line


def _header_ok(tokens):
    """A `for NAME [in WORDS]` / `select NAME ...` header runs no command; its words
    are data. Accept the well-formed shapes; reject C-style `for (( ))` and `case`."""
    kw = tokens[0]
    if kw in ("for", "select"):
        if len(tokens) < 2 or not NAME_RE.match(tokens[1]):
            return False
        return len(tokens) == 2 or tokens[2] == "in"
    return False  # `case` headers are not decomposed here; fail closed


def command_ok(cmd, depth=0):
    if depth > 6 or len(cmd) > 10000:
        return False
    cmd = _strip_subs(cmd, depth)
    if cmd is None:
        return False
    # A newline separates commands for bash but is whitespace to `tokenize`, so each
    # line loses its comment and the lines are joined with `;`. `tokenize` knows no
    # comments: a `#` inside a word is part of the word, as in bash. A backslash
    # continuation is not modelled and falls through.
    if re.search(r"\\\r?\n", cmd):
        return False
    cmd = cmd.replace("\r\n", "\n").replace("\r", "\n")
    cmd = " ; ".join(_strip_comment(line) for line in cmd.split("\n"))
    try:
        tokens = tokenize(cmd)
    except ValueError:
        return False
    segments = []
    cur = []
    for t in tokens:
        if t in ALWAYS_DELIM:
            if cur:
                segments.append(cur)
                cur = []
            continue
        if not cur:  # command position: reserved words are structural here only
            if t in WORD_DROP:
                continue
            if t in WORD_COND or t in WORD_HEADER:
                cur = [t]
                continue
        cur.append(t)
    if cur:
        segments.append(cur)
    if not segments:
        return False
    for seg in segments:
        head = seg[0]
        if head in WORD_HEADER:
            if not _header_ok(seg):
                return False
        elif head in WORD_COND:
            rest = seg[1:]
            if rest and rest[0] == "!":
                rest = rest[1:]
            if not rest or not segment_ok(rest):
                return False
        else:
            rest = seg[1:] if head == "!" else seg
            if not rest or not segment_ok(rest):
                return False
    return True


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if payload.get("tool_name") != "Bash":
        return
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if command_ok(cmd):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "read-only command (allow-readonly-bash hook)",
            }
        }))


if __name__ == "__main__":
    main()
