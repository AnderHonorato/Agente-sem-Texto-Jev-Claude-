# Perfil: Automação de E-commerce (robôs de tarefas repetitivas)

Use este perfil quando o pedido for sobre um robô/script que automatiza um processo de trabalho recorrente (ex.: sincronizar pedidos, atualizar estoque, gerar relatórios, integrar sistemas, enviar notificações).

## Ajustes ao fluxo padrão (`ORQUESTRADOR.md`)

- **`especialista-automacao` é sempre o especialista principal.** `especialista-frontend` só entra se o robô precisar de algum painel/tela de acompanhamento — não assuma que precisa por padrão.
- **`critico-seguranca` é sempre obrigatório e nunca pode ser pulado**, mesmo que o pedido pareça simples. Automação sem supervisão humana constante é justamente onde um erro pequeno vira dano grande (ex.: duplicar um pedido, cobrar duas vezes, apagar um registro por engano).
- **`debatedor-riscos` deve sempre perguntar explicitamente:**
  1. O que acontece se o sistema de origem ou destino estiver fora do ar no meio da execução?
  2. A ação é reversível? Se não for, existe modo de teste (`--dry-run`) antes de rodar de verdade?
  3. Quem é avisado se o robô falhar silenciosamente (log, alerta, e-mail)?
- **Toda automação nova entra primeiro em modo de teste/observação** antes de rodar "de verdade" e sem supervisão — isso deve estar no plano aprovado na Fase 1, não ser uma sugestão pós-fato do crítico.
- **Frequência e agendamento fazem parte do plano**, não são detalhe de implementação: o `debatedor-arquitetura` já propõe a frequência (ex.: diário, a cada hora) e o `especialista-automacao` implementa exatamente isso.

## Validação final (Fase 5) — checklist obrigatório

Antes de declarar "projeto validado" para qualquer automação deste tipo, confirme que a resposta é "sim" para todos os itens abaixo — senão, volte para o especialista responsável:

- [ ] Nenhuma credencial em texto puro no código.
- [ ] Existe limite de tentativas (retry) em toda chamada externa.
- [ ] Existe log do que foi feito (sem dado sensível no log).
- [ ] Se a ação é irreversível, existe modo de teste (`--dry-run`) documentado.
- [ ] O usuário sabe exatamente quando/com que frequência o robô vai rodar.
