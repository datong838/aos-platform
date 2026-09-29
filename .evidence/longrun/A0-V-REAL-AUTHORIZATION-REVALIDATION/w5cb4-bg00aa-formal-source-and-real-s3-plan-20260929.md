# W5CB4 BG-00aa｜正式 Eval 来源只读对账与固定 MinIO 隔离回环方案

## 上位与进入事实

231 首链与 228 G2 内容官要求正式 Eval 内容事实/渠道适配；AIP-4 与 BG-00v/w 要求独立 Eval issuer、Target/Judge 身份和签名 Receipt。当前签名增长包 `content/evals/placeholder.json` SHA256 `e90c23c9234793da6f76f82cc78ceddd677ce47c4c6ed7ced8397bb11d0a69c2`，原文明示 `BLOCKED / Waiting for G2 review / Growth evals are produced by G2`。当前权威库已 `a0v_113`，但四张 authority 表保持空；代码有形状和隔离验证能力，没有正式 producer/Owner/批准材料。228 G2 指增长内容方案，勿与另一份 G2 OAuth Connector 债混同。

BG-00o 固定 MinIO 镜像 `minio/minio:RELEASE.2025-04-22T22-12-26Z` 当时因 Docker Hub 443 超时未取到；目前 test-only context 无本地镜像/容器，19000 无监听，独立空卷 `aos-bg00o-eval-minio-data` 与 mode 0600 的 `/tmp/aos-bg00o-minio.env` 仍在。此卷/凭证仅用于隔离机制，不对应业务 G2 内容。

## 本波文件、步骤、退出

1. 只读核现时签名包、四表行数、现有 G2 产品/技术文件与 issuer/Owner 配置路径，按“设计、代码、当前正式数据/批准”分栏。不得造 issuer、改签名包、使用 OCI trust root 冒充 Eval root，不触碰商城源或当前库写入。
2. 对仓库固定镜像在 `colima-aos-a0v-test-only` 作一次有界 pull。若成功，核 image digest，再用既有独立空卷、仅本地 19000 端口及保密 test-only 凭证启动专用 MinIO；通过项目 S3 adapter 创建隔离 bucket，PUT 一份非业务字节到 `org-org/dev-project/evals/bg00aa/...`，再由 `read_verified_eval_object` 真实 GET/校验 SHA256，记录确切 key/hash/退出码。错 hash/越租户仍需拒绝；测试对象不成为正式 Dataset/Receipt。
3. 若镜像仍不可得，保留卷与现状，只记录错误和容器/端口无运行；不换未知镜像或模拟对象存储。继续完成第 1 项独立来源审计和后继文件级清单，不能称真实 S3 GREEN。

预计新增 `.evidence/.../w5cb4-bg00aa-*-{plan,verification}-20260929.md`、docs 302 与 D-waves 清单；无生产代码改动则只精确提交文档。当前 m1/权威库、Host/worker/Provider/18181、旧 12 Run、230 L0 与 dev-org 均维持禁入。回环若成功只证明字节存取机制；正式 G2 内容、独立签发和自然首链仍各自需要当前授权证据。
