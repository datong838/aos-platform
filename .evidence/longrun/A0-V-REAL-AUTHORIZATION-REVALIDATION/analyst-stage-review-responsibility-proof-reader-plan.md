# 阶段评审 responsibility proof reader 方案

日期：2026-09-12

基线：`08bf0558`

## 目标与 Rules

把现有当前人工职责核验扩展为只读 `read_stage_review_responsibility_authority`。同一事务先完成 ResponsibilityPlan raw/typed hash、frozen/ready/complete、唯一阶段槽、当前成员、Resolution Receipt 有效期与 body hash、Owner exact resolution 回读，再输出 plan/slot/receipt snapshot 和 `validate_review_slot` exact payload/expected。

现有 `require_stage_review_authority` 保持签名并只返回 reviewer。proof 不代表 Eval 或 runtime 权限，不 IPC、不写库、不接受调用方槽或 Receipt 内容。

## 文件与验收

- 修改 authority reader 与真实隔离 PG 测试。
- 新增本 plan/files/verification，更新 closure。
- 合法 proof 全部 canonical JSON；actor/stage/ref/成员/过期/hash 漂移继续拒绝。

下一波实现 Eval/source proof reader，随后组合 runtime、responsibility、command、Eval、structure 五门。
