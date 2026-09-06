# AR1-c 正式预算引用适配检查点

2026-09-06；基线0c0fc6a7/AOS-000532；AR1-C-CONFIGURATION-BUDGET-ADAPTER子Lease，主生命周期Lease保持有效。

AIP侧新增只读适配器，复用原BudgetRevision、materialize_revision和canonical_hash合同；运行内核不反向依赖AIP。显式事务与aos_runtime角色、双租户GUC必须一致；锁定原budget head并核对当前revision，原结构列、规范payload、原摘要与精确引用一致；DB当前时间核对有效窗口，要求active/development/CNY/hard-stop与未知即拒绝。返回预算原记录，不授予执行、hold、扣费或发布权限。

隔离18432的临时schema应用原aip10_001迁移，未运行共享BudgetStore写测试。缺模块Red14后通过；补充原合同生成的撤销、暂停、过期、未来版本，以及head锁并发测试。专项适配16项，加原预算合同/静态迁移10项，共26passed/7.61s；最终累计621passed/6既有warnings/95.82s/exit0。退出时既有JDBC清理日志写关闭流警告不改变exit0。独立Prime只读代码复审未发现新增实质问题，没有代替实际测试。

无页面改动、在线重载、共享迁移、真实数据写、Provider或费用；因此不新增浏览器业务验收或真实业务场景完成结论。AR1-c仍IN_PROGRESS，新增业务场景0。下一施工项为剩余配置引用与生效链，实际执行仍需权限、策略和费用控制。
