# 经营参谋阶段评审职责槽纯规则验证

日期：2026-09-12

基线：`61de33c4`

结论：阶段评审职责槽的无权威匹配规则已进入 growth 作者包；宿主计划、成员、Receipt 与
StageDecision Store 权威未迁移。

## 实现核对

- portrait、diagnosis、solution-design 均只接受各自的 `analyst.{stage}.review` 唯一槽形状。
- responsibilityType 固定为 independent_review，returnStage 必须回到原阶段。
- requiredCapabilityIds 必须是严格空列表；人工独立评审不能借用机器 capability。
- assignee 必须是 actor 本人的 human_principal v1；布尔值不能冒充 version 1。
- assigneeResolutionReceiptId 必须规范非空且不超过 240 字符。
- 输入仅来自宿主已验证计划的值投影；包内没有 TenantScope、事务、数据库或平台 import。

## 验证结果

- 本波规则、相邻四个包迁移和对应宿主合同联合测试：`110 passed`。
- 宿主 ResponsibilitySlot 合法结构保持兼容；机器职责缺少 capability 的既有拒绝规则通过。
- 独立进程阻断 `aos_api` 后可导入纯规则；Python 编译通过。
- `verify_closure.py --phase ar2-7`：扫描 1769，分类 132，迁移 90；所有错误数组为空。
- `git diff --check`：提交前执行并要求通过。

## 方案一致性与风险

实现符合 exact 人工评审必须来自当前职责计划的产品边界，同时没有把一个字段匹配函数扩大成
授权来源。剩余风险是宿主 StageDecision Store、评审 command/runtime 和安装包运行身份仍未
接入包内规则；1.4.0 不含该实现。下一波审计 stage review command，优先拆出不持有数据库、
Principal、TenantScope 或 Provider 的命令构造与领域比较。
