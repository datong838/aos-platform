"""Local isolated signing profile for the growth 1.12 build receipt."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_signer():
    path = ROOT / "scripts/sign_ecommerce_current_candidates.py"
    spec = importlib.util.spec_from_file_location("growth_1_12_base_signer", path)
    if spec is None or spec.loader is None:
        raise ValueError("current signer unavailable")
    signer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(signer)
    signer.PROFILE = ROOT / "scripts/build_ecommerce_growth_1_12_candidates.py"
    signer.KEY_ID = "a0v-local-ecommerce-growth-1-12-v1"
    return signer


def validate_qualification(*, build: Path, build_receipt: Path,
                           qualification_receipt: Path) -> None:
    if not qualification_receipt.is_file():
        raise ValueError("QUALIFICATION_RECEIPT_REQUIRED")
    try:
        build_raw = build_receipt.read_bytes()
        build_data = json.loads(build_raw)
        qualification = json.loads(qualification_receipt.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError("QUALIFICATION_RECEIPT_MISMATCH") from exc
    resolved = qualification.get("resolved")
    exact_growth = [item for item in resolved if isinstance(item, dict)
                    and item.get("id") == "solution.ecommerce.growth"] if isinstance(resolved, list) else []
    expected_rejections = {"imageIndexBytes", "imageDigest", "dependencyLock",
                           "sbom", "backend", "schemaCompatibility", "schemaRequirements"}
    if (build_data.get("outcome") != "BUILD_GREEN"
            or build_data.get("output") != str(build.resolve(strict=True))
            or qualification.get("outcome") != "QUALIFICATION_GREEN"
            or qualification.get("buildReceipt") != str(build_receipt.resolve(strict=True))
            or qualification.get("buildReceiptHash") != "sha256:" + hashlib.sha256(build_raw).hexdigest()
            or qualification.get("outputTreeHash") != build_data.get("outputTreeHash")
            or qualification.get("gitHead") != build_data.get("gitHead")
            or qualification.get("effects") != build_data.get("effects")
            or len(exact_growth) != 1 or exact_growth[0].get("version") != "1.12.0"
            or set(qualification.get("tamperRejections", [])) != expected_rejections):
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
