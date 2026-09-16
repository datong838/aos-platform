"""Exact successor authority, Policy9, and binding for the second natural Cron window."""
import argparse
import importlib.util
import json

import a0v_l_successor_business as current
import a0v_l_product_window as predecessor
from a0v_l_product_preflight import load_profile as preflight


current.G_ID = current.L_ID
current.G_GENERATION = current.L_GENERATION


def module(name):
    path = current.ROOT / "scripts" / f"a0v_event_complete_product_{name}.py"
    spec = importlib.util.spec_from_file_location(f"l_window2_{name}", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    value.f = current
    return value


def _previous_ref(phase):
    expected = {
        "selection": ("SourceSelectionRevision", 1, "sha256:32ecbe636f41ddac2e9cc3aa088f15bd1e79530159f058067fb99c93f62f4e6a"),
        "control": ("PipelineRuntimeControlRevision", 1, "sha256:022bdb52cdd3732c18daae8614e0a192d24e2644e5b550f0fdc18bae2d8fe8bc"),
        "binding": ("PipelineScheduleControlBinding", 14, "sha256:5c293c52951d3706241082dcad9b58c4c1d82a4ef65d725bf9b4486979f9fede"),
    }
    if phase not in expected:
        raise ValueError("unknown predecessor phase")
    ref = predecessor.authority_profile().load(phase)["ref"]
    resource_type, revision, content_hash = expected[phase]
    if (ref.get("resourceType") != resource_type or ref.get("revision") != revision
        or ref.get("contentHash") != content_hash):
        raise ValueError("exact L v1 authority predecessor required")
    return ref


def authority_profile():
    value = module("authority")
    value.STATE = current.STATE / "product-authority-v2"
    value.PREFIX = "a0v-p02-l-authority-20260917-v2"
    value.previous_reference = _previous_ref
    value.preflight_profile = preflight
    return value


def policy_profile():
    value = module("policy")
    old = predecessor.policy_profile()
    value.STATE = current.STATE / "product-event-v2"
    value.PREFIX = "a0v-qyh-product-event-l-20260917-v2"
    value.authority = authority_profile()

    def previous():
        policy = old.load("prepare")["command"]["policy"]
        receipt = old.load("put")["receiptRef"]
        if (receipt["resourceId"] != value.POLICY or receipt["revision"] != 8
            or policy["revision"] != 8 or receipt["contentHash"] != policy["contentHash"]):
            raise ValueError("exact L Policy8 predecessor required")
        return dict(policy, tenant={"orgId": "org-org", "projectId": "dev-project"})

    value.previous_policy_payload = previous
    return value


def enable_profile():
    value = module("enable")
    value.STATE = current.STATE / "event-enable-v2"
    value.PREFIX = "a0v-qyh-l-event-enable-20260917-v2"
    value.policy_profile = policy_profile
    value.EXPECTED_GROUP_REVISION = 37
    value.EXPECTED_BINDING_REVISION = 0
    return value


def run(kind, phase):
    allowed = {
        "authority": ("prepare", "selection", "control", "binding"),
        "policy": ("prepare", "approve", "put"),
        "enable": ("approve-control", "enable"),
    }
    if kind not in allowed or phase not in allowed[kind]:
        raise ValueError("unsupported L second natural-window phase")
    return globals()[kind + "_profile"]().run(phase, current.setup())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["authority", "policy", "enable"])
    parser.add_argument("phase")
    args = parser.parse_args()
    print(json.dumps(run(args.kind, args.phase), ensure_ascii=False, default=str, indent=2))
