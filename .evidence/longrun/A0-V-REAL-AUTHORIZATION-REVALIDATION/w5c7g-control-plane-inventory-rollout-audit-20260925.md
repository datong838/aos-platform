# W5c7g 控制面清单与安全 rollout 缺口审计（只读，非部署）

## 当前来源与覆盖性

| 来源/启动面 | 已证明 | 未证明及正式 rollout 所需读回 |
| --- | --- | --- |
| `deploy/dev/com.aos.a0v-w5c3-runtime-host.plist` | 本机一个 launchd 定义，`RunAtLoad=true`、`KeepAlive=false`，启动 `scripts/a0v_ecommerce_runtime_host.py` | 不列跨机器/CI/容器/手工入口；即便本机 stop，也没有控制面禁止旧服务重启与逐节点 ACK。当前参数未带 `--host-lease-opt-in`。 |
| `scripts/a0v_ecommerce_runtime_host.py` | 本机文件锁阻止相同锁路径的并发 Host；可选 DB lease 参数默认 off | 文件锁非跨机；默认 off 的 lease 不约束未受管/旧二进制；worker 全路径 fence 与旧登录角色撤销未齐。 |
| `deploy/dev/docker-compose.yml` | 开发依赖服务定义；没有 A0-V Runtime Host 服务 | 不能据此声称无容器/CI/手工 Host；需要正式部署控制面清单与实际运行资产比对。 |
| `deploy/spoke-full/chart` | Spoke Helm 模板和可变 replica | 非 A0-V Runtime Host 清单；Helm 模板不是当前机器实例，也不能禁止未列入口。 |
| Apollo `/v1/apollo/fleet` | Hub/Spoke 产品目录，`fullSpokeRuntimeDeferred=true` | 不是 A0-V Host 部署控制面或签名资产全集。 |
| `ar1_003` directory / `a0v_093/094` | 受管 assignment 与隔离 PG lease/fence 合同 | 真实 DB 仍 `a0v_092`，目录不覆盖未受管/离线/旧身份；真实迁移和全部 worker opt-in 均缺。 |
| W5c7c/e/f | 隔离结构、签名和注入根生命周期验证，三授权标志恒 false | 没有正式 signer、根签发/分发/撤销持久锚点、资产/部署 revision 交叉证明、逐节点启动禁令。 |
| 本机进程/DB session | 局部实时诊断 | 无法排除尚未连接或别处可重启 Host；物理第二 Host=0 必须独立全机读回。 |

搜索范围为当前仓库 `deploy/`、`scripts/`、`services/` 的受管启动定义与已知来源；仓库外机器/编排、云控制面和人工部署入口不可由此排除。此审计既不修改 launcher，也不发现一个可直接信任的完整 fleet authority。

## 串行 rollout 前置（未来独立波次，不在本波执行）

1. 指定唯一控制面所有者与正式 Fleet signer/根生命周期；取得从资产清单到部署清单的同一 revision 可核验覆盖关系，枚举所有机器、cluster/namespace、launch surface、角色/OID 和离线节点。未受管入口先纳管或撤销，不以零连接替代。
2. 真实 DB `a0v_093/094` 迁移须独立方案、备份/回滚/权限核验；默认 off 的 Host lease 和所有可能写受管元数据的 worker/Owner 在隔离环境先证明同事务 fencing。Store 外部效果及未知提交边界另行防重/冻结。
3. 逐节点 stop/drain、旧部署/登录资格撤销与“不能重启”ACK；以控制面和节点双向读回进程/容器/会话/租约/worker=0，再独立证明物理第二 Host=0。离线节点也须在旧凭据/网络层失效。
4. 最后才建立独立真实 stalled closure plan/key，Fresh Owner 同事务重验 rev4 disabled、12 原 Run 状态、严格 24h、零增量与零 Receipt。时间条件满足不替代前 3 项，也不自动运行。

当前无第 1 项可信控制面来源，故不能推进真实迁移或 closure。下一波只能继续 no-effect 的隔离 rollout 决策/拒绝合同，或等待仓库外正式控制面证据进入范围。旧 attempt 不重发、不手工 `run_definition`；商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。
