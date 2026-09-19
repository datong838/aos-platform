# AO 三 attempt 失败后的正式暂停与退休方案

## 当前权威

AO installation `d4186607-c93f-4fd0-8daa-46e349184ab9` / generation `00bb99df-d436-483d-86df-496718c6f129` 的 recoverable Store 链已固定为三笔：

1. ordinal-1 `67c2331d-…` abandoned revision255 / `ATTEMPT_LEASE_EXPIRED`；
2. ordinal-2 `dbcde37a-…` failed revision11 / `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`；
3. ordinal-3 `70241ae9-…` abandoned revision2 / `ATTEMPT_LEASE_EXPIRED`，无 heartbeat。

qcursor 已 bootout，running attempt=0。definition 仍 rev59 enabled，recovery rev19，十二 Run/Receipt/关系/链接命令冻结，Store Receipt、links 和本组 Outbox 均为零。先正式暂停 definition，随后才允许 retirement；禁止重新启动 qcursor。

## 文件级清单

1. `scripts/a0v_ao_saved_snapshot_recovery.py`
   - 增加 `pause-failed`；固定三笔 attempt 的 ID、revision、state、reason、同 request hash 与 ordinal key；
   - 要求 running=0、无第四笔、definition rev59 enabled、recovery rev19、十二 controls 仍属于 AO 且未漂移、Store 零提交、三资源 live、九路由 current、canary=0；
   - 唯一写动作调用正式 schedule definition transition，以新幂等 key推进 rev60 disabled；不调用 `run_definition`。
2. `scripts/a0v_ao_attempt_guard.py`、`scripts/a0v_ao_continuation_router.py`
   - 将上述 exact 三段终态分类为 `FAILED_CHAIN_PAUSE_REQUIRED`，其他第三/第四 attempt 继续 fail closed。
3. `services/aos-api/tests/extension_runtime/test_a0v_ao_*.py`
   - 覆盖 exact 三段链、原因/ordinal/request 漂移、pause 门禁、纯 SELECT guard 与只读路由。
4. `scripts/a0v_ao_failed_retirement.py` 与测试
   - pause 成功后按正式 Runtime disable Owner 执行 `preflight → request-disable → process-disable → audit`；固定 binding、resource、九路由、definition 与三 attempt 边界。
5. AP direct successor 文件
   - 只在 AO detach Receipt 固定后，以既有 replacement/successor/cutover/saved-recovery模板生成 AP；所有身份和 revision 从现场重读后固化，禁止预猜。

## 顺序、停止规则与完成条件

先实现并测试 pause，再执行一次 transition 并只读验证 rev60 disabled、无第四 attempt。之后实现退休并完成 detach，最后才创建 AP。任何 Store Receipt/links/outbox 新增、attempt 数变化、request hash 漂移、canary 非零或 Receipt unknown 均停止写动作，只读对账。测试、服务恢复或 pause 成功均不代表首链完成。
