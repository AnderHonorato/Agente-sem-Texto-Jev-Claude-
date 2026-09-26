# SPDX-License-Identifier: MIT
"""Se um cliente lançado sob um ambiente preparado conseguiria se autenticar de algum jeito.

Uma sondagem nativa lança seu cliente sob um `HOME` descartável, então só as credenciais nomeadas
no ambiente viajam com ele. Uma máquina ou container cujo único login é uma sessão interativa —
`claude login` escrevendo `.claude/.credentials.json`, `codex login` escrevendo `.codex/auth.json`,
ambos sob a home real do operador — não entrega nada ao cliente, e o cliente espera por um login
que nunca vai receber até o timeout do turno disparar. O custo registrado disso é uma travada de
300 segundos reportada como timeout em vez de como a falha de autenticação que realmente é.

`reachable` responde à mesma pergunta em chamadas do tipo stat: nenhum subprocesso, nenhuma rede,
nenhum valor lido ou registrado. É um check da camada de smoke test determinística, que é
aditiva — não escreve nada sob `compatibility/evidence/`, não aparece em nenhum registro de
catálogo, e uma execução verde nunca é qualificação de cliente nativo.
"""
import os
import sys
from pathlib import Path

# Uma chave ou token que o cliente lê diretamente. A presença é todo o teste; o valor nunca é lido.
# `CLAUDE_CODE_OAUTH_TOKEN` é o token de assinatura de longa duração que `claude setup-token` gera.
API_KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY")
# Ponteiros para um arquivo de credencial. Cada um precisa nomear um path que exista, ou a
# consulta atrás dele trava.
FILE_POINTER_VARS = ("AWS_SHARED_CREDENTIALS_FILE", "AWS_CONFIG_FILE",
                     "GOOGLE_APPLICATION_CREDENTIALS")
# Um login interativo, que fica na home que o realizou e nunca alcança uma descartável.
SESSION_LOGIN_FILES = (Path(".claude") / ".credentials.json", Path(".codex") / "auth.json")
# Todo nome que `reachable` pode retornar. `main` verifica a associação e então imprime uma string
# fixa: qual variável foi encontrada é em si derivada do ambiente, e um chamador que precisa do
# nome chama `reachable` para obtê-lo, em vez de ler a saída padrão.
REPORTABLE_VARS = API_KEY_VARS + ("AWS_PROFILE", "GOOGLE_APPLICATION_CREDENTIALS")


class Unreachable(Exception):
    """Nenhuma credencial que o cliente pudesse usar é alcançável a partir do ambiente preparado."""


def points_at_a_file(value):
    """Se um valor nomeia um arquivo que existe, com qualquer coisa inutilizável contada como ausente.

    `Path.exists()` levanta exceção para um valor que não é sequer um path utilizável — um
    documento JSON colado na variável em vez de um path para um, um nome além do limite do
    sistema — e esse erro carrega o valor na própria mensagem. Nenhuma mensagem aqui pode conter
    um valor: a variável é nomeada e o valor nunca sai desta função.
    """
    try:
        return Path(value).exists()
    except OSError:
        return False


def session_logins(home):
    """Os arquivos de login interativo presentes em `home`, que um `HOME` substituído deixa para trás."""
    return [str(name) for name in SESSION_LOGIN_FILES
            if points_at_a_file(Path(home) / name)]


def reachable(env, home=None):
    """Nomeia a credencial que um cliente lançado sob `env` usaria, ou levanta `Unreachable`.

    `home` é a home real a partir da qual o ambiente foi construído, usada apenas para dizer por
    que nada viajou.
    """
    for name in FILE_POINTER_VARS:
        value = env.get(name)
        if value and not points_at_a_file(value):
            raise Unreachable("%s names a file that does not exist; unset it or point it at a "
                              "real credential file" % name)
    for name in API_KEY_VARS:
        if env.get(name):
            return name
    if env.get("AWS_PROFILE"):
        if any(env.get(name) for name in ("AWS_SHARED_CREDENTIALS_FILE", "AWS_CONFIG_FILE")):
            return "AWS_PROFILE"
        raise Unreachable("AWS_PROFILE is set but neither AWS_SHARED_CREDENTIALS_FILE nor "
                          "AWS_CONFIG_FILE points into the home the profile lives in")
    if env.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return "GOOGLE_APPLICATION_CREDENTIALS"
    held = session_logins(home if home is not None else os.path.expanduser("~"))
    if held:
        raise Unreachable("this home holds only an interactive session login (%s), which does not "
                          "travel into the disposable home the probe launches under; export an API "
                          "key or a cloud profile instead" % ", ".join(held))
    raise Unreachable("no API key, cloud profile or session login is reachable; the client would "
                      "wait on a login prompt until the turn timeout")


def main():
    """Reporta que uma execução de sondagem tem uma credencial. Sai com 1 e o motivo quando não há nenhuma.

    A linha verde é uma string fixa de propósito: ela não nomeia a variável que respondeu.
    `reachable` só retorna um membro de uma tupla constante em nível de módulo e nunca um valor
    lido do ambiente, mas o CodeQL lê qualquer saída que diga qual variável respondeu como
    registro em texto claro de dados sensíveis, em severidade alta, e três formas de nomeá-la
    foram sinalizadas antes que a string fixa limpasse o alerta. Uma varredura limpa sem
    dispensas foi julgada valer mais do que o nome no stdout; um chamador que precisa dele chama
    `reachable` diretamente, e o caminho de falha no stderr ainda carrega o motivo completo.
    """
    try:
        found = reachable(dict(os.environ))
    except Unreachable as error:
        print("credentials: unreachable: %s" % error, file=sys.stderr)
        return 1
    if found not in REPORTABLE_VARS:
        print("credentials: unreachable: the reachable credential is not a reportable variable",
              file=sys.stderr)
        return 1
    print("credentials: reachable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
