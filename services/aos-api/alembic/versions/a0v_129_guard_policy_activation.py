"""Formal guard policy metadata and isolated activation boundary.

No current-instance deployment or issuer login is authorized by this migration.
Consumer roles default to NOLOGIN and can only use the bounded function once
separately provisioned; ordinary Store active publication remains closed.
"""
from pathlib import Path
from alembic import op

revision = "a0v_129"
down_revision = "a0v_128"
branch_labels = depends_on = None

ACTIONS = "'aip_activate_egress_policy','aip_activate_data_policy'"
OBJECTS = "'EgressPolicyRevision','DataClassificationPolicyRevision'"


def upgrade():
    op.execute("""DO $$ DECLARE r record; role_name text; BEGIN
      FOREACH role_name IN ARRAY ARRAY['aos_guard_approval_issuer','aos_guard_policy_consumer_owner',
                                      'aos_guard_policy_consumer_call'] LOOP
        SELECT * INTO r FROM pg_roles WHERE rolname=role_name;
        IF NOT FOUND THEN
          EXECUTE format('CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',role_name);
        ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
           OR r.rolreplication OR r.rolbypassrls THEN
          RAISE EXCEPTION 'GUARD_POLICY_ROLE_DRIFT' USING ERRCODE='42501';
        END IF;
        IF EXISTS(SELECT 1 FROM pg_auth_members m
          WHERE (m.roleid=role_name::regrole OR m.member=role_name::regrole)
            AND NOT (role_name='aos_guard_approval_issuer'
                     AND m.member=role_name::regrole AND m.roleid='aos_runtime'::regrole)) THEN
          RAISE EXCEPTION 'GUARD_POLICY_MEMBERSHIP_DRIFT' USING ERRCODE='42501';
        END IF;
      END LOOP;
    END $$""")
    op.execute("GRANT aos_runtime TO aos_guard_approval_issuer")
    op.execute(f"""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM public.meta_object_type WHERE id IN ({OBJECTS}))
        OR EXISTS(SELECT 1 FROM public.meta_action_type WHERE id IN ({ACTIONS})) THEN
        RAISE EXCEPTION 'FORMAL_GUARD_METADATA_ALREADY_PRESENT' USING ERRCODE='23505';
      END IF;
    END $$""")
    op.execute(f"""CREATE FUNCTION public.guard_policy_metadata_a0v129()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      DECLARE owner_name text; BEGIN
        IF (TG_OP IN ('UPDATE','DELETE') AND OLD.id IN ({OBJECTS}))
           OR (TG_OP IN ('INSERT','UPDATE') AND NEW.id IN ({OBJECTS})) THEN
          SELECT pg_get_userbyid(relowner) INTO owner_name FROM pg_class
            WHERE oid='public.meta_object_type'::regclass;
          IF current_user IS DISTINCT FROM owner_name THEN
            RAISE EXCEPTION 'GUARD_POLICY_METADATA_RESERVED' USING ERRCODE='42501';
          END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.guard_policy_metadata_a0v129() FROM PUBLIC")
    op.execute("""CREATE TRIGGER guard_policy_metadata_a0v129
      BEFORE INSERT OR UPDATE OR DELETE ON public.meta_object_type
      FOR EACH ROW EXECUTE FUNCTION public.guard_policy_metadata_a0v129()""")
    op.execute("""INSERT INTO public.meta_object_type(id,name,description,published,properties,required_markings)
      VALUES('EgressPolicyRevision','出口策略修订','受控出口策略激活目标',true,'[]','[]'),
            ('DataClassificationPolicyRevision','数据分类策略修订','受控数据分类策略激活目标',true,'[]','[]')""")
    op.execute("""INSERT INTO public.meta_action_type(id,name,object_type,parameters,required_markings,submission_criteria)
      VALUES('aip_activate_egress_policy','激活出口策略','EgressPolicyRevision','[]','[]','[]'),
            ('aip_activate_data_policy','激活数据分类策略','DataClassificationPolicyRevision','[]','[]','[]')""")
    op.execute("""CREATE FUNCTION public.guard_policy_write_a0v129()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      DECLARE protected boolean:=false; BEGIN
        IF TG_TABLE_NAME='aip_runtime_guard_policy_revision' THEN
          protected := NEW.lifecycle='active' OR NEW.payload->>'lifecycle'='active';
        ELSIF TG_TABLE_NAME='aip_runtime_guard_policy_head' THEN
          protected := EXISTS(SELECT 1 FROM public.aip_runtime_guard_policy_revision r
            WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
              AND r.policy_kind=NEW.policy_kind AND r.policy_id=NEW.policy_id
              AND r.revision=NEW.current_revision AND r.lifecycle='active');
        ELSE
          protected := NEW.operation IN ('guard_policy.egress.activate','guard_policy.data_classification.activate');
        END IF;
        IF protected AND (current_user<>'aos_guard_policy_consumer_owner'
                          OR session_user<>'aos_guard_policy_consumer_call') THEN
          RAISE EXCEPTION 'GUARD_POLICY_CONSUMER_REQUIRED' USING ERRCODE='42501';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.guard_policy_write_a0v129() FROM PUBLIC")
    for table in ('aip_runtime_guard_policy_head','aip_runtime_guard_policy_revision','aip_runtime_guard_policy_receipt'):
        event = 'INSERT OR UPDATE' if table.endswith('_head') else 'INSERT'
        op.execute(f"CREATE TRIGGER guard_policy_write_a0v129 BEFORE {event} ON public.{table} "
                   "FOR EACH ROW EXECUTE FUNCTION public.guard_policy_write_a0v129()")
    op.execute(f"""CREATE FUNCTION public.guard_policy_proposal_a0v129()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN
        IF TG_OP='INSERT' THEN
          IF NEW.action_type_id IN ({ACTIONS}) THEN
            IF NEW.status<>'drafted' OR NEW.version<>1 OR NEW.action_binding_hash IS NULL
               OR NEW.approval_policy_hash IS NULL OR session_user='aos_guard_approval_issuer' THEN
              RAISE EXCEPTION 'GUARD_POLICY_DRAFT_MAKER_REQUIRED' USING ERRCODE='42501';
            END IF;
          END IF;
          RETURN NEW;
        END IF;
        IF TG_OP='DELETE' THEN
          IF OLD.action_type_id IN ({ACTIONS}) THEN
            RAISE EXCEPTION 'GUARD_POLICY_PROPOSAL_IMMUTABLE' USING ERRCODE='42501';
          END IF;
          RETURN OLD;
        END IF;
        IF OLD.action_type_id IN ({ACTIONS}) OR NEW.action_type_id IN ({ACTIONS}) THEN
          IF (to_jsonb(OLD)-ARRAY['status','version','updated_at']) IS DISTINCT FROM
             (to_jsonb(NEW)-ARRAY['status','version','updated_at']) OR NEW.version<>OLD.version+1 THEN
            RAISE EXCEPTION 'GUARD_POLICY_PROPOSAL_IMMUTABLE' USING ERRCODE='42501';
          END IF;
          IF NEW.status IN ('approved','rejected') AND NEW.status IS DISTINCT FROM OLD.status
             AND (session_user<>'aos_guard_approval_issuer' OR current_user<>'aos_runtime') THEN
            RAISE EXCEPTION 'GUARD_POLICY_ISSUER_REQUIRED' USING ERRCODE='42501';
          END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.guard_policy_proposal_a0v129() FROM PUBLIC")
    op.execute("""CREATE TRIGGER guard_policy_proposal_a0v129
      BEFORE INSERT OR UPDATE OR DELETE ON public.aip_action_proposal
      FOR EACH ROW EXECUTE FUNCTION public.guard_policy_proposal_a0v129()""")
    op.execute(f"""CREATE FUNCTION public.guard_policy_approval_a0v129()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      DECLARE action_id text; BEGIN
        IF TG_OP='INSERT' THEN
          SELECT action_type_id INTO action_id FROM public.aip_action_proposal
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND proposal_id=NEW.proposal_id;
        ELSE
          SELECT action_type_id INTO action_id FROM public.aip_action_proposal
            WHERE org_id=OLD.org_id AND project_id=OLD.project_id AND proposal_id=OLD.proposal_id;
        END IF;
        IF action_id IN ({ACTIONS}) AND (TG_OP<>'INSERT'
            OR session_user<>'aos_guard_approval_issuer' OR current_user<>'aos_runtime') THEN
          RAISE EXCEPTION 'GUARD_POLICY_ISSUER_REQUIRED' USING ERRCODE='42501';
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.guard_policy_approval_a0v129() FROM PUBLIC")
    op.execute("""CREATE TRIGGER guard_policy_approval_a0v129
      BEFORE INSERT OR UPDATE OR DELETE ON public.aip_action_approval_event
      FOR EACH ROW EXECUTE FUNCTION public.guard_policy_approval_a0v129()""")
    op.execute("GRANT USAGE ON SCHEMA public TO aos_guard_policy_consumer_owner,aos_guard_policy_consumer_call")
    scoped = ('aip_action_proposal','aip_action_draft','aip_action_approval_event',
              'aip_action_withdrawal_event','meta_membership','aip_runtime_guard_policy_head',
              'aip_runtime_guard_policy_revision','aip_runtime_guard_policy_receipt')
    for table in scoped:
        op.execute(f"GRANT SELECT ON public.{table} TO aos_guard_policy_consumer_owner")
        op.execute(f"""CREATE POLICY guard_consumer_a0v129 ON public.{table} TO aos_guard_policy_consumer_owner
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    for table,column in (('aip_action_proposal','proposal_id'),('aip_action_draft','proposal_id'),
        ('aip_action_approval_event','approval_event_id'),('meta_membership','subject'),
        ('aip_runtime_guard_policy_head','policy_id'),('meta_object_type','id'),('meta_action_type','id')):
        op.execute(f"GRANT SELECT,UPDATE({column}) ON public.{table} TO aos_guard_policy_consumer_owner")
    op.execute("GRANT INSERT ON public.aip_runtime_guard_policy_revision,public.aip_runtime_guard_policy_receipt TO aos_guard_policy_consumer_owner")
    op.execute("GRANT UPDATE(current_revision,version,updated_at) ON public.aip_runtime_guard_policy_head TO aos_guard_policy_consumer_owner")
    op.execute("GRANT EXECUTE ON FUNCTION public.aip_network_consumer_hash_a0v_120(jsonb) TO aos_guard_policy_consumer_owner")
    source=Path(__file__).resolve().parents[2]/'aos_api/aip_guard_policy_consumer.sql'
    op.get_bind().exec_driver_sql(source.read_text().replace('%','%%'))
    signature='public.aip_guard_activation_a0v_129('+','.join(['text']*8+['boolean'])+')'
    op.execute(f"ALTER FUNCTION {signature} OWNER TO aos_guard_policy_consumer_owner")
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO aos_guard_policy_consumer_call")


def downgrade():
    raise RuntimeError("formal guard activation boundaries cannot be silently removed")
