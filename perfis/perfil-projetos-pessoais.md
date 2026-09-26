# Perfil: Projetos Pessoais (sites/SPAs front-end)

Use este perfil quando o projeto for um site estático, uma SPA ou qualquer aplicação que roda 100% no navegador, sem backend próprio (ex.: os projetos de sites com monetização Pix/AdSense, ou o jogo em React/Vite).

## Ajustes ao fluxo padrão (`ORQUESTRADOR.md`)

- **`especialista-automacao` normalmente não entra.** Estes projetos não têm robôs de automação de processo — se aparecer um pedido desse tipo, primeiro confirme com o usuário se é realmente para este projeto ou se é para o contexto de trabalho (ver `perfil-automacao-ecommerce.md`).
- **`critico-seguranca` só entra se houver dado sensível de verdade** (ex.: geração de PDF/Excel com dados que o usuário digitou, formulários que salvam algo em `localStorage`/`IndexedDB`). Para a maioria dos pedidos (ajuste visual, novo cálculo, novo componente), o ciclo de crítica usa só `critico-experiencia` e `critico-qualidade`.
- **`critico-experiencia` deve sempre verificar responsividade mobile** — estes sites são acessados por celular.
- **Sem servidor = sem variável de ambiente de produção.** Qualquer "configuração" (ex.: chave de um serviço de terceiros gratuito) precisa ser algo que o próprio usuário final configura no navegador ou que já vem embutido de forma pública (nunca uma chave secreta).
- **Disciplina de testes é alta neste tipo de projeto** (os projetos existentes já têm dezenas de testes automatizados) — `especialista-testes` deve sempre rodar a suíte completa existente, não só os testes novos, antes de considerar a Fase 3 concluída.

## Debate (Fase 1) — ênfase

`debatedor-simplicidade` deve ser mais rígido aqui: como não há backend, qualquer proposta que exija servidor, banco de dados ou infraestrutura paga deve ser questionada com força — normalmente existe uma solução 100% client-side que resolve o pedido.
