# 阶段评审 responsibility proof reader 验证

日期：2026-09-12

基线：`08bf0558`

结论：当前 ResponsibilityPlan、唯一人工阶段槽、租户成员及 AssigneeResolution Receipt 已由同一真实只读路径生成可封印 snapshot 和 `validate_review_slot` exact 消息；单独 proof 不构成完整发布授权。

## 验证

- 隔离 PostgreSQL 真实创建 membership、Resolution Receipt、ResponsibilityPlan draft/freeze，proof reviewer/payload/expected 与 Owner 读回一致。
- snapshot 固定 Plan exact ref/version、slot canonical hash、member subject、Receipt id/snapshotHash/contentHash/有效期。
- snapshot、payload、expected 均通过项目 canonical JSON。
- 旧 wrapper 返回 reviewer 不变；actor/stage/plan ref/跨租户、成员删除、Receipt 过期和 raw/typed/hash 漂移继续拒绝。
- responsibility + package slot/operation 定向 `34 passed`；compileall、diff check 通过。既有 7 warning 与退出 logging 提示未由本切片引入。
- AR2-7 closure 扫描 1777、分类 140、迁移 93；所有错误数组为空。

## SHA256

- reader：`08a88647c32b92e9e967aded1492fcfc7c67b833c0de970af2e4c028ba519ee5`
- tests：`18d574c313f52640e3f3dfa8b0567bcb0946e0b7585434713f4c008c18b3839f`
- plan：`b48702083a838ed4d4bb0c3a7bb193e73b576763f552316fa8c13f22c4be1c20`

## 下一门

实现生成来源与 Eval contract/report/gate proof reader，输出 `validate_eval_proof` 和 `validate_structure_case` 两条消息；随后组合 command、responsibility、runtime、Eval、structure 五门并接 Owner 双事务。
