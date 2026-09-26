# W5cat｜内容能力新签名包与安装代次安全迁移（开码前方案）

上位：231 A1、231-2 制品不可变与签名准入、231-3 安装/禁入/卸载重装状态机、231-5/6 首链内容/费用与 Host；W5caq～W5cas verification。基线 m1 `23c45d0c`（W5cas 方案提交 `8887bc8c`）。用户已授权唯一开发，但**没有**授权重播未知原 Run 或绕过当前业务/Provider 权威。

## 当前证据与未决版本

仓库作者树 `bundles/solutions/ecommerce-growth` 已含 v2 `PENDING` 内容回执及销售武器方法；仓库固定候选最高 `solution.ecommerce.growth/1.10.0`。工作区外 BM/BN 恢复目录有独立签名 `1.10.2`，BN 9 月 20 日曾 active，但历史 verification 不能代替 9 月 26 日当前 Registry/Installation 真值。1.10.0/1.10.2 未含 v2 PENDING 合同，不能改写其已签名 bytes；新坐标必须经只读 Registry 去重后选定，并从可信源构建、复核差异、签名/发布，不能由旧签名包自动继承新授权。当前生产内容 Worker 默认关闭。

## 串行第 1～6 步

1. **只读清册**：核当前服务、Runtime Host、Registry/Installation/Dispatch/epoch、四依赖及已签名候选坐标和哈希；不读商城源，不接触 12 旧 Run。无法连当前权威则只做离线新包，不假称 installed。
2. **文件级新包清单**：在 `scripts/` 新增专用候选冻结脚本，来源为已审作者树与已签名 1.10.2 的可证明基线；输出到 `bundles/candidates/ecommerce/solution.ecommerce.growth/<new-version>/`（坐标由第 1 步去重确定）。只引入内容 v2 PENDING/批准方法及其真实依赖，重新生成 runtime image index、依赖锁、SBOM/evals/前端 manifest 的准确 hash；必要时同步 `domain.ecommerce.core` 等依赖，绝不暗改旧制品。精确文件清单在版本/差异审计后补入本方案才编码。
3. **RED→GREEN**：原 1.10.0/1.10.2 digest 不变；新包声明与实际 SDK register 集合相等，PENDING 不会被误当 COMPLETED；旧 v1 行为保留；tamper/撤销/过期/跨租户/旧 epoch 拒绝；隔离 OCI 注册/心跳与业务端口无效果。
4. **安全发布与安装**：先做构建、签名、Registry/lock/依赖 exact 验证；再依 231-3 禁入→排空→旧代 detach/未决义务审计→新代安装/configure/enable→9 路原子切换。每一步单独 Receipt 与回读；如果旧 12 Run 未决义务会挡卸载，不强行关旧代，优先规划并行新安装/明确 scoped cutover；绝不删除或改写原 12 Run。
5. **当前只读 canary 与浏览器**：`org-org/dev-project` 核当前安装、Host/Provider/费用/审批/事实/TaskRun；`dev-org/dev-project` 仅零 canary。安装和 UI/路由若改变，按产品八页当前有效入口做浏览器专项验收；无当前门则不打开生产 Worker、不调用 Provider。
6. **证据与续波**：专项+累计测试、方案/代码一致性、verification、m1 精确 commit、D-waves/AOS/Prime 记忆。下一波 W5cau：当前 scoped 自然内容执行与人工评审续跑；若安装仍被权威挡，则先做人工评审链的无效果代码/隔离验收，不死磕旧快照。

停止条件：无法证明签名信任根/Registry/Installation/旧代未决义务时，只完成离线候选审计和安全代码，不发布/迁移；提交或外呼结果未知先冻结和只读对账，绝不重发。`230 L0` 挂起，旧 12 Run 后置，m1 单写不 push。
