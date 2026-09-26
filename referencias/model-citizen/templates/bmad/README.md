# Templates de sobrescrita do BMad

Arquivos seus, no formato de sobrescrita do [BMad Method](https://github.com/bmad-code-org/BMAD-METHOD)
(`_bmad/custom/<skill>.user.toml`), roteando os disparos de subagente do framework pelas
definições de agente do harness, para que a postura `delegation` os alcance. Nada aqui
é uma cópia de um arquivo do framework.

    bin/harness bmad check <repo>   # cada chave e id de camada em relação às skills instaladas
    bin/harness bmad apply <repo>   # instala o que estiver faltando; --force substitui um que difira

O hook `harness-session` roda `check` quando uma sessão começa. A instalação é explícita:
rode `citizen bmad apply` para adicionar templates compatíveis preservando sobrescritas
diferentes. Um template que a skill instalada não declara mais é ignorado, nunca escrito. Veja
a [integração com o BMad](../../docs/bmad.md) para os procedimentos de instalação e compatibilidade.
