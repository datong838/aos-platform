# W5CB4 E17-aa3b1｜预算批准消费前核验验证

## Rules 与边界

按 AOS engineering delivery、231-3/5、栖月汇与 E17 上位方案先方案后代码；m1 单写、精确提交、不 push。当前真实库只读，`dev-org` 仅负向 canary；无外部费用来源、第二位正式 checker 和 active 消费写入权威时，Host/worker/Provider、手工 Run、旧 Run、商城源均禁入。

## RED、修复、GREEN

- 新增内部 `precheck_consumption` 前，4 项隔离 PG 测试因入口缺失失败。首版在不可变 Decision/Preview 上使用 `FOR SHARE`，运行账号仅有 SELECT/INSERT，4 项均因 `permission denied for table aip_budget_activation_decision` 失败；先改方案，再改为与撤销共享决策级 advisory lock 及普通只读 SELECT，不放宽 ACL。
- `AOS_DOTENV_DISABLED=1 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/aip/test_aip_budget_activation_consumption_precheck_pg.py` → exit 0，4 passed；覆盖 approved 仍缺外部证明且无 active/Receipt 副作用、撤销、Head 漂移、非正式身份/跨租户/成员撤销。
- 同命令加 `test_aip_budget_activation_store_pg.py test_aip_budget_store.py` → exit 0，10 passed；`python -m compileall -q` 与 `git diff --check` → exit 0。

## 当前实例只读回查

- 通过 `scripts/a0v_current_preview_bootstrap.py::_connection_parameters` 定位当前运行容器连接，`BEGIN READ ONLY`：`aos_current_preview_20260927@a0v_111`；`org-org/dev-project` 的 Budget Head 0、activation Decision/Revocation/Receipt 各 0、SkillBinding 0、HostAssignment 0。未读商城源或写当前库。
- `curl`：`8080/v1/health=200`、`8080/v1/ready=200`、`8434/aip/skill-publish=200`；页面 200 不作业务首链证明。

## 复审结论与余险

实现只增加内部调用入口；本实现总是以明确异常失败，不注册 HTTP、不写预算或 Receipt、不开放 active。`external_usage_proven` 的数据库 CHECK(false) 仍阻断外部证明正向。决策级锁与撤销同键；未来如开发可成功的原子消费者，必须重新审查事务快照时序、外部账单证据、单次消费唯一性与跨系统效果，不能直接把此预检当授权。正式第二人、价格 Head/费用来源及首链仍缺。

下一波 E17-aa3b2：正式外部价格与费用证明来源/上界合同，仅做独立方案与可测试的失败封闭边界；之后才设计原子 active 写入与 Receipt，并按独立备份克隆迁移门推进。
