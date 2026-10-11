#!/usr/bin/env python3
"""Exact recovery candidate signer profile with a read-only validation mode."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {
    "domain.ecommerce.core": "1.4.3", "platform.ecommerce.niushop": "1.23.0",
    "solution.ecommerce.growth": "1.13.0", "solution.ecommerce.operations-base": "1.2.0",
}


def _qualification_profile():
    path = ROOT / "scripts/sign_ecommerce_growth_1_13_candidates.py"
    spec = importlib.util.spec_from_file_location("qyh_recovery_qualification_signer", path)
    if spec is None or spec.loader is None:
        raise ValueError("qualification validator unavailable")
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    profile.VERSIONS = dict(VERSIONS)
    return profile


def load_signer():
    signer = _qualification_profile().load_signer()
    signer.PROFILE = ROOT / "scripts/build_ecommerce_qyh_recovery_candidates.py"
    signer.KEY_ID = "a0v-local-qyh-core143-growth113-v1"
    return signer


def validate_inputs(*, build: Path, build_receipt: Path,
                    qualification_receipt: Path, state: Path):
    _qualification_profile().validate_qualification(
        build=build, build_receipt=build_receipt, qualification_receipt=qualification_receipt)
    signer = load_signer()
    builder, receipt = signer.validate_build(build=build, receipt_path=build_receipt, state=state)
    return signer, {
        "outcome": "VALIDATED_UNSIGNED_BUILD_NO_SIGN",
        "versions": dict(VERSIONS), "outputTreeHash": receipt["outputTreeHash"],
        "sourceGitHead": receipt["gitHead"], "moduleCount": 8,
        "authorization": "INPUT_VALIDATION_ONLY_NO_PUBLISH_OR_RUNTIME_START",
    }


def validate_output(*, output: Path, build: Path, state: Path) -> None:
    if output.is_symlink():
        raise ValueError("SIGNING_OUTPUT_INVALID")
    output = output.resolve()
    forbidden = (ROOT, build.resolve(strict=True), state.resolve())
    if (output.exists() or output.is_symlink() or not output.parent.is_dir()
            or any(output == path or output.is_relative_to(path) for path in forbidden)):
        raise ValueError("SIGNING_OUTPUT_INVALID")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--build-receipt", type=Path, required=True)
    parser.add_argument("--qualification-receipt", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    if args.validate_only:
        if args.output is not None:
            raise ValueError("VALIDATION_OUTPUT_NOT_ALLOWED")
    else:
        if args.output is None:
            raise ValueError("SIGNING_OUTPUT_REQUIRED")
        validate_output(output=args.output, build=args.build_dir, state=args.state_dir)
    signer, report = validate_inputs(build=args.build_dir, build_receipt=args.build_receipt,
                                     qualification_receipt=args.qualification_receipt,
                                     state=args.state_dir)
    if not args.validate_only:
        report = signer.sign(build=args.build_dir, receipt_path=args.build_receipt, state=args.state_dir)
        # Recheck after signing; never overwrite an output that appeared meanwhile.
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
