#!/usr/bin/env python3
"""Inspect a qualified Qiyuehui successor installation; never starts services."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import validate_ecommerce_qyh_successor_signing as qualified

ROOT=Path(__file__).resolve().parents[1]


class SuccessorInstallationBlocked(ValueError):
    pass


def load_entry():
    # Independent fixed profile, preserving the retained release's entry/defaults.
    spec=importlib.util.spec_from_file_location('qyh_successor_readonly_profile',ROOT/'scripts/a0v_qyh_restored_http.py')
    entry=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    entry.SELECTED_VERSIONS=dict(qualified.VERSIONS)
    return entry


def require_content_hashes(selected,expected):
    releases=selected['releases']
    actual={r['id']:r['contentHash'] for r in releases}
    if len(releases)!=4 or len(actual)!=4 or actual!=expected:
        raise SuccessorInstallationBlocked('QUALIFIED_INSTALLATION_CONTENT_HASH_DRIFT')


def signed_content_hashes(signed_root,trust_roots_file,expected):
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.asset_registry.signature import FileTrustRootProvider
    try:
        trust=FileTrustRootProvider(trust_roots_file).snapshot()
        loader=ManifestLoader({'qyh-successor':signed_root},trust_roots=trust)
        policy=ReleasePolicy(trust_roots=trust)
        builder=qualified.load_signer()._builder()
        hashes={}
        for relative,bundle_id,_,_ in builder.ALL_CASES:
            loaded=loader.load(f'bundle://qyh-successor/{relative}')
            policy.evaluate(builder._release_record(loaded),checked_at=datetime.now(timezone.utc))
            if loaded.manifest.metadata.version!=qualified.VERSIONS[bundle_id]:
                raise ValueError('version drift')
            hashes[bundle_id]=loaded.content_hash
        if hashes!=expected:
            raise ValueError('content drift')
        return hashes
    except Exception:
        raise SuccessorInstallationBlocked('QUALIFIED_SIGNED_ARTIFACT_REJECTED') from None


def run(*,build,build_receipt,qualification_receipt,signed_root,trust_roots_file,identity_file,installation_id):
    before=build_receipt.read_bytes()
    proof=qualified.validate_inputs(build=build,build_receipt=build_receipt,
        qualification_receipt=qualification_receipt,state=signed_root.parent/'.qyh-successor-preflight-unused')
    if build_receipt.read_bytes()!=before:
        raise SuccessorInstallationBlocked('BUILD_RECEIPT_CHANGED_DURING_VALIDATION')
    expected=json.loads(before)['contentHashes']
    signed_content_hashes(signed_root,trust_roots_file,expected)
    # Original reader verifies tenant, Registry PUBLISHED/currentness, immutable
    # installation lock, exact signed bytes and the limited READ ONLY connection.
    entry=load_entry()
    try:
        result=entry.select_current_installation(identity_file=identity_file,
            bundle_root=signed_root,trust_roots_file=trust_roots_file,installation_id=installation_id)
    except entry.RestorationBlocked:
        raise SuccessorInstallationBlocked('CURRENT_SUCCESSOR_INSTALLATION_NOT_VERIFIED') from None
    require_content_hashes(result['currentInstallation'],expected)
    return {**result,'outcome':'QYH_QUALIFIED_SUCCESSOR_CURRENT_INSTALLATION_EVIDENCE_ONLY',
        'qualifiedBuildTreeHash':proof['outputTreeHash'],
        'formalIdentityVerified':False,'registryPublishAuthorized':False,
        'runtimeAuthorized':False,'eightWorkbenchesVerified':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('build','build-receipt','qualification-receipt','signed-root','trust-roots-file','identity-file'):
        parser.add_argument('--'+arg,type=Path,required=True)
    parser.add_argument('--installation-id',required=True)
    args=parser.parse_args()
    try:
        result=run(**vars(args))
    except Exception:
        print(json.dumps({'outcome':'QYH_SUCCESSOR_INSTALLATION_REFUSED','runtimeAuthorized':False}))
        return 1
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':
    raise SystemExit(main())
