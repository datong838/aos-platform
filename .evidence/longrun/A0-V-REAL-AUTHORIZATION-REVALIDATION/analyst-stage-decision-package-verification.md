# 经营参谋阶段决定合同包化验证

日期：2026-09-12

基线：`c37d5acc`

结论：exact 人工阶段决定 DTO 与纯适用性比较已进入 growth 作者包；当前决定和人工评审权威未迁移。

## 实现核对

- AnalystStageDecisionRevision、EvalStageAttemptRef、AssigneeRef 的 JSON Schema 与宿主完全一致。
- portrait、diagnosis、solution-design 三阶段对象的序列化与宿主一致。
- subject、plan、Artifact、EvalReport、ResponsibilityPlan 和 StepRunAttempt 绑定均为 exact。
- accept 只在 createdAt 到不超过七天的 expiresAt 半开区间内适用；到期即拒绝。
- 跨租户上下文、内容 hash 变化、subject 替换、非 accept 与布尔版本全部拒绝。
- TenantContext 不授予权限；包不读取当前决定、Principal、角色或任何数据库 Owner。

## 验证结果

- 本波规则、前三波包迁移与全部对应宿主合同联合测试：`97 passed`。
- 独立进程阻断 `aos_api` 后可导入并生成 schema；Python 编译通过。
- `verify_closure.py --phase ar2-7`：扫描 1768，分类 131，迁移 89；所有错误数组为空。
- `git diff --check`：提交前执行并要求通过。

## 方案一致性与风险

实现符合“exact 方案评审后才进入内部 Handoff”的产品边界，也没有把评审决定误作外部动作
批准。主要剩余风险是宿主 StageDecision Store、评审 authority/runtime 和安装包运行身份尚未
接入该合同；1.4.0 不含它。下一波审计 stage decision Store 的读写职责并拆出最窄宿主端口。
