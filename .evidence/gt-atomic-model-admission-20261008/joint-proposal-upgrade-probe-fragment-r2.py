    # Native original composition probe, all outcomes rolled back.
    from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore
    composition_results=[];composition_second={};composition_started=threading.Event()
    def composition_waiter():
        try:
            with connect_serializable(scope) as second:
                composition_second.update(second.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone())
                composition_started.set()
                judge_owner._prepare_dual_purpose_bucket_fences(second,scope,budget_pending['request_id'],be['approval_event_id'],release_policy=policy,artifact_bytes=files)
                second.rollback()
            composition_results.append({'caller':'second','outcome':'rolled-back'})
        except BaseException as exc:
            root=exc
            while root.__cause__ is not None:root=root.__cause__
            composition_results.append({'caller':'second','outcome':type(root).__name__,'sqlstate':getattr(root,'sqlstate',None),'detail':str(root)})
    composition_thread=threading.Thread(target=composition_waiter)
    composition_first={};composition_observed=None
    try:
        with connect_serializable(scope) as first:
            composition_first.update(first.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone())
            judge_owner._prepare_dual_purpose_bucket_fences(first,scope,budget_pending['request_id'],be['approval_event_id'],release_policy=policy,artifact_bytes=files)
            composition_thread.start();assert composition_started.wait(5)
            with psycopg.connect(get_dsn(),row_factory=__import__('psycopg.rows',fromlist=['dict_row']).dict_row) as observer:
                observer.execute('SET TRANSACTION READ ONLY')
                for _ in range(150):
                    observer.execute('SELECT pg_stat_clear_snapshot()')
                    composition_observed=observer.execute("SELECT pid,wait_event_type,wait_event,query,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE pid=%s AND wait_event_type='Lock'",(composition_second['pid'],)).fetchone()
                    if composition_observed:break
                    time.sleep(.02)
            (base/'joint-proposal-upgrade-observation-r2.json').write_text(json.dumps({'observed':composition_observed,'results':composition_results,'first':composition_first,'second':composition_second},default=str,indent=2)+'\n')
            assert composition_observed,composition_results
            try:
                AipModelEvalBudgetReservationStore().hold(first,scope,target['request_id'],ids[0])
                composition_results.append({'caller':'first','outcome':'rolled-back'})
            except BaseException as exc:
                root=exc
                while root.__cause__ is not None:root=root.__cause__
                composition_results.append({'caller':'first','outcome':type(root).__name__,'sqlstate':getattr(root,'sqlstate',None),'detail':str(root)})
            finally:first.rollback()
    finally:
        if composition_thread.ident is not None:composition_thread.join(15)
    assert not composition_thread.is_alive(),composition_results
    with connect(scope) as no_effect:
        composition_target_count=no_effect.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=%s',(target['request_id'],)).fetchone()['n']
        composition_judge_count=no_effect.execute('SELECT count(*) AS n FROM aip_model_judge_budget_reservation WHERE request_id=%s',(budget_pending['request_id'],)).fetchone()['n']
    composition_proof={'first':composition_first,'second':composition_second,'observed':dict(composition_observed),'outcomes':composition_results,'threads_terminal':True,'new_target_holds':composition_target_count,'original_judge_holds':composition_judge_count,'execution_allowed':False,'scope':'actual original budget prefix followed by Target hold; no physical Source joint claim'}
    (base/'joint-proposal-upgrade-native-red-r2-proof.json').write_text(json.dumps(composition_proof,default=str,indent=2)+'\n')
    assert composition_target_count==0 and composition_judge_count==1
    assert all(x['outcome']=='rolled-back' for x in composition_results),composition_results
