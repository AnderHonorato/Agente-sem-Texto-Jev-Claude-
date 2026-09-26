#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Imprime os cabeçalhos OTLP que um runtime deveria enviar, como um único objeto JSON, e nada mais.

O Claude Code lê o caminho para este script da configuração `otelHeadersHelper`, o roda a cada
uns 29 minutos, e faz parse da sua saída padrão como `{"name": "value"}`. `harness sync` só
escreve essa configuração quando `telemetry.native` nomeia `claude-code` e uma fonte de
cabeçalho está configurada.

Todo valor aqui é uma credencial, então uma falha não imprime **nada de forma alguma** e falha
pelo status de saída: texto na saída padrão seria interpretado como um cabeçalho, e texto no
erro padrão cai em logs dos quais o valor foi deliberadamente mantido fora. As fontes são
aquelas que o exportador usa e nenhuma outra — a variável de ambiente nomeada e o arquivo modo
600 fora de toda árvore de trabalho.

Uma variável só alcança este script se alcançou o runtime que o lançou, o que um cliente
lançado por desktop pode não ter; `headers_file` é a fonte que não depende disso. Veja docs/telemetry.md.
"""
import importlib.util
import json
import sys
from pathlib import Path


def load():
    """As próprias configurações e regras de cabeçalho do exportador, a partir do arquivo ao lado deste."""
    path = Path(__file__).resolve().parent / "telemetry.py"
    spec = importlib.util.spec_from_file_location("harness_telemetry", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    try:
        telemetry = load()
        config = telemetry.settings()
        if "claude-code" not in (config.get("native") or []):
            return 1
        values = telemetry.headers(config)
    except Exception:
        return 1
    if not values:
        return 1
    sys.stdout.write(json.dumps({str(k): str(v) for k, v in sorted(values.items())}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
