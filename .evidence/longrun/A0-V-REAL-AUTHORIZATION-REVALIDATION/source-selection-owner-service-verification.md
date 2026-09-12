# 来源选择当前审批服务验证

2026-09-12；基线 ee6ac032；m1 单写者；未 push。

新增 pipeline_source_selection_owner.py：固定 PostgreSQL 安装仓库、当前发布资产读取器、ReleasePolicy 依赖，内部构造当前配置四源权限。调用者事务内先校验 aos_runtime 与双租户身份、锁安装，再检查安装锁/代际/epoch/绑定/config、当前角色数据预算策略、源配置、图修订与摘要、三份导出资产及发布签名证据。资产读取后重查当前配置和时窗。固定快照图逐项匹配表/主键/范围/字段映射/目标，不接受额外节点或自定义表达式。

同事务追加不可变 SourceSelectionRevision。首请求不把随机 identity 混入请求 hash；同键同请求回读，仍经过当前检查；同键异请求、陈旧 previousRef 拒绝；外层 rollback 不留追加。无源连接、ScheduleRun、启用、业务写入行为。

## 验证

- RED：缺少 Owner 模块，两个测试文件收集失败。
- 初次实现后 17 通过/3 失败：测试草稿沿用 test-org 与 ledger 的 org-org 不一致，随后临时父表缺少行锁权限。修正测试租户，且仅临时 schema 的 fixture 父表授予测试所需 SELECT/UPDATE；未修改生产身份或权限。
- 新 Owner 图/组合检查及独立 PostgreSQL 持久检查 29 项；关联合同/资产/codec/当前四源权限/绑定锁/发布资产回归合计 **175 passed**，7 个既有警告，11.98 秒。
- PG 持久测试的 named_fake_current_check 只证明数据库事务/CAS，不是实际权限证明；Owner 组合测试也明确标记为控制流替身。真实当前四源和绑定锁的原有 PG 测试另行通过，但尚未完成真实租户全组合审批验收。
- AR2 ar2-7：1794 scanned / 158 classified / 93 migrated，五类错误数组均空；git diff --check 通过。

## 当前边界与下一波

新服务尚未接生产工厂/HTTP，未迁移真实 a0v_021 库，未批准/启用 P01，也未执行商城业务读取。注册库读取器的独立连接观察不能冒充跨连接原子权限；真实执行仍须重新校验发布状态。下一波实现有上限、显式选列、版本一致的快照读取与截断拒绝，再接持久控制和实际 Owner 组合验收；不得把样本当完整快照。真实经营首链仍未完成，230 L0 保持挂起。
