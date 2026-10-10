"""Preserve published preparation SQL while sharing its complete claim checks."""
import inspect
import json
from pathlib import Path

import pytest

from aos_api import aip_shared_parent_certificate_prepare as api


def test_existing_sql_remains_byte_exact():
    root = Path(__file__).resolve().parents[4]
    before = json.loads((root / '.evidence/gt-shared-certificate-validation-kernel-20261010/original-sql-beforeimage.json').read_text())
    assert list(api.shared_parent_certificate_prepare_statements()) == before['statements']


def test_original_producer_uses_same_kernel(monkeypatch):
    kernel = api.shared_parent_certificate_claim_sql()
    statements = api.shared_parent_certificate_prepare_statements()
    prepare = next(x for x in statements if x.startswith('CREATE FUNCTION ' + api.FUNCTION.split('(')[0] + '('))
    assert prepare.count(kernel) == 1
    marker = '\n-- test-owned replacement; never executed\n'
    monkeypatch.setattr(api, 'shared_parent_certificate_claim_sql', lambda: marker)
    changed = api.shared_parent_certificate_prepare_statements()
    assert changed == tuple(x.replace(kernel, marker) if x == prepare else x for x in statements)


def test_kernel_has_fixed_source_and_no_write_or_end_channel():
    kernel = api.shared_parent_certificate_claim_sql()
    assert len(inspect.signature(api.shared_parent_certificate_claim_sql).parameters) == 0
    assert 'INSERT INTO' not in kernel and 'UPDATE ' not in kernel and 'COMMIT' not in kernel
    # This is the original full-set/Root/claim/signature validation region,
    # never a replacement verifier, new signing domain or release decision.
    assert 'SHARED_CERTIFICATE_COMPLETE_SET_REQUIRED' in kernel
    assert 'FOR SHARE OF e' in kernel
    assert 'verify_model_shared_parent_certificate_signature' in kernel
    assert 'SHARED_CERTIFICATE_SIGNATURE_OR_TIME_REQUIRED' in kernel
    assert 'rootProvenanceVerified' not in kernel


def test_original_producer_uses_exact_native_verifier_requirement(monkeypatch):
    kernel = api.shared_parent_native_verifier_requirement_sql()
    statements = api.shared_parent_certificate_prepare_statements()
    prepare = next(x for x in statements if x.startswith('CREATE FUNCTION ' + api.FUNCTION.split('(')[0] + '('))
    assert prepare.count(kernel) == 1
    assert "p.probin='$libdir/aos_ed25519'" in kernel
    assert "p.prosrc='aos_ed25519_verify'" in kernel
    assert 'pg_auth_members' in kernel and 'rolbypassrls' in kernel
    marker = '\n-- test-owned verifier requirement replacement; never executed\n'
    monkeypatch.setattr(api, 'shared_parent_native_verifier_requirement_sql', lambda: marker)
    assert api.shared_parent_certificate_prepare_statements() == tuple(x.replace(kernel, marker) if x == prepare else x for x in statements)


@pytest.mark.parametrize('override', ['other_schema', {'root': 'fake'}, True, None])
def test_no_caller_selected_issuer_or_validation_override(override):
    with pytest.raises(TypeError):
        api.shared_parent_certificate_claim_sql(override)
