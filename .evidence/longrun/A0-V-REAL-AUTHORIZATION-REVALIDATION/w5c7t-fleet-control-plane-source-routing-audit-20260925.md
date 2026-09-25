# W5c7t Fleet 控制面来源与接入路由审计（只读）

## 结论

当前仓库和真实 A0-V 现场均没有可核验的、覆盖所有可启动 Runtime Host/worker 的控制面权威来源。W5c7b 要求的签名 FleetUniverseRevision 不只是成员列表：必须与资产/部署 revision 交叉证明所有机器、cluster/namespace、launch surface、角色/OID、离线节点及旧入口不可重启。缺一项即 `NO_AUTHORITY`。本波没有从本机状态或自报字段推断全机覆盖，也没有新增真实授权 adapter。

## 文件级来源与信任边界

| 文件/来源 | 实际职责 | 不能证明的事实 / 后续接入条件 |
| --- | --- | --- |
| `deploy/dev/com.aos.a0v-w5c3-runtime-host.plist` | 一个本机 launchd 入口；未带 lease opt-in | 跨机、容器、CI、手工、灾备入口及离线节点；需要控制面资产清单、部署 revision、stop/drain ACK 与禁止重启读回。 |
| `scripts/a0v_ecommerce_runtime_host.py` | 本机 Host，`--host-lease-opt-in` 默认为 false；可选 acquire/renew | 本机文件锁/可选 lease 不排除旧二进制和别处启动；不能自行启用真实 lease。 |
| `services/aos-api/aos_api/extension_runtime/host_lease.py` | opt-in 事务 fence 客户端 | 真实库仍 `a0v_092`；`a0v_093/094`、角色部署、所有写路径覆盖和旧资格撤销均未正式验证。 |
| `scripts/a0v_w5c7c_fleet_universe_structure.py` | 纯清单形状检查 | 返回 `STRUCTURE_ONLY_UNTRUSTED` 且三授权标志 false；成员自报不是资产/部署全集。 |
| `scripts/a0v_w5c7e_fleet_signature_envelope.py` / `scripts/a0v_w5c7f_fleet_trust_root_lifecycle.py` | 注入密钥的隔离签名/根生命周期合同 | 无正式 signer、信任根分发/撤销锚点及同 revision 覆盖证据；签名有效也不等于全机完整。 |
| `scripts/a0v_w5c7h_rollout_rejection_contract.py` | 纯拒绝分类；全自报 true 仍三授权标志 false | 不是上线门或可调用真实 closure 的 adapter。 |
| `scripts/a0v_w5c5g_real_closure_gate_composition.py` | 当前只读真实 closure 组合门 | 仍缺独立全机控制面、Fresh Owner 同事务 closure 方案/key；不能用该读数发起动作。 |
| `services/aos-api/aos_api/pipeline_snapshot_schedule_worker.py` 及 `pipeline_snapshot_*`/`extension_runtime/*consumer*` | 调度与各写路径/可选 fence | 需要逐入口证明 lease 对象传递、同事务 fence、失租后拒绝和未知外部结果冻结；现有片段不构成全覆盖证明。 |

`deploy/dev/docker-compose.yml` 无 A0-V Host 服务；`deploy/spoke-full/chart` 是 Spoke 模板；Apollo fleet 产品接口不是 Host 部署全集。这些负面观察只限仓库，不能排除仓外启动面。数据库会话、本机 `ps`/launchd 或物理第二 Host 的局部读数均只能是诊断，不替代全机控制面。

## 未来正式接入的文件/证据顺序

1. 先由独立受管部署控制面给出可核验的身份、根 revision、资产/部署同版覆盖、完整启动面、旧凭据/入口失效及逐节点 ACK；没有该外部来源，不实现生产 authority adapter。
2. 以 `w5c7c/e/f/h` 纯合同为输入边界设计隔离 adapter；新增测试必须证明伪签名、过期/倒退、漏机器/离线节点、漏启动面、角色复用、未知提交边界全部拒绝。测试 GREEN 仍非真实授权。
3. 独立方案处理真实 `a0v_093/094` 迁移、备份/回滚、Host 与全部 worker/Owner 的 opt-in/fence；旧入口停机、撤权和跨机读回先于 closure。
4. 最后另起 Fresh Owner 同事务、唯一 key 的 stalled closure 方案；严格 24h、原 rev4/12 Run/零增量/零 Receipt 重验；只读门不自动动作。

下一波 W5c7u 可在不触碰真实运行态的条件下，对上表最后一行做静态+隔离测试的**写路径覆盖矩阵**。真实控制面来源仍为外部事实缺口，不能用一轮本地编码消除。230 L0 挂起、dev-org 零 canary、m1 不 push、商城源行不读。
