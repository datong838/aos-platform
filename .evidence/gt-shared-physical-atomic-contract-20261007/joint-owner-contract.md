# 联合 Owner 接线合同草案：原入口复用、同 caller、未知义务保留

本合同以 m1 56ac78b8、AOS-001475 和本目录原生证据为依据。角色窄桥已在保留隔离库验证，产品 ledger 还未实现；剩余门不因文档存在而通过。完整 231 业务目标不缩减。

## 角色与资料流

专用 occupation SCRAM session 仅 SET 原 aos_runtime，无私有表/Owner membership。原客户端 `_consumption_packet` 完成外部 JWT 验签，packet 是已验证 claims，不是 JWT；原 SQL 检查 native identity、期限、current Owner、精确 Source、原批准/Provider/Evidence/root/registry。不得公开客户端构造 claims 的捷径或把 SQL 称独立 JWT 验签器。

新独立 physical ledger Owner 应 NOLOGIN/NOINHERIT、无 membership/CREATEDB/CREATEROLE/SUPERUSER/BYPASSRLS，仅持新私有 schema。其窄 Source 桥由原 SourceOwner 持有、固定正文、search_path=pg_catalog，只委托未改变的 `read_capacity_source_for_occupation`，桥仅授新 ledger Owner EXECUTE。外层联合入口只授原 runtime。新 ledger Owner 不授原 Source 私有表、原 Source RPC 或 C verifier。所有生产表、函数、ACL、触发器与角色形态必须按 trusted 编译产物审计，不从目标 catalog 反推“期待值”。

原生 prototype 实际证明上述两层 SECURITY DEFINER 能保留 caller xid/pid，原 Source reader/auditor 定义 ACL 不变；错期限/ref/非专用 session 原 SQL 拒绝。prototype 无 production ledger 数据写入，未来生产桥与新 Owner 的正式身份仍需独立安装验收。

## 同 caller 原子协议

1. 从原批准、Source、当前 Model/Route/Price/配置/安装身份发现精确输入，保护完整原权限锁前缀，按最终强度预持费用 fence UPDATE。发现数据不是准入。
2. 取稳定物理账户 guard 并实际更新共同 version；旧 SERIAL 快照在此拒绝。独立 advisory 或不更新 FOR UPDATE 不能当“计数自动刷新”。
3. ordinary 可调用原 `reserve_pool_in_transaction` 保留单池约束；pool/revision 计数永远不能替代 physicalAccount 共同计额。新 ledger 私有 hold 与所有未决旧义务一起核并发/token 上界。
4. 回到同原生 connection 的 runtime caller，复用原普通 `reserve_in_transaction` 或 Eval `hold`。保持原真 Task / 一等 Eval request、原 checker/Price/三桶/current cost risk 语义，禁止伪 Task/AgentRun 或另开连接。
5. 联合 finalize 核全部精确绑定，持久写同一次唯一 Intent。caller 自己执行实际 COMMIT；capacity/budget/Intent 任一失败整体回滚，函数返回不能冒充 COMMIT。
6. 实际 COMMIT 前还须守期限和当前性；需要原生 deferred/等效数据库门和并发撤回证明，不能只检查 Python 返回前时间。发送权限来自独立正式门，Source 的 execution_allowed=false 仍只授非执行资料。

上述序列只定义所需协议，不代表现有独立 Content claim/start/ack 已合并。Intent writer 与预算 finalize 的精确权威校验、一次性身份和 deferred 门尚未实现。private ledger 不能信任 caller 传入的 Source DTO、budget Receipt 或“READY”标签。

## 额度与旧义务

物理主键是 server physical_account_id，跨 Provider、pool、revision、用途共同计数，继续保留租户所有者。仅 Provider id 关联不够，旧行还需 pool 精确 revision/hash 与签名 Source Provider refs、全账户映射及真实执行来源。

inflight_upper_bound 保留所有 held/prepared/submitted/unknown 未决上界；TTL/Source撤回不解除。fixed_window_rate 同时保留并发义务和签名 anchor/seconds 定义的窗口预留/支出，使用 DB clock；submitted/unknown 不因窗口滚动返还。新 Source revision 或窗口定义变更不得清零旧义务。

旧 reserved/consumed/released/expired 不能直接决定余额。仅不可变未提交证明、结算或正式只读 reconcile 可做幂等解除；不明映射或不明结果应保守保留/拒绝该账户新准入，禁止删除记录、清库或重发。当前所有盘点行是隔离 counterexample，没有合法 AgentRun；不可据此声称业务历史切换已验证。

## 全入口切换与剩余开码门

当前 ordinary/Eval 在预算桶后取原费用 fence，联合序列若 fence 前置但旧入口混跑，会有相反顺序。先零执行窗口、全入口共同切换或明确禁入旧 writer；再证明真实 opposite-writer 等待/无死锁。Source 发布/撤回、Model/Price/head、审批与成员 writer 的完整传递锁图仍须逐项核对，不以静态 AST 代替动态 SQL 与原生竞争。

拟议文件为 `aos_api/aip_physical_capacity_occupation.py`、追加迁移、完整 `tests/aip/test_physical_capacity_joint_pg.py`，再接 AgentRun、Eval、Content 原入口；这些产品文件尚未取得本 Task 的代码 Lease，不能偷偷开码。原 Source/profile dirty Scope 亦不纳入本 Task。

下一验收必须同时覆盖：两 token 模式、same caller COMMIT/rollback/replay、不同 Provider/pool/revision/ordinary/Eval 共同上限、真实并发与过时快照、等待后和实际 COMMIT 期限、旧 unknown 导入/零执行切换、合法 Skill/Logic/ModelRoute/Task 创建链、一次 Intent、原功能相邻与租户零副作用。正式数据库迁移、服务重启、自然首链、八工作台、连续观察与发布仍走 231 后续门。

## 原费用撤回隐式 writer 边补证

2026-10-07 原生catalog盘点（完整157 retained库）及cost-revoke-lock r2补证：原BudgetCostIssuer从REVIEWER member SHARE→budget-cost-review advisory→撤回 INSERT→AFTER ROW INSERT的aip_budget_cost_revoke_fence_a0v_126 UPDATE原fence。触发器body独立核对a0v_126 trusted迁移完全相同。实际签名checker/consumer/get原测试后，同批准maker签名revoke对SER/runtimecaller持有的fence真实等待；caller rollback后原Issuer COMMIT，fence1→2/revocation1/receipt1。这里的caller仅持锁，不是联合ledger caller，也没有budgethold/Intent。

原费用Issuer角色不同于SourceOwner：a0v_125要求仅原aos_runtime SET membership（无ADMIN/INHERIT），consumer无membership；不得因新Owner零membership设计而误改旧Issuer原身份。原Source reader清理由fixture完成，catalog无该入口不授重装/重发。此native边证据不能把完整锁图标GREEN；新联合Owner仍须预持并复验review/member/currentness与最终强度fence，核两方原writer对向路径，不凭词法事件猜全序。catalog_lock_inventory明确dynamic EXECUTE/helper call和控制流尚未闭包。

## Source 活跃安装 AST 闭包检查点

完整原Source distinct r2测试1PASS/7warnings48.73s，真实SCRAM/SER/runtime消费后只读采集59函数，嵌入SQL解析失败0、显式未解析调用0、实际动态EXECUTE0。词法扫描三个EXECUTE实为ACL字符串；独立synthetic语法正负例覆盖literal/dynamic/lock/assignment，不能当业务证据。public.digest两个重载保守遍历，三个非SQL密码函数仍opaque。7函数含显式锁子句，仅evidence_epoch_lock出现INSERT（缺失epoch时ON CONFLICT），隐式唯一/FK锁仍独立分析。锁子句别名与关系候选不直接等于全部真实持锁对象，控制流结构不是全writer运行顺序。

独立SER READ ONLY复核：54 helper hash未变，两个legacy profile恢复为可信原编译；两个public occupation入口由内层清理，private installation audit由exact_public_source_caller外层finally精确DROP。活跃audit先匹配occupation可信编译，清理来源经原fixture AST核对，缺失不能作当前准入。原Source签名/hash正确、registry epoch2/origin撤回，occupation角色NOLOGIN零membership，AgentRun/容量/普通预算/Eval预算0/canary0。原verifier误期待audit清理后保留，失败未修改数据库，修正仅生命周期断言；独立复核通过。所有实验库卷备份保留。

r1部分AST43函数/414解析失败归档，不抹除失败；r2严格处理PL parseMode=3固定target赋值，非支持语法仍失败透明。此检查点收窄Source helper资料缺口，不冻结完整joint锁图，不实现physical ledger/budget/Intent，不授正式库迁移或业务启动。下一候选是Source发布/撤回和审批/Provider/Price原writer与锁前缀对照，再核旧unknown零执行切换；父Task和完整Goal保持ACTIVE。
