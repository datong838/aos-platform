#!/usr/bin/env python3
"""Fixed public synthetic text evaluation; no business writes or implicit retries."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / '.aos-recovery-20260910/state/a0v-exact-text-live-eval'
CASES = (
    ('instruction', '仅回复四个汉字：指令通过。不要标点或解释。', '指令通过'),
    ('source', '这是合成评测材料：[S1] 商品甲颜色为蓝色。问题：商品甲颜色的来源编号是什么？只回复 S1，不要解释。', 'S1'),
    ('missing', '这是合成评测材料：商品甲颜色为蓝色，未提供销量。问题：销量是多少？只回复 UNKNOWN，不得猜测数字。', 'UNKNOWN'),
)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def claim(path, identity):
    if path.exists():
        prior = json.loads(path.read_text())
        if prior.get('identity') != identity:
            raise RuntimeError('EVAL_JOURNAL_DRIFT')
        if prior.get('status') != 'completed':
            raise RuntimeError('EVAL_ATTEMPT_UNRESOLVED')
        return prior
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump({'identity': identity, 'status': 'submitted'}, out)
        out.flush()
        os.fsync(out.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return None


def complete(path, value):
    temporary = path.with_suffix('.completed.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(value, out)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, path)


def require_passed(prior):
    if (prior.get('status') != 'completed'
            or prior['result'].get('status') != 'healthy'
            or prior['result'].get('response_contract_passed') is not True):
        raise RuntimeError('EVAL_CASE_NOT_PASSED')


def run(apply=False, *, state_dir=STATE):
    if not apply:
        return {'mode': 'preflight', 'cases': [c[0] for c in CASES], 'providerCalls': 0}
    sys.path.insert(0, str(ROOT / 'services/aos-api'))
    os.environ['AOS_DOTENV_DISABLED'] = '1'
    from a0v_real_text_provider_health import _load_first_installer, _scoped_factory, _exact_ref, APPROVAL_REF
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    from aos_api.aip_network_policy_store import AipNetworkPolicyStore
    from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore
    from aos_api.aip_r1_bootstrap_probe import AipR1BootstrapProbe, R1BootstrapProbeRequest
    from aos_api.tenant_scope import TenantScope
    connect = _load_first_installer().container_database_connect_factory(
        context='colima-aos-extension', container='aos-a0v-recovery-pg', database_name='aos_meta_head')
    factory = _scoped_factory(connect)
    scope = TenantScope('org-org', 'dev-project')
    store = AipModelRuntimeStore(factory)
    networks = AipNetworkPolicyStore(factory)
    provider = store.get_provider(scope, 'a0v-agnes-text-readonly-dev', 1)
    network = networks.get(scope, 'a0v-ecommerce-network-v1', 1)
    probe = AipR1BootstrapProbe(model_store=store, network_store=networks,
        guard_store=AipRuntimeGuardPolicyStore(factory), allowed_approval_refs=frozenset({APPROVAL_REF}))
    for name in ('httpx', 'httpcore'):
        logging.getLogger(name).setLevel(logging.WARNING)
    results = []
    calls = 0
    for case_id, prompt, expected in CASES:
        request = R1BootstrapProbeRequest(
            provider=_exact_ref('ProviderInstanceRevision', provider, 'provider_instance_id'),
            networkPolicy=_exact_ref('NetworkPolicyRevision', network, 'policy_id'),
            providerModelId='agnes-2.5-flash', dataClassification='public_catalog',
            prompt=prompt, expectedResponseBehavior='exact_text', expectedText=expected,
            approvalRef=APPROVAL_REF, maxOutputTokens=32)
        identity = {'caseId': case_id, 'requestHash': digest(request.model_dump(mode='json')),
            'provider': request.provider.model_dump(mode='json'),
            'network': request.network_policy.model_dump(mode='json')}
        path = Path(state_dir) / (case_id + '.json')
        prior = claim(path, identity)
        if prior is None:
            result = probe.run(scope, request)
            calls += 1
            prior = {'identity': identity, 'status': 'completed',
                'result': result.model_dump(mode='json')}
            complete(path, prior)
        results.append(prior)
        require_passed(prior)
    return {'mode': 'apply', 'providerCalls': calls, 'businessMutationCount': 0,
        'outcome': 'FIXED_TEXT_CASES_PASSED', 'cases': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--state-dir', type=Path, default=STATE)
    args = parser.parse_args()
    try:
        rendered = json.dumps(run(args.apply, state_dir=args.state_dir), ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(rendered + '\n', encoding='utf-8')
        print(rendered)
    except Exception as exc:
        print(json.dumps({'outcome': 'BLOCKED', 'errorType': type(exc).__name__,
            'note': 'Inspect attempt state; do not resend unresolved calls.'}))
        raise SystemExit(2)
