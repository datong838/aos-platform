# 原完整计划与共享父风险语义对账

基线 AOS-001668 / a5d14431e。原 Task 同 owner ACTIVE，Task/Lease 精确相等、无 Delivery、无重叠，租约至 2026-10-09T21:37:31.958805+00:00。

本波候选：完整计划风险→实际占用（已有1608登记）；Target真实结果→晚Judge输入（依赖可信提交/结果）。先调查第一项，不修改产品或既有原生结果。

精确新增文件均位于本 Task 的 `.evidence/gt-atomic-model-admission-20261008/`：本计划、`shared-parent-manifest-audit-1668.py`、其独占新结果 `shared-parent-manifest-result-1668.json`、复审记录。读取产品 `aip_model_eval_execution_contracts.py`、`aip_model_eval_execution_owner.py` 与 `aip_physical_capacity_occupation_authority.py`，不修改。

方法：只读连接保留的 v2 Target 实验库 aos_test_ff40de426907_ti4_test，核数据库/cluster/read_only。读取已有完整 manifest，保留原件不改数据库；内存中分别将两个 case 每个 purpose 的描述分配调整为1/1、5/5、1/9、6/6、0/0。调用现有纯契约验证，输出是否接纳与总上界，不把接纳当预算授权或执行证明。原文件哈希前后一致，Provider、DDL、DML、原生新事务提交均零。

退出条件：证明契约能/不能区分描述性每腿分配与数据库批准父风险；明确现有 Owner 是否从原来源推导每腿分配，prepared_plan_risk 是否仍共享父风险语义。若描述接纳不同分配，只登记实际缺口及完整适配方案，不补猜测价格、不废旧v1、不据此授 transport。

风险：保留库可能不可用、无manifest或资料改变则失败并诊断，不能创建新库或重放native；只读材料来自测试签名，不支持正式可信root/Provider首链结论。现有父预算10、三价未知仍完整保留。
