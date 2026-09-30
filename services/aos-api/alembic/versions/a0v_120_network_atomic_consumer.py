"""Consume an exact network approval through a nonprivileged atomic function."""
from alembic import op

revision = "a0v_120"
down_revision = "a0v_119"
branch_labels = depends_on = None

SCOPED_TABLES = (
    "aip_action_proposal", "aip_action_draft", "aip_action_approval_event",
    "aip_action_withdrawal_event", "meta_membership",
    "aip_runtime_guard_policy_head", "aip_runtime_guard_policy_revision",
    "aip_network_policy_head", "aip_network_policy_revision", "aip_network_policy_receipt",
)

ROLE_PREFLIGHT_SQL = """DO $$ BEGIN
  IF (SELECT count(*) FROM pg_roles WHERE rolname IN
      ('aos_network_consumer_call','aos_network_consumer_owner')) <> 2
     OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN
        ('aos_network_consumer_call','aos_network_consumer_owner')
        AND (rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole
             OR rolreplication OR rolbypassrls))
     OR EXISTS (SELECT 1 FROM pg_auth_members WHERE
        roleid IN ('aos_network_consumer_call'::regrole,'aos_network_consumer_owner'::regrole)
        OR member IN ('aos_network_consumer_call'::regrole,'aos_network_consumer_owner'::regrole)) THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_ROLE_DRIFT' USING ERRCODE='42501';
  END IF;
END $$"""

HISTORY_GATE_SQL = """DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM public.aip_network_policy_receipt WHERE operation='network_policy.activate')
     OR EXISTS (SELECT 1 FROM public.aip_action_approval_event a
                JOIN public.aip_action_proposal p USING(org_id,project_id,proposal_id)
                WHERE p.action_type_id='aip_activate_network_policy') THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_HISTORY_RECONCILIATION_REQUIRED' USING ERRCODE='42501';
  END IF;
END $$"""


CONSUMER_SQL = """CREATE FUNCTION public.aip_consume_network_activation_a0v_120(
  p_org text,p_project text,p_proposal text,p_event text) RETURNS jsonb
  LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE
  p public.aip_action_proposal%ROWTYPE;
  a public.aip_action_approval_event%ROWTYPE;
  h public.aip_network_policy_head%ROWTYPE;
  e public.aip_runtime_guard_policy_revision%ROWTYPE;
  prior public.aip_network_policy_receipt%ROWTYPE;
  stable jsonb; candidate jsonb; meta jsonb; obj jsonb; result jsonb; payload jsonb;
  expected_policy jsonb := '{"floor":"R2","reasons":["formal_policy_activation"],
    "makerChecker":true,"minimumApprovals":1,"executionAllowed":true,"draftOnly":false}';
  maker_role text; checker_role text; request_digest text; target_digest text;
  binding_digest text; v_policy_id text; receipt_id text; egress_id text;
  target_revision bigint; expected_revision bigint; expected_version bigint; egress_revision bigint;
  checked_at timestamptz; starts_at timestamptz; ends_at timestamptz;
BEGIN
  IF session_user <> 'aos_network_consumer_call' OR current_user <> 'aos_network_consumer_owner'
     OR p_org IS NULL OR p_org='' OR p_org<>btrim(p_org)
     OR p_project IS NULL OR p_project='' OR p_project<>btrim(p_project)
     OR p_proposal IS NULL OR p_proposal='' OR p_proposal<>btrim(p_proposal)
     OR p_event IS NULL OR p_event='' OR p_event<>btrim(p_event)
     OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_SCOPE_IDENTITY_REQUIRED' USING ERRCODE='42501';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN (session_user,current_user)
               AND (rolsuper OR rolbypassrls OR rolinherit OR rolcreatedb OR rolcreaterole OR rolreplication
                    OR (rolname=current_user AND rolcanlogin)))
     OR EXISTS (SELECT 1 FROM pg_auth_members WHERE roleid IN (session_user::regrole,current_user::regrole)
                 OR member IN (session_user::regrole,current_user::regrole)) THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_ROLE_DRIFT' USING ERRCODE='42501';
  END IF;
  SELECT * INTO p FROM public.aip_action_proposal
    WHERE org_id=p_org AND project_id=p_project AND proposal_id=p_proposal FOR UPDATE;
  IF NOT FOUND OR p.action_type_id IS DISTINCT FROM 'aip_activate_network_policy' THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_PROPOSAL_UNAVAILABLE' USING ERRCODE='42501';
  END IF;
  request_digest := public.aip_network_consumer_hash_a0v_120(jsonb_build_object(
    'operation','network_policy.activate','tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),
    'proposalId',p_proposal,'approvalEventId',p_event,
    'targetContentHash',p.payload->>'targetContentHash','bindingHash',p.action_binding_hash));
  SELECT * INTO prior FROM public.aip_network_policy_receipt WHERE org_id=p_org AND project_id=p_project
    AND operation='network_policy.activate' AND idempotency_key=p_proposal;
  IF FOUND THEN
    IF prior.request_hash IS DISTINCT FROM request_digest
       OR prior.result_ref->>'approvalEventId' IS DISTINCT FROM p_event
       OR prior.result_ref->>'proposalId' IS DISTINCT FROM p_proposal
       OR prior.result_ref->>'receiptId' IS DISTINCT FROM prior.receipt_id THEN
      RAISE EXCEPTION 'NETWORK_CONSUMER_RECEIPT_CONFLICT' USING ERRCODE='23514';
    END IF;
    RETURN prior.result_ref; -- Historical reconciliation; no new authorization or write.
  END IF;
  IF p.status IS DISTINCT FROM 'approved' OR p.risk_level IS DISTINCT FROM 'R2'
     OR p.policy_snapshot IS DISTINCT FROM expected_policy
     OR p.approval_policy_hash IS DISTINCT FROM public.aip_network_consumer_hash_a0v_120(expected_policy)
     OR p.task_id IS NOT NULL OR p.run_id IS NOT NULL OR p.impact_preview_id IS NOT NULL
     OR p.source_draft_id IS NOT NULL OR p.client_risk_hint IS NOT NULL
     OR (p.object_ref IS NOT NULL AND p.object_ref<>'null'::jsonb)
     OR p.diff IS DISTINCT FROM '{}'::jsonb OR p.evidence_refs IS DISTINCT FROM '[]'::jsonb THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_PROPOSAL_INVALID' USING ERRCODE='42501';
  END IF;
  PERFORM approval_event_id FROM public.aip_action_approval_event
    WHERE org_id=p_org AND project_id=p_project AND proposal_id=p_proposal
    ORDER BY approval_event_id FOR SHARE;
  IF (SELECT count(*) FROM public.aip_action_approval_event
       WHERE org_id=p_org AND project_id=p_project AND proposal_id=p_proposal)<>1 THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_APPROVAL_UNAVAILABLE' USING ERRCODE='42501';
  END IF;
  SELECT * INTO a FROM public.aip_action_approval_event WHERE org_id=p_org AND project_id=p_project
    AND proposal_id=p_proposal AND approval_event_id=p_event;
  IF NOT FOUND OR a.decision IS DISTINCT FROM 'approved' OR a.slot_id IS DISTINCT FROM 'checker.1'
     OR a.actor_id IS NOT DISTINCT FROM p.created_by OR a.expires_at IS NULL
     OR p.version IS DISTINCT FROM a.proposal_version+1
     OR a.proposal_hash IS DISTINCT FROM p.proposal_hash
     OR a.action_binding_hash IS DISTINCT FROM p.action_binding_hash
     OR a.approval_policy_hash IS DISTINCT FROM p.approval_policy_hash THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_APPROVAL_INVALID' USING ERRCODE='42501';
  END IF;
  IF EXISTS (SELECT 1 FROM public.aip_action_withdrawal_event
              WHERE org_id=p_org AND project_id=p_project AND proposal_id=p_proposal) THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_WITHDRAWN' USING ERRCODE='42501';
  END IF;
  SELECT snapshot INTO stable FROM public.aip_action_draft WHERE org_id=p_org AND project_id=p_project
    AND proposal_id=p_proposal FOR SHARE;
  IF NOT FOUND OR public.aip_network_consumer_hash_a0v_120(stable) IS DISTINCT FROM p.proposal_hash
     OR stable->'tenantScope' IS DISTINCT FROM jsonb_build_object('orgId',p_org,'projectId',p_project)
     OR stable->>'createdBy' IS DISTINCT FROM p.created_by
     OR stable->'actionType' IS DISTINCT FROM p.action_type_snapshot
     OR stable->'payload' IS DISTINCT FROM p.payload OR stable->'policy' IS DISTINCT FROM p.policy_snapshot
     OR stable->>'actionBindingHash' IS DISTINCT FROM p.action_binding_hash
     OR stable->>'approvalPolicyHash' IS DISTINCT FROM p.approval_policy_hash
     OR (stable->>'expiresAt')::timestamptz IS DISTINCT FROM p.expires_at THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_DRAFT_DRIFT' USING ERRCODE='42501';
  END IF;
  PERFORM subject FROM public.meta_membership WHERE org_id=p_org AND project_id=p_project
    AND subject IN (p.created_by,a.actor_id) ORDER BY subject FOR SHARE;
  SELECT lower(role) INTO maker_role FROM public.meta_membership
    WHERE org_id=p_org AND project_id=p_project AND subject=p.created_by;
  SELECT lower(role) INTO checker_role FROM public.meta_membership
    WHERE org_id=p_org AND project_id=p_project AND subject=a.actor_id;
  IF (maker_role IN ('owner','admin') AND checker_role IN ('owner','admin')) IS NOT TRUE
     OR a.eligibility_snapshot_hash IS DISTINCT FROM public.aip_network_consumer_hash_a0v_120(jsonb_build_object(
       'tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),'actorId',a.actor_id,
       'roles',jsonb_build_array(checker_role),'slotId','checker.1','approvalPolicyHash',p.approval_policy_hash)) THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_CURRENT_MEMBER_REQUIRED' USING ERRCODE='42501';
  END IF;
  SELECT jsonb_build_object('id',id,'name',name,'description',description,'published',published,
      'properties',properties,'requiredMarkings',required_markings) INTO obj
    FROM public.meta_object_type WHERE id='NetworkPolicyRevision' FOR SHARE;
  IF obj IS DISTINCT FROM '{"id":"NetworkPolicyRevision","name":"网络策略修订",
      "description":"受控网络策略激活目标","published":true,"properties":[],"requiredMarkings":[]}'::jsonb THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_METADATA_DRIFT' USING ERRCODE='42501';
  END IF;
  SELECT jsonb_build_object('id',id,'name',name,'objectType',object_type,'parameters',parameters,
      'requiredMarkings',required_markings,'submissionCriteria',submission_criteria) INTO meta
    FROM public.meta_action_type WHERE id='aip_activate_network_policy' FOR SHARE;
  IF meta IS DISTINCT FROM '{"id":"aip_activate_network_policy","name":"激活网络策略",
      "objectType":"NetworkPolicyRevision","parameters":[],"requiredMarkings":[],"submissionCriteria":[]}'::jsonb
     OR p.action_type_snapshot IS DISTINCT FROM meta || jsonb_build_object(
          'revisionHash',public.aip_network_consumer_hash_a0v_120(meta))
     OR p.action_type_revision_hash IS DISTINCT FROM public.aip_network_consumer_hash_a0v_120(meta) THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_METADATA_DRIFT' USING ERRCODE='42501';
  END IF;
  candidate := p.payload->'candidate';
  v_policy_id := candidate->>'policyId';
  target_revision := (candidate->>'revision')::bigint;
  expected_revision := (p.payload->>'expectedHeadRevision')::bigint;
  expected_version := (p.payload->>'expectedHeadVersion')::bigint;
  starts_at := (candidate->>'effectiveFrom')::timestamptz;
  ends_at := (candidate->>'effectiveUntil')::timestamptz;
  target_digest := public.aip_network_consumer_hash_a0v_120(candidate);
  binding_digest := public.aip_network_consumer_hash_a0v_120(jsonb_build_object(
    'tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),
    'actionTypeId','aip_activate_network_policy','policyId',v_policy_id,'revision',target_revision,
    'expectedHeadRevision',expected_revision,'expectedHeadVersion',expected_version,'targetContentHash',target_digest));
  IF (v_policy_id<>'' AND v_policy_id=btrim(v_policy_id) AND target_revision=expected_revision+1
      AND expected_revision>=0 AND expected_version>=0 AND starts_at<ends_at
      AND jsonb_typeof(candidate->'revision')='number'
      AND jsonb_typeof(p.payload->'expectedHeadRevision')='number'
      AND jsonb_typeof(p.payload->'expectedHeadVersion')='number'
      AND candidate->'allowedSchemes'='["https"]'::jsonb AND candidate->'allowedPorts'='[443]'::jsonb
      AND candidate->'tlsRequired'='true'::jsonb AND candidate->'publicFallbackAllowed'='false'::jsonb
      AND candidate->>'lifecycle'='active' AND candidate->>'owner'<>'' AND candidate->>'approvalRef'<>''
      AND candidate->'egressPolicyRef'->>'assetType'='EgressPolicyRevision'
      AND jsonb_typeof(candidate->'allowedHosts')='array'
      AND jsonb_array_length(candidate->'allowedHosts') BETWEEN 1 AND 32) IS NOT TRUE
     OR p.payload->>'targetContentHash' IS DISTINCT FROM target_digest
     OR p.payload->>'bindingHash' IS DISTINCT FROM binding_digest
     OR p.action_binding_hash IS DISTINCT FROM binding_digest THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_TARGET_DRIFT' USING ERRCODE='42501';
  END IF;
  SELECT * INTO h FROM public.aip_network_policy_head
    WHERE org_id=p_org AND project_id=p_project AND aip_network_policy_head.policy_id=v_policy_id FOR UPDATE;
  IF coalesce(h.current_revision,0)<>expected_revision OR coalesce(h.version,0)<>expected_version THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_HEAD_DRIFT' USING ERRCODE='23514';
  END IF;
  egress_id := candidate->'egressPolicyRef'->>'assetId';
  SELECT current_revision INTO egress_revision FROM public.aip_runtime_guard_policy_head
    WHERE org_id=p_org AND project_id=p_project AND policy_kind='egress'
      AND aip_runtime_guard_policy_head.policy_id=egress_id FOR SHARE;
  SELECT * INTO e FROM public.aip_runtime_guard_policy_revision
    WHERE org_id=p_org AND project_id=p_project AND policy_kind='egress'
      AND aip_runtime_guard_policy_revision.policy_id=egress_id AND revision=egress_revision;
  IF NOT FOUND OR (egress_revision=(candidate->'egressPolicyRef'->>'revision')::bigint
      AND e.content_hash=candidate->'egressPolicyRef'->>'contentHash' AND e.lifecycle='active'
      AND e.payload->'tenant'=jsonb_build_object('orgId',p_org,'projectId',p_project)
      AND e.payload->>'policyId'=e.policy_id AND (e.payload->>'revision')::bigint=e.revision
      AND e.payload->>'contentHash'=e.content_hash AND e.payload->>'lifecycle'=e.lifecycle
      AND (e.payload->>'effectiveFrom')::timestamptz=e.effective_from
      AND (e.payload->>'effectiveUntil')::timestamptz=e.effective_until
      AND e.content_hash=public.aip_network_consumer_hash_a0v_120(
          e.payload-ARRAY['tenant','contentHash','createdBy','createdAt'])
      AND e.payload->>'environment'='development' AND e.payload->>'regionState'='confirmed'
      AND length(btrim(e.payload->>'region'))>0 AND e.payload->'allowPublicFallback'='false'::jsonb
      AND e.payload->>'unknownDestinationBehavior'='block'
      AND (e.payload->'allowedHosts') @> (candidate->'allowedHosts')
      AND (e.payload->'allowedSchemes') @> (candidate->'allowedSchemes')
      AND (e.payload->'allowedPorts') @> (candidate->'allowedPorts')
      AND starts_at>=e.effective_from AND ends_at<=e.effective_until) IS NOT TRUE THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_EGRESS_DRIFT' USING ERRCODE='42501';
  END IF;
  checked_at := clock_timestamp();
  IF (checked_at<p.expires_at AND checked_at<a.expires_at AND starts_at<=checked_at
      AND checked_at<ends_at AND e.effective_from<=checked_at AND checked_at<e.effective_until) IS NOT TRUE THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_EXPIRED' USING ERRCODE='42501';
  END IF;
  IF h.policy_id IS NULL THEN
    INSERT INTO public.aip_network_policy_head(org_id,project_id,policy_id,current_revision,version)
      VALUES(p_org,p_project,v_policy_id,target_revision,1);
  ELSE
    UPDATE public.aip_network_policy_head SET current_revision=target_revision,version=version+1,updated_at=checked_at
      WHERE org_id=p_org AND project_id=p_project AND aip_network_policy_head.policy_id=v_policy_id;
  END IF;
  payload := candidate || jsonb_build_object('tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),
    'contentHash',target_digest,'createdBy',p.created_by,'createdAt',checked_at);
  INSERT INTO public.aip_network_policy_revision(org_id,project_id,policy_id,revision,content_hash,lifecycle,
    effective_from,effective_until,payload,created_by,created_at)
    VALUES(p_org,p_project,v_policy_id,target_revision,target_digest,'active',starts_at,ends_at,payload,p.created_by,checked_at);
  receipt_id := 'network-consume-' || request_digest;
  result := jsonb_build_object('resourceType','NetworkPolicyRevision','resourceId',v_policy_id,
    'revision',target_revision,'contentHash',target_digest,'proposalId',p_proposal,
    'approvalEventId',p_event,'receiptId',receipt_id);
  INSERT INTO public.aip_network_policy_receipt(org_id,project_id,receipt_id,operation,idempotency_key,
    request_hash,result_ref,created_by,created_at)
    VALUES(p_org,p_project,receipt_id,'network_policy.activate',p_proposal,request_digest,result,p.created_by,checked_at);
  checked_at := clock_timestamp();
  IF (checked_at<p.expires_at AND checked_at<a.expires_at AND checked_at<ends_at
      AND checked_at<e.effective_until) IS NOT TRUE THEN
    RAISE EXCEPTION 'NETWORK_CONSUMER_EXPIRED' USING ERRCODE='42501';
  END IF;
  RETURN result;
END $$"""


def upgrade() -> None:
    op.execute(ROLE_PREFLIGHT_SQL)
    op.execute(HISTORY_GATE_SQL)
    op.execute("GRANT USAGE ON SCHEMA public TO aos_network_consumer_owner,aos_network_consumer_call")
    for table in SCOPED_TABLES:
        op.execute(f"GRANT SELECT ON public.{table} TO aos_network_consumer_owner")
        op.execute(f"""CREATE POLICY network_consumer_a0v120 ON public.{table} TO aos_network_consumer_owner
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    for table, column in (
        ("aip_action_proposal", "proposal_id"), ("aip_action_draft", "proposal_id"),
        ("aip_action_approval_event", "approval_event_id"), ("meta_membership", "subject"),
        ("aip_runtime_guard_policy_head", "policy_id"),
        ("meta_object_type", "id"), ("meta_action_type", "id"),
    ):
        op.execute(f"GRANT SELECT,UPDATE({column}) ON public.{table} TO aos_network_consumer_owner")
    op.execute("GRANT INSERT ON public.aip_network_policy_head,public.aip_network_policy_revision,"
               "public.aip_network_policy_receipt TO aos_network_consumer_owner")
    op.execute("GRANT UPDATE(current_revision,version,updated_at) ON public.aip_network_policy_head TO aos_network_consumer_owner")
    op.execute("""CREATE FUNCTION public.aip_network_consumer_hash_a0v_120(value jsonb) RETURNS text
      LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog AS $$
        SELECT encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(value),'UTF8'),'sha256'),'hex')
      $$""")
    op.execute("REVOKE ALL ON FUNCTION public.aip_network_consumer_hash_a0v_120(jsonb) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.aip_network_consumer_hash_a0v_120(jsonb) TO aos_network_consumer_owner")
    # psycopg receives an empty parameter mapping from SQLAlchemy; escape literal %.
    op.get_bind().exec_driver_sql(CONSUMER_SQL.replace("%", "%%"))
    signature = "public.aip_consume_network_activation_a0v_120(text,text,text,text)"
    op.execute(f"ALTER FUNCTION {signature} OWNER TO aos_network_consumer_owner")
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO aos_network_consumer_call")
    op.execute("""CREATE OR REPLACE FUNCTION public.aip_network_active_insert_guard()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
        IF NEW.lifecycle='active' AND (session_user<>'aos_network_consumer_call'
            OR current_user<>'aos_network_consumer_owner') THEN
          RAISE EXCEPTION 'NETWORK_ACTIVATION_CONSUMPTION_REQUIRED' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$""")


def downgrade() -> None:
    raise RuntimeError("atomic network consumption authority may not be silently removed")
