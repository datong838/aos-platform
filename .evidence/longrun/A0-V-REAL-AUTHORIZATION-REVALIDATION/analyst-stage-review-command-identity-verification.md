# 经营参谋阶段评审命令身份纯规则验证

日期：2026-09-12

基线：`25127063`

结论：阶段评审命令的稳定目标 ID 与无权威身份校验已进入 growth 作者包；来源、Eval、权限、
事务、Receipt 和发布仍由宿主独占。

## 实现核对

- portrait、diagnosis、solution-design 的 decisionId 与现行宿主算法逐字节一致。
- ID 绑定 tenant 和七个稳定目标字段；ResponsibilityPlan 保留在 exact 正文与 contentHash 中，
  按现行宿主合同允许职责计划迭代继续归于同一评审目标链。
- tenant、createdBy/actor、幂等 key、expectedVersion、decisionId 和 contentHash 任一漂移均拒绝。
- 布尔值不能冒充 expectedVersion；key 必须规范非空且不超过 200 字符。
- 函数返回重新解析的值对象，不读取数据库，也不声称 actor、current、Eval 或 Receipt 已授权。

## 验证结果

- 本波规则、阶段决定/职责槽相邻包和对应宿主命令合同联合测试：`115 passed`。
- 首轮测试发现包 ID 多纳入 ResponsibilityPlan，三项 parity 失败；对照宿主哈希正文后按冻结的
  “保持现行算法”约束修正，第二轮全部通过，没有修改宿主合同。
- 独立进程阻断 `aos_api` 后可导入；Python 编译和平台 import 扫描通过。
- `verify_closure.py --phase ar2-7`：扫描 1770，分类 133，迁移 91；所有错误数组为空。
- `git diff --check`：提交前执行并要求通过。

## 方案一致性与风险

实现没有把数字同事的分析结果升级为人工评审，也没有增加外部副作用入口。主要剩余风险是
宿主 command 还未调用包内纯规则，stage review runtime 的 exact 当前链尚待拆分，1.4.0 安装
也不含该实现。下一波审计 `ecommerce_analyst_stage_review_runtime.py`，只迁移可证明无权威的
exact 比较部分。
