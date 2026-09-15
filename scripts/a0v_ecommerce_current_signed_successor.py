"""Build the permanent signed successor for the current ecommerce four-pack."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("current signed successor dependency unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_successor():
    scripts = Path(__file__).resolve().parent
    successor = _load(
        scripts / "a0v_ecommerce_1_7_registry_successor.py",
        "current_ecommerce_signed_successor",
    )
    profile = _load(
        scripts / "build_ecommerce_current_candidates.py",
        "current_ecommerce_build_profile",
    )
    ui_successor = _load(
        scripts / "a0v_ecommerce_ui_signed_successor.py",
        "current_ecommerce_ui_successor",
    ).load_successor()
    helper = successor.legacy()
    helper._builder = profile.load_builder
    successor.legacy = lambda: helper
    recovery = successor.ROOT.parent / ".aos-recovery-20260916"
    successor.BUILD = recovery / "state/growth-1.9-current-package/build/candidates"
    successor.BUILD_RECEIPT = recovery / "state/growth-1.9-current-package/build/build-receipt.json"
    successor.QUALIFICATION = recovery / "state/growth-1.9-current-package/build/qualification-receipt.json"
    successor.STATE = recovery / "state/growth-1.9-current-package/registry"
    successor.OLD_ROOT = (
        successor.ROOT.parent
        / ".aos-recovery-20260915/state/niushop-1.23-current-package/registry/signed-bundles-niushop-1.23-current"
    )
    successor.NEW_ROOT = successor.STATE / "signed-bundles-growth-1.9-current"
    successor.VERSIONS = dict(
        successor.VERSIONS,
        **{
            "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.9.0",
        },
    )
    successor.EXPECTED_OLD_COUNT = 16
    successor.EXPECTED_NEW_COUNT = 17
    successor.EXTRA_BUILD_PATHS = (
        "scripts/build_ecommerce_ui_candidates.py",
        "scripts/build_ecommerce_current_candidates.py",
        "scripts/prepare_ecommerce_growth_1_9_candidate.py",
        "scripts/fixtures/analyst-workspace-read-probe.json",
    )
    successor.ACTOR_PREFIX = "a0v-growth-1.9-current-20260916"
    successor.SUCCESS_OUTCOME = "GROWTH_1_9_CURRENT_REGISTRY_GREEN"
    base_require_sessions = ui_successor.require_sessions
    def require_sessions(document):
        patched = json.loads(json.dumps(document))
        growth = (patched.get("runtimeSessions") or {}).get("solution.ecommerce.growth") or {}
        if growth.get("contributionCount") != 25:
            raise ValueError("growth 1.9 requires 25 runtime contributions")
        growth["contributionCount"] = 24
        base_require_sessions(patched)
    successor.require_sessions = require_sessions
    return successor


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("immutable output already exists; inspect before retry")
    successor = load_successor()
    sys.path.insert(0, str(successor.API))
    helper = successor.legacy()
    build = successor.verify_inputs(helper)
    result = {
        "outcome": "PREFLIGHT_GREEN",
        "outputTreeHash": build["outputTreeHash"],
        "registryPublishCount": 0,
        "installationMutationCount": 0,
        "environmentMutationCount": 0,
    }
    if args.apply:
        trust_path, hashes = successor.signed_tree(helper, build)
        backup = helper._database_backup(
            context=helper.DOCKER_CONTEXT,
            container=helper.DATABASE_CONTAINER,
            state_dir=successor.STATE,
        )
        connect = helper._first_installer().container_database_connect_factory(
            context=helper.DOCKER_CONTEXT,
            container=helper.DATABASE_CONTAINER,
            database_name=helper.DATABASE_NAME,
        )
        before = helper._database_counts(connect)
        if before["canary"] != 0:
            raise ValueError("canary state drift")
        releases = successor.publish(helper, connect, trust_path)
        after = helper._database_counts(connect)
        if before != after:
            raise ValueError("installation counts changed during registry publication")
        result.update(
            outcome=successor.SUCCESS_OUTCOME,
            releases=releases,
            signedContent=hashes,
            backup=backup,
            before=before,
            after=after,
            registryPublishCount=sum(
                sum(item["mutations"].values()) for item in releases
            ),
        )
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
