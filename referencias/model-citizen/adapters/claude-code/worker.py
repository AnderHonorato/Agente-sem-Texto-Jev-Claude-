"""As ferramentas do worker Claude são somente leitura; o modo seguro preserva a autenticação nativa."""
import json
import subprocess
from pathlib import Path

# Provedores de nuvem autenticam pelas próprias cadeias de credenciais, o que `claude auth status`
# não relata como um login; um worker sob um deles é lançado sem verificação, como antes.
CLOUD_PROVIDERS = ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")
TOKEN_ONLY = ("refused before launch: the Claude worker would not authenticate. This command runs "
              "inside a Claude Code session, which strips CLAUDE_CODE_OAUTH_TOKEN from its tool "
              "subprocesses, and no other credential or stored login reaches the worker. Run "
              "`harness role run` from a shell that exports CLAUDE_CODE_OAUTH_TOKEN, or log the "
              "client in with `claude auth login` so its stored login is found.")


def identity(original, env):
    """Mantém o home e o usuário do operador, para que o cliente encontre seu login e keychain salvos."""
    env["HOME"] = original.get("HOME", str(Path.home()))
    # A busca nativa do keychain no macOS inclui a identidade do usuário, independentemente do HOME.
    if "USER" in original:
        env["USER"] = original["USER"]
    if "CLAUDE_CONFIG_DIR" in original:
        env["CLAUDE_CONFIG_DIR"] = original["CLAUDE_CONFIG_DIR"]


def refusal(executable, original, env, cwd):
    """Por que um worker lançado a partir deste processo falharia ao autenticar, ou None para lançar.

    Só um processo dentro de uma sessão do Claude Code é verificado (`CLAUDECODE` é definido lá): o
    cliente remove `CLAUDE_CODE_OAUTH_TOKEN` de seus subprocessos de ferramentas, então uma sessão
    só-com-token não entrega nada a um worker. O próprio `auth status` do cliente responde sob o
    ambiente do worker; sua saída nomeia a conta, então ela é analisada apenas em busca de
    `loggedIn` e nunca é impressa ou guardada. Uma verificação que não pode rodar também recusa: o
    token nunca é escrito em lugar nenhum para contornar isso. Ela roda a partir de `cwd`, um
    diretório vazio como o do worker, então nenhuma configuração de projeto responde por ela.
    """
    if not original.get("CLAUDECODE") or any(env.get(name) for name in CLOUD_PROVIDERS):
        return None
    env = dict(env)
    identity(original, env)
    try:
        done = subprocess.run([executable, "auth", "status", "--json"], env=env, cwd=cwd, text=True,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=30)
        logged_in = done.returncode == 0 and json.loads(done.stdout).get("loggedIn") is True
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        return TOKEN_ONLY + " (`claude auth status` could not confirm a login.)"
    return None if logged_in else TOKEN_ONLY


def prepare(executable, work, root, workspace, read_roots, instructions, bindings, original, env):
    # Preserva a descoberta de login/keychain, enquanto os modos seguro/restrito suprimem a personalização do usuário.
    identity(original, env)
    (work / "instructions.md").write_text(instructions)
    command = [executable, "-p", "--safe-mode", "--restricted", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
               "--setting-sources", "", "--tools", "Read,Grep,Glob", "--permission-mode", "dontAsk",
               "--permission-prompts", "none", "--disable-slash-commands", "--no-chrome", "--no-session-persistence",
               # O checkout do harness deliberadamente não é uma raiz de leitura: a política compartilhada
               # chega ao worker como o prompt de sistema, e sua autoridade de skill chega em read_roots.
               "--add-dir", str(workspace), "--output-format", "json",
               "--append-system-prompt-file", str(work / "instructions.md"), "--model", bindings["model"]]
    if bindings.get("effort"):
        command += ["--effort", bindings["effort"]]
    for path in read_roots:
        command += ["--add-dir", str(path)]
    return command


def usage(work, run_dir):
    """Os totais de tokens da execução, a partir do envelope de resultado que `--output-format json` já escreve.

    `--no-session-persistence` não deixa transcrição para ler, então o envelope é a única fonte;
    ele não relata contagem de chamadas de ferramenta, o que o registro portanto deixa desconhecido.
    """
    try:
        envelope = json.loads((run_dir / "stdout.log").read_text())
        counts = envelope["usage"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    if not isinstance(counts, dict):
        return {}
    fields = {"input": "input_tokens", "output": "output_tokens",
              "cache_read": "cache_read_input_tokens", "cache_write": "cache_creation_input_tokens"}
    return {name: int(counts[key]) for name, key in fields.items()
            if isinstance(counts.get(key), int)}


def result(work, run_dir):
    path = run_dir / "stdout.log"
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("resultado nativo excede 1 MiB")
    result = json.loads(path.read_text())
    if not isinstance(result, dict) or result.get("type") != "result" or result.get("subtype") != "success" or result.get("is_error") is not False:
        raise ValueError("o worker Claude não retornou um envelope de resultado bem-sucedido")
    return result.get("result")
