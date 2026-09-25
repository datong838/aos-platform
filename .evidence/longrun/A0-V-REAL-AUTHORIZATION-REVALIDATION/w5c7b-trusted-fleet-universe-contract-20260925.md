# W5c7b 可信 Fleet Universe 与旧 Host 排他合同（设计，未部署）

## 1. 现场与判定目标

截至本波，真实 `aos_meta_head` 为 `a0v_092`；`a0v_093/094` 仅代码/隔离 PG，Host `--host-lease-opt-in` 默认 off，worker 全路径 fencing 未证明。W5c7a 本机 launcher 0、已知登录会话 0，只是局部观测。正式旧代 stalled closure 的目标不是“当前没看到进程”，而是：在完整 Runtime Host 启动范围内，旧代无法再受理该租户工作，并在同一数据库事务里重新证明原定义/12 Run/零副作用/严格时间资格。

## 2. Fleet Universe 权威输入（尚不存在）

需要一个受管部署控制平面作为**唯一可授权启动**的来源，输出不可变、签名、限时的 `FleetUniverseRevision`。最低字段：控制平面身份与签名 key revision、租户/环境、fleet revision 和生效/到期 DB 时间、全部 machine/cluster/namespace/launch-surface/Host identity、对应部署 revision 与可启动状态、允许使用的数据库登录角色与角色 OID、覆盖性声明及其可核验的上游资产/部署清单 revision。必须能核实所有启动入口（launchd、容器编排、手工/CI 服务、灾备）；不能只列当前在线实例。

拒绝条件：签名/信任根未知，清单过期或 revision 倒退，资产清单与部署清单不一致，存在未登记启动入口或离线节点可凭旧凭据重启，机器/角色重复或不可追溯，控制平面无法证明“禁止旧进程再次启动”。这些情况不得降格为“当前零进程”。单机 `flock`、DB lease、`ps`、`pg_stat_activity`、受管目录 assignment 分别只能证明其局部性质，不能代替 universe。

## 3. 旧 Host 排他与 cutover 顺序

1. 先在隔离环境完成 `a0v_093/094`、所有会写受管元数据的 Owner/worker 同事务 fence 与外部 Store 幂等/未知冻结覆盖；真实数据库迁移须独立审批和备份/回滚验证。迁移只增结构，不激活权威。
2. 完整 universe 的每个启动面切到受管 Host lease/worker fence，且旧未受管启动入口禁止新增。对旧 Host 执行受控 stop/drain；每节点给出精确 deployment revision、停止 ACK 与控制平面禁止重启的读回。离线节点须先撤销可用登录/部署资格或隔离其网络路径，不能等它上线后补查。
3. 在完整清单逐节点读回进程/容器 0、旧角色连接 0、租户 worker 0，以及控制平面的启动禁令；新入口也须 DB lease/epoch 限制。任何节点无 ACK、读回超时、未知提交边界、连接/lease 漂移，立即冻结，不猜测、不重试旧 attempt。
4. 第二 Runtime Host=0 的用户原始条件要单独读回。即便 DB 无有效租约，也不能把这个物理/全机条件判作已满足。

## 4. 正式 closure 仍是独立门

取得可信 universe 和 Host cutover 证据之后，仍需新鲜单事务 Owner 门：原 definition 精确 rev4 disabled、12 原 Run 精确状态及每个 `started_at` 严格早于数据库时钟减 24 小时、Store Receipt/ecom_link/projection 无增量、stalled Receipt=0、scope/角色/版本/唯一 closure key 精确匹配。计划文件、执行、verification、commit 顺序独立；未知结果先冻结读回，不重发、不手工 `run_definition`。未来 lease/fence 不自动结清历史 Runs，也不取代正式退休/direct successor。

## 5. 已实现与未实现边界

已实现：受管目录、默认 off 的 Host lease 客户端、`a0v_093/094` 迁移代码及多层隔离 PG fence、只读 topology/closure 合成门。未实现/未证明：真实迁移、全 worker/Owner 入口覆盖、唯一受管部署控制平面、签名完整 universe、所有旧入口禁止重启、跨机逐节点读回、Fresh Owner closure 执行计划。此文是下一波验证器/接入设计基线，不是上线或 closure 许可。

不读商城源行；230 L0 挂起；dev-org 仅零 canary；m1 单写不 push。
