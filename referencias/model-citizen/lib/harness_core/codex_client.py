"""Qual grafia da chave de revisor de aprovação do Codex o cliente instalado realmente aceita.

A promessa da postura `auto` é que o Codex revisa seus próprios pedidos de aprovação. O Codex
expressa isso como uma única chave de configuração, e uma chave que este cliente não reconhece é
descartada em silêncio: a postura então resolve como revisão pelo usuário, sem nada dito. Por isso
o nome é lido do cliente em vez de suposto, e um cliente que não reconhece nenhuma das duas
grafias é reportado em vez de receber uma escrita.

Duas sondagens, em ordem, ambas offline e nenhuma iniciando um turno de modelo:

1. o próprio schema de protocolo do cliente (`codex app-server generate-json-schema`), cuja
   definição `Config` lista os campos de configuração que este build desserializa;
2. faltando isso, `codex app-server --listen off --strict-config` contra um `CODEX_HOME`
   descartável contendo uma chave candidata, que reporta `unknown configuration field` para um
   nome que o build não conhece e falha no transporte ausente assim que a config foi parseada.

Medido no macOS contra codex-cli 0.154.0-alpha.6.2, 0.155.0-alpha.9, 0.155.1 e
0.156.0-alpha.9: todos eles desserializam `approvals_reviewer` (valores `user`,
`auto_review`, `guardian_subagent`) e rejeitam `approval_reviewer` sob `--strict-config`,
registrando-o como configuração ignorada nos demais casos. Nenhuma versão suportada quer a
grafia antiga, então nenhuma das duas é escrita ao mesmo tempo; a obsoleta é removida em vez disso.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Grafia mais recentemente aceita primeiro. Todo nome aqui pertence ao harness onde quer que seja
# encontrado numa config do Codex: remover o que não é mais desejado é parte de escrever o que é.
REVIEWER_KEYS = ("approvals_reviewer", "approval_reviewer")
REVIEWER_VALUES = {"auto": "auto_review", "manual": "user"}
TIMEOUT = 30


class Reviewer:
    """O que o cliente instalado aceita, e a evidência para afirmá-lo.

    `status` é `detected` (o cliente nomeou uma chave), `absent` (nenhum cliente para perguntar),
    `unsupported` (o cliente não reconhece nenhuma das grafias) ou `unprobed` (um cliente que não
    pôde ser questionado). `key` é None apenas quando nada deve ser escrito.
    """

    def __init__(self, status, key, detail, version=None):
        self.status = status
        self.key = key
        self.detail = detail
        self.version = version

    @property
    def reliable(self):
        return self.status in ("detected", "absent")

    def __repr__(self):  # pragma: no cover - apenas diagnóstico
        return "Reviewer(%r, %r, %r)" % (self.status, self.key, self.detail)


def _run(argv, home, timeout=TIMEOUT):
    environment = dict(os.environ, CODEX_HOME=str(home))
    environment.pop("RUST_LOG", None)
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                            env=environment)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def _version(executable, home):
    try:
        code, text = _run([executable, "--version"], home, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return text.strip().splitlines()[0] if code == 0 and text.strip() else None


def _from_schema(executable, home):
    """A chave que este build desserializa, lida do próprio schema de protocolo emitido por ele."""
    with tempfile.TemporaryDirectory() as out:
        try:
            _run([executable, "app-server", "generate-json-schema", "--out", out], home)
        except (OSError, subprocess.SubprocessError):
            return None
        schema = Path(out) / "v2" / "ConfigReadResponse.json"
        if not schema.is_file():
            return None
        try:
            definitions = json.loads(schema.read_text(encoding="utf-8"))["definitions"]
            fields = definitions["Config"]["properties"]
        except (ValueError, KeyError, OSError):
            return None
    return [key for key in REVIEWER_KEYS if key in fields]


def _from_strict_config(executable, root):
    """As chaves que este build parseia, perguntadas uma a uma sob `--strict-config`.

    Silêncio não é aceitação: a sondagem conta uma chave como parseada só quando o cliente chega
    longe o bastante para reclamar do transporte que esta chamada deliberadamente omite. Qualquer
    outra resposta deixa a pergunta em aberto, o que é reportado em vez de adivinhado.
    """
    accepted = []
    for key in REVIEWER_KEYS:
        home = Path(root) / ("probe-" + key)
        home.mkdir(parents=True, exist_ok=True)
        (home / "config.toml").write_text('%s = "auto_review"\n' % key, encoding="utf-8")
        try:
            _, text = _run([executable, "app-server", "--listen", "off", "--strict-config"], home)
        except (OSError, subprocess.SubprocessError):
            return None
        if "unknown configuration field" in text and key in text:
            continue
        if "no transport configured" in text:
            accepted.append(key)
            continue
        return None
    return accepted


def detect(executable=None):
    """Pergunta ao cliente Codex instalado qual chave de revisor de aprovação ele aceita.

    Nenhum cliente não é uma falha: a grafia suportada mais recente é escrita, porque a config é
    para qualquer cliente que o usuário instale a seguir. Um cliente que não responde a nenhuma
    sondagem é reportado.
    """
    executable = executable or shutil.which("codex")
    if not executable:
        return Reviewer("absent", REVIEWER_KEYS[0],
                        "no codex client on PATH; wrote %s, the key the newest supported "
                        "version accepts" % REVIEWER_KEYS[0])
    with tempfile.TemporaryDirectory() as root:
        version = _version(executable, root)
        if version is None:
            return Reviewer("unprobed", REVIEWER_KEYS[0],
                            "codex at %s did not report a version; wrote %s unverified"
                            % (executable, REVIEWER_KEYS[0]))
        schema, source = _from_schema(executable, root), "its protocol schema"
        accepted = schema
        if not accepted:
            accepted = _from_strict_config(executable, root)
            source = "--strict-config"
        if accepted is None and schema is not None:
            accepted, source = schema, "its protocol schema"
        if accepted is None:
            return Reviewer("unprobed", REVIEWER_KEYS[0],
                            "%s could not be asked which approval-reviewer key it accepts; "
                            "wrote %s unverified" % (version, REVIEWER_KEYS[0]), version)
        if not accepted:
            return Reviewer("unsupported", None,
                            "%s accepts neither %s nor %s (%s), so no approval-reviewer key was "
                            "written; this client cannot route approvals automatically"
                            % (version, REVIEWER_KEYS[0], REVIEWER_KEYS[1], source), version)
        key = next(k for k in REVIEWER_KEYS if k in accepted)
        return Reviewer("detected", key, "%s accepts %s (%s)" % (version, key, source), version)
