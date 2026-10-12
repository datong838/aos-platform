"""Remove inherited defaults from the three new Skill dispatch journals only."""
from alembic import op

revision = 'a0v_161'
down_revision = 'a0v_160'
branch_labels = depends_on = None


def upgrade():
    op.execute("""DO $acl$
    DECLARE
      names text[] := ARRAY['aip_skill_eval_intent','aip_skill_eval_dispatch','aip_skill_eval_dispatch_observation'];
      name text;
      relation oid;
      owner_id oid;
      runtime_id oid := (SELECT oid FROM pg_roles WHERE rolname='aos_runtime');
      writer_id oid := (SELECT oid FROM pg_roles WHERE rolname='aos_aip_eval_writer');
      col record;
    BEGIN
      IF runtime_id IS NULL OR writer_id IS NULL OR EXISTS (
        SELECT 1 FROM pg_roles WHERE oid=writer_id AND
        (rolcanlogin OR rolinherit OR rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication)
      ) THEN
        RAISE EXCEPTION 'Skill journal role profile mismatch' USING ERRCODE='42501';
      END IF;
      -- Validate the complete set before changing any grants. Unknown identities
      -- require reconciliation; never silently revoke their unrelated authority.
      FOREACH name IN ARRAY names LOOP
        relation := to_regclass(format('public.%I',name));
        IF relation IS NULL OR NOT EXISTS (
          SELECT 1 FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner
          WHERE c.oid=relation AND c.relkind='r' AND r.rolname='aos_app'
            AND c.relrowsecurity AND c.relforcerowsecurity
        ) THEN
          RAISE EXCEPTION 'Skill journal identity mismatch' USING ERRCODE='42501';
        END IF;
        SELECT relowner INTO owner_id FROM pg_class WHERE oid=relation;
        IF EXISTS (
          SELECT 1 FROM pg_class c CROSS JOIN LATERAL
            aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a
          WHERE c.oid=relation AND
            (a.grantee NOT IN (0,owner_id,runtime_id,writer_id)
             OR (a.grantee=writer_id AND
                 (a.privilege_type NOT IN ('SELECT','INSERT') OR a.is_grantable)))
        ) OR EXISTS (
          SELECT 1 FROM pg_attribute at CROSS JOIN LATERAL aclexplode(at.attacl) a
          WHERE at.attrelid=relation AND at.attnum>0 AND NOT at.attisdropped AND
            (a.grantee NOT IN (0,owner_id,runtime_id,writer_id)
             OR (a.grantee=writer_id AND
                 (name<>'aip_skill_eval_intent' OR at.attname<>'version'
                  OR a.privilege_type<>'UPDATE' OR a.is_grantable)))
        ) THEN
          RAISE EXCEPTION 'Skill journal unexpected grant' USING ERRCODE='42501';
        END IF;
      END LOOP;
      FOREACH name IN ARRAY names LOOP
        relation := to_regclass(format('public.%I',name));
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM aos_runtime,PUBLIC',name);
        FOR col IN SELECT attname FROM pg_attribute
          WHERE attrelid=relation AND attnum>0 AND NOT attisdropped LOOP
          EXECUTE format('REVOKE ALL PRIVILEGES (%I) ON TABLE public.%I FROM aos_runtime,PUBLIC',col.attname,name);
        END LOOP;
        EXECUTE format('GRANT SELECT ON TABLE public.%I TO aos_runtime',name);
        -- Effective privilege checks also catch inherited roles/column grants.
        IF NOT has_table_privilege(runtime_id,relation,'SELECT') OR
          has_table_privilege(runtime_id,relation,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') OR EXISTS (
            SELECT 1 FROM pg_attribute at WHERE at.attrelid=relation AND at.attnum>0 AND NOT at.attisdropped
              AND has_column_privilege(runtime_id,relation,at.attnum,'INSERT,UPDATE,REFERENCES')
          ) THEN
          RAISE EXCEPTION 'Skill journal effective privilege drift' USING ERRCODE='42501';
        END IF;
      END LOOP;
    END $acl$""")


def downgrade():
    raise RuntimeError('Historical broad journal grants must not be restored')
