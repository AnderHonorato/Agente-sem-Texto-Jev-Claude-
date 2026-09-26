"""Pacotes de perguntas versionados: conteúdo, uma versão, e o hash do conteúdo.

Um pacote em `jev.py` é um dict comum, o que é suficiente para enviar e insuficiente para medir.
Uma avaliação que diz "este limiar se sustenta" é uma alegação sobre um conjunto de perguntas,
então o conjunto precisa de um nome e uma versão contra os quais uma execução futura pode ser
comparada, e um hash que diga se as palavras de fato mudaram. `Pack` é essas três coisas, e o
registro abaixo é onde uma versão nomeada é consultada.

Duas propriedades que o dict não tinha. Um pacote é **congelado** na construção: as perguntas são
canonicalizadas uma vez e toda leitura desserializa uma cópia nova, então nada que um chamador
segure — conteúdo de tarefa, um contexto, uma resposta mutada — pode voltar e reescrever um
critério entre o hash ser tirado e a requisição ser construída. E a **identidade de um pacote
viaja com o resultado**: `identity()` é o que `JevProvider` coloca na linha do ledger ao lado do
hash da requisição, então uma linha diz qual versão de qual pacote a produziu em vez de um hash
que ninguém consegue resolver de volta para palavras.
"""
import json
import re
from typing import Any, Dict, List, Optional

from . import jev

ID = re.compile(r"[a-z][a-z0-9-]{0,31}")
# `:` e não `@`: um `id@version` lê como um endereço de e-mail para o próprio lint de dados
# pessoais do repositório, e uma grafia que torna toda menção a um pacote um achado de lint é a errada.
SEPARATOR = ":"
VERSION = re.compile(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}")


class Pack:
    """Um pacote de perguntas nomeado, versionado e congelado.

    `decision=True` também exige as perguntas que `JevProvider.decide` lê, então um pacote que
    deixaria aquele código lendo uma pergunta que ninguém fez é recusado aqui em vez de na
    primeira chamada.
    """

    def __init__(self, pack_id: str, version: str, questions: Any, decision: bool = True):
        if not isinstance(pack_id, str) or not ID.fullmatch(pack_id):
            raise jev.PackError("a pack id is a short lowercase identifier, not " + repr(pack_id))
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            raise jev.PackError("pack " + pack_id + " needs a major.minor.patch version, not "
                                + repr(version))
        check = jev.require_decision_questions if decision else jev.validate_pack
        self._frozen = jev.canonical(check(questions))
        self.pack_id = pack_id
        self.version = version
        self.content_hash = jev.digest(json.loads(self._frozen.decode("utf-8")))

    @property
    def questions(self) -> Dict[str, Any]:
        """Uma cópia nova das perguntas. Mutar o que isto retorna não muda nenhuma leitura futura."""
        return json.loads(self._frozen.decode("utf-8"))

    def identity(self) -> Dict[str, Any]:
        return {"pack_id": self.pack_id, "pack_version": self.version,
                "pack_hash": self.content_hash}

    def key(self) -> str:
        return self.pack_id + SEPARATOR + self.version

    def verify(self, content_hash: str) -> None:
        """Levanta exceção a menos que este pacote ainda seja as palavras sobre as quais `content_hash` foi tirado."""
        if content_hash != self.content_hash:
            raise jev.PackError("pack " + self.key() + " hashes " + self.content_hash
                                + ", not the " + str(content_hash) + " this result was fitted "
                                "against; a threshold does not carry across a pack edit")


REGISTRY = {}


def register(pack: Pack) -> Pack:
    if pack.key() in REGISTRY:
        raise jev.PackError("pack " + pack.key() + " is already registered; a published "
                            "version is never re-pointed, it is superseded by a new one")
    REGISTRY[pack.key()] = pack
    return pack


def _order(version: str):
    return tuple(int(part) for part in version.split("."))


def versions(pack_id: str) -> List[str]:
    """Toda versão registrada de `pack_id`, mais antiga primeiro."""
    return sorted((p.version for p in REGISTRY.values() if p.pack_id == pack_id), key=_order)


def get(pack_id: str, version: Optional[str] = None) -> Pack:
    """Um pacote registrado. Sem versão, a mais alta registrada."""
    if version is None:
        known = versions(pack_id)
        if not known:
            raise jev.PackError("no pack named " + repr(pack_id) + "; known packs are "
                                + (", ".join(sorted(set(p.pack_id for p in REGISTRY.values())))
                                   or "none"))
        version = known[-1]
    pack = REGISTRY.get(pack_id + SEPARATOR + str(version))
    if pack is None:
        raise jev.PackError("pack " + repr(pack_id) + " has no version " + repr(version)
                            + "; registered versions are " + ", ".join(versions(pack_id)))
    return pack


def resolve(name: Optional[str]) -> Pack:
    """`pack_id`, `pack_id:version`, ou None para o pacote de decisão padrão."""
    if not name:
        return get(DECISION_ID)
    pack_id, _, version = str(name).partition(SEPARATOR)
    return get(pack_id, version or None)


DECISION_ID = "decision"
# 1.0.0 é a versão sob a qual o pacote `jev.DECISION_PACK` foi lançado. As palavras vivem lá, não
# aqui: um pacote é um conjunto de palavras, e uma cópia seria um segundo que ninguém edita em sincronia.
DECISION_V1 = register(Pack(DECISION_ID, "1.0.0", jev.DECISION_PACK))
