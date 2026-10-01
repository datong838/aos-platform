"""Source/cryptographic boundary probe, never business acceptance; no database or network."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "services/aos-api"
sys.path.insert(0, str(API))
from aos_api.aip_eval_contracts import EvalExecutionReceipt
from aos_api.aip_eval_execution_authority import canonical_receipt_bytes

fixture = API / "tests/aip/test_aip_eval_execution_authority.py"
spec = importlib.util.spec_from_file_location("signed_fixture", fixture)
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
root, target, judge = f._signed_pair()
verified = f._verify(root, target, judge)
assert verified.passed is True
missing = sorted({"subject_artifact_ref", "stage_attempt_ref", "eval_contract_ref",
    "gate_policy_ref", "evidence_cutoff_at", "query_artifact_ref"} - set(EvalExecutionReceipt.model_fields))
assert len(missing) == 6
# Cryptography is real but all keys, refs and outputs here are synthetic fixture claims.
assert b"subjectArtifactRef" not in canonical_receipt_bytes(target[1])
paths = ["aip_eval_contracts.py", "aip_eval_execution_authority.py",
    "aip_eval_writer_authority_preflight.py", "aip_eval_runner.py",
    "aip_release_publication_service.py", "ecommerce_analyst_stage_eval_report.py",
    "ecommerce_analyst_stage_review_command.py"]
sources = {}
for name in paths:
    path = API / "aos_api" / name
    body = path.read_bytes()
    tree = ast.parse(body)
    sources[name] = dict(sha256=hashlib.sha256(body).hexdigest(),
        functions={n.name: n.lineno for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))})
stage = (API / "aos_api/ecommerce_analyst_stage_eval_report.py").read_text()
assert "read_verified_skill_eval_report" not in stage
release = (API / "aos_api/aip_release_publication_service.py").read_text()
assert 'formal Skill Eval executor authority unavailable' in release
result = dict(schemaVersion="aos.stage-eval-design-probe/v1",
    codeHead=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    fixtureSignedPairVerified=True, receiptContextFieldsAbsent=missing,
    directStageReaderHasSignedReaderCall=False, releaseSkillGateStillExplicitlyClosed=True,
    businessAcceptance=False, databaseAccess=False, sources=sources)
print(json.dumps(result, ensure_ascii=False, indent=2))
