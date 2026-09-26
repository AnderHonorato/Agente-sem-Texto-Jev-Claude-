"""Provedores de decisão que respondem à interface de `harness_core.decision` sobre um transporte.

O contrato em si — `Action`, `Decision`, `DecisionProvider`, e os provedores `none` e `local`
que não precisam de transporte — vive em `harness_core.decision`. Um módulo aqui implementa
esse contrato contra algo fora deste processo, então um provedor que precisa importar o
contrato não pode ser importado por ele: `decision.select_provider` os carrega preguiçosamente
por nome.
"""
