#!/usr/bin/env python3
"""Pontua todo detector de regra contra um corpus rotulado e falha abaixo do piso.

Dois corpora, um registro. O wheel vendorizado `ruleprobe` entrega um corpus rotulado para os seis
detectores genéricos que também entrega; `tests/fixtures/detector-corpus/` rotula os treze em
`claude/hooks/rule-detectors.py` que são sobre as próprias regras deste repositório. Os dois são
pontuados com o registro inteiro, então um detector do repositório que dispara no corpus do motor
também é um falso positivo ali, e uma precisão ou recall abaixo do piso é uma saída diferente de
zero.

Um detector sem rótulo em lugar nenhum é uma falha, não uma aprovação: `ruleprobe corpus` passa por
cima de um detector não medido porque não consegue saber de quem é o corpus que está pontuando,
mas aqui toda linha que `harness usage --rules` imprime deve ter uma precisão e um recall
conhecidos, e um novo detector chegando sem um exemplo é a lacuna que este job existe para mostrar.

    python3 scripts/detector_corpus.py [--floor 0.9] [--json]
"""
import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "claude" / "hooks" / "rule-detectors.py"
REPO_CORPUS = ROOT / "tests" / "fixtures" / "detector-corpus"


def rule_pack():
    """O módulo do pacote de regras, que coloca o wheel vendorizado em `sys.path` ao carregar."""
    spec = importlib.util.spec_from_file_location("harness_rule_detectors", str(PACK))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ungated(pack):
    """O registro inteiro com todo gate de postura removido.

    O pontuador roda uma sessão sem posturas, então um detector com gate ficaria desativado sobre
    o corpus e todo positivo para o qual foi rotulado passaria como um erro. O que o corpus mede é
    o julgamento do detector; se uma postura o liga é configuração, e
    `tests/test_rule_detectors.py` guarda essa metade.
    """
    from ruleprobe.registry import Registry

    return Registry([pack.Detector(d.id, d.rule, d.event, d.fn, None)
                     for d in pack.DETECTORS.values()])


def wheel_corpus(into):
    """Onde fica o próprio corpus do motor, desempacotado sob `into` quando necessário.

    O wheel é importado direto de `sys.path` e nunca instalado, então seu corpus é um membro de um
    arquivo zip e não um diretório que algo possa percorrer. O pontuador recebe um caminho, então
    o corpus é extraído para a execução e descartado depois dela.
    """
    import zipfile

    import ruleprobe

    inside = Path(ruleprobe.__file__).resolve().parent / "corpus"
    if inside.is_dir():
        return str(inside)
    for parent in inside.parents:
        if parent.is_file():
            with zipfile.ZipFile(str(parent)) as archive:
                names = [n for n in archive.namelist() if n.startswith("ruleprobe/corpus/")]
                archive.extractall(into, names)
            return str(Path(into) / "ruleprobe" / "corpus")
    raise RuntimeError("the vendored wheel holds no corpus: %s" % inside)


class CorpusRecordError(Exception):
    """Uma entrada de `known_below_floor` que não pode ser verificada contra uma medição."""


def known_below_floor(path):
    """`{detector_id: (floor, precision, recall)}` que o corpus do repositório registra como conhecidamente ruim.

    Um detector que não consegue alcançar o piso num corpus honesto mantém o piso e é anotado aqui
    com a pontuação medida e o piso contra o qual foi medido, em vez de o piso ser abaixado para
    atendê-lo. Os três são comparados, não apenas consultados, então uma entrada que não descreve
    mais o detector falha o job nas duas direções: uma regressão e uma melhora silenciosa são
    ambas notícia. Rodar com um piso mais baixo que o nomeado pela entrada a deixa dormente em vez
    de desatualizada - o registro continua verdadeiro para as execuções de CI com o gate de 0,9,
    seja lá o que um `--floor 0.8` avulso pediu.
    """
    from ruleprobe.declarative import load

    document, _lines = load(str(path))
    return dict((entry["detector"], (float(entry["floor"]), float(entry["precision"]),
                                     float(entry["recall"])))
                for entry in document.get("known_below_floor") or [])


def measured(score):
    """A precisão e o recall de uma pontuação com duas casas, ou uma falha legível.

    Uma entrada de `known_below_floor` para um detector que o corpus não rotula, ou para um id que
    não existe mais, chega aqui como uma linha não pontuada ou como nenhuma linha. Uma linha não
    pontuada ainda responde 1,0 às duas perguntas - um detector que nunca disparou e nunca errou -
    então arredondá-la registraria uma pontuação perfeita para algo que ninguém mediu. Isso é um
    corpus a corrigir, não um número a arredondar.
    """
    if score is None or not score.scored or score.precision is None or score.recall is None:
        raise CorpusRecordError(
            "%s has no measured score; a known_below_floor entry names a detector the corpus "
            "does not label" % (score.detector if score is not None else "the detector"))
    return (round(score.precision, 2), round(score.recall, 2))


def merge(parts):
    """Um `Score` por detector sobre todo corpus pontuado."""
    from ruleprobe.validity import Score

    out = {}
    for scores in parts:
        for detector_id, score in scores.items():
            out.setdefault(detector_id, Score(detector_id)).add(score)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--floor", type=float, default=None, metavar="F",
                        help="falha quando a precisão ou o recall de um detector fica abaixo disso")
    parser.add_argument("--json", action="store_true",
                        help="imprime as pontuações mescladas como JSON em vez das tabelas")
    args = parser.parse_args(argv)

    pack = rule_pack()
    from ruleprobe.validity import (CorpusError, DEFAULT_FLOOR, below_floor, score_corpus,
                                    scores_as_dict, validity_table)

    floor = DEFAULT_FLOOR if args.floor is None else args.floor
    registry = ungated(pack)
    unpacked = tempfile.mkdtemp(prefix="detector-corpus-")
    scores_per_corpus, tables = [], []
    try:
        corpora = [("the wheel's corpus", wheel_corpus(unpacked)),
                   ("this repository's corpus", str(REPO_CORPUS))]
        for title, directory in corpora:
            try:
                scores = score_corpus(registry=registry, directory=directory)
            except CorpusError as exc:
                sys.stderr.write("corpus: %s\n" % exc)
                return 2
            scores_per_corpus.append(scores)
            tables.append("%s\n%s" % (title, validity_table(scores, floor)))
    finally:
        shutil.rmtree(unpacked, ignore_errors=True)

    scores = merge(scores_per_corpus)
    try:
        known = known_below_floor(REPO_CORPUS / "labels.yaml")
        failing = set(below_floor(scores, floor))
        waived, dormant, stale = [], [], []
        for detector_id, record in sorted(known.items()):
            recorded_floor, pair = record[0], (round(record[1], 2), round(record[2], 2))
            now = measured(scores.get(detector_id))
            if now != pair:
                stale.append("%s measures p=%.2f r=%.2f, not the recorded p=%.2f r=%.2f"
                             % ((detector_id,) + now + pair))
            elif now[0] >= recorded_floor and now[1] >= recorded_floor:
                stale.append("%s is recorded as below a %.2f floor and is not"
                             % (detector_id, recorded_floor))
            elif detector_id in failing:
                waived.append("%s p=%.2f r=%.2f" % ((detector_id,) + now))
            else:
                dormant.append("%s is recorded below %.2f, which the %.2f floor in force does "
                               "not ask about" % (detector_id, recorded_floor, floor))
    except CorpusRecordError as exc:
        sys.stderr.write("corpus: %s\n" % exc)
        return 2
    unscored = sorted(did for did, score in scores.items() if not score.scored)
    failed = [did for did in sorted(failing) if did not in known]

    if args.json:
        data = scores_as_dict(scores, floor)
        data.update({"unscored": unscored, "failed": failed,
                     "known_below_floor": sorted(waived), "dormant": sorted(dormant),
                     "stale": sorted(stale)})
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print("\n\n".join(tables))
        print("\nboth corpora, %d detectors" % len(scores))
        print(validity_table(scores, floor))
        for line in waived:
            print("\nknown below the %.2f floor, and recorded as such: %s" % (floor, line))
        for line in dormant:
            print("\n%s" % line)
        if unscored:
            print("\n%d detector(s) with no labelled example: %s"
                  % (len(unscored), ", ".join(unscored)))
        for line in stale:
            print("\nthe known_below_floor entry is out of date: %s" % line)
        if failed:
            print("\n%d detector(s) under the %.2f floor: %s"
                  % (len(failed), floor, ", ".join(failed)))
    return 1 if failed or unscored or stale else 0


if __name__ == "__main__":
    sys.exit(main())
