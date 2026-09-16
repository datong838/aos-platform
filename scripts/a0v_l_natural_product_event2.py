"""Second one-shot natural Cron observer, isolated from the sealed first window."""
import argparse
import json

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
    if phase not in {"arm", "observe", "disarm"}:
        raise ValueError("unsupported natural-window phase")
    configure()
    return getattr(base, phase)()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["arm", "observe", "disarm"])
    args = parser.parse_args()
    print(json.dumps(run(args.phase), ensure_ascii=False, indent=2, default=str))
