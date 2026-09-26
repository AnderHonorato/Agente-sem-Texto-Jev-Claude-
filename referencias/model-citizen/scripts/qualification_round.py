#!/usr/bin/env python3
"""Conduz uma rodada de qualificação por seus alvos, a partir de um diretório de rodada provisionado.

O driver que rodava cada rodada vivia só numa cópia de rascunho por rodada, então toda rodada o
reescrevia e nenhuma duas rodadas eram conduzidas exatamente da mesma forma. Este é esse driver,
versionado: ele roda o nível determinístico de fumaça (smoke) uma vez, depois
`scripts/native_acceptance.py` por alvo a partir do clone congelado, e escreve um registro por
alvo ao lado de um resumo que um operador lê.

Um nível de fumaça que não passa, falhou ou expirou, para a rodada antes de qualquer alvo rodar:
o nível não gasta nenhum turno de modelo, então uma rodada que teria falhado é recusada antes de
um ser gasto. O registro da rodada nomeia o resultado do nível e por que nada rodou.
`--skip-smoke`, para um nível já rodado verde neste commit, é registrado como `skipped` e roda
todo alvo.

Além do nível ele não decide nada. O veredito de um alvo é o do runner, um alvo que falha não para
os outros — uma rodada coleta os defeitos de todo alvo antes de qualquer um deles ser corrigido,
que é a regra em docs/releasing.md — e o status de saída é 0 só quando o nível passou ou foi
pulado e todo caso de todo alvo passou.

    python3 scripts/qualification_round.py --round ../round-0.13.0 --targets claude-code-cli-macos
    python3 scripts/qualification_round.py --round ../round-0.13.0 --plan
    python3 scripts/qualification_round.py --round ../round-0.13.0 --execution-class light

Cada alvo carrega uma classe de execução e uma classe de avaliação, resolvidas antes de qualquer
coisa ser lançada e registradas com a rodada; `harness_core.qualification` guarda as regras e as
duas recusas.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_core import qualification  # noqa: E402
from native_acceptance import (CLIENTS, catalog, confirmed_targets,  # noqa: E402
                               executed_by, host_mismatch, unobserved_note)

SMOKE = "smoke_tier.py"
RUNNER = "native_acceptance.py"
PASSED = "passed"
SKIPPED = "skipped"
RUNNING = "running"
ROUND_TIMEOUT = 5400


def provision_record(round_dir):
    path = Path(round_dir) / "provision.json"
    if not path.is_file():
        raise SystemExit("no provision record at %s; run scripts/qualification_provision.py first"
                         % path)
    return json.loads(path.read_text())


def environment(report):
    """O ambiente do operador, inalterado: nenhum caso obrigatório lê nada que a rodada adiciona.

    As credenciais que um cliente usa são as do operador e são repassadas pelo nome pelo próprio
    runner. Um checkout do BMad provisionado é para a suíte de integração opcional, rodada
    manualmente.
    """
    import os
    return dict(os.environ)


def smoke(clone, env, targets=()):
    """O nível determinístico, ou `None` quando ele passa do próprio prazo da rodada.

    O nível verifica as precondições dos alvos que esta rodada roda e nenhum outro, então uma
    rodada que deixa um alvo de fora não falha pelo login ou daemon ausente daquele alvo.
    """
    argv = [sys.executable, str(Path(clone) / "scripts" / SMOKE)]
    if targets:
        argv += ["--targets", ",".join(targets)]
    try:
        return subprocess.run(argv, cwd=str(clone), env=env, check=False, timeout=ROUND_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None


def nothing_observed(reason):
    """O registro de um alvo quando o runner não escreveu nenhum: todo caso obrigatório, não observado.

    Um `--out` ausente é o único formato que nunca pode ser lido como o de uma execução anterior:
    um runner que morreu antes de escrever não deixou nenhuma leitura, e relatar o arquivo
    desatualizado publicaria uma aprovação antiga como sendo desta rodada.
    """
    cases = dict((name, "unverified") for name in catalog()["required_cases"])
    return {"cases": cases, "observations": [reason]}


def target_argv(clone, client, model, out, confirmed, routing):
    """O próprio argv do runner para um alvo; a confirmação é repassada só por alvo.

    Sem um `--model` do operador, o modelo de execução roteado do alvo é passado, então o runner
    executa no modelo que a rodada declara; só um alvo cuja classe o adaptador deixa sem
    mapeamento alcança o padrão do próprio runner.
    """
    argv = [sys.executable, str(Path(clone) / "scripts" / RUNNER), "--client", client,
            "--out", str(out), "--execution-class", routing["execution_class"],
            "--assessment-class", routing["assessment_class"]]
    model = model or (routing.get("execution_model")
                      if routing.get("model_source") != "runner default" else None)
    if model:
        argv += ["--model", model]
    if client in confirmed_targets(confirmed):
        argv += ["--home-confirmed", client]
    return argv


def routing(targets, execution, assessment):
    """Um par de classes por alvo, resolvido antes de qualquer coisa ser lançada.

    Um par recusado para a rodada inteira em vez do alvo que o pediu: o registro da rodada, senão,
    diria duas coisas diferentes sobre quem leu sua evidência.
    """
    try:
        executes = qualification.parse_class_map(execution, targets,
                                                 qualification.EXECUTION_DEFAULT,
                                                 "--execution-class", CLIENTS)
        assesses = qualification.parse_class_map(assessment, targets,
                                                 qualification.ASSESSMENT_DEFAULT,
                                                 "--assessment-class", CLIENTS)
        return dict((client, qualification.resolve(ROOT, CLIENTS[client]["runtime"],
                                                   executes[client], assesses[client]))
                    for client in targets)
    except ValueError as error:
        raise SystemExit(str(error))


def with_models(tier_routing, model):
    """O roteamento de cada alvo reafirmado com o modelo que será passado ao seu runner.

    O runner reafirma seu próprio roteamento pela mesma regra, `native_acceptance.executed_by`, a
    partir do `--model` que esta rodada lhe passa, para que o registro da rodada e o registro do
    alvo concordem.
    """
    return dict((client, executed_by(routes, model or routes.get("execution_model"))[1])
                for client, routes in tier_routing.items())


def where(client):
    """Onde os casos de um alvo rodam, lido a partir da mesma comparação em que o runner recusa."""
    if not host_mismatch(client):
        return "runs on this host"
    if CLIENTS[client]["platform"] == "linux":
        return "runs inside the Linux image"
    return "runs on a macOS host, not this one"


def summarise(records):
    """Uma linha por alvo e caso, na ordem em que um revisor os lê: o pior primeiro."""
    lines = []
    for client in sorted(records):
        data = records[client]
        cases = data.get("cases") or {}
        if not cases:
            lines.append("%-24s no record" % client)
            continue
        bad = sorted(name for name, value in cases.items() if value != PASSED)
        lines.append("%-24s %s of %s passed%s"
                     % (client, len(cases) - len(bad), len(cases),
                        (", not " + ", ".join(bad)) if bad else ""))
    return "\n".join(lines)


def write_round(round_dir, result):
    """O registro da rodada como está, reescrito conforme cada alvo termina.

    É escrito antes de o nível de fumaça rodar, para que uma rodada morta no meio do caminho ainda
    nomeie as classes que estavam executando e quaisquer alvos que tivessem terminado.
    """
    (Path(round_dir) / "round.json").write_text(json.dumps(result, indent=2, sort_keys=True)
                                                + "\n")
    return result


def run_round(round_dir, targets, model, confirmed, skip_smoke=False, tier_routing=None):
    tier_routing = tier_routing or with_models(routing(targets, None, None), model)
    report = provision_record(round_dir)
    clone = Path(report["clone"])
    records_dir = Path(report["records"])
    records_dir.mkdir(parents=True, exist_ok=True)
    env = environment(report)
    # Uma rodada morta no meio do nível não pode ser lida como um pulo deliberado.
    result = {"source_commit": report.get("source_commit"),
              "smoke": SKIPPED if skip_smoke else RUNNING, "targets": {},
              "tier_routing": tier_routing}
    write_round(round_dir, result)
    if not skip_smoke:
        finished = smoke(clone, env, targets)
        result["smoke"] = ("timed out" if finished is None
                           else PASSED if finished.returncode == 0 else "failed")
        if result["smoke"] != PASSED:
            result["stopped"] = ("the smoke tier %s, so no target ran; fix what it names and "
                                 "run the round again" % result["smoke"])
            result["not_run"] = list(targets)
            return write_round(round_dir, result)
    for client in targets:
        out = records_dir / (client + ".json")
        note = unobserved_note(client, confirmed)
        # Move qualquer registro anterior para o lado antes de o runner ser lançado. Um runner que
        # sai antes de escrever `--out` senão deixaria o arquivo da rodada anterior no lugar e
        # esta rodada relataria as aprovações dele como suas próprias.
        if out.exists():
            out.replace(out.with_suffix(".json.previous"))
        failure = ""
        try:
            subprocess.run(target_argv(clone, client, model, out, confirmed,
                                       tier_routing[client]),
                           cwd=str(clone), env=env, check=False, timeout=ROUND_TIMEOUT)
        except subprocess.TimeoutExpired:
            # Relatado e carregado, não levantado: uma rodada coleta os defeitos de todo alvo, e
            # um alvo que passou do prazo não pode custar os alvos depois dele.
            failure = "the target ran past the round deadline of %ss" % ROUND_TIMEOUT
        try:
            data = json.loads(out.read_text())
        except (OSError, ValueError):
            data = nothing_observed(failure or "the runner wrote no record for this target")
        if failure and failure not in data.get("observations", []):
            data.setdefault("observations", []).append(failure)
        if note:
            data.setdefault("observations", []).append(note)
        result["targets"][client] = data
        write_round(round_dir, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--round", type=Path, required=True, help="o diretório da rodada provisionado")
    parser.add_argument("--targets", default=",".join(sorted(CLIENTS)))
    parser.add_argument("--model", help="o modelo em que todo alvo roda, sobrepondo o modelo de "
                                        "execução roteado de cada alvo")
    parser.add_argument("--home-confirmed", action="append", default=[], metavar="CLIENT",
                        help="um cliente cujo home de configuração foi comparado contra uma "
                             "execução manual; repita para cada um, e nunca para uma superfície "
                             "que ninguém comparou")
    parser.add_argument("--skip-smoke", action="store_true",
                        help="o nível de fumaça já passou neste commit; registrado como "
                             "skipped, e todo alvo roda")
    parser.add_argument("--execution-class", action="append", metavar="[TARGET=]CLASS",
                        help="classe de capacidade que roda os casos (padrão %s, por alvo com "
                             "TARGET=CLASS)" % qualification.EXECUTION_DEFAULT)
    parser.add_argument("--assessment-class", action="append", metavar="[TARGET=]CLASS",
                        help="classe de capacidade que avalia as observações (padrão %s)"
                             % qualification.ASSESSMENT_DEFAULT)
    parser.add_argument("--plan", action="store_true",
                        help="imprime o que a rodada rodaria, sem lançar nada")
    args = parser.parse_args(argv)
    targets = [name.strip() for name in args.targets.split(",") if name.strip()]
    unknown = [name for name in targets if name not in CLIENTS]
    if unknown:
        raise SystemExit("unknown qualification target: " + ", ".join(unknown))
    tier_routing = with_models(routing(targets, args.execution_class, args.assessment_class),
                               args.model)
    # Um alvo cuja plataforma não é a deste host é relatado e deixado de fora, nunca rodado: o
    # runner o recusaria, e uma rodada conduzida aqui senão escreveria o resultado de uma
    # plataforma sob o nome de outra.
    elsewhere = dict((client, reason) for client, reason in
                     ((client, host_mismatch(client)) for client in targets) if reason)
    here = [client for client in targets if client not in elsewhere]
    if args.plan:
        print("round: %s, targets %s, smoke tier %s"
              % (args.round, ", ".join(targets), "skipped" if args.skip_smoke else "first"))
        for client in targets:
            print("  %-24s %s" % (client, unobserved_note(client, args.home_confirmed)
                                  or "driven by this runner"))
            print("  %-24s %s" % ("", qualification.describe(tier_routing[client])))
            print("  %-24s %s" % ("", where(client)))
        return 0
    for client in sorted(elsewhere):
        print("%-24s not run here: %s" % (client, elsewhere[client]))
    if not here:
        print("no named target runs on this host, so the round ran nothing")
        return 1
    result = run_round(args.round, here, args.model, args.home_confirmed, args.skip_smoke,
                       dict((client, tier_routing[client]) for client in here))
    if elsewhere:
        result["not_run_here"] = elsewhere
    result = write_round(args.round, result)
    print("smoke tier: " + result["smoke"])
    if result.get("stopped"):
        print("round stopped: " + result["stopped"])
        return 1
    print(summarise(result["targets"]))
    for client in here:
        print("%-24s %s" % (client, qualification.describe(tier_routing[client])))
    clean = result["smoke"] in (PASSED, SKIPPED) and all(
        value == PASSED
        for data in result["targets"].values()
        for value in (data.get("cases") or {"none": "unverified"}).values())
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
