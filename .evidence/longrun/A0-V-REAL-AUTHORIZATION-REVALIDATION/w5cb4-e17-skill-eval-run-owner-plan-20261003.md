# W5CB4 E17-s3a｜原 Skill EvalRun Owner 接线文件级方案（待 RED）

## 上位与事实

- 231、228 G2、56/64、BG-00p/ah/aj/ak、553–557 要求原 Skill 的正式 Target/Judge 独立签名、受限 writer 同事务证据与合法 Run Owner；普通 callback/历史 Report 不能成为正式来源。
- `AipEvalRunner.run_by_contract` 和 `run` 对 Skill 在写 Run 前硬拒，这是正确边界。`AipEvalAuthorityStore.create_eval_run` 是通用持久入口，接受 `EvalRunAuthorityRecord` 与首个 queued 事件，但没有证明调用者是 Skill 正式 Owner；直接开放它会变成手工 Run 捷径。`persist_signed_skill_eval_report` 又要求此前已 succeeded 的 exact Run。当前正租户相关六表和 writer role 都为0。

## 最小施工顺序

1. 先在 `services/aos-api/tests/aip/test_aip_eval_runner.py` 增加 RED，证明 callback 即使给出既有 EvalContract 与 test-only 签名声明，也仍不得创建 Skill Run/Report；同时覆盖通用 Store 不能被当作外部正式 Owner 的界限。原 LogicGraph/Model 拒绝路径和普通 Eval 不回归。
2. 在 `services/aos-api/aos_api/aip_eval_authority_store.py` 与 Runner 实际调用处追踪可复用的 Run 创建/状态转换约束；冻结一个独立 Owner 的输入合同：当前获批安装/精确 Skill+Suite+Dataset/独立 Target/Judge executor 身份/签发根/预算与审批/幂等键/受限角色。Owner 必须拥有受控执行路径并产生真实 target/judge signed receipts，才能使 Run `succeeded`；不能先手插 succeeded 再补 proof。
3. 若仓内已存在满足上述输入与执行合同的生产者，只增专用入口并在 test-only PG 实现 queued→running→succeeded 与 writer 原子写入的正反链；若缺任何核心生产者，本波只提交 RED 与精确依赖图，保持 Runner 硬拒，转 E17-s3b Logic/Route/Policy 原生产者独立代码项，不制造空 Owner/helper。

## 边界与完成条件

当前真实库只读，Host/worker/Provider关闭；不读商城源、不回放旧 Run、不手工 run_definition、不写 dev-org、不 push。现阶段未授权用 test-only issuer 或超级用户填正式身份。新入口必须有真实来源、Receipt、租户隔离和撤销/漂移禁入；否则仅能标“合同/RED 完成，正式 Owner pending”，不得将 Goal blocked。
