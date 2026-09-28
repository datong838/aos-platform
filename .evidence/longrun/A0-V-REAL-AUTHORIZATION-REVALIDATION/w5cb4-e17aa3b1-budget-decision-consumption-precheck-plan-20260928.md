# W5CB4 E17-aa3b1｜预算批准消费前当前性核验

## 上位与当前事实

复习 231-3/5、E17-x/y/y2/aa1/aa2/aa3a 方案与当前 `a0v_111`。正式审批预览/决定/撤销是不可变同租户记录；`aip_budget_activation_preview.external_usage_proven` 当前有 `CHECK(false)`，真实价格 Head、外部账单、第二位正式 checker 均缺；active INSERT 在 Store 与 DB 层都禁入。不得把一条 approved Decision 直接等同于可消费授权。

## 本子波文件级方案

- `services/aos-api/aos_api/aip_budget_activation_store.py`：只添加内部消费前核验入口，不注册 HTTP，不写 Receipt 或 BudgetRevision。以正式 OIDC Principal 建立 SERIALIZABLE 租户事务，用与撤销相同的决策级 advisory lock 串行化，再只读不可变 Decision/Preview（运行账号只有 SELECT/INSERT，行级 `FOR SHARE` 需要额外 UPDATE 权限，不放宽 ACL）；重算预览与目标哈希，核 maker/checker 当前成员、distinct 身份、approved 且未撤销/过期、Draft Head/version/内部费用账本仍精确；再检查外部使用证明。由于当前 schema 只能 false，固定返回明确的外部证明缺失错误。未知/跨租户/过期/撤销/Head 漂移全部先失败关闭；不依赖请求方可伪造的布尔值或金额。
- `services/aos-api/tests/aip/test_aip_budget_activation_consumption_precheck_pg.py`：先 RED；覆盖正式双人 Decision 后仍拒绝外部证明缺失且零 active/消费 Receipt、撤销、Head 漂移、成员撤销、非正式身份/错租户。仅使用 conftest 可销毁测试库，`dev-org` 如出现只作无写入负向 canary。
- 不做 `a0v_112`、不迁当前库、不开 Host/Provider。后续 E17-aa3b2 才设计正式外部费用来源与最坏费用上界；证据齐备再做安全 DB writer/唯一消费 Receipt，并单独备份克隆迁移。

## 退出门

专项/相邻回归、`compileall`、精确 diff check；核方案/代码一致、当前库仅只读且 active/绑定 0。代码完成只称“消费前核验失败封闭”，不称原子消费或预算激活完成。波尾记录 verification、D-waves/上下文与 m1 精确提交。
