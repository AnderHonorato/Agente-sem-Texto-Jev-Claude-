"""A configuração do worker Codex é isolada das configurações do pai e do projeto."""
import json
from pathlib import Path
import re
from harness_core import reconcile


def prepare(executable, work, root, workspace, read_roots, instructions, bindings, original, env):
    source = Path(original.get("CODEX_HOME", str(Path(original.get("HOME", str(Path.home()))) / ".codex")))
    native = reconcile.tomlkit.parse((source / "config.toml").read_text()).unwrap() if (source / "config.toml").is_file() else {}
    home = work / "codex"
    home.mkdir(mode=0o700)
    env["CODEX_HOME"] = str(home)
    if (source / "auth.json").is_file():
        (home / "auth.json").symlink_to((source / "auth.json").resolve())
    provider = native.get("model_provider", "openai")
    if not isinstance(provider, str) or not provider:
        raise ValueError("provedor de modelo nativo inválido")
    config = {"model": bindings["model"], "model_provider": provider,
              "developer_instructions": instructions, "sandbox_mode": "read-only", "approval_policy": "never",
              "agents": {"enabled": False}, "web_search": "disabled", "mcp_servers": {},
              "apps": {"_default": {"enabled": False}}, "shell_environment_policy": {"inherit": "none"},
              "allow_login_shell": False,
              "features": {"apps": False, "multi_agent": False, "remote_plugin": False, "image_generation": False,
                           "in_app_local_automation": False, "in_app_browser": False, "goals": False,
                           "memories": False, "shell_snapshot": False}}
    if "model_reasoning_effort" in bindings:
        config["model_reasoning_effort"] = bindings["model_reasoning_effort"]
    if provider in native.get("model_providers", {}):
        selected = native["model_providers"][provider]
        if not isinstance(selected, dict):
            raise ValueError("definição de provedor nativo inválida")
        if any(key in selected for key in ("http_headers", "experimental_bearer_token")):
            raise ValueError("as credenciais do provedor do worker devem usar referências de ambiente, não cabeçalhos ou tokens embutidos")
        allowed = {"name", "base_url", "env_key", "env_key_instructions", "wire_api", "requires_openai_auth",
                   "env_http_headers", "supports_websockets", "request_max_retries", "stream_max_retries", "stream_idle_timeout_ms"}
        if set(selected) - allowed:
            raise ValueError("o provedor do worker tem configurações de conexão não suportadas")
        config["model_providers"] = {provider: selected}
        if not isinstance(selected.get("env_http_headers", {}), dict):
            raise ValueError("referências de cabeçalho de ambiente do provedor inválidas")
        keys = [selected.get("env_key")] + list(selected.get("env_http_headers", {}).values())
        for key in keys:
            if key is not None and (not isinstance(key, str) or not key):
                raise ValueError("referência de ambiente de credencial do provedor inválida")
            if key is not None and (not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
                                    or key in {"HOME", "PATH", "SHELL", "ENV", "BASH_ENV", "ZDOTDIR", "TMPDIR"}
                                    or key.startswith(("CODEX_", "XDG_", "LD_", "DYLD_", "NODE_", "PYTHON"))):
                raise ValueError("a referência de credencial do provedor não pode sobrepor as configurações de execução do worker")
            if key in original:
                env[key] = original[key]
    elif provider != "openai":
        raise ValueError("o provedor nativo selecionado não tem definição de conexão explícita")
    (home / "config.toml").write_text(reconcile.tomlkit.dumps(config))
    return [executable, "exec", "--ephemeral", "--strict-config", "--ignore-rules", "--skip-git-repo-check",
            "--cd", str(work / "cwd"), "--sandbox", "read-only", "--json", "-o", str(work / "result.md"), "-"]


def usage(work, run_dir):
    """Os totais de tokens da execução, a partir do stream de eventos `--json` que o worker já escreveu.

    O Codex relata totais cumulativos, então o último snapshot é o da execução, nunca uma soma
    deles; seu `input_tokens` inclui a parcela em cache, que é subtraída assim como faz o leitor
    de transcrição. O stream não relata contagem de chamadas de ferramenta, o que o registro
    deixa desconhecido.
    """
    totals = None
    try:
        lines = (run_dir / "stdout.log").read_text(errors="replace").splitlines()
    except OSError:
        return {}
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        for scope in (event, event.get("msg"), event.get("payload"), event.get("info")):
            info = scope.get("info") if isinstance(scope, dict) else None
            found = (info or {}).get("total_token_usage") if isinstance(info, dict) else None
            if isinstance(found, dict):
                totals = found
    if not totals:
        return {}
    cached = totals.get("cached_input_tokens")
    served = totals.get("input_tokens")
    out = {}
    if isinstance(served, int) and isinstance(cached, int):
        out["input"], out["cache_read"] = max(0, served - cached), cached
    if isinstance(totals.get("output_tokens"), int):
        out["output"] = totals["output_tokens"]
    return out


def result(work, run_dir):
    if (work / "result.md").stat().st_size > 1024 * 1024:
        raise ValueError("resultado nativo excede 1 MiB")
    return (work / "result.md").read_text()
