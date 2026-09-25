# W5c7d Fleet 签名与资产来源审计（只读，非授权）

## 候选来源逐项判定

| 候选 | 现有真实作用 | 不能提供的 Fleet Universe 权威 |
| --- | --- | --- |
| `asset_registry/signature.py` + `ReleasePolicy` | 按 publisher/keyId 的 Ed25519 TrustRoot 验证 Bundle/Release，带 validity/revocation/revision | 签名语义是**发布物**而非 Runtime Host 部署控制面；没有 machine/launch surface 覆盖性、禁止旧入口重启或逐节点关闭 ACK。算法可借鉴，不可复用包信任根作为 fleet authority。 |
| `AOS_BUNDLE_TRUST_ROOTS_FILE` | Host 为 Registry 包提供 trust root 文件 | 当前文件不是 fleet 专用 trust root；读取它也不能证明被签清单覆盖所有机器。不得把现有 key 重新命名为 fleet signer。 |
| `ar1_003` directory/`a0v_093/094` | 受管 assignment、可选 DB Host lease 与隔离 worker fence | 目录只包含受管身份；真实 DB 尚在 `a0v_092`，租约函数/表未部署；没有对未受管/离线 Host 的控制面覆盖。 |
| `deploy/dev/*.plist` | 本机 launchd 一个已知 Host 启动定义 | 非跨机器 inventory，不含 CI/容器/灾备/手工入口；本机停止不阻止别处重启。 |
| `deploy/spoke-full/chart` | Spoke 应用 Helm 模板，replica 可变 | 不是 A0-V Runtime Host 部署；模板不是当前全机实例清单，也没有签名覆盖声明。 |
| Apollo `/v1/apollo/fleet` | Hub/Spoke 产品目录，代码明确 `fullSpokeRuntimeDeferred`/mock | 不是 Runtime Host 资产/部署控制平面；不能作为全机 A0-V Host inventory。 |
| `deploy/dev/aos-deps-inventory.md` | 2026-07 开发依赖目录记录 | 与 Runtime Host 机器和启动面无关。 |
| 本机 `ps` 与已知 DB session | 当前局部诊断计数 | 不能排除未受管、离线、尚未连接或未来重启的 Host。 |

结论：在已审阅的仓库/部署来源中，没有可证明“所有可启动 A0-V Runtime Host 的机器/入口”且能禁止旧入口重启的签名控制面清单。此为**权威来源缺失**，不是“使用现有签名 API 改个 payload”即可解决。若有仓库外正式部署控制面，必须先以其接口/资产覆盖/信任根/签名轮换证据接入并做正反向逐节点核对；本波不能假定它存在。

## 后续最小切片与禁入

可独立开发：专用 `fleet-universe/v1` 签名信封的纯 Ed25519 验证器及 isolated 负例，使用独立 fleet trust-root namespace 与 domain-separated canonical payload；验证成功也只能证明某 signer 签了某 bytes，不能证明覆盖全部机器或旧入口被禁止。结构分类器 W5c7c 已固定无授权。未来控制面 adapter 应交叉核对资产 revision、部署 revision、机器/入口全集、禁止重启状态、DB role/OID、live cutover ACK，再在 Fresh Owner 单事务中使用；真实 closure 另 plan/key。

真实库 `a0v_092`、Host lease 默认 off、worker 全路径 fence 未证明。A0-V rev4 disabled、12 原 Run running、stalled Receipt 0；严格 24 小时与物理第二 Host=0 均未成为 closure 授权。商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。
