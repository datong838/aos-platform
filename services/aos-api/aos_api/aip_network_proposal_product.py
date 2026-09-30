"""Persist one product creation request before dispatch; PG remains authority."""
from datetime import UTC, datetime, timedelta
import json
import os

from aos_api.aip_action_store import canonical_hash
from aos_api.aip_network_issuer_application import IssuerApplicationConfig, IssuerApplicationBlocked
from aos_api.aip_network_issuer_attempt import _private_directory_fd, _read_marker
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.aip_network_policy_action_producer import (
    NetworkActivationProposalRequest, build_network_proposal_request, propose_network_activation,
)
from aos_api.aip_network_proposal_reconcile import inquire_network_proposal
from aos_api.auth import Principal, parse_bearer, resolve_principal
from aos_api.tenant_scope import TenantScope


def _identity(config, principal, authorization):
    if type(config) is not IssuerApplicationConfig:
        raise IssuerApplicationBlocked('NETWORK_PROPOSAL_PRODUCT_UNCONFIGURED', 503)
    try:
        config.__post_init__()
    except Exception:
        raise IssuerApplicationBlocked('NETWORK_PROPOSAL_PRODUCT_CONFIG_BLOCKED', 503) from None
    try:
        _require_external_oidc_config()
        if type(principal) is not Principal or principal.token_kind != 'oidc':
            raise ValueError()
        verified = resolve_principal(token=parse_bearer(authorization),
            header_org=principal.org_id, header_project=principal.project_id)
        if (verified.token_kind != 'oidc' or not verified.subject or verified.subject == 'unknown'
                or verified.subject != verified.subject.strip() or not verified.subject.isprintable()
                or (verified.subject, verified.org_id, verified.project_id) != (
                    principal.subject, principal.org_id, principal.project_id)):
            raise ValueError()
        return verified
    except Exception:
        raise IssuerApplicationBlocked('NETWORK_PROPOSAL_PRODUCT_IDENTITY_BLOCKED', 403) from None


def _slot(principal, policy_id, revision, version):
    if (type(policy_id) is not str or not 1 <= len(policy_id) <= 200
            or policy_id != policy_id.strip() or not policy_id.isprintable()
            or type(revision) is not int or revision < 1
            or type(version) is not int or version < 0):
        raise IssuerApplicationBlocked('NETWORK_PROPOSAL_PRODUCT_INPUT_INVALID', 422)
    return 'network-proposal-v1-'+canonical_hash([
        principal.org_id, principal.project_id, principal.subject, policy_id, revision, version])


def _envelope(principal, body, version):
    key = _slot(principal, body.candidate.policy_id, body.candidate.revision, version)
    build_network_proposal_request(TenantScope(principal.org_id, principal.project_id),
                                   body.candidate, version, body.expires_at)
    request = body.model_dump(mode='json', by_alias=True)
    return {'schemaVersion': 1, 'state': 'ATTEMPTED', 'key': key,
        'orgId': principal.org_id, 'projectId': principal.project_id,
        'subject': principal.subject, 'headVersion': version,
        'requestHash': canonical_hash(request), 'request': request}


def _read(directory_fd, key, principal, policy_id, revision, version):
    prior = _read_marker(directory_fd, key+'.json', allow_missing=True)
    if prior is None:
        return None
    body = NetworkActivationProposalRequest.model_validate(prior['request'])
    if (type(prior.get('schemaVersion')) is not int or type(prior.get('headVersion')) is not int
            or body.expires_at.tzinfo is None or body.candidate.policy_id != policy_id
            or body.candidate.revision != revision or prior != _envelope(principal, body, version)):
        raise ValueError('saved request mismatch')
    return body


def _observe(principal, body, version, key):
    return inquire_network_proposal(principal, body, expected_version=version, idempotency_key=key)


def inquire_product_proposal(config, policy_id, revision, version, principal, authorization):
    verified = _identity(config, principal, authorization)
    key = _slot(verified, policy_id, revision, version)
    try:
        fd = _private_directory_fd(config.attempt_directory)
        try:
            body = _read(fd, key, verified, policy_id, revision, version)
        finally:
            os.close(fd)
    except Exception:
        raise IssuerApplicationBlocked('NETWORK_PROPOSAL_SAVED_REQUEST_UNTRUSTED', 503) from None
    return {'status': 'not_attempted'} if body is None else _observe(verified, body, version, key)


def submit_product_proposal(config, body, version, principal, authorization):
    verified = _identity(config, principal, authorization)
    try:
        if type(body) is not NetworkActivationProposalRequest or body.expires_at.tzinfo is None:
            raise ValueError()
        envelope = _envelope(verified, body, version)
        raw = json.dumps(envelope, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        if len(raw) > 4096:
            raise ValueError()
    except Exception:
        raise IssuerApplicationBlocked('NETWORK_PROPOSAL_PRODUCT_INPUT_INVALID', 422) from None
    key = envelope['key']
    reserved = False
    try:
        directory_fd = _private_directory_fd(config.attempt_directory)
        try:
            prior = _read(directory_fd, key, verified, body.candidate.policy_id, body.candidate.revision, version)
            if prior is None:
                now = datetime.now(UTC)
                if not now < body.expires_at <= now+timedelta(minutes=15):
                    raise IssuerApplicationBlocked('NETWORK_PROPOSAL_PRODUCT_EXPIRY_INVALID', 422)
                try:
                    fd = os.open(key+'.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                 | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory_fd)
                except FileExistsError:
                    prior = _read(directory_fd, key, verified, body.candidate.policy_id, body.candidate.revision, version)
                    if prior is None:
                        raise ValueError('reservation disappeared')
                else:
                    try:
                        os.fchmod(fd, 0o600)
                        written = 0
                        while written < len(raw):
                            count = os.write(fd, raw[written:])
                            if count <= 0:
                                raise OSError('partial persistence')
                            written += count
                        os.fsync(fd)
                        os.fsync(directory_fd)
                        reserved = True
                    finally:
                        os.close(fd)
            if prior is not None and _envelope(verified, prior, version) != envelope:
                raise IssuerApplicationBlocked('NETWORK_PROPOSAL_PRODUCT_REQUEST_CONFLICT', 409)
        finally:
            os.close(directory_fd)
    except IssuerApplicationBlocked:
        raise
    except Exception:
        raise IssuerApplicationBlocked('NETWORK_PROPOSAL_SAVED_REQUEST_UNTRUSTED', 503) from None
    if reserved:
        try:
            propose_network_activation(verified, body.candidate, expected_version=version,
                idempotency_key=key, expires_at=body.expires_at)
        except Exception:
            # A failed response cannot prove rollback. Never delete the reservation.
            pass
    return _observe(verified, body, version, key)
