# 经营计划审批纯规则包化验证

日期：2026-09-12

基线：`8801589a`

结论：GrowthPlan 审批的领域状态转换已进入 growth 作者包；审批权威、Receipt 和发布事务仍在宿主。

## 实现核对

- 只允许 exact、当前、版本匹配的 DRAFT 产生相邻 APPROVED revision。
- priorRef、approvedAt、createdAt、createdBy 和规范 contentHash 均由确定性输入生成。
- 伪造 contentHash、path 漂移、陈旧 If-Match、非当前、非 DRAFT、非规范 actor、无时区时间均拒绝。
- `is_current` 要求严格 bool，不能以整数或调用方自由文本绕过。
- 函数不访问数据库、Receipt、身份、Provider、预算或外部系统。

## 验证结果

- 包内规则、上一波 DTO parity、宿主既有审批与宿主合同联合测试：`37 passed`。
- 首轮测试为 36 通过、1 失败；失败原因是测试夹具创建 approved 对象时漏填 required
  `approvedAt`，对象在被测规则前已被 DTO 拒绝。仅修正夹具后全绿，生产逻辑和断言未放宽。
- 合法 successor 与宿主现有 Service 生成对象逐字段一致。
- 独立进程阻断 `aos_api` 后可导入包规则；Python 编译通过。
- `verify_closure.py --phase ar2-7`：扫描 1766，分类 129，迁移 87；所有错误数组为空。
- `git diff --check`：提交前执行并要求通过。

## 方案一致性与风险

实现遵守“经营参谋形成计划、人工 exact 评审、外部动作另行授权”的产品边界。主要剩余风险是
宿主混合 Service 尚未通过可安装包的窄端口调用该规则，当前 1.4.0 安装也不含它。因此这只是
作者包迁移证据，不是生产审批切换证明。下一波审计 receipt-first 宿主写端口所需的最小合同。
