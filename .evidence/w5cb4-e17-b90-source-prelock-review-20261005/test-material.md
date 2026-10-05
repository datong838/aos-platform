def assert_formal_signed_source_consumer(request, loader, release_policy):
    """Original signed Source/Proposal/OIDC approval/issuer, actual evaluator SCRAM."""
    from uuid import uuid4
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    from psycopg.types.json import Jsonb
    from aos_api.aip_license_source_authority import read_formal_license_source_facts, LicenseSourceUnavailable
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from tests.aip.test_aip_license_source_authority_pg import raw_revoke, wait_blocked
    source_ref = FormalExactRef(assetType='EvidenceBundleRevision', assetId=request.source.resource_id,
        revision=request.source.revision, contentHash=request.source.content_hash)
    with isolated_owner() as owner:
        def scope():
            owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        def counts():
            return tuple(owner.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']
                for table in ('aip_license_source_issuance','aip_agent_registry_receipt','aip_binding_evaluation_proof'))
        before = counts()
        owner.commit()
        with _temporary_fixed_evaluator_login(owner) as factory:
            args = dict(scope=SCOPE, source_refs=[source_ref], installation_id=request.installation_id,
                installation_revision=request.installation_revision, installation_etag=request.installation_etag,
                loader=loader, release_policy=release_policy)
            with factory(SCOPE) as conn:
                from aos_api.aip_license_source_authority import _prepare_formal_source_approvals
                discovered, approvals = _prepare_formal_source_approvals(conn, SCOPE, args['source_refs'])
                assert len(discovered) == 1 and len(approvals) == 1
                assert all('actor_id' in event for _, event in approvals.values())
                facts = read_formal_license_source_facts(conn=conn, **args)
                assert {owner['subject'] for owner in facts[0].owners} == {
                    subject for _, _, approved, maker in discovered
                    for subject in (maker, approvals[approved.resource_id][1]['actor_id'])}
                assert len(facts) == 1
                fact = facts[0]
                assert fact.source.source.resource_id == request.source.resource_id
                assert fact.request == request and len(fact.owners) == 2
                assert fact.source.owner_authorization_ref['approvalEventId'] == fact.approval_event_id
                assert fact.valid_until <= fact.source.expires_at
                assert fact.authorization == 'FORMAL_SOURCE_FACT_ONLY_NO_START'
            assert counts() == before
            owner.commit()
            for changes in (
                {'source_refs': [source_ref.model_copy(update={'content_hash':'f'*64})]},
                {'installation_etag':request.installation_etag+1},
                {'installation_revision':request.installation_revision+1},
                {'installation_etag':True}, {'source_refs':[source_ref,source_ref]},
            ):
                with factory(SCOPE) as conn:
                    with pytest.raises(LicenseSourceUnavailable):
                        read_formal_license_source_facts(conn=conn, **{**args, **changes})
            with factory(SCOPE) as conn:
                conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
                with pytest.raises(BindingEvaluatorConnectionBlocked):
                    read_formal_license_source_facts(conn=conn, **args)
            for subject in (entry['subject'] for entry in fact.owners):
                scope()
                owner.execute("UPDATE meta_membership SET role='admin' WHERE org_id=%s AND project_id=%s AND subject=%s",
                              (*SCOPE.key,subject))
                owner.commit()
                try:
                    with factory(SCOPE) as conn:
                        with pytest.raises(LicenseSourceUnavailable, match='BOTH_CURRENT_OWNERS_REQUIRED'):
                            read_formal_license_source_facts(conn=conn, **args)
                finally:
                    scope()
                    owner.execute("UPDATE meta_membership SET role='owner' WHERE org_id=%s AND project_id=%s AND subject=%s",
                                  (*SCOPE.key,subject))
                    owner.commit()
            # Native reader holds the original Owner/install/Source fences.
            pids = Queue()
            def writer(kind):
                with isolated_owner() as other:
                    other.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
                    pids.put(other.info.backend_pid)
                    try:
                        if kind == 'owner':
                            other.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                                (*SCOPE.key,fact.owners[0]['subject']))
                        elif kind == 'installation':
                            other.execute('SELECT installation_id FROM bundle_installation WHERE org_id=%s AND project_id=%s '
                                'AND installation_id=%s FOR UPDATE', (*SCOPE.key,request.installation_id))
                        else:
                            raw_revoke(other, request.source.resource_id, content_hash=request.source.content_hash)
                    finally:
                        other.rollback()
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = []
                try:
                    with factory(SCOPE) as conn:
                        read_formal_license_source_facts(conn=conn, **args)
                        futures = [pool.submit(writer, kind) for kind in ('owner','installation','revoke')]
                        writer_pids = [pids.get(timeout=5) for _ in futures]
                        owner.commit()
                        wait_blocked(owner, writer_pids, conn.info.backend_pid, futures)
                        owner.rollback()
                    for future in futures:
                        future.result(timeout=8)
                finally:
                    for future in futures:
                        future.result(timeout=8)
            assert counts() == before
            owner.commit()
            # Historical maintenance faults are never positive license authority.
            # Immutable injected rows remain only in this disposable database.
            scope()
            original = owner.execute('SELECT * FROM aip_license_source_issuance WHERE issuance_id=%s',
                                     (fact.source.issuance_id,)).fetchone()
            owner.commit()
            for mode in ('legacy_schema', 'wrong_original_receipt'):
                injected = {**original, 'issuance_id':'b90-fault-'+uuid4().hex}
                if mode == 'legacy_schema':
                    injected['owner_authorization_ref'] = {'test':'legacy fixture'}
                scope()
                owner.execute(sql.SQL('INSERT INTO aip_license_source_issuance ({}) VALUES ({})').format(
                    sql.SQL(',').join(map(sql.Identifier, injected)),
                    sql.SQL(',').join(sql.Placeholder() for _ in injected)),
                    [Jsonb(value) if isinstance(value,dict) else value for value in injected.values()])
                owner.execute('UPDATE aip_license_source_head SET issuance_id=%s WHERE org_id=%s AND project_id=%s '
                    'AND bundle_id=%s AND revision=%s',
                    (injected['issuance_id'],*SCOPE.key,request.source.resource_id,request.source.revision))
                owner.commit()
                fault_before = counts()
                owner.commit()
                try:
                    with factory(SCOPE) as conn:
                        expected = 'ORIGINAL_AUTHORIZATION_REQUIRED' if mode == 'legacy_schema' else 'ORIGINAL_RECEIPT_DRIFT'
                        with pytest.raises(LicenseSourceUnavailable, match=expected):
                            read_formal_license_source_facts(conn=conn, **args)
                    assert counts() == fault_before
                    owner.commit()
                finally:
                    scope()
                    owner.execute('UPDATE aip_license_source_head SET issuance_id=%s WHERE org_id=%s AND project_id=%s '
                        'AND bundle_id=%s AND revision=%s',
                        (original['issuance_id'],*SCOPE.key,request.source.resource_id,request.source.revision))
                    owner.commit()
            assert counts() == (before[0]+2,before[1],before[2])
            import json
            from pathlib import Path
            evidence = Path(__file__).resolve().parents[4] / '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob90/implementation/source-consumer-facts.json'
            evidence.write_text(json.dumps({
                'database':owner.info.dbname,'port':owner.info.port,
                'original_source_issuance':fact.source.issuance_id,
                'original_approval_event':fact.approval_event_id,
                'original_receipt':fact.source.receipt_id,
                'owner_count':len(fact.owners),'source_epoch':fact.source.epoch,
                'checked_at':fact.checked_at.isoformat(),'valid_until':fact.valid_until.isoformat(),
                'positive_counts_before':before,'positive_counts_after':before,
                'fault_injected_immutable_rows':2,'final_counts':counts(),
                'real_scram':True,'writer_fences':['owner','installation','source_revoke'],
                'rejected':['wrong_hash','installation_etag','installation_revision','bool_etag',
                            'duplicate_ref','canary_guc','maker_demoted','checker_demoted',
                            'legacy_schema','wrong_original_receipt'],
                'scope':'Isolated original signed Source consumer only; complete evaluator pending',
            },indent=2)+'\n')


