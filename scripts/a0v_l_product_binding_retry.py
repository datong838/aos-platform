"""Fresh approval and idempotency for Policy9 after the rejected binding CAS."""
import argparse
import importlib.util
import json

import a0v_l_successor_business as current
import a0v_l_product_window2 as window


current.G_ID = current.L_ID
current.G_GENERATION = current.L_GENERATION


def enable_profile():
    path = current.ROOT / "scripts" / "a0v_event_complete_product_enable.py"
    spec = importlib.util.spec_from_file_location("l_policy9_binding_retry", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    value.f = current
    value.STATE = current.STATE / "event-enable-v3"
    value.PREFIX = "a0v-qyh-l-event-enable-20260917-v3"
    value.policy_profile = window.policy_profile
    value.EXPECTED_GROUP_REVISION = 37
    value.EXPECTED_BINDING_REVISION = 0
    return value


def run(phase):
    if phase not in {"approve-control", "enable"}:
        raise ValueError("unsupported Policy9 binding retry phase")
    return enable_profile().run(phase, current.setup())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["approve-control", "enable"])
    args = parser.parse_args()
    print(json.dumps(run(args.phase), ensure_ascii=False, default=str, indent=2))
