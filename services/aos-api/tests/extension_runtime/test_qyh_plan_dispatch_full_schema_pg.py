"""Original signed PG case with independent Plan and ordinary connection routing."""
import os
from contextlib import contextmanager

import pytest

import plan_restricted_issuer_case as restricted
import test_growth_signed_installation_full_schema_pg as original

pytestmark = pytest.mark.skipif(
    os.getenv('AOS_EXTENSION_PG_TEST') != '1' or os.getenv('AOS_EXTENSION_OCI_TEST') != '1',
    reason='real isolated PG and original OCI opt-in required',
)


def test_original_signed_plan_routes_only_plan_transactions(tmp_path, request, monkeypatch):
    counts = {'plan': 0, 'successor': 0, 'ordinary': 0}

    def ordinary_forbidden(scope):
        counts['ordinary'] += 1
        raise AssertionError('Plan transaction incorrectly used ordinary runtime connection')

    def tracked(factory, kind):
        @contextmanager
        def open_plan(scope):
            counts[kind] += 1
            with factory(scope) as conn:
                assert conn.execute('SELECT session_user AS login').fetchone()['login'] == 'aos_bi_plan_issuer'
                yield conn
        return open_plan

    class PlanStore(restricted.AipProductionContractStore):
        def __init__(self, *args, **kwargs):
            factory = kwargs['connect_factory']
            kwargs['plan_connect_factory'] = tracked(factory, 'plan')
            kwargs['connect_factory'] = ordinary_forbidden
            super().__init__(*args, **kwargs)

    class SuccessorStore(restricted.AipResponsibilityAssignmentStore):
        def __init__(self, *args, **kwargs):
            factory = kwargs['connect_factory']
            kwargs['plan_connect_factory'] = tracked(factory, 'successor')
            kwargs['connect_factory'] = ordinary_forbidden
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(restricted, 'AipProductionContractStore', PlanStore)
    monkeypatch.setattr(restricted, 'AipResponsibilityAssignmentStore', SuccessorStore)
    original.test_signed_growth_release_reaches_approved_installation_in_full_schema(
        tmp_path, request, monkeypatch)
    assert counts['plan'] >= 8
    assert counts['successor'] == 1
    assert counts['ordinary'] == 0
