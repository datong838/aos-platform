# W5ca5｜Fresh Owner 同事务关闭门的已具备与不可补造边界

方案 `m1@c815b702`。只读静态检查 `a0v_091` SQL、Python 服务、W3/W4 调用脚本及隔离 PG 测试；没有执行 SQL 关闭函数、任何 `apply`、真实迁移或测试 DB。原组仍 W5ca4 十二 Run running、`ELIGIBLE_NO_AUTHORITY`。

| 范围 | 已有合同/证据 | 仍缺的真实权威 |
| --- | --- | --- |
| DB actor/事务 | `StalledSnapshotGroupClosureService` 使用 SERIALIZABLE 连接；SQL 要求 maintainer 角色、非 super/bypassRLS、tenant；`meta_membership ... FOR SHARE` 后同事务校验 actor 为 admin/owner；claim/head/member/Run 上锁，Receipt 插入和十二 Run 终结同事务。W5c4x/y 隔离 PG 有角色/时间/缺 claim 拒绝与完整 fixture 成功回放。 | `p_actor` 来自调用者，当前 DB membership 锁只证明该 subject 在此库的角色，不包含独立控制面授权原组关闭、全机 Host 身份/epoch、旧入口撤权的证据。不能把“完全没有 Owner 事务”作为结论，也不能把 membership 校验扩大成全机授权。 |
| 效果/回放 | SQL 读取原组 effect counts 写入 Receipt，`businessAccepted=false`；服务验证 Receipt hash/readback。W5c4z、W5c6i 覆盖非零效果回滚与 Store/closure 分事务界限。 | effect 计数的读取并不等于全机消费者已排空；Store 单独事务不能被 closure Receipt 授权。幂等同 key 回放在 SQL 锁定当前 claim/Run 之前返回既有 Receipt，必须保持只作原提交对账，不能用它开启新动作。 |
| Fleet/Host 与历史语义 | W5c7c/e/f/h 是结构/签名/拒绝的隔离合同；W5c9h 已证原保存链内部 hash 自洽。 | `a0v_091` 请求/SQL/服务没有可验证的 FleetUniverseRevision、完整启动面/旧节点禁启、Host lease fence 与同事务 Owner 绑定；真实库仍旧迁移基线（此前 `a0v_092`），`a0v_093/094` 未正式部署。原十二 Run 无同源事务独立 raw-row 证明，且用户禁止重读商城源，不能从保存 `outputRows` 推造。 |

最小工程判断：现有 DB 原子性与角色锁不应重复实现；直接写一个默认拒绝或自签 Fleet token 只会生成代码绿色而不缩小真实权威缺口。下一步必须取得可信部署/资产控制面的完整 Fleet 来源与旧入口撤权/逐节点 ACK，以及历史原始行独立证明的合法来源（若不存在，明确采用不接受业务结果的正式退休合同），再单独设计 Host-fenced 同事务真实关闭与唯一 key。未满足前，`a0v_091` 对原组绝不可调用。可做的本地测试不替代这两项外部事实。18181 本地服务与租约不改变结论。
