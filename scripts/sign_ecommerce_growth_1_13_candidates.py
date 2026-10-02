"""Local isolated signer for the exact Growth 1.13 qualified build."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {
    "domain.ecommerce.core": "1.4.0",
    "platform.ecommerce.niushop": "1.23.0",
    "solution.ecommerce.growth": "1.13.0",
    "solution.ecommerce.operations-base": "1.2.0",
}
RUNTIME_IDS = set(VERSIONS) - {"solution.ecommerce.operations-base"}
EFFECTS = {"registryPublishCount": 0, "installationMutationCount": 0,
           "providerInvocationCount": 0, "externalPublicationCount": 0}
TAMPER_REJECTIONS = {"imageIndexBytes", "imageDigest", "dependencyLock",
                     "sbom", "backend", "schemaCompatibility", "schemaRequirements"}


def load_signer():
    path = ROOT / "scripts/sign_ecommerce_current_candidates.py"
    spec = importlib.util.spec_from_file_location("growth_1_13_base_signer", path)
    if spec is None or spec.loader is None:
        raise ValueError("current signer unavailable")
    signer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(signer)
    signer.PROFILE = ROOT / "scripts/build_ecommerce_growth_1_13_candidates.py"
    signer.KEY_ID = "a0v-local-ecommerce-growth-1-13-v1"
    return signer


def validate_qualification(*, build: Path, build_receipt: Path,
                           qualification_receipt: Path) -> None:
    if not qualification_receipt.is_file():
        raise ValueError("QUALIFICATION_RECEIPT_REQUIRED")
    try:
        build_raw = build_receipt.read_bytes()
        build_data = json.loads(build_raw)
        qualification = json.loads(qualification_receipt.read_bytes())
        resolved = qualification.get("resolved")
        versions = {item["id"]: item["version"] for item in resolved}
        sessions = qualification.get("runtimeSessions")
        admissions = qualification.get("runtimeAdmissions")
        images = build_data.get("images")
        valid_runtime = (
            isinstance(sessions, dict) and set(sessions) == RUNTIME_IDS
            and isinstance(admissions, dict) and set(admissions) == RUNTIME_IDS
            and isinstance(images, dict)
            and all(
                sessions[name].get("registration") == "exact"
                and sessions[name].get("cleanup") == "released"
                and sessions[name].get("heartbeatChecks") == 2048
                and admissions[name].get("imageId") == images[name.replace(".", "-")]["configDigest"]
                for name in RUNTIME_IDS
            )
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ValueError("QUALIFICATION_RECEIPT_MISMATCH") from exc
    if (build_data.get("outcome") != "BUILD_GREEN"
            or build_data.get("output") != str(build.resolve(strict=True))
            or build_data.get("effects") != EFFECTS
            or qualification.get("outcome") != "QUALIFICATION_GREEN"
            or qualification.get("buildReceipt") != str(build_receipt.resolve(strict=True))
            or qualification.get("buildReceiptHash") != "sha256:" + hashlib.sha256(build_raw).hexdigest()
            or qualification.get("outputTreeHash") != build_data.get("outputTreeHash")
            or qualification.get("gitHead") != build_data.get("gitHead")
            or qualification.get("effects") != EFFECTS
            or qualification.get("ephemeralSignaturePersisted") is not False
            or not isinstance(resolved, list) or len(resolved) != len(VERSIONS)
            or versions != VERSIONS
            or set(qualification.get("tamperRejections", [])) != TAMPER_REJECTIONS
            or not valid_runtime):
        raise ValueError("QUALIFICATION_RECEIPT_MISMATCH")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--build-receipt", type=Path, required=True)
    parser.add_argument("--qualification-receipt", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(ROOT):
        raise ValueError("SIGNING_OUTPUT_INVALID")
    validate_qualification(build=args.build_dir, build_receipt=args.build_receipt,
                           qualification_receipt=args.qualification_receipt)
    result = load_signer().sign(build=args.build_dir, receipt_path=args.build_receipt,
                                state=args.state_dir)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
