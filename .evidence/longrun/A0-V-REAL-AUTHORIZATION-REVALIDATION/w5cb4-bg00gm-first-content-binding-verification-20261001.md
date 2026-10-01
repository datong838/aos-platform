# BG00GM 首生内容 Action 绑定 verification

2026-10-01；基线AOS-001053/m1 dfd6aca7。开工七强一致CURRENT，validate GREEN。遵循231-5及GK/GL。当前真库未连接、无迁移/重启、无Provider/商城源读取/旧Run重放/手工run_definition。

## 实现与复审

- 显式firstContentReviewKey/firstContentSources/budgetUpperBoundMinor合同，仅专用guard可提案/决定；服务端R2 floor，普通草稿/RETURN保持原门。
- 外部OIDC配置与每次JWT复验；同事务唯一成员、checker沿业务ACTION_APPROVAL_ROLES、持久internal及metadata/field marking bearer，不借安装/预算管理权限。无新身份表/审批表。
- 原_prepare_sources结果供source envelope使用：Review、Task/Plan真实hash/Run、AgentRun/request/Skill、installation代次/dispatch/runtime、模型/Provider/价格/预算/Quota/Capacity及期限；不包含每次变化的观察时间。maker、checker与新预算消费均重验当前来源和不可变Draft canonical。
- 预算共享_approval_authority新增首生门，包含exact预算/价格和自然invocation key，防绕开Owner改扣或换key；已有reservation幂等回读行为不改。自然intent缺失即拒，不凭有binding冒当前来源。
- 通用Action执行器拒绝首生费用批准，留原自然Content Owner消费。没有新增HTTP/UI路由，没有启用正式实例。
- 专用服务不能通过不带marker的请求或非首生Proposal落入通用路径。preview只有SELECT/锁并rollback，不调用费用fence；proposal/checker写事务才调用原费用门。

## RED/验证

1. /tmp/aos-gm-red.log：5 failed/1 passed，退出1；缺服务端R2/通用producer/checker不拒绝。
2. 初19 passed/4.37s（Owner相邻）；首次PG夹具8 errors/9 passed，原因是临时库缺meta_workspace外键来源，补齐仅测试租户目录后17 passed/5.52s。未放宽生产schema/门。
3. 七组相邻61 passed/18.62s，退出0。
4. 累计（services/aos-api cwd）：

```sh
.venv/bin/python -m pytest -q tests/aip/test_content_first_action_binding.py tests/aip/test_content_first_action_binding_pg.py tests/extension_runtime/test_ecommerce_content_budget_command_owner.py tests/extension_runtime/test_ecommerce_content_repair_action_binding.py tests/aip/test_content_budget_risk_bound_pg.py tests/aip/test_content_first_action_budget_pg.py tests/aip/test_budget_configuration_runtime_pg.py tests/aip/test_aip3_action_control.py tests/aip/test_aip3b_action_execution.py tests/aip/test_aip_network_policy_action_producer.py --tb=short --show-capture=no
```

/tmp/aos-gm-final-regression.log：93 passed/91.28s，退出0。之后专用入口防通用落入与Plan hash补强，末次两个新文件专项/tmp/aos-gm-final-focused.log：24 passed/6.76s，退出0；未将不同时间结果相加为总数。8个Python文件compileall及精确diff check退出0。7条已有Pydantic/Starlette warnings。无UI改动，browser不适用。

## 证据强度与剩余缺口

新PG测试真实验证ActionStore SQL、不可变Draft、checker、幂等、当前成员/markings/metadata及失败零Approval。TLS测试实际验签/JWKS并拒跨scope/错签名，身份均为隔离测试身份。

_source preparation和envelope在PG组合正向中明确替换；source_envelope单测也有模型与查询替身。因此不是正式原始Review/安装/模型来源→held证明。实际共享预算authority对没有自然intent的这份批准拒绝，说明绑定不是凭空执行权。预算/价格/key对比正向仅替换source admission以测比较，不创建held。无直接INSERT审批、无测试手填binding hash。

同波追加Budget与EXEC两个互不重叠Task；尝试扩原ACTIVE Lease被API以自身scope冲突拒绝，未手改Receipt，改登记各独立文件的补充Lease。当前正向租户固定org-org/dev-project，其他既有dirty未纳入。

## BG00GN 下一必做

构建合法Review/TaskRun/AgentRun/ModelRoute/Quota/Capacity的隔离来源生产链，撤掉_prepare_sources/envelope替身，使本次实际producer/checker→GE风险预算held联合证明通过；若来源producer仍缺，直接施工该依赖。确认60秒容量租约与人工审批时序是否需要按上位方案调整生产时序，不能自动续旧claim或延长过期授权。然后正式HTTP/现有Action详情预览接线与browser验收，受控元数据/真实身份、当前实例恢复仍独立安全门。自然首链/八场景/观察发布未完成，Goal保持active。Watchdog未部署，不push。

## 文件 SHA256

- services/aos-api/aos_api/ecommerce_content_first_action_binding.py: `9757f10d1b813f07e70c07c7acdd1e4cf34c119363e632722f15da035659dce9`
- services/aos-api/aos_api/ecommerce_content_budget_command_owner.py: `1fb4925bafc8ace0559bc36ecba322d41c90f9587a0c19fe4d89a8c5c81c17a5`
- services/aos-api/aos_api/aip_action_store.py: `93fdd486dc134b00963f0b78758bb7d4bb9919aa96e353bbcb25338078bba8eb`
- services/aos-api/aos_api/aip_action_policy.py: `3271f221cd97e1a8557a1dfbf1dee9ea4e36020708bb014b0fe3283199efaad4`
- services/aos-api/aos_api/aip_budget_reservation_store.py: `711e51dd11b6638a22845de9ca82e095f11f666dcdee8aa2179f43bfa4a22e0c`
- services/aos-api/aos_api/aip_action_execution.py: `1c1a33ed1d24b673aacdd3161cee6fc972485127cddc4670a6ca4ffdfa434275`
- services/aos-api/tests/aip/test_content_first_action_binding.py: `70c4c235512bad1c6d9b5b597107ac8f9a4b307e0a94aadd58aa4786db5f5f45`
- services/aos-api/tests/aip/test_content_first_action_binding_pg.py: `8a8c083ab78cf20236c81955334287e0657b93256d3620fcf3cc9f7fe0b2ab9c`
