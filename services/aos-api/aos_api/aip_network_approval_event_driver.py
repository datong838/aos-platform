"""One exact durable approval event; no polling, identity substitution or startup."""
from aos_api.auth import Principal, parse_bearer, resolve_principal
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.aip_network_consumer_application import (
    ConsumerApplicationConfig, ConsumerApplicationBlocked, execute_consumer,
)
from aos_api.aip_network_consumer_contracts import NetworkConsumerReferences
from aos_api.db import connect_read_only
from aos_api.tenant_scope import TenantScope


def process_network_approval_event(config, proposal_id, approval_event_id, principal, authorization,
                                   *, connect_factory=None):
    """Resolve authoritative references then use the existing once-or-inquiry boundary.

    A future authorized subscriber supplies an exact event and current original-maker
    identity. A notification alone grants nothing; final consumption stays in the
    independent service/PG transaction. This function never stores credentials.
    """
    if type(config) is not ConsumerApplicationConfig:
        raise ConsumerApplicationBlocked('NETWORK_EVENT_CONSUMER_UNCONFIGURED', 503)
    try:
        config.__post_init__()
    except Exception:
        raise ConsumerApplicationBlocked('NETWORK_EVENT_CONSUMER_CONFIG_BLOCKED', 503) from None
    try:
        if (type(principal) is not Principal or principal.token_kind != 'oidc'
                or any(type(v) is not str or not 1 <= len(v) <= 160
                       or not v.isprintable() or any(c.isspace() for c in v)
                       for v in (proposal_id, approval_event_id))):
            raise ValueError()
        _require_external_oidc_config()
        verified = resolve_principal(token=parse_bearer(authorization),
            header_org=principal.org_id, header_project=principal.project_id)
        if (type(verified) is not Principal or verified.token_kind != 'oidc'
                or not verified.subject or verified.subject == 'unknown'
                or verified.subject != verified.subject.strip() or not verified.subject.isprintable()
                or (verified.subject, verified.org_id, verified.project_id) != (
                    principal.subject, principal.org_id, principal.project_id)):
            raise ValueError()
        scope = TenantScope(verified.org_id, verified.project_id)
    except Exception:
        raise ConsumerApplicationBlocked('NETWORK_EVENT_CURRENT_IDENTITY_REQUIRED', 403) from None
    try:
        with (connect_factory or connect_read_only)(scope) as conn:
            identity = conn.execute("SELECT current_user AS role,"
                "current_setting('aos.org_id',true) AS org_id,"
                "current_setting('aos.project_id',true) AS project_id,"
                "current_setting('transaction_read_only') AS readonly,"
                "current_setting('transaction_isolation') AS isolation").fetchone()
            if (conn.read_only is not True or identity is None or
                    (identity['role'], identity['org_id'], identity['project_id'],
                     identity['readonly'], identity['isolation']) != (
                         'aos_runtime', *scope.key, 'on', 'repeatable read')):
                raise ConsumerApplicationBlocked('NETWORK_EVENT_READ_IDENTITY_REQUIRED', 503)
            row = conn.execute("""SELECT p.proposal_hash,p.action_binding_hash,p.payload,
                p.approval_policy_hash,p.created_by,p.action_type_id,
                a.decision,a.actor_id,a.proposal_hash AS event_proposal_hash,
                a.action_binding_hash AS event_binding_hash,
                a.approval_policy_hash AS event_policy_hash,a.slot_id,
                EXISTS(SELECT 1 FROM meta_membership m WHERE m.org_id=p.org_id
                  AND m.project_id=p.project_id AND m.subject=p.created_by
                  AND lower(m.role) IN ('owner','admin')) AS maker_member
                FROM aip_action_proposal p JOIN aip_action_approval_event a
                  USING(org_id,project_id,proposal_id)
                WHERE p.org_id=%s AND p.project_id=%s AND p.proposal_id=%s
                  AND a.approval_event_id=%s""",
                (*scope.key, proposal_id, approval_event_id)).fetchone()
            if (row is None or row['created_by'] != verified.subject
                    or row['action_type_id'] != 'aip_activate_network_policy'
                    or row['decision'] != 'approved' or row['slot_id'] != 'checker.1'
                    or row['actor_id'] == verified.subject or row['maker_member'] is not True
                    or row['proposal_hash'] != row['event_proposal_hash']
                    or row['action_binding_hash'] != row['event_binding_hash']
                    or row['approval_policy_hash'] != row['event_policy_hash']
                    or row['payload'].get('bindingHash') != row['action_binding_hash']):
                raise ConsumerApplicationBlocked('NETWORK_EVENT_EXACT_MAKER_APPROVAL_REQUIRED', 403)
            refs = NetworkConsumerReferences(schema_version=1, proposal_id=proposal_id,
                approval_event_id=approval_event_id, proposal_hash=row['proposal_hash'],
                target_content_hash=row['payload']['targetContentHash'],
                binding_hash=row['action_binding_hash'])
    except ConsumerApplicationBlocked:
        raise
    except Exception:
        raise ConsumerApplicationBlocked('NETWORK_EVENT_AUTHORITY_READ_UNAVAILABLE', 503) from None
    # Connection is closed before IPC; the consumer rechecks current authority under
    # its own locks. Repeated events become Inquiry through the existing marker.
    return execute_consumer(config, refs, verified, authorization, inquiry=False)
