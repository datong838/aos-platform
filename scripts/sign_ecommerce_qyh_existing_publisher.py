"""Sign qualified Qiyuehui artifacts with existing material; no identity or publication grant."""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import stat
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import validate_ecommerce_qyh_successor_signing as qualified

ROOT = Path(__file__).resolve().parents[1]


class PublisherSigningBlocked(RuntimeError):
    pass


def existing_material(*, key_file: Path, trust_roots_file: Path, key_id: str):
    from aos_api.asset_registry.signature import FileTrustRootProvider

    if (not key_id or key_id != key_id.strip()
            or key_id.startswith(('a0v-local-', 'a0v-ephemeral-'))):
        raise PublisherSigningBlocked('EXISTING_PUBLISHER_KEY_ID_REQUIRED')
    if key_file.resolve().is_relative_to(ROOT):
        raise PublisherSigningBlocked('PUBLISHER_PRIVATE_MATERIAL_MUST_BE_EXTERNAL')
    descriptor = None
    try:
        descriptor = os.open(key_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        before = os.fstat(descriptor)
        if (not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode) != 0o600
                or before.st_uid != os.getuid() or before.st_size > 8192):
            raise PublisherSigningBlocked('EXISTING_KEY_PERMISSIONS_INVALID')
        with os.fdopen(descriptor, 'rb') as handle:
            descriptor = None
            raw = handle.read(8193)
            after = os.fstat(handle.fileno())
        if (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns, before.st_size) != (
                after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns, after.st_size):
            raise PublisherSigningBlocked('EXISTING_KEY_CHANGED_DURING_READ')
        key = serialization.load_pem_private_key(raw, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise PublisherSigningBlocked('EXISTING_KEY_ALGORITHM_INVALID')
        trust = FileTrustRootProvider(trust_roots_file.absolute()).snapshot()
        root = trust.get_trust_root(publisher='aos', key_id=key_id)
        now = datetime.now(UTC)
        if (root is None or root.revoked_at is not None or root.not_before is None
                or root.not_after is None or not root.not_before <= now < root.not_after):
            raise PublisherSigningBlocked('EXISTING_TRUST_NOT_CURRENT')
        public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        if public != root.public_key:
            raise PublisherSigningBlocked('EXISTING_KEY_TRUST_MISMATCH')
        return key, trust, root
    except PublisherSigningBlocked:
        raise
    except (OSError, ValueError, TypeError):
        raise PublisherSigningBlocked('EXISTING_PUBLISHER_MATERIAL_UNAVAILABLE') from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def run(*, build: Path, build_receipt: Path, qualification_receipt: Path,
        state: Path, key_file: Path, trust_roots_file: Path, key_id: str, sign: bool = False):
    import sys
    sys.path.insert(0, str(ROOT / 'services/aos-api'))
    state = state.resolve()
    if state.exists():
        raise PublisherSigningBlocked('OUTPUT_ALREADY_EXISTS_RECONCILE_READ_ONLY')
    receipt_bytes = build_receipt.read_bytes()
    preflight = qualified.validate_inputs(build=build, build_receipt=build_receipt,
        qualification_receipt=qualification_receipt, state=state)
    if build_receipt.read_bytes() != receipt_bytes:
        raise PublisherSigningBlocked('BUILD_RECEIPT_CHANGED_DURING_VALIDATION')
    expected = json.loads(receipt_bytes)['contentHashes']
    if (key_file.resolve().is_relative_to(build.resolve())
            or key_file.resolve().is_relative_to(state)
            or trust_roots_file.resolve().is_relative_to(state)):
        raise PublisherSigningBlocked('PUBLISHER_MATERIAL_OUTPUT_OVERLAP')
    arguments = dict(key_file=key_file, trust_roots_file=trust_roots_file, key_id=key_id)
    key, trust, root = existing_material(**arguments)
    public = {'outcome': 'QYH_EXISTING_SIGNING_MATERIAL_MATCHED_NO_SIGN',
        'keyId': key_id, 'trustRootRevision': root.revision,
        'buildTreeHash': preflight['outputTreeHash'], 'formalIdentityVerified': False,
        'registryPublishAuthorized': False, 'formalRuntimeReady': False,
        'effects': preflight['effects']}
    if not sign:
        return public
    builder = qualified.load_signer()._builder()
    state.mkdir(mode=0o700)
    if stat.S_IMODE(state.stat().st_mode) != 0o700:
        raise PublisherSigningBlocked('OUTPUT_PERMISSIONS_INVALID')
    (state / 'intent.json').write_text(json.dumps(public, sort_keys=True) + '\n')
    signed = state / 'signed-bundles'
    shutil.copytree(build, signed)
    if builder._tree_hash(signed) != preflight['outputTreeHash']:
        raise PublisherSigningBlocked('INPUT_CHANGED_BEFORE_SIGN')
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.release_policy import ReleasePolicy
    unsigned = ManifestLoader({'qyh-existing': signed})
    for relative, _, _, _ in builder.ALL_CASES:
        loaded = unsigned.load(f'bundle://qyh-existing/{relative}')
        envelope = {'algorithm': 'Ed25519', 'keyId': key_id,
            'signature': base64.b64encode(key.sign(builder._signature_payload(loaded))).decode('ascii'),
            'signedAt': datetime.now(UTC).isoformat()}
        (signed / relative / 'bundle.signature.json').write_text(json.dumps(envelope, sort_keys=True) + '\n')
    _, current_trust, current_root = existing_material(**arguments)
    if current_root != root:
        raise PublisherSigningBlocked('EXISTING_TRUST_CHANGED_DURING_SIGN')
    loader = ManifestLoader({'qyh-existing': signed}, trust_roots=current_trust)
    policy = ReleasePolicy(trust_roots=current_trust)
    content_hashes = {}
    for relative, bundle_id, _, _ in builder.ALL_CASES:
        loaded = loader.load(f'bundle://qyh-existing/{relative}')
        policy.evaluate(builder._release_record(loaded), checked_at=datetime.now(UTC))
        content_hashes[bundle_id] = loaded.content_hash
    if content_hashes != expected:
        raise PublisherSigningBlocked('SIGNED_CONTENT_HASH_MISMATCH')
    result = {**public, 'outcome': 'QYH_EXISTING_MATERIAL_SIGNED_ARTIFACTS_NO_PUBLICATION',
        'signedTree': str(signed), 'signedTreeHash': builder._tree_hash(signed),
        'contentHashes': content_hashes}
    (state / 'result.json').write_text(json.dumps(result, sort_keys=True) + '\n')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('build', 'build-receipt', 'qualification-receipt', 'state', 'key-file', 'trust-roots-file'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--key-id', required=True)
    parser.add_argument('--sign', action='store_true', help='Create new signed artifacts; never publish or install')
    args = vars(parser.parse_args(argv))
    print(json.dumps(run(**args), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
