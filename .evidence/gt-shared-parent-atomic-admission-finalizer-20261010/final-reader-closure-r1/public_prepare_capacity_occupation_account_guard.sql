CREATE FUNCTION public.prepare_capacity_occupation_account_guard(p_raw bytea,p_source jsonb) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $guard$
          DECLARE document jsonb; guard_version bigint; now_at timestamptz;
          BEGIN
            document:=public.capacity_occupation_source_fact(p_raw,p_source);
            INSERT INTO aos_physical_capacity_occupation_private.account_guard AS g
              (physical_account_id,org_id,project_id,supplier_id,supplier_account_fingerprint,version)
              VALUES((document->>'physicalAccountId')::uuid,'org-org','dev-project',
                     document->>'supplierId',document->>'supplierAccountFingerprint',1)
              ON CONFLICT(physical_account_id) DO UPDATE SET version=g.version+1
                WHERE g.org_id='org-org' AND g.project_id='dev-project'
                  AND g.supplier_id=EXCLUDED.supplier_id
                  AND g.supplier_account_fingerprint=EXCLUDED.supplier_account_fingerprint
              RETURNING version INTO guard_version;
            IF NOT FOUND THEN RAISE EXCEPTION 'PHYSICAL_ACCOUNT_MAPPING_REQUIRED' USING ERRCODE='23514'; END IF;
            now_at:=clock_timestamp();
            IF (document->>'validUntil')::timestamptz<=now_at THEN
              RAISE EXCEPTION 'PHYSICAL_ACCOUNT_CURRENT_SOURCE_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('sourceRef',p_source,'physicalAccountId',document->>'physicalAccountId',
              'version',guard_version,'xid',pg_current_xact_id()::text,'pid',pg_backend_pid(),
              'checkedAt',now_at,'executionAllowed',false);
          END $guard$;
