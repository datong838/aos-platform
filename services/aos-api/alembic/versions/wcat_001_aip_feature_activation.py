"""Add tenant-bound AIP feature activation authority. Revision ID: wcat_001."""

from collections.abc import Sequence

from alembic import op


revision: str = "wcat_001"
down_revision: str | Sequence[str] | None = "biw8_001"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE aip_feature_activation(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,feature_id TEXT NOT NULL,
      revision BIGINT NOT NULL,content_hash TEXT NOT NULL,status TEXT NOT NULL,
      activated_at TIMESTAMPTZ NOT NULL,expires_at TIMESTAMPTZ,
      authority_data JSONB NOT NULL,created_by TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,feature_id,revision),
      CHECK(feature_id ~ '^aip[.][a-z0-9]+([.-][a-z0-9]+)*$'),CHECK(revision>=1),
      CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(status IN('active','superseded','revoked')),
      CHECK(expires_at IS NULL OR expires_at>activated_at),
      CHECK(jsonb_typeof(authority_data)='object'))""")
    op.execute("""CREATE UNIQUE INDEX uq_aip_feature_activation_active
      ON aip_feature_activation(org_id,project_id,feature_id) WHERE status='active'""")
    op.execute("ALTER TABLE aip_feature_activation ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_feature_activation FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope_aip_feature_activation_wcat_001
      ON aip_feature_activation TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("GRANT SELECT ON aip_feature_activation TO aos_runtime")
    op.execute("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON aip_feature_activation FROM aos_runtime")
    op.execute("""CREATE TABLE aip_feature_activation_command_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,receipt_id TEXT NOT NULL,
      feature_id TEXT NOT NULL,operation TEXT NOT NULL,idempotency_key TEXT NOT NULL,
      request_hash TEXT NOT NULL,expected_revision BIGINT NOT NULL,result_revision BIGINT NOT NULL,
      result_status TEXT NOT NULL,result_ref JSONB NOT NULL,created_by TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,receipt_id),UNIQUE(org_id,project_id,idempotency_key),
      CHECK(operation IN('activate','revoke')),CHECK(expected_revision>=0),CHECK(result_revision>=1),
      CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(result_status IN('active','revoked')),
      CHECK(jsonb_typeof(result_ref)='object'))""")
    op.execute("ALTER TABLE aip_feature_activation_command_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_feature_activation_command_receipt FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope_aip_feature_activation_receipt_wcat_001
      ON aip_feature_activation_command_receipt TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("GRANT SELECT ON aip_feature_activation_command_receipt TO aos_runtime")
    op.execute("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON aip_feature_activation_command_receipt FROM aos_runtime")
    op.execute("""CREATE FUNCTION ecommerce_workshop_feature_activation_command_wcat_001(
      p_feature_id text,p_operation text,p_expected_revision bigint,p_content_hash text,
      p_expires_at timestamptz,p_idempotency_key text,p_request_hash text,p_actor text)
      RETURNS TABLE(receipt_data jsonb,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_existing record;v_active record;v_revision bigint;v_receipt_id text;
        v_now timestamptz:=statement_timestamp();v_result jsonb;
      BEGIN
        IF v_org IS NULL OR v_project IS NULL OR p_feature_id !~ '^aip[.][a-z0-9]+([.-][a-z0-9]+)*$'
          OR p_operation NOT IN('activate','revoke') OR p_expected_revision<0
          OR p_idempotency_key IS NULL OR btrim(p_idempotency_key)='' OR length(p_idempotency_key)>200
          OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR p_actor IS NULL OR btrim(p_actor)=''
        THEN RAISE EXCEPTION USING ERRCODE='WC001',MESSAGE='invalid feature activation command';END IF;
        IF p_operation='activate' AND (p_content_hash !~ '^sha256:[0-9a-f]{64}$' OR p_expires_at IS NULL OR p_expires_at<=v_now)
          THEN RAISE EXCEPTION USING ERRCODE='WC001',MESSAGE='activation requires exact hash and future expiry';END IF;
        IF p_operation='revoke' AND (p_content_hash IS NOT NULL OR p_expires_at IS NOT NULL)
          THEN RAISE EXCEPTION USING ERRCODE='WC001',MESSAGE='revoke does not accept activation content';END IF;
        PERFORM pg_advisory_xact_lock(hashtextextended(v_org||':'||v_project||':'||p_feature_id,0));
        SELECT request_hash,result_ref INTO v_existing FROM aip_feature_activation_command_receipt
          WHERE org_id=v_org AND project_id=v_project AND idempotency_key=p_idempotency_key;
        IF FOUND THEN
          IF v_existing.request_hash<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='WC002',MESSAGE='feature activation idempotency conflict';END IF;
          RETURN QUERY SELECT v_existing.result_ref,true;RETURN;
        END IF;
        SELECT revision,content_hash,status INTO v_active FROM aip_feature_activation
          WHERE org_id=v_org AND project_id=v_project AND feature_id=p_feature_id AND status='active' FOR UPDATE;
        IF p_operation='activate' THEN
          IF (v_active IS NULL AND p_expected_revision<>0) OR (v_active IS NOT NULL AND v_active.revision<>p_expected_revision)
            THEN RAISE EXCEPTION USING ERRCODE='WC002',MESSAGE='feature activation expected revision conflict';END IF;
          v_revision:=p_expected_revision+1;
          IF v_active IS NOT NULL THEN UPDATE aip_feature_activation SET status='superseded'
            WHERE org_id=v_org AND project_id=v_project AND feature_id=p_feature_id AND revision=v_active.revision;END IF;
          INSERT INTO aip_feature_activation(org_id,project_id,feature_id,revision,content_hash,status,
            activated_at,expires_at,authority_data,created_by,created_at)
          VALUES(v_org,v_project,p_feature_id,v_revision,p_content_hash,'active',v_now,p_expires_at,
            jsonb_build_object('schemaVersion','aos.aip-feature-activation/v1','featureId',p_feature_id,
              'revision',v_revision,'contentHash',p_content_hash,'activatedAt',v_now,'expiresAt',p_expires_at),p_actor,v_now);
        ELSE
          IF v_active IS NULL OR p_expected_revision=0 OR v_active.revision<>p_expected_revision
            THEN RAISE EXCEPTION USING ERRCODE='WC002',MESSAGE='feature activation expected revision conflict';END IF;
          v_revision:=v_active.revision;
          UPDATE aip_feature_activation SET status='revoked' WHERE org_id=v_org AND project_id=v_project
            AND feature_id=p_feature_id AND revision=v_revision;
        END IF;
        v_receipt_id:='wcat-'||substr(md5(v_org||':'||v_project||':'||p_idempotency_key),1,24);
        v_result:=jsonb_build_object('schemaVersion','aos.ecommerce-workshop.feature-activation-command-receipt/v1',
          'receiptId',v_receipt_id,'featureId',p_feature_id,'operation',p_operation,'revision',v_revision,
          'status',CASE WHEN p_operation='activate' THEN 'active' ELSE 'revoked' END,
          'contentHash',CASE WHEN p_operation='activate' THEN p_content_hash ELSE v_active.content_hash END,
          'createdAt',v_now);
        INSERT INTO aip_feature_activation_command_receipt(org_id,project_id,receipt_id,feature_id,operation,
          idempotency_key,request_hash,expected_revision,result_revision,result_status,result_ref,created_by,created_at)
        VALUES(v_org,v_project,v_receipt_id,p_feature_id,p_operation,p_idempotency_key,p_request_hash,
          p_expected_revision,v_revision,CASE WHEN p_operation='activate' THEN 'active' ELSE 'revoked' END,v_result,p_actor,v_now);
        RETURN QUERY SELECT v_result,false;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION ecommerce_workshop_feature_activation_command_wcat_001(text,text,bigint,text,timestamptz,text,text,text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION ecommerce_workshop_feature_activation_command_wcat_001(text,text,bigint,text,timestamptz,text,text,text) TO aos_runtime")


def downgrade() -> None:
    op.execute("DROP FUNCTION ecommerce_workshop_feature_activation_command_wcat_001(text,text,bigint,text,timestamptz,text,text,text)")
    op.execute("DROP TABLE aip_feature_activation_command_receipt")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM aip_feature_activation LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade wcat_001 with AIP feature authority'
      USING ERRCODE='55000';END IF;END $$""")
    op.execute("DROP TABLE aip_feature_activation")
