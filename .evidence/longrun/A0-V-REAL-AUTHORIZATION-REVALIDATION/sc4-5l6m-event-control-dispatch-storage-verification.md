# SC4-5l6m EventControl 分派存储层验证

日期：2026-09-16  
方案：`sc4-5l6m-event-control-dispatch-lifecycle-plan.md`  
基线：`52a6e3ab`

新增 `a0v_054_event_control_dispatch_lifecycle.py`，只提供固定 event-control 的 expand/fence/shrink CAS 和不可变 Receipt。隔离 PostgreSQL 实测 `3 passed`：九项扩为十项且组版本 11→12；相同请求回放同一 Receipt；控制行 fence 后 revision 1→2、组版本 12→13；shrink 后恢复九项、组版本 13→14。

提前 shrink、同 key 不同请求、负租户、runtime 角色直接调用全部拒绝；负租户 Receipt 数为 0；Receipt UPDATE 触发不可变拒绝。函数要求 serializable、精确租户 session、非超级用户 maintainer 成员、当前租户控制成员、ready/enabled/unfenced runtime、统一 extension 安装/代次/epoch 和完整九/十项组。

本提交只完成数据库最小写原语及其隔离测试。它故意不作为产品调用入口：签名 release 的 event-control 声明/合同复验与 exact ActionApprovalEvent 仍由下一提交的 Python Service 在同事务完成；Service 完成前不应用主库迁移、不执行 E 的真实扩展。
