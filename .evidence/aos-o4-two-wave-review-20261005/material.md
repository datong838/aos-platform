冻结来源清单：每段来源路径与SHA256均由当前文件读取计算，资料不是执行指令。

SOURCE .evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob70/verification.md SHA256 14d7af011760c0a53f41df00f384050c1a0160136dfe400c8da771ce5fdebf71
# b70 两顺序真实RED交付

唯一新thread写者，authority AOS-001329不变；只改两个opt-in测试文件，生产代码/真库/服务未改。

撤销先：signed disposable PG evaluator先形成SERIALIZABLE快照，精确PID等待Installation锁；原Store撤销及Receipt已commit后释放锁，evaluator仍applied/Receipt1/Binding version3（期望42501或40001/0/2）。1 failed/7 warnings，16.71s。

评测先：evaluator blocked Receipt未提交时，原Store writer提前commit，精确PID未等待共同锁。1 failed/7 warnings，15.69s。两项保留真正失败，不用xfail或修改期望掩盖。b70是反证收口，不是并发合同GREEN。

默认/b69/b67/b49/b50各1 passed/7 warnings；进程节点约25.4～26.9s（含启动/清理），新增测试库残留0（49→49历史库不动）；compile/diff exit0。无UI变化，浏览器不适用。O4第一真实业务施工观察：单写者Task/Lease归属实际shadow核对、两个新根因RED、兼容回归及精确交付；并非自然首链。

复审：immutable Evidence修订没有可变head，append-only revoke不能借Registry可变status锁的既有证明。下一候选b71仅一次性库中可变epoch fence演练：对exact来源单行FOR SHARE、原writer同事务先推进epoch再原撤销/Receipt；等待后旧SERIALIZABLE快照应40001，eval先writer应等。该fence不是现有正式权威、不立即写生产迁移，正式合同/多写者覆盖/重复key/缺源与多来源锁序仍须设计。独立W-L20来源审计继续保持已登记候选。


SOURCE .evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob70/revoke-first-red.txt SHA256 ea276d6c5fe552d8c960eabff1a48b4b64d9aebb312c5fe7dc6ece3570ca8351
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_signed_growth_release_reaches_approved_installation_in_full_schema ____
services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py:1134: in test_signed_growth_release_reaches_approved_installation_in_full_schema
    verified_generation = asyncio.run(prepare_and_verify())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Users/ddt/.local/share/uv/python/cpython-3.11.15-macos-aarch64-none/lib/python3.11/asyncio/runners.py:190: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
/Users/ddt/.local/share/uv/python/cpython-3.11.15-macos-aarch64-none/lib/python3.11/asyncio/runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Users/ddt/.local/share/uv/python/cpython-3.11.15-macos-aarch64-none/lib/python3.11/asyncio/base_events.py:654: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py:1012: in prepare_and_verify
    assert_restricted_blocked_evaluate_composes_lock(
services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py:347: in assert_restricted_blocked_evaluate_composes_lock
    _assert_license_race(
services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py:847: in _assert_license_race
    assert (outcome, receipts, version) in {('42501', 0, 2), ('40001', 0, 2)}, (
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   AssertionError: ('B70_STALE_SNAPSHOT_AFTER_COMMITTED_LICENSE_REVOKE', 'applied', 1, 3)
=========================== short test summary info ============================
FAILED services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py::test_signed_growth_release_reaches_approved_installation_in_full_schema
1 failed, 7 warnings in 16.71s


SOURCE .evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob70/evaluate-first-red.txt SHA256 f615533d6ab9f980693e5d05bc165c6a179c61de5a0a23aeaf04225f6aef4f8c
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_signed_growth_release_reaches_approved_installation_in_full_schema ____
services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py:1134: in test_signed_growth_release_reaches_approved_installation_in_full_schema
    verified_generation = asyncio.run(prepare_and_verify())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Users/ddt/.local/share/uv/python/cpython-3.11.15-macos-aarch64-none/lib/python3.11/asyncio/runners.py:190: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
/Users/ddt/.local/share/uv/python/cpython-3.11.15-macos-aarch64-none/lib/python3.11/asyncio/runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Users/ddt/.local/share/uv/python/cpython-3.11.15-macos-aarch64-none/lib/python3.11/asyncio/base_events.py:654: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py:1012: in prepare_and_verify
    assert_restricted_blocked_evaluate_composes_lock(
services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py:347: in assert_restricted_blocked_evaluate_composes_lock
    _assert_license_race(
services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py:876: in _assert_license_race
    assert waiting, 'B70_LICENSE_WRITER_COMMITTED_BEFORE_EVALUATOR_WITHOUT_COMMON_LOCK'
           ^^^^^^^
E   AssertionError: B70_LICENSE_WRITER_COMMITTED_BEFORE_EVALUATOR_WITHOUT_COMMON_LOCK
=========================== short test summary info ============================
FAILED services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py::test_signed_growth_release_reaches_approved_installation_in_full_schema
1 failed, 7 warnings in 15.69s


SOURCE .evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob71/verification.md SHA256 519cdf578c436b0ff09ba1c83dd109d7bf3f91babacc7c05676b777260a6632b
# b71隔离epoch候选验证

b70真实两RED保留。候选只改两测试文件，随机epoch表只在disposable库；原生产Store未改。受限命令Installation→Registry→exact epoch FOR SHARE→License→Binding/Receipt；原writer test-only连接包装同事务UPDATE epoch后原撤销/Receipt commit，保持SERIALIZABLE。

最初缺writer租户policy，影响0行，1 failed/7 warnings/16.88s，失败保留；补原aos_runtime仅test-only表SELECT/UPDATE(epoch)及tenant RLS，撤公共/默认宽权。最终撤销先：明确40001、Receipt0/version2；评测先：精确PID确认writer等eval，后续新key42501且Receipt0；各1 passed/7 warnings。b69/默认各1 passed；节点26.09/25.71/26.16/27.89秒包含启动清理；测试内约16秒。随机表/角色finally清理，test数据库49→49新增残留0；历史库不删。编译/diff通过，无UI变化浏览器不适用。

复审和剩余风险：这是test-only concurrency candidate，不是正式可信epoch权威；原writer所有入口/其他七源未强制接同合同。连接包装器在重放key前推进epoch，可能无意义改变epoch；错hash失败的epoch/event/Receipt整体回滚、重复key与并发同key尚待专门验证，不能声称幂等合同完备。正式化须覆盖writer DB强制门、epoch初始化/来源绑定/迁移恢复与多来源锁序后另波批准，不直接写135或上生产迁移。Host/worker/Provider关、不读商城源/旧Run/230L0、不push。

O4第二真实施工观察有方案/Task/两顺序与相邻证据，但独立复核与新thread实际定时到达尚待核验，不将两测试波当全天候效果通过。下一登记b72：epoch候选幂等/回滚RED及正式合同冻结；W-L20实例ToolBinding来源审计独立候选（已有代码仍只核tenant/active instance，无signed exact source/Owner/安装代次合同，不能由定义级Tool ref推导运行可用）。

readiness相邻24 passed/2既有xfail/7 warnings/5.83s；xfail不算正式门GREEN。


SOURCE .evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob71/summary.json SHA256 378377b0927ad7a2a0801ac7168a7c3eb649826fc6c88d38acad939ce2c648ba
{
  "results": [
    {
      "mode": "revoke-first-final",
      "exit_code": 0,
      "seconds": 26.09
    },
    {
      "mode": "evaluate-first",
      "exit_code": 0,
      "seconds": 25.71
    },
    {
      "mode": "b69",
      "exit_code": 0,
      "seconds": 26.16
    },
    {
      "mode": "default",
      "exit_code": 0,
      "seconds": 27.89
    }
  ],
  "before_count": 49,
  "after_count": 49,
  "new_residue": []
}

SOURCE .evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob71/revoke-first-final.txt SHA256 3da35c98b896e3958aca37996f180b9c5a802aa1c42db0c544af2c28e06965b7
.                                                                        [100%]
1 passed, 7 warnings in 16.55s


SOURCE .evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob71/evaluate-first.txt SHA256 96c1e9182539ff298aa25930ecf53e343cce542898c89be80d4be80f41b16ded
.                                                                        [100%]
1 passed, 7 warnings in 16.30s


SOURCE services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py SHA256 f391d0caa33512fd9d91d2828b781cc859edcfdeec81014b57b65cff9d458e06

20: 
21: def assert_restricted_blocked_evaluate_composes_lock(
22:     *, scope, role, restricted_parts, lock_function, installation, etag, growth,
23:     registry=None, concurrent_revoke=False, evaluate_first=False,
24:     forged_available=False, paired_receipt=False, license_authority=False,
25:     license_revoke_first=False, license_evaluate_first=False,
26:     license_epoch_fence=False,
27: ):
28:     suffix = secrets.token_hex(4)
29:     definer = "b47_definer_" + suffix
30:     function = "b47_blocked_evaluate_" + suffix
31:     binding = "b47-binding-" + suffix
32:     key = "b47-first-" + suffix
33:     signature = sql.SQL("public.{}(text,text,uuid,bigint,text,bigint,text)").format(
34:         sql.Identifier(function))
35:     call = sql.SQL("SELECT public.{}(%s,%s,%s,%s,%s,%s,%s) AS revision").format(
36:         sql.Identifier(function))
37:     binding_ref = {"assetType": "CapabilityRevision", "assetId": "b47-test-only",
38:                    "revision": 1, "contentHash": "a" * 64}
39:     scoped_tables = ("bundle_installation", "bundle_installation_revision",
40:                      "bundle_composition_lock", "aip_capability_binding",
41:                      "aip_agent_registry_receipt")
42:     license_id = "b69-license-" + suffix
43:     license_hash = "c" * 64
44:     fence_table = 'b71_license_epoch_' + suffix if license_epoch_fence else None
45:     if license_authority:
46:         scoped_tables += ("aip_evidence_bundle_revision",
47:                           "aip_evidence_bundle_revoke_event")
48:     if fence_table:
49:         scoped_tables += (fence_table,)
50:     license_check = sql.SQL("")
51:     if license_authority:
52:         license_check = sql.SQL("""IF NOT EXISTS (
53:             SELECT 1 FROM public.aip_evidence_bundle_revision e
54:              WHERE e.org_id=p_org AND e.project_id=p_project
55:                AND e.bundle_id={} AND e.revision=1
56:                AND e.content_hash={} AND e.lifecycle='frozen'
57:                AND e.license_summary<>'{{}}'::jsonb
58:                AND NOT EXISTS (
59:                  SELECT 1 FROM public.aip_evidence_bundle_revoke_event r
60:                   WHERE r.org_id=e.org_id AND r.project_id=e.project_id
61:                     AND r.bundle_id=e.bundle_id AND r.revision=e.revision
62:                     AND r.content_hash=e.content_hash))
63:           THEN RAISE EXCEPTION 'license evidence unavailable'
64:                USING ERRCODE='42501';
65:           END IF;""").format(sql.Literal(license_id), sql.Literal(license_hash))
66:         if fence_table:
67:             license_check = sql.SQL("""PERFORM 1 FROM public.{}
68:                 WHERE org_id=p_org AND project_id=p_project AND bundle_id={}
69:                   AND revision=1 AND content_hash={} FOR SHARE;
70:                 IF NOT FOUND THEN RAISE EXCEPTION 'license epoch unavailable'
71:                   USING ERRCODE='42501'; END IF;""").format(
72:                     sql.Identifier(fence_table), sql.Literal(license_id),
73:                     sql.Literal(license_hash)) + license_check
74:     receipt_guards = None
75:     with psycopg.connect(get_dsn(), autocommit=True, row_factory=dict_row) as admin:
76:         if fence_table:
77:             admin.execute(sql.SQL("""CREATE TABLE public.{}(
78:                 org_id text NOT NULL, project_id text NOT NULL, bundle_id text NOT NULL,
79:                 revision bigint NOT NULL, content_hash text NOT NULL, epoch bigint NOT NULL,
80:                 PRIMARY KEY(org_id,project_id,bundle_id,revision,content_hash))""").format(
81:                     sql.Identifier(fence_table)))
82:             admin.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(sql.Identifier(fence_table)))
83:             admin.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(sql.Identifier(fence_table)))
84:             admin.execute(sql.SQL('REVOKE ALL ON {} FROM PUBLIC,aos_runtime').format(sql.Identifier(fence_table)))
85:             admin.execute(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s,1,%s,0)').format(
86:                 sql.Identifier(fence_table)), (*scope.key, license_id, license_hash))
87:             admin.execute(sql.SQL('GRANT SELECT,UPDATE(epoch) ON {} TO aos_runtime').format(
88:                 sql.Identifier(fence_table)))
89:             admin.execute(sql.SQL("CREATE POLICY b71_writer ON {} TO aos_runtime "
90:                 "USING(org_id=current_setting('aos.org_id',true) AND "
91:                 "project_id=current_setting('aos.project_id',true)) "
92:                 "WITH CHECK(org_id=current_setting('aos.org_id',true) AND "
93:                 "project_id=current_setting('aos.project_id',true))").format(sql.Identifier(fence_table)))
94:         admin.execute("""INSERT INTO aip_capability_binding(
95:             org_id,project_id,binding_id,capability_ref,secret_ref,health,
96:             network_policy_revision,quota_policy_revision,timeout_ms,max_concurrency,
97:             status,version)
98:             VALUES('org-org','dev-project',%s,%s::jsonb,'secret://test-only',
99:                    'unknown','test-only','test-only',1000,1,'provisioning',1)""",
100:             (binding, json.dumps(binding_ref)))
101:         if license_authority:
102:             admin.execute("""INSERT INTO aip_evidence_bundle_revision
103:                 (org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,
104:                  item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
105:                  license_summary,content_hash,lifecycle,created_by)
106:                 VALUES(%s,%s,%s,1,'{}'::jsonb,'[]'::jsonb,NOW(),'[]'::jsonb,

809: def _assert_license_race(
810:     *, admin, restricted_parts, call, scope, installation, etag,
811:     binding, key, license_id, license_hash, evaluate_first,
812:     fence_table=None,
813: ):
814:     """Probe the real Evidence writer; no direct revoke INSERT or current DB."""
815:     writer_pids = Queue()
816:     evaluator_pids = Queue()
817:     revoke_key = key + '-b70-revoke'
818:     evaluate_key = key + '-b70-evaluate'
819: 
820:     @contextmanager
821:     def writer_connection(selected_scope):
822:         with connect(selected_scope) as conn:
823:             conn.execute("SET LOCAL statement_timeout='10s'")
824:             conn.execute("SET LOCAL lock_timeout='8s'")
825:             writer_pids.put(conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
826:             if fence_table:
827:                 updated = conn.execute(sql.SQL('UPDATE {} SET epoch=epoch+1 '
828:                     'WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=1 '
829:                     'AND content_hash=%s').format(sql.Identifier(fence_table)),
830:                     (*scope.key, license_id, license_hash))
831:                 assert updated.rowcount == 1, 'exact epoch source missing'
832:             yield conn
833: 
834:     def revoke():
835:         return AipProductionContractStore(connect_factory=writer_connection).revoke_evidence_bundle(
836:             scope, 'b70-test-only-revoker', license_id, revoke_key,
837:             RevokeEvidenceBundleRequest(expected_revision=1,
838:                                         expected_content_hash=license_hash,
839:                                         reason='b70 isolated concurrent revoke'),
840:         )
841: 
842:     def evaluate():
843:         try:
844:             with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
845:                 with limited.transaction():
846:                     limited.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
847:                     limited.execute("SET LOCAL statement_timeout='10s'")
848:                     limited.execute("SELECT set_config('aos.org_id',%s,true),"
849:                                     "set_config('aos.project_id',%s,true)", scope.key)
850:                     evaluator_pids.put(limited.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
851:                     limited.execute(call, (*scope.key, installation, etag,
852:                                           binding, 2, evaluate_key))
853:             return 'applied'
854:         except psycopg.Error as exc:
855:             return exc.sqlstate
856: 
857:     if not evaluate_first:
858:         with psycopg.connect(get_dsn(), autocommit=True) as blocker:
859:             blocker.execute('BEGIN')
860:             try:
861:                 blocker_pid = blocker.execute('SELECT pg_backend_pid()').fetchone()[0]
862:                 blocker.execute('SELECT 1 FROM bundle_installation WHERE org_id=%s '
863:                                 'AND project_id=%s AND installation_id=%s FOR UPDATE',
864:                                 (*scope.key, installation))
865:                 with ThreadPoolExecutor(max_workers=1) as pool:
866:                     evaluated = pool.submit(evaluate)
867:                     pid = evaluator_pids.get(timeout=8)
868:                     try:
869:                         deadline = time.monotonic() + 8
870:                         while time.monotonic() < deadline:
871:                             blocked = admin.execute('SELECT %s=ANY(pg_blocking_pids(%s)) AS waiting',
872:                                                     (blocker_pid, pid)).fetchone()['waiting']
873:                             if blocked:
874:                                 break
875:                             assert not evaluated.done(), 'evaluate did not reach Installation wait'
876:                             time.sleep(0.025)
877:                         else:
878:                             raise AssertionError('exact Installation lock wait not observed')
879:                         assert revoke().revoked is True
880:                         assert admin.execute('SELECT count(*) AS n FROM aip_production_contract_receipt '
881:                             "WHERE operation='evidence_bundle.revoke' AND idempotency_key=%s",
882:                             (revoke_key,)).fetchone()['n'] == 1
883:                     finally:
884:                         blocker.execute('ROLLBACK')
885:                     outcome = evaluated.result(timeout=12)
886:                 receipts = admin.execute('SELECT count(*) AS n FROM aip_agent_registry_receipt '
887:                     'WHERE idempotency_key=%s', (evaluate_key,)).fetchone()['n']
888:                 version = admin.execute('SELECT version FROM aip_capability_binding WHERE binding_id=%s',
889:                                         (binding,)).fetchone()['version']
890:                 assert (outcome, receipts, version) in {('42501', 0, 2), ('40001', 0, 2)}, (
891:                     'B70_STALE_SNAPSHOT_AFTER_COMMITTED_LICENSE_REVOKE', outcome, receipts, version)
892:                 if fence_table:
893:                     assert outcome == '40001', 'epoch fence must reject the stale serializable snapshot'
894:             finally:
895:                 blocker.execute('ROLLBACK')
896:     else:
897:         waiting = False
898:         with ThreadPoolExecutor(max_workers=1) as pool:
899:             with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
900:                 with limited.transaction():
901:                     limited.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
902:                     limited.execute("SET LOCAL statement_timeout='10s'")
903:                     limited.execute("SELECT set_config('aos.org_id',%s,true),"
904:                                     "set_config('aos.project_id',%s,true)", scope.key)
905:                     limited_pid = limited.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
906:                     assert limited.execute(call, (*scope.key, installation, etag,
907:                         binding, 2, evaluate_key)).fetchone()['revision'] == 3
908:                     assert admin.execute('SELECT count(*) AS n FROM aip_agent_registry_receipt '
909:                         'WHERE idempotency_key=%s', (evaluate_key,)).fetchone()['n'] == 0
910:                     revoked = pool.submit(revoke)
911:                     writer_pid = writer_pids.get(timeout=8)
912:                     deadline = time.monotonic() + 8
913:                     while time.monotonic() < deadline:
914:                         waiting = admin.execute('SELECT %s=ANY(pg_blocking_pids(%s)) AS waiting',
915:                                                 (limited_pid, writer_pid)).fetchone()['waiting']
916:                         if waiting or revoked.done():
917:                             break
918:                         time.sleep(0.025)
919:                 result = revoked.result(timeout=12)
920:             assert result.revoked is True
921:         assert waiting, 'B70_LICENSE_WRITER_COMMITTED_BEFORE_EVALUATOR_WITHOUT_COMMON_LOCK'
922:         assert admin.execute('SELECT count(*) AS n FROM aip_agent_registry_receipt '
923:             'WHERE idempotency_key=%s', (evaluate_key,)).fetchone()['n'] == 1
924:         with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
925:             with limited.transaction():
926:                 limited.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
927:                 limited.execute("SELECT set_config('aos.org_id',%s,true),"
928:                                 "set_config('aos.project_id',%s,true)", scope.key)
929:                 with pytest.raises(psycopg.errors.InsufficientPrivilege):
930:                     with limited.transaction():
931:                         limited.execute(call, (*scope.key, installation, etag,
932:                                               binding, 3, evaluate_key + '-after'))
933:         assert admin.execute('SELECT count(*) AS n FROM aip_agent_registry_receipt '
934:             'WHERE idempotency_key=%s', (evaluate_key + '-after',)).fetchone()['n'] == 0
