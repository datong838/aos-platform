"""Second one-shot natural Cron observer, isolated from the sealed first window."""
import argparse
from datetime import datetime, timezone
import json
from time import monotonic, sleep

import a0v_l_natural_product_event as base
import a0v_l_successor_business as current


STATE = current.STATE / "natural-product-event-v2"
POLICY_REVISION = 9
EXPECTED_BINDING_REVISION = 1


def configure():
    base.STATE = STATE
    base.POLICY_REVISION = POLICY_REVISION
    base.EXPECTED_BINDING_REVISION = EXPECTED_BINDING_REVISION


def run(phase):
    if phase not in {"arm", "observe", "disarm", "watch"}:
        raise ValueError("unsupported natural-window phase")
    configure()
    if phase == "watch":
        return watch()
    return getattr(base, phase)()


def watch(*, initial_timeout_seconds=2280, running_timeout_seconds=600,
          poll_seconds=5, clock=monotonic, pause=sleep):
    base._private("arm-intent.json")
    deadline = clock() + initial_timeout_seconds
    disabled = False
    extended = False
    while True:
        value = base.snapshot()
        base.validate_ready(value, require_drained=False)
        runs = value["runs"]
        if len(runs) > 1:
            raise ValueError("more than one natural run observed")
        terminal = runs[0] if runs and runs[0]["status"] in {"succeeded", "failed"} else None
        downstream_ready = bool(value["investigationRuns"])
        if terminal and (terminal["status"] == "failed" or downstream_ready):
            disarmed = base.disarm()
            final = disarmed["snapshot"]
            if final["schedule"]["enabled"] is not False:
                raise ValueError("terminal natural window was not disarmed")
            return {
                "outcome": "L_POLICY9_NATURAL_TERMINAL_OBSERVED",
                "observedAt": datetime.now(timezone.utc).isoformat(),
                "terminalRun": terminal,
                "downstreamReady": downstream_ready,
                "snapshot": final,
            }
        if clock() >= deadline:
            if runs and runs[0]["status"] == "running" and not extended:
                deadline = clock() + running_timeout_seconds
                extended = True
            else:
                disarmed = base.disarm()
                if runs and runs[0]["status"] == "running":
                    outcome = "L_POLICY9_NATURAL_RUN_TERMINAL_TIMED_OUT"
                elif terminal and terminal["status"] == "succeeded":
                    outcome = "L_POLICY9_NATURAL_DOWNSTREAM_TIMED_OUT"
                else:
                    outcome = "L_POLICY9_NATURAL_WINDOW_TIMED_OUT"
                return {
                    "outcome": outcome,
                    "observedAt": datetime.now(timezone.utc).isoformat(),
                    "terminalRun": terminal,
                    "snapshot": disarmed["snapshot"],
                }
        pause(poll_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["arm", "observe", "disarm", "watch"])
    args = parser.parse_args()
    print(json.dumps(run(args.phase), ensure_ascii=False, indent=2, default=str))
