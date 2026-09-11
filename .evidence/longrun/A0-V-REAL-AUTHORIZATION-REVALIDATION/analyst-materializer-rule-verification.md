# 经营计划任务图纯展开规则验证

日期：2026-09-12

基线：`e7c3f47a`

结论：approved exact GrowthPlan 到 Canonical Task 请求和 TaskGraph 的纯展开规则已进入 growth 作者包；宿主写权威未改变。

## 审批端口审计

- GrowthPlan 批准入口从认证 Principal 派生 scope 与 actor，并执行 review write role 门禁。
- `publish_plan` 在单一数据库事务内先读幂等 Receipt，再锁 head、核验版本、CAS 更新并同时写
  revision 与 Receipt；并发陈旧请求在发布点 fail closed。
- 该人工命令不是 extension operation。未增加 DispatchRef 端口或第二审批状态机。

## 实现与验证

- 包只展开 eligible item，保留顺序和业务字段；不合格 item 不进入 Task 请求。
- plan/planRef、APPROVED 状态、Task 映射键全集及 exact Task 类型均严格核验。
- partial、extra、非 Task、错误 plan hash、DRAFT、空 actor、无时区时间全部拒绝。
- 合法 Task 请求与 TaskGraph 和宿主现行编排逐字段一致。
- 包规则、前两波包合同/审批规则及宿主回归联合测试：`50 passed`。
- 独立进程禁止 `aos_api` import 仍可加载；Python 编译通过。
- `verify_closure.py --phase ar2-7`：扫描 1767，分类 130，迁移 88；全部错误数组为空。
- `git diff --check`：提交前执行并要求通过。

## 方案一致性与风险

本波保持工作台不直接创建平台 Task 或第二审批状态机的产品边界。主要剩余风险是当前宿主
Materializer 尚未经安装包运行身份调用这些纯规则，Task/TaskGraph 写端口也未完成包化接缝；
1.4.0 不含本实现。下一波拆分 stage decision 领域 DTO，继续为一次性 1.5.0 冻结收拢作者树。
