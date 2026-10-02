# W5CB4 E17-s3a｜原 Skill EvalRun Owner 合同核验

## 原路径结果

- `rg` 全部生产代码：`AipEvalAuthorityStore.create_eval_run` 只有 `AipEvalRunner.run` 调用；`persist_signed_skill_eval_report` 只有测试调用，生产无正式 Target/Judge 签发器或其调用方。原 Runner 的两个 Skill 硬拒均在创建 Run 之前。
- 现有原型测试 `test_formal_skill_contract_rejects_unattested_callbacks_before_run`、`test_direct_skill_run_rejects_unattested_callbacks_before_persistence` 重新执行：2 passed、exit0；未授权 callback 调用数0，Run/Report/Gate 新行0。这是既有失败关闭基线，不谎报新 RED。
- `AipEvalAuthorityStore.create_eval_run` 只验 queued/初始事件/租户与幂等，没有识别 Skill 专属 Owner；直接在 Store 或 Runner 解除硬拒，会允许任意 callback 操作产生看似合法的 Run，且 writer 仍无独立签发者。当前正式身份/角色/Run 均0，不能把 isolated test-only 签发材料注入当前实例。

## 方案复审与决定

- 本波完成文件级 Owner 输入/状态顺序合同及来源缺口审计，**没有实现正式 Owner，也没有改生产门禁**。缺少当前获批安装、执行器与 Judge 签发进程、受限 writer 和合法 Owner 的联结来源；新增空 Owner/helper 只会制造假进展。
- 此缺口仅封 Skill Eval/当前实例；立即转 E17-s3b 原 LogicRevision、ModelRoute/RuntimePolicy 生产者的独立正反联测。之后回 E17-s3a 的 Owner 真接线与签名执行，当前库角色/迁移/凭据另立独立安全波。Goal active，Host/worker/Provider关，真实库只读。
