# Política de compatibilidade e lançamento

A versão 1 protege as interfaces das quais um usuário ou integração precisa depender, deixando os
detalhes de implementação livres para melhorar. Uma alegação de compatibilidade se aplica ao
próprio Model Citizen; ela não pode prometer que um runtime externo, provedor de modelo ou cliente
vai preservar comportamento fora do controle do harness. O [catálogo de compatibilidade](compatibility.md)
versionado registra o que foi de fato observado.

## Interfaces públicas estáveis

O versionamento semântico se aplica a estas interfaces documentadas a partir da v1.0.0:

- comandos, opções, significado de sucesso de saída e campos JSON legíveis por máquina do
  `harness` documentados;
- chaves de configuração do usuário, tipos de valor, precedência e as regras de posse/conflito
  usadas para mesclar configurações nativas;
- o contrato de autoria de primitivos para regras, dimensões e variantes de postura, skills,
  papéis e workflows;
- contratos versionados de adaptador e processo, incluindo nomes de capacidade e identidades de
  requisição;
- os significados de status e requisitos de evidência do catálogo de compatibilidade;
- comportamento de posse, prévia, migração, rollback e desinstalação de arquivos gerenciados; e
- o piso de suporte estável nomeado pelo catálogo de compatibilidade do lançamento.

Texto legível por humanos, ordenação e espaçamento não são estáveis, a menos que uma página diga o
contrário. Módulos Python internos, funções auxiliares, locks, caches, fixtures de teste,
artefatos de planejamento e estado não documentado são detalhes de implementação. Arquivos nativos
gerados podem mudar de forma enquanto seu comportamento efetivo documentado, posse e garantias de
migração permanecem compatíveis. O formato de configuração privada de um runtime nativo não é uma
API do harness.

Capacidades em prévia podem ser lançadas sob um rótulo explícito. Elas ainda recebem posse segura
e comportamento de preservação de dados, mas o formato de sua funcionalidade e o status de suporte
nativo não são cobertos pela promessa estável da v1. A promoção para estável exige uma decisão de
lançamento e evidência nativa.

## Regras de versionamento

- Lançamentos **patch** restauram comportamento documentado, corrigem defeitos de segurança ou de
  preservação de dados, atualizam evidência e documentação, ou restringem uma alegação que fatos
  externos tornaram falsa. Não exigem que um usuário altere uma configuração válida.
- Lançamentos **minor** adicionam comandos, campos opcionais, primitivos, adaptadores ou clientes
  suportados de forma retrocompatível. Comportamento novo tem como padrão ficar inativo ou
  preservar o comportamento efetivo anterior.
- Lançamentos **major** podem remover uma interface estável, rejeitar uma configuração antes
  válida, mudar o comportamento efetivo de um padrão documentado, reduzir o piso de suporte
  estável por escolha de produto, ou exigir uma migração que não pode ser realizada de forma
  segura e reversível pelo harness.

Mudar um hook aplicado, uma projeção de permissão ou um limite de posse é classificado pelo seu
efeito observável, não pelo tamanho do diff. Um padrão supostamente aditivo que muda o
comportamento de agente de um usuário existente é quebra de compatibilidade, a menos que seja
opt-in.

## Depreciação e remoção

Uma interface estável é depreciada antes de ser removida. A depreciação nomeia o substituto, a
configuração ou comando afetado, o procedimento de migração, a primeira versão depreciada e a
versão de remoção mais antiga possível. As notas de lançamento e a página de referência relevante
carregam o aviso; diagnósticos avisam quando o harness consegue identificar uso afetado sem coletar
telemetria.

A remoção normalmente espera até o próximo lançamento major e pelo menos 90 dias após o aviso
publicado. Um lançamento minor pode parar de gerar uma forma depreciada apenas quando instalações
existentes são migradas automaticamente e de forma reversível enquanto a entrada antiga continua
sendo aceita. Interfaces em prévia podem mudar em um lançamento minor, com orientação de migração
sempre que estado possuído pelo usuário for afetado.

## Migração de configuração e de arquivos gerados

A migração começa com uma prévia. Ela identifica chaves e arquivos possuídos, conflitos de adoção,
backups e a configuração efetiva resultante antes de escrever. O harness deve preservar
configurações nativas não relacionadas, arquivos do usuário, backups adotados e estado de conflito
visível. Uma migração falha ou interrompida se recupera para o estado prévio completo ou para o
estado novo completo; estado parcial ambíguo é relatado e nunca tratado como sucesso.

As notas de lançamento afirmam **Nenhuma ação de migração necessária** ou listam a ação exata e o
caminho de recuperação. Quando ação é necessária, elas linkam o guia versionado relevante. O
rollback restaura o executável ou checkout anterior, as projeções gerenciadas e o diário de posse
sem apagar dados não relacionados. A desinstalação remove apenas a saída possuída pelo harness e
relata o estado do usuário que foi retido.

## Exceções de segurança e de runtime externo

Uma vulnerabilidade confirmada, exposição de credencial ou defeito de perda de dados pode exigir
remoção ou desativação imediata sem o período de aviso normal. Use a menor mudança segura, publique
um aviso de segurança e os passos de migração ou contenção, e emita uma nova versão; nunca mova
uma tag existente. Restrições legais podem exigir o mesmo tratamento.

Quando um provedor ou runtime nativo muda de comportamento fora do harness, atualize o catálogo e a
alegação pública assim que a evidência mudar. Um lançamento patch pode marcar um cliente como não
qualificado ou adicionar uma limitação, porque continuar uma alegação de suporte falsa não é
compatibilidade. Restaurar ou substituir esse suporte segue as regras normais de minor/major, de
acordo com as mudanças de harness exigidas.

## Lançamentos falhos e parciais

Tags e artefatos publicados são imutáveis. Se a publicação falhar depois que uma tag já existe,
registre quais superfícies foram concluídas, pare, corrija a causa e publique uma nova versão sob
esta política. Não redirecione, apague e recrie, nem substitua silenciosamente uma tag ou ativo.

A transação de lançamento publica em ordem: tag de origem e artefato verificados, depois metadados
do repositório. Os metadados do repositório retrocedem reaplicando o `product.json` do lançamento
anterior. Um lançamento corretivo repete a qualificação, o ciclo de vida e as portas de auditoria
afetados; o lançamento anterior permanece como registro histórico. As notas de lançamento sempre
linkam esta política e afirmam as ações de migração.
