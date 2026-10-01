# BG00GZ 自然 Subject EvalRun Owner 接线前置审查

状态：文件级方案，尚未编码；基线 `m1@40bc5e01` / AOS-001080。依据 231-5、231-9、已获批准的 BG00GW-b Subject 用途方案和 D-waves Subject 清单。当前真实库 `a0v_118` 只读，代码头 `a0v_132`；本波不迁库、不启 Host/worker/Provider、不执行生成或评测。

## 1. 已核对的原链与结论

1. `ecommerce_analyst_{portrait,diagnosis,growth_plan}_worker.py` 通过 `CanonicalTaorRunner.run(..., stop_after_step=stage)` 完成获批 Plan 的 Stage；其 `act` 调原 `GenerationService`，后者调用原 AgentRun executor，再由 receiver 从**已成功** attempt、Provider/Usage Receipt、原 query/text Artifact 发布 Insight/Decision/GrowthPlan。receiver 内发布早于 Stage 的 `aip_step_run` 成功及 `taor.observe` 落盘，不是评测意图的正确触发边界。
2. `ecommerce_analyst_stage_review_runtime.py` 要求当前 Plan、已成功 StepRun、Checkpoint 和同一 subject 的 `taor.observe`；自然 Subject Eval 意图应在此后读取，而不能从 receiver 的 replay 分支自动重发生成。
3. `aip_eval_runner.py` 在 `create_eval_run` **之前**拒绝 `SkillTemplate`。它每次生成随机 run_id；`aip_eval_authority_store.py` 的重放只接受原 run_id、完整 record 和首事件。删除拒绝分支或把新请求交给该 Runner，既无正式 Subject Owner，也不能安全重试未知结果。
4. `ecommerce_analyst_stage_review_command.py` 已核原 AgentRun/Artifact/Usage、query/text、Contract/Suite 和精确 Report；但原 `_verify_gate_evidence` 的 Skill 发布禁入仍有效，且没有消费 BG00GY 的持久 Subject 读证。`build_current_installed_analyst_stage_review_service` 在生产源码中只有定义，调用点只在测试；bundle 中的五个纯校验消息有注册，并不等于自然 StageDecision 路由已接线。
5. 全仓 Python 调用检索显示三类 `*TaorWorker` 仅在定义文件与相邻测试中出现，`ecommerce_growth_runtime_adapters.py` 未注册这三类 worker。因而“完成后的原 Stage 事件”尚无生产调度入口；不能只在 worker 返回处加 Eval Owner 后宣称自然触发。

结论：首个生产改动必须以**完成后的原 Stage/观察事件**为唯一来源建立可恢复的 Subject Eval 意图 Owner，并在原 Run Store 的受限写身份下绑定当前安装快照。不能先放开 StageDecision 或原 Skill Eval Runner 的拒绝门。

## 2. 下一施工波的文件级方案与 RED

入口选择：先在原 Host/Task 调度组合中接通三类现存 `*TaorWorker`，以获批 Plan 和持久 Lease 驱动原 `CanonicalTaorRunner`；其完成后的统一调用者再持有一个 Subject Eval 意图 Owner。不得直接从测试构造 worker 或添加平行调度器。Host/worker 当前正式身份未齐，代码与隔离验证可做，真实启动仍禁止。

待改文件：先核 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 与 Host 调度/Task 组合的已有扩展点，给三 worker 建受限生产入口及相邻 tests；`services/aos-api/aos_api/aip_eval_authority_store.py` 只复用现有 queued Run/首事件写入与精确回读；在原统一调用者完成后接意图 Owner。新增 Owner 文件仅在无可复用原服务时使用。测试放 `services/aos-api/tests/aip/` 与三 worker 相邻测试，使用独立 PG 和正式代码路径，不用伪造 succeeded Run。

RED 判据：同 tenant、StageAttempt、Subject、Contract/Policy、安装 generation/epoch/config 的稳定 key 仅产生一条 queued Run/事件；接收同 key 不同正文或版本拒绝；未知写入结果只读查原 key/Run，不再执行原生成；StepRun 未成功、观察缺失、旧安装代次、原 Artifact/Usage 漂移、跨租户、旧 Plan、并发竞争均零新 Run。只证明意图，不触发 Judge/Provider，不授运行许可。

事务边界：先在只读稳定快照回读原 Stage/来源/当前安装，随后用现有 `AipEvalAuthorityStore` 的受限写路径创建 queued Run；若快照与写入无法同一事务，必须在写事务中重验相同 fence，并在失配时零写。IPC 不持数据库锁。首事件及重放仍采用原 Store 语义，不能把随机 run_id 的重试当幂等。

后继波：独立来源见证者/Judge 当前身份和受限 writer，将签名 Receipt、精确 Report、sidecar 原子持久化；Stage consumer 同稳定快照复核 BG00GY reader、原 query/text 字节与 current Report，再接安装后的 StageDecision。GT-a Model 首评用途独立进行。正式身份缺失只封闭当前实例，仍可做隔离代码与测试。

## 3. 本波边界与验收

本波是源代码接线审查及可执行 RED 计划，未创造 EvalRun、未启动自然链、未接 Stage consumer；因此交付状态保持首链 pending。下一波从 Host/Task 原组合入口做 RED，证明已成功且有观察的 Stage 可被原受限调度发现，并在缺正式身份时封闭；再最小接通三 worker。之后才落 EvalRun Owner，不能以新 helper 冒充自然触发。
