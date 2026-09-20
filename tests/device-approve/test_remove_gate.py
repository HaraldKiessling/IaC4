"""Owner-Gate fuer den Remove-Modus (DEVICE-REMOVE) – Workflow-05-Struktur.

Schranken-Vereinheitlichung 2026-09-20 (ADR-005): Loeschen bleibt DAUERHAFT
owner-pflichtig. `mode=remove` (device UND instance) verlangt den Input
`confirm` EXAKT `DEVICE-REMOVE` – fail-closed VOR jedem Write/SSH.

Rein offline (Workflow-Form), kein Netz, kein Deploy.
"""

import os

import yaml

WORKFLOW = os.path.join(
    os.path.dirname(__file__), "..", "..", ".github", "workflows", "05-device-approve.yml"
)

GATE_WORD = "DEVICE-REMOVE"


def _load():
    with open(WORKFLOW, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _on(doc):
    for key in (True, "on"):
        if key in doc:
            return doc[key]
    raise AssertionError("kein `on:`-Block")


def _steps(doc):
    jobs = doc.get("jobs") or {}
    job = next(iter(jobs.values()))
    return job.get("steps") or []


def test_confirm_input_declared_and_optional():
    inputs = _on(_load())["workflow_dispatch"]["inputs"]
    assert "confirm" in inputs, "Input 'confirm' (Owner-Gate mode=remove) fehlt"
    assert inputs["confirm"].get("required", False) is False
    assert inputs["confirm"].get("default") == ""
    assert GATE_WORD in inputs["confirm"].get("description", "")


def test_remove_gate_is_fail_closed():
    doc = _load()
    steps = _steps(doc)
    validation = next(s for s in steps if "Eingaben validieren" in str(s.get("name", "")))
    run = str(validation["run"])
    # Gate: mode=remove nur mit EXAKT DEVICE-REMOVE.
    assert 'INPUT_MODE" = "remove"' in run
    assert GATE_WORD in run
    assert '!= "DEVICE-REMOVE"' in run
    assert "exit 1" in run
    # Der Gate-Input wird genau aus confirm (dispatch + client_payload) gespeist.
    env = validation.get("env", {})
    assert "client_payload.confirm" in str(env.get("INPUT_CONFIRM", ""))
    assert "inputs.confirm" in str(env.get("INPUT_CONFIRM", ""))


def test_remove_gate_is_before_any_write_step():
    steps = _steps(_load())
    names = [str(s.get("name", "")) for s in steps]

    def idx(substr):
        for i, s in enumerate(names):
            if substr in s:
                return i
        return -1

    gate = idx("Eingaben validieren")
    tailnet = idx("Connect Runner to Tailnet")
    ssh = idx("SSH-Key vorbereiten")
    assert gate != -1, "Validierungs-/Gate-Step fehlt"
    assert tailnet != -1 and ssh != -1
    assert gate < tailnet, "Gate steht NACH dem Tailnet-Connect (fail-open!)"
    assert gate < ssh, "Gate steht NACH der SSH-Vorbereitung (fail-open!)"


def test_gate_applies_only_to_remove_mode():
    # e2e ist ein reiner Test-Lifecycle eines frischen, EIGENEN Clients und
    # darf NICHT am (echten) Owner-Wort DEVICE-REMOVE haengen; das Gate gilt
    # ausschliesslich fuer mode=remove.
    run = "\n".join(str(s.get("run", "")) for s in _steps(_load()))
    assert 'INPUT_MODE" = "remove" ] && [ "$INPUT_CONFIRM" != "DEVICE-REMOVE"' in run
