"""Require a separate database login to issue network approval evidence."""

from alembic import op


revision = "a0v_118"
down_revision = "a0v_117"
branch_labels = depends_on = None


def upgrade() -> None:
    # Fail closed until a separate deployment gate provisions SCRAM credentials,
    # denies local trust for this role, and starts an isolated issuer process.
    op.execute("""DO $$
      DECLARE found_role record;
      BEGIN
        SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,
               rolreplication,rolbypassrls INTO found_role
          FROM pg_roles WHERE rolname='aos_network_approval_issuer';
        IF NOT FOUND THEN
          CREATE ROLE aos_network_approval_issuer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
        ELSIF found_role.rolcanlogin OR found_role.rolinherit OR found_role.rolsuper
           OR found_role.rolcreatedb OR found_role.rolcreaterole
           OR found_role.rolreplication OR found_role.rolbypassrls THEN
          RAISE EXCEPTION 'NETWORK_APPROVAL_ISSUER_ROLE_DRIFT' USING ERRCODE='42501';
        END IF;
        IF EXISTS (
          SELECT 1 FROM pg_auth_members m JOIN pg_roles target ON target.oid=m.roleid
           WHERE m.member='aos_network_approval_issuer'::regrole
             AND target.rolname<>'aos_runtime'
        ) THEN
          RAISE EXCEPTION 'NETWORK_APPROVAL_ISSUER_MEMBERSHIP_DRIFT' USING ERRCODE='42501';
        END IF;
      END $$""")
    op.execute("GRANT aos_runtime TO aos_network_approval_issuer")
    op.execute("""CREATE FUNCTION public.aip_network_approval_event_guard_a0v_118()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
      DECLARE old_action text; new_action text;
      BEGIN
        IF TG_OP IN ('UPDATE','DELETE') THEN
          SELECT p.action_type_id INTO old_action FROM public.aip_action_proposal p
            WHERE p.org_id=OLD.org_id AND p.project_id=OLD.project_id
              AND p.proposal_id=OLD.proposal_id;
          IF old_action IS NULL THEN
            RAISE EXCEPTION 'NETWORK_APPROVAL_PROPOSAL_UNAVAILABLE' USING ERRCODE='42501';
          END IF;
        END IF;
        IF TG_OP IN ('INSERT','UPDATE') THEN
          SELECT p.action_type_id INTO new_action FROM public.aip_action_proposal p
            WHERE p.org_id=NEW.org_id AND p.project_id=NEW.project_id
              AND p.proposal_id=NEW.proposal_id;
          IF new_action IS NULL THEN
            RAISE EXCEPTION 'NETWORK_APPROVAL_PROPOSAL_UNAVAILABLE' USING ERRCODE='42501';
          END IF;
        END IF;
        IF old_action='aip_activate_network_policy'
           OR new_action='aip_activate_network_policy' THEN
          IF TG_OP <> 'INSERT' THEN
            RAISE EXCEPTION 'NETWORK_APPROVAL_EVENT_IMMUTABLE' USING ERRCODE='42501';
          END IF;
          IF session_user <> 'aos_network_approval_issuer'
             OR current_user <> 'aos_runtime' THEN
            RAISE EXCEPTION 'NETWORK_APPROVAL_ISSUER_REQUIRED' USING ERRCODE='42501';
          END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.aip_network_approval_event_guard_a0v_118() FROM PUBLIC")
    op.execute("""CREATE TRIGGER aip_network_approval_event_guard_a0v_118
      BEFORE INSERT OR UPDATE OR DELETE ON public.aip_action_approval_event
      FOR EACH ROW EXECUTE FUNCTION public.aip_network_approval_event_guard_a0v_118()""")
    op.execute("""CREATE FUNCTION public.aip_network_proposal_guard_a0v_118()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
      BEGIN
        IF TG_OP='INSERT' THEN
          IF NEW.action_type_id='aip_activate_network_policy'
             AND (NEW.status <> 'drafted' OR NEW.version <> 1
                  OR NEW.action_binding_hash IS NULL
                  OR NEW.approval_policy_hash IS NULL) THEN
            RAISE EXCEPTION 'NETWORK_PROPOSAL_INITIAL_STATE_REQUIRED' USING ERRCODE='42501';
          END IF;
          IF NEW.action_type_id='aip_activate_network_policy'
             AND session_user='aos_network_approval_issuer' THEN
            RAISE EXCEPTION 'NETWORK_PROPOSAL_MAKER_ROLE_REQUIRED' USING ERRCODE='42501';
          END IF;
          RETURN NEW;
        END IF;
        IF TG_OP='DELETE' THEN
          IF OLD.action_type_id='aip_activate_network_policy' THEN
            RAISE EXCEPTION 'NETWORK_PROPOSAL_DELETE_FORBIDDEN' USING ERRCODE='42501';
          END IF;
          RETURN OLD;
        END IF;
        IF OLD.action_type_id='aip_activate_network_policy'
           OR NEW.action_type_id='aip_activate_network_policy' THEN
          IF (to_jsonb(OLD) - ARRAY['status','version','updated_at'])
             IS DISTINCT FROM
             (to_jsonb(NEW) - ARRAY['status','version','updated_at']) THEN
            RAISE EXCEPTION 'NETWORK_PROPOSAL_CORE_IMMUTABLE' USING ERRCODE='42501';
          END IF;
          IF NEW.version <> OLD.version + 1 THEN
            RAISE EXCEPTION 'NETWORK_PROPOSAL_VERSION_INVALID' USING ERRCODE='23514';
          END IF;
          IF NEW.status IN ('approved','rejected') AND NEW.status IS DISTINCT FROM OLD.status
             AND (session_user <> 'aos_network_approval_issuer'
                  OR current_user <> 'aos_runtime') THEN
            RAISE EXCEPTION 'NETWORK_APPROVAL_ISSUER_REQUIRED' USING ERRCODE='42501';
          END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.aip_network_proposal_guard_a0v_118() FROM PUBLIC")
    op.execute("""CREATE TRIGGER aip_network_proposal_guard_a0v_118
      BEFORE INSERT OR UPDATE OR DELETE ON public.aip_action_proposal
      FOR EACH ROW EXECUTE FUNCTION public.aip_network_proposal_guard_a0v_118()""")


def downgrade() -> None:
    raise RuntimeError("network approval issuer boundary may not be silently removed")
