# Postura de commits: Conventional Commits, pushes com gate

**Conventional Commits em todo commit**, em todo repositório: `type(scope): summary`. **Antes de
dar push, rode o gate de qualidade do repositório no `HEAD`** no checkout exato que você vai
enviar — o que quer que suas instruções de agente nomeiem, ou o que o CI roda se não nomeiam
nada. **Nunca dê push direto para um branch padrão:** crie um branch, abra um PR, mescle através
dele, a menos que um repositório sem gate de revisão diga o contrário. **Sem trailers de
atribuição.** **`AGENTS.md` e `CLAUDE.md` são um único arquivo, com link simbólico**, para que
agentes diferentes não divirjam.
