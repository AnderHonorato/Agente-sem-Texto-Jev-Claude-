# Jev — Framework de agentes para Claude Code

Um conjunto de **agentes e prompts** (nenhum servidor próprio) que faz o Claude Code trabalhar em fases: agentes debatem a melhor abordagem, especialistas executam cada um na sua área sem se atropelar, e agentes críticos independentes auditam o resultado antes de considerar o projeto pronto.

Inspirado em duas ideias:
- **[Keel](https://github.com/codejunkie99/keel)**: o "Jev", um seletor que decide qual agente de IA executa cada tarefa e valida a escolha antes de aplicar.
- **[model-citizen](https://github.com/JakeSelby/model-citizen)**: papéis nomeados com escopo bem definido e revisão por um agente que não escreveu o código.

Serve tanto para projetos pessoais de front-end (sites, SPAs) quanto para automações/robôs de trabalho (ex.: tarefas repetitivas de e-commerce). Veja o fluxo completo em [`docs/fluxo-jev.md`](docs/fluxo-jev.md) e o prompt do orquestrador em [`ORQUESTRADOR.md`](ORQUESTRADOR.md).

## O que tem aqui

```
├── ORQUESTRADOR.md          → o prompt-mestre que o modelo Opus 5.5 segue como orquestrador
├── .claude/
│   ├── agents/               → debatedores, especialistas e críticos (prontos para usar)
│   └── commands/jev.md       → o comando /jev que dispara o ciclo inteiro
├── docs/fluxo-jev.md         → explicação detalhada do ciclo, com diagrama
├── perfis/                   → ajustes de escopo por tipo de projeto (site pessoal vs. automação)
└── referencias/               → os dois projetos que inspiraram o Jev, trazidos para o repositório
    ├── model-citizen/         → cópia funcional traduzida para PT-BR (código intacto, textos traduzidos)
    ├── keel-explicado.md      → resumo em português da arquitetura do Keel (sem código, é app só de Mac)
    └── README.md              → créditos e licenças dos dois projetos originais
```

Nada aqui roda sozinho — é configuração e prompts para o **Claude Code**, que você já usa (CLI, app desktop ou app web).

---

## Como instalar num projeto

1. Copie as pastas `.claude/agents/`, `.claude/commands/jev.md`, o arquivo `ORQUESTRADOR.md` e a pasta `perfis/` para dentro do repositório do projeto onde você quer usar o Jev (ex.: `site-de-renda-passiva`, `roleta-a-dois-`, ou o repositório dos robôs do trabalho).
2. Se o projeto já tem uma pasta `.claude/agents/`, apenas adicione os novos arquivos `.md` — eles não conflitam com agentes que já existirem lá, desde que os nomes sejam diferentes.
3. Pronto. Não precisa instalar dependência nenhuma, não precisa configurar servidor, não precisa de chave de API separada (o Claude Code já usa a sua sessão normal).

## Como usar

Dentro do Claude Code, no projeto onde você instalou o Jev:

```
/jev "descrição do que você quer que seja feito"
```

Exemplos:

```
/jev "adicionar um cupom de desconto no cálculo de orçamento da confeitaria"
/jev "criar um robô que baixa os pedidos novos de uma planilha e atualiza o status no sistema interno todo dia de manhã"
```

O orquestrador vai:
1. Rodar o debate de plano (você vê um resumo antes de qualquer código ser escrito).
2. Dividir o trabalho entre especialistas sem que um pise no espaço do outro.
3. Rodar a crítica cruzada — se algo for reprovado, ele corrige sozinho e reavalia.
4. Te avisar quando o projeto estiver validado, com um resumo do que mudou.

Para pedidos pequenos e sem ambiguidade (um ajuste de texto, uma correção pontual), o próprio orquestrador simplifica o ciclo — veja a seção 8 de `ORQUESTRADOR.md`.

---

## Como rodar no PC

Se você ainda não tem o Claude Code instalado:

```bash
npm install -g @anthropic-ai/claude-code
```

Depois, dentro da pasta do projeto:

```bash
claude
```

E use o comando `/jev "..."` normalmente dentro da sessão.

## Como usar pelo celular (na rede/internet)

O jeito mais simples e que já funciona sem configurar nada extra: abra **[claude.ai/code](https://claude.ai/code)** no navegador do celular, entre com a mesma conta que você usa no PC, e abra (ou continue) uma sessão apontando para o mesmo repositório. Isso funciona pela internet — o celular não precisa estar na mesma rede Wi-Fi do PC, só ter conta e repositório conectados.

Assim você pode, por exemplo, disparar `/jev "..."` do celular enquanto está fora de casa, e conferir o resultado depois no PC (ou vice-versa) — a sessão e os arquivos ficam no repositório, não presos numa máquina só.

### Se você quiser controlar uma sessão do PC pelo celular, na mesma rede Wi-Fi (opcional)

Isso é um cenário mais avançado e **não é necessário** para usar o Jev — só documentado aqui como alternativa para quem já tem esse hábito:

1. Instale algo como o [Tailscale](https://tailscale.com/) (gratuito para uso pessoal) no PC e no celular, na mesma conta.
2. Isso cria uma rede privada entre os dois aparelhos, funcionando mesmo em redes Wi-Fi diferentes (não precisa nem estar na mesma rede local).
3. Com os dois conectados, você consegue acessar um terminal do PC pelo celular (ex.: via um app de SSH/terminal) e rodar o Claude Code lá dentro normalmente.

Isso é opcional e não faz parte do funcionamento padrão do Jev — o caminho recomendado continua sendo o `claude.ai/code` pelo navegador do celular.

---

## Perguntas frequentes

**Preciso pagar por algo além da minha assinatura do Claude?**
Não. Este repositório é só configuração (arquivos `.md`) — não há custo adicional, servidor ou API própria.

**Posso usar isso em qualquer projeto meu?**
Sim. Os agentes genéricos (`especialista-frontend`, `especialista-logica-dados`, `especialista-automacao`, `especialista-testes`) e os críticos cobrem a maioria dos casos. Use os arquivos em `perfis/` para ajustar o comportamento conforme o tipo de projeto (site pessoal vs. automação de trabalho).

**E se eu quiser adicionar um especialista novo (ex.: para um assunto bem específico do meu trabalho)?**
Copie um dos arquivos em `.claude/agents/especialista-*.md` como modelo, ajuste a descrição e o escopo, e adicione o novo especialista ao mapeamento de críticos em `ORQUESTRADOR.md` (seção 6) para que ele também passe por uma crítica antes de ser considerado pronto.
