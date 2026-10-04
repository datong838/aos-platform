# E17-s3o-w-ao-b43｜Capability operation 来源缺口审计

## 范围、复审与新结论

- 方案 `m1@cad23635`。复习 b25–b32 验证：b26 已拒 version-only evaluate；b27 拒双 Receipt；b28–b32 固定非法列、CREATE 初态、published Catalog/source revision。当前无需重复改这些已在 disposable 库证明的守卫。
- 原 `AipCapabilityBindingService.evaluate` 在 issuer 写事务**之前**调用 `readiness_service.evaluate_capability` 得到依赖快照；进入写事务后持久化结果字段、版本并插 `capability_binding.evaluate` Receipt。现有 test-only issuer 可绕过服务，直接以任意 `dependency_snapshot_hash='b'*64`、`last_evaluated_at=now()`、`readiness_expires_at` 更新行并附同事务 Receipt（`test_e17_s3owaob22_capability_receipt_identity_pg.py` 正向段）。它满足 test-only 行形状和双向 Receipt 守卫，却没有可信当前依赖计算；因此账号独立/私有也不能单独证明评估来源。
- 此审计没有新增生产代码/迁移/当前库写；检出的缺口是**有效形状但无可信 operation 来源**，不同于 b26 已修的空版本伪 evaluate。下一门不能靠单纯新增 `a0v_136` 或 b41 行锁函数完成。

## 可复核命令

| 命令 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py -k 'not downgrade'`，工作目录 `services/aos-api` | 退出0，1 passed、1 xfailed、7 warnings；passed 的 test-only issuer 正向段含任意 hash 的 evaluate 行+Receipt，并在结尾核 Receipt7/Binding1；xfail 是现有生产共享 Receipt 缺配对门 |
| `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py tests/aip/test_e17_s3owaob12_tool_receipt_identity_pg.py tests/aip/test_aip6_003_exact_instance.py tests/aip/test_aip6_capability_run_handoff.py tests/aip/test_aip_binding_readiness_service.py -k 'not downgrade'` | 退出0，34 passed、1 deselected、3 xfailed、7 warnings；deselected 为135禁降级旧测试，xfail 仍是未闭合合同 |
| `git diff -- services/aos-api/aos_api/aip_capability_binding_service.py services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` | 无生产/测试改动，本波只读复核 |

## 下一步和风险

- 下一波先在隔离库给“评估来源与最终事务同一事实”写 RED：如果可调用 issuer 的账号提交形状合法但并无当前依赖计算，必须失败；确定是否由数据库受限命令重算、独立可信签发且数据库核验，或收紧 issuer 对表的直接 DML 为只执行受控函数。这个公共协议需要与 231/BIND-1 和实际服务接口复审，不能给私有凭据无限表写权后仅依赖行形状。
- 正式 issuer/Reader/OIDC/Owner、当前 active 安装、八配置/六 Binding/Host/自然首链仍未齐；当前 `a0v_135` 真实库只读，Host/worker/Provider关，b34/b37 与共享 Receipt strict xfail 保留。Goal active、不 push。
