# Postura de testes: pragmática

Escreva um teste quando ele compra algo: comportamento que já quebrou antes, lógica difícil de
raciocinar apenas lendo, um contrato público do qual outros dependem, e toda correção de bug (um
teste de regressão provando que o bug se foi). Não adicione testes que reafirmam a implementação
ou apenas exercitam um framework. Antes de terminar, rode a suíte do módulo afetado e conserte o
que você quebrou. Siga a convenção de coposicionamento do repositório, leia um teste vizinho
primeiro, e diga claramente no relatório qual comportamento novo está sem teste e por quê.
