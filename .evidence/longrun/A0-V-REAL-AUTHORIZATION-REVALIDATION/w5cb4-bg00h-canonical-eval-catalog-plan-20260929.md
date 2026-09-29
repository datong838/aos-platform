# W5CB4 BG-00h 正式 Eval 元数据目录文件级方案

## 上位约束与现场

- 231 总控与 231-1/5/9：栖月汇首链须有真实来源、精确评审和批准；本波不读取商城源、不派发业务任务。
- AIP-4 `05-228` E1A/B/E2：Dataset manifest 只存来源、字段白名单与脱敏 Receipt 元数据；Suite 锁定 target/dataset/judge/cases exact refs；旧 Logic Eval 不等于正式 Skill 发布证据。
- BG-00e 与 2026-09-29 当前库只读对账：D01 evaluated，canonical Dataset/Suite/Run/Report/Gate/Event 为零。已有 `get_dataset_revision` 与 `list_suite_revisions`，缺按租户发现 Dataset/Suite 的 API。

## 最小改动

1. `services/aos-api/aos_api/aip_eval_authority_store.py`：新增 scoped Dataset 元数据列表；只 SELECT ref 列，不返回 manifest 或业务行。
2. `services/aos-api/aos_api/routers/aip_eval_authority.py`：新增只读 Dataset/Suite 列表路由，沿用认证 Principal→TenantScope 与现有异常映射；Suite 仅输出 exact refs/case artifact refs，不运行。
3. `services/aos-api/tests/aip/test_aip_eval_authority_api.py` 与 `test_aip_eval_pack_registry.py`：先写 RED，再验证认证租户、跨租户不泄漏、空目录与存储失败关闭。

## 边界与验收

- 当前真实库只读，不注册假 Dataset，不触发 Runner/ReleaseGate/Publication；无 Host/worker/Provider。
- 新列表只证明权威目录是否有可审查候选，不能证明来源合法、评测通过或发布可行。D01 仍因正式来源缺失禁入。
- 专项与相邻回归、编译、diff check、实际 API 只读空目录对账；写 verification 后精确 m1 提交、D-waves/01/06 登记并进入下一波来源接线。
