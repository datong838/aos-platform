# W5CB4 BG-00o｜隔离真实对象存储读回门

## 上位与现场

231 首链、228 G2、AIP-4 E1A 要求正式 Eval 来源可复验；BG-00n 只在注入测试字节下证明 tenant key、大小与 SHA-256 门。仓库 `deploy/dev/docker-compose.yml` 固定 MinIO `RELEASE.2025-04-22T22-12-26Z`；当前 9000 无监听，`aos-a0v-test-only` 只有隔离 PostgreSQL，当前业务卷/API/Web 不依赖该测试存储。

## 本波步骤与边界

1. 在 `aos-a0v-test-only` Docker context 下确认容器名与 19000 端口空闲；拉仓库固定镜像，以新 test-only 容器和独立卷启动 MinIO，不碰当前权威卷、历史库或默认 Colima。测试凭证仅用于隔离实例，不进提交/日志。
2. 用现有 S3 adapter 对精确 `org-org/dev-project/evals/bg00o/...` key 写一份非业务测试字节；真实 GET 由 BG-00n reader 验 SHA-256。缺对象、错 hash、越租户与超过上限分别失败关闭；核 S3 请求与 tenant 前缀，没有任何商城源读取或当前 DB 写入。
3. 如镜像拉取、bucket 创建或端口权限失败，定位具体可修复点再尝试一次；不改生产校验来适配测试环境。证据记录命令/退出码、镜像 digest、容器/卷身份、测试对象 key 与结果，敏感凭证不得入证据。

本波不生成 G2 Dataset/Receipt、不接正式 Store、Judge 或 Target executor；不把测试对象或存储回环称业务验收。若代码无改动，verification、D-waves/AOS/Prime 与 m1 精确文档提交后进入正式格式/签发接线下一波。Host/worker/Provider 关闭，旧 12 Run/230 L0 挂起，不 push。
