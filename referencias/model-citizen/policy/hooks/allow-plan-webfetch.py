#!/usr/bin/env python3
"""Hook de PreToolUse: aprova WebFetch enquanto em modo plano, para que reunir contexto para um
plano não peça confirmação para toda URL de documentação ou referência.

O escopo é deliberadamente estreito: só quando `permission_mode` é `plan`, e só para URLs
`http`/`https`. Todo outro modo mantém seu fluxo de permissão normal, então isso não muda nada
fora do planejamento. Este hook nunca nega.

Por que isso é seguro o bastante para permitir: o modo plano já bloqueia edições, então a busca
não pode mudar nada, e o hook `neutralize-tool-output` ainda escaneia o texto buscado em busca de
conteúdo em forma de instrução antes que alcance o modelo. Não torna as páginas buscadas
confiáveis; remove o prompt para pesquisa somente leitura.

Teste: echo '{"tool_name":"WebFetch","permission_mode":"plan","tool_input":{"url":"https://example.com"}}' | python3 allow-plan-webfetch.py
"""
import json
import sys


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if payload.get("tool_name") != "WebFetch":
        return
    if payload.get("permission_mode") != "plan":
        return
    url = (payload.get("tool_input") or {}).get("url")
    if not isinstance(url, str):
        return
    if not (url.startswith("https://") or url.startswith("http://")):
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "plan-mode web research (allow-plan-webfetch hook)",
        }
    }))


if __name__ == "__main__":
    main()
