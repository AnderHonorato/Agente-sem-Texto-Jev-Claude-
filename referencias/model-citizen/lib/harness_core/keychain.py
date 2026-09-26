"""O keychain padrão de uma home diferente da do operador, no macOS.

O macOS resolve o keychain padrão sob `HOME`. Um cliente nativo lançado numa home sem um levanta
um diálogo de sistema — "A keychain cannot be found" — cujo botão padrão reseta as configurações
de keychain do operador. Todo lugar que lança um cliente sob um `HOME` substituído passa por este
módulo: `provision` antes de um lançamento pretendido, `missing` antes de um que pode ser pulado.
"""
import os
import platform
import subprocess
from pathlib import Path


def default_path(home):
    return Path(home) / "Library" / "Keychains" / "login.keychain-db"


def missing(home=None, host=None):
    """Se um cliente lançado sob `home` não encontraria keychain padrão nenhum. False fora do macOS."""
    if (host or platform.system()) != "Darwin":
        return False
    return not default_path(home or os.environ.get("HOME") or Path.home()).exists()


def provision(home, host=None):
    """Dá a `home` um keychain padrão descartável próprio; um no-op fora do macOS ou quando um já existe.

    O keychain tem senha vazia e nenhum timeout de bloqueio, então um armazenamento é bem-sucedido
    silenciosamente e nunca toca o keychain de login do operador. Levanta `OSError` quando não
    consegue ser criado.
    """
    if not missing(home, host):
        return None
    path = default_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home))
    created = subprocess.run(["security", "create-keychain", "-p", "", str(path)],
                             capture_output=True, text=True, env=env)
    if created.returncode:
        raise OSError("no keychain for the substituted home, so a client launch would raise a "
                      "system dialog: " + (created.stderr or "").strip()[-200:])
    subprocess.run(["security", "set-keychain-settings", str(path)],
                   capture_output=True, text=True, env=env)
    return path
