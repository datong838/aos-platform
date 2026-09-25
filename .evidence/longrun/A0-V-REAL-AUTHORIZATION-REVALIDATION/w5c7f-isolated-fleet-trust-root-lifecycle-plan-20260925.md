# W5c7f 隔离 Fleet Trust Root 生命周期方案（2026-09-25）

## 上位与目标

复习 W5c7b–e、Registry trust-root 生命周期和 231/231-9。W5c7e 只验证注入公钥签过字节，根的来源、轮换、撤销及防回退未证明；真实控制面清单也不存在。本波只建隔离合同，绝不将信任根快照或签名有效升为 Host/closure 权威。

## 文件级九步

1. 复习上位及现有纯验证器、Registry 范例；不复用 Registry 文件/namespace/实际 key。
2. 本方案先提交。新增 `scripts/a0v_w5c7f_fleet_trust_root_lifecycle.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c7f_fleet_trust_root_lifecycle.py` 和 verification；不改 W5c7e、生产/DB/部署。
3. 纯入口仅接受显式注入 `aos.fleet-root-snapshot/v1` 快照：严格字段、单调 snapshotRevision floor、唯一 keyId、Ed25519 32-byte 公钥、各 key 有效区间/撤销时间。按注入的 aware 时钟选择**唯一**当前 key，转交 W5c7e 验签。快照本身没有权威来源，结果仍三授权标志 false。
4. 专项负例：回退 revision、过期/未生效、撤销、重复/未知 key、畸形根、错误 namespace、无效时钟、签名篡改；轮换期新旧 key 均可按各自窗口验证，但撤销即冻结旧 key。输入不变，无真实 key 或私钥落盘。
5. 跑专项、Host/closure 与 W5c5k–z/W5c6a–z/JDBC 累计回归；临时 PG 用后停。
6. 浏览器只读 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审验证器/上位边界与风险：独立根快照签发/分发/防回退持久锚点和资产覆盖均未实现；真实 closure 仍 no-effect。
8. verification 落盘提交；CAS 更新 docs/AOS 跨对话上下文和 Prime 独立长记忆并读回。
9. 下一波 W5c7g：先方案，审计真实控制面/部署清单接入缺口与安全 rollout；不得因隔离合同而迁移真实 DB 或 closure。

m1 单写不 push；旧 attempt 不重发、不手工 `run_definition`；商城源行不读、230 L0 挂起、dev-org 零 canary。任何未知结果先冻结读回。
