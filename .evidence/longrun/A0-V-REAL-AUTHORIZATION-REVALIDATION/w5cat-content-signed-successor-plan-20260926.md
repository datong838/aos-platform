# W5cat｜内容能力新签名包与安装代次安全迁移（开码前方案）

上位：231 A1、231-2 制品不可变与签名准入、231-3 安装/禁入/卸载重装状态机、231-5/6 首链内容/费用与 Host；W5caq～W5cas verification。基线 m1 `23c45d0c`（W5cas 方案提交 `8887bc8c`）。用户已授权唯一开发，但**没有**授权重播未知原 Run 或绕过当前业务/Provider 权威。

## 当前证据与未决版本

仓库作者树 `bundles/solutions/ecommerce-growth` 已含 v2 `PENDING` 内容回执及销售武器方法；仓库固定候选最高 `solution.ecommerce.growth/1.10.0`。工作区外 BM/BN 恢复目录有独立签名 `1.10.2`，BN 9 月 20 日曾 active，但历史 verification 不能代替 9 月 26 日当前 Registry/Installation 真值。1.10.0/1.10.2 未含 v2 PENDING 合同，不能改写其已签名 bytes；新坐标必须经只读 Registry 去重后选定，并从可信源构建、复核差异、签名/发布，不能由旧签名包自动继承新授权。当前生产内容 Worker 默认关闭。

## 串行第 1～6 步

1. **只读清册**：核当前服务、Runtime Host、Registry/Installation/Dispatch/epoch、四依赖及已签名候选坐标和哈希；不读商城源，不接触 12 旧 Run。无法连当前权威则只做离线新包，不假称 installed。
2. **文件级新包清单**：在 `scripts/` 新增专用候选冻结脚本，来源为已审作者树与已签名 1.10.2 的可证明基线；输出到 `bundles/candidates/ecommerce/solution.ecommerce.growth/<new-version>/`（坐标由第 1 步去重确定）。只引入内容 v2 PENDING/批准方法及其真实依赖，重新生成 runtime image index、依赖锁、SBOM/evals/前端 manifest 的准确 hash；必要时同步 `domain.ecommerce.core` 等依赖，绝不暗改旧制品。精确文件清单在版本/差异审计后补入本方案才编码。
   - 17:28 只读差异复核：仓库 1.10.0 到当前作者树的 backend 业务差异精确为 `content_capability_runtime.py`、`ecommerce_content_campaign_workflow_contracts.py` 和新增 `sales_weapon_brief.py`；作者树 `__init__.py` 少候选专用 `_STATIC_CONTRIBUTIONS`，不能覆盖候选该文件。已签名工作区外 1.10.2 同样缺上述业务增量，且其 canonical alias 及签名 bytes 必须保留不变。先以仓库版本化 1.10.0 为离线基础、精确 overlay 这三文件，再更新新版本 manifest/八个自引用、评估证据；`scripts/prepare_ecommerce_growth_1_11_candidate.py` 与 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_1_11_candidate.py` 是本波新增文件，生成目录 `bundles/candidates/ecommerce/solution.ecommerce.growth/1.11.0/`。1.11.0 仅是**离线拟用坐标**；18181 GET Registry 返回 401，尚未证明当前 Registry 不占用，未通过前不得签名发布。候选构建器必须记录 1.10.0 tree hash 和三份作者源 hash 并拒绝漂移，不从临时 pycache 或非版本化恢复目录混入。构建/OCI/签名/安装另设门，不因复制目录自动推进。
   - 17:30 固化源哈希：1.10.0 tree `f473d9a452bdac2f5547525672b32cabf53a4f58dcddcfc8d75cd372e06fe688`；三份作者文件 SHA-256 为 `3d0dacd0...`、`c7751997...`、`5c7dc979...`（完整常量入脚本）。旧 `runtime-image-index.json`、SBOM、旧 bundle eval、旧签名不得随改码后的新候选冒充有效；现有 build pipeline 需以源 SBOM components 为输入再追加 SDK/base，因此源候选保留其基础 components、删除旧 eval/签名/任何 image index，并标 `UNBUILT/UNSIGNED`，待隔离 build 重新生成/审核。旧候选 1.10.0/签名 1.10.2 完全不动。
3. **RED→GREEN**：原 1.10.0/1.10.2 digest 不变；新包声明与实际 SDK register 集合相等，PENDING 不会被误当 COMPLETED；旧 v1 行为保留；tamper/撤销/过期/跨租户/旧 epoch 拒绝；隔离 OCI 注册/心跳与业务端口无效果。
4. **安全发布与安装**：先做构建、签名、Registry/lock/依赖 exact 验证；再依 231-3 禁入→排空→旧代 detach/未决义务审计→新代安装/configure/enable→9 路原子切换。每一步单独 Receipt 与回读；如果旧 12 Run 未决义务会挡卸载，不强行关旧代，优先规划并行新安装/明确 scoped cutover；绝不删除或改写原 12 Run。
5. **当前只读 canary 与浏览器**：`org-org/dev-project` 核当前安装、Host/Provider/费用/审批/事实/TaskRun；`dev-org/dev-project` 仅零 canary。安装和 UI/路由若改变，按产品八页当前有效入口做浏览器专项验收；无当前门则不打开生产 Worker、不调用 Provider。
6. **证据与续波**：专项+累计测试、方案/代码一致性、verification、m1 精确 commit、D-waves/AOS/Prime 记忆。下一波 W5cau：当前 scoped 自然内容执行与人工评审续跑；若安装仍被权威挡，则先做人工评审链的无效果代码/隔离验收，不死磕旧快照。

停止条件：无法证明签名信任根/Registry/Installation/旧代未决义务时，只完成离线候选审计和安全代码，不发布/迁移；提交或外呼结果未知先冻结和只读对账，绝不重发。`230 L0` 挂起，旧 12 Run 后置，m1 单写不 push。

## 本轮停笔门记录（17:36）

本机 8080 未监听；18181 是历史 W5c9a HTTP-only 诊断 PID 36529，Host=false、Cron=false、snapshot=false 的启动证据，**不是**当前可发布身份。18181 对 Registry/Installation GET 均返回 401；本轮无可用的当前只读 Registry/Installation 认证上下文。故第 4/5 步的签名发布、安装迁移、真实 scoped canary 在本轮停止，绝不拿 9 月 20 日 BN active 证据冒充当前状态。已依据停止条件转为离线源候选与静态/包合同测试；下一波优先推进可并行人工评审/续跑 Owner，同时另设当前 Registry 身份与安装门只读诊断，不因为这一角落阻塞首链核心。
