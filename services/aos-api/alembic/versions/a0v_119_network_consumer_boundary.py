"""Seal consumer identities and activation receipts before enabling consumption."""
from alembic import op


revision = "a0v_119"
down_revision = "a0v_118"
branch_labels = depends_on = None


ROLE_BOUNDARY_SQL = """DO $$
  DECLARE role_name text; found_role record;
  BEGIN
    FOREACH role_name IN ARRAY ARRAY['aos_network_consumer_call','aos_network_consumer_owner'] LOOP
      SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,
             rolreplication,rolbypassrls INTO found_role
        FROM pg_roles WHERE rolname=role_name;
      IF NOT FOUND THEN
        EXECUTE format('CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
                       'NOCREATEROLE NOREPLICATION NOBYPASSRLS',role_name);
      ELSIF found_role.rolcanlogin OR found_role.rolinherit OR found_role.rolsuper
         OR found_role.rolcreatedb OR found_role.rolcreaterole
         OR found_role.rolreplication OR found_role.rolbypassrls THEN
        RAISE EXCEPTION 'NETWORK_CONSUMER_ROLE_DRIFT' USING ERRCODE='42501';
      END IF;
      IF EXISTS (SELECT 1 FROM pg_auth_members
                 WHERE roleid=role_name::regrole OR member=role_name::regrole) THEN
        RAISE EXCEPTION 'NETWORK_CONSUMER_MEMBERSHIP_DRIFT' USING ERRCODE='42501';
      END IF;
      IF EXISTS (SELECT 1 FROM pg_class WHERE relowner=role_name::regrole)
         OR EXISTS (SELECT 1 FROM pg_proc WHERE proowner=role_name::regrole)
         OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspowner=role_name::regrole)
         OR EXISTS (SELECT 1 FROM pg_class c, LATERAL aclexplode(c.relacl) a
                    WHERE a.grantee=role_name::regrole) THEN
        RAISE EXCEPTION 'NETWORK_CONSUMER_OBJECT_PRIVILEGE_DRIFT' USING ERRCODE='42501';
      END IF;
    END LOOP;
  END $$"""


def upgrade() -> None:
    # No login, membership, table DML or function EXECUTE is granted here.
    # Provisioning and the atomic function each require a separate gate.
    op.execute(ROLE_BOUNDARY_SQL)
    op.execute("""CREATE FUNCTION public.aip_network_activation_receipt_guard_a0v_119()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
      BEGIN
        IF NEW.operation='network_policy.activate'
           AND (session_user <> 'aos_network_consumer_call'
                OR current_user <> 'aos_network_consumer_owner') THEN
          RAISE EXCEPTION 'NETWORK_CONSUMER_IDENTITY_REQUIRED' USING ERRCODE='42501';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.aip_network_activation_receipt_guard_a0v_119() FROM PUBLIC")
    op.execute("""CREATE TRIGGER aip_network_activation_receipt_guard_a0v_119
      BEFORE INSERT ON public.aip_network_policy_receipt FOR EACH ROW
      EXECUTE FUNCTION public.aip_network_activation_receipt_guard_a0v_119()""")


def downgrade() -> None:
    raise RuntimeError("network consumption identity boundary may not be silently removed")
