"""Fixed safe rejection types for future saved recovery attempts only."""

import inspect
import re

import pytest

from aos_api.extension_runtime.recoverable_store_attempt import _terminal_failure
from aos_api import pipeline_snapshot_group_recovery_authority as authority


@pytest.mark.parametrize("name", (
    "OriginalRecoveryExecutorDenied",
    "CurrentRecoveryDefinitionDenied",
    "CurrentRecoveryExecutorDenied",
))
def test_recovery_denials_remain_permission_error_and_persist_no_message(name):
    denial = getattr(authority, name)("private tenant detail must not persist")
    assert isinstance(denial, PermissionError)
    assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,159}", type(denial).__name__)
    reason, error_type = _terminal_failure(denial, None, True)
    assert reason == "RECOVERABLE_EXECUTION_EXCEPTION"
    assert error_type == name
    assert "private" not in error_type


def test_exact_existing_recovery_permission_predicates_are_retained():
    source = inspect.getsource(authority)
    assert source.count("actor!=body['executor']") == 2
    assert "self._definitions._permission(conn,org_id=scope.org_id,project_id=scope.project_id" in source
    assert source.count("raise OriginalRecoveryExecutorDenied('original recovery executor required')") == 2
    assert "raise CurrentRecoveryDefinitionDenied('current recovery definition permission required')" in source
    assert "raise CurrentRecoveryExecutorDenied('current recovery executor permission required')" in source
