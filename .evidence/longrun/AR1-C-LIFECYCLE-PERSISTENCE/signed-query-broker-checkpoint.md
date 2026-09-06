# AR1-c 内部签名查询 broker 检查点

2026-09-06；基线 m1@600ab6f0 / AOS-000544。主波继续，本检查点不等于 AR1-c 或业务工作台完成。

新增可信宿主内部 `SignedQueryBroker`，组合原签名查询注册接纳、当前 Installation/CompositionLock、binding generation/epoch/fence、当前策略，以及原低权限 FORCE RLS 查询端口。没有新增 HTTP、IPC、任意 SQL、可复用许可 token 或领域数据库凭证；只在专用 `127.0.0.1:18432` 隔离 PostgreSQL 临时 schema 读写测试数据，不触碰共享库、真实业务数据、Provider、费用或发布。

独立复审首先发现锁外签名接纳存在时序缺口：broker 可能在等待 binding 锁时跨过 evidence 有效期。新增真实双连接反证先稳定复现失败；实现随后把 release、evidence、registry 制品与 operation 的最终接纳移入 `run_guarded` 的安装/binding 共享锁，并在打开查询连接前使用新数据库时间复核。最终测试先从 `pg_stat_activity` 确认连接确实处于 Lock 等待，再跨过短期 evidence 截止时间释放锁；结果明确拒绝且查询连接打开次数为 0。

专项：broker 10 passed；与原签名接纳、查询端口、runtime gate 联合 32 passed。修正后安全累计 806 passed、6 个既有 warning、130.42 秒、exit 0；累计覆盖全部 extension_runtime 与既定 asset_registry 安全集。修正前更宽累计 903 passed 已运行，但不把它冒充修正后结果。已知 JDBC 退出阶段 closed stream 日志错误仍为既有问题，缓存计数 0，不属于本切片逻辑。

Prime 独立复审确认竞态闭合、方案与实现一致，未发现新的阻断级问题；其稳健性建议已落实为数据库锁等待观测。无页面改动，浏览器验收不适用；业务场景仍为 0，历史 Workshop 44/81 不变。

下一段继续 AR1-c：把命名测试策略替换为正式当前 data/policy 引用，并将内部签名 broker 接入受控运行调用路径；随后闭合费用预留、排空以及完整启停卸载重装。未获得正式入口闭环前不对工作台开放。
