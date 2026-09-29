# W5CB4 BG-00o｜隔离真实对象存储读回未通过记录

方案 `w5cb4-bg00o-isolated-eval-object-store-plan-20260929.md`，基线 `m1@5ceb8abc`、权威 `AOS-000863`。目标是仅在 `aos-a0v-test-only` context 跑仓库固定 MinIO 镜像，向 tenant eval key 写非业务字节，再由 BG-00n reader 真实 S3 GET/hash 读回。

- 前检：`docker ... ps -a --filter name=aos-bg00o-eval-minio` 无容器；固定 MinIO 镜像在 test-only、extension 与 desktop context 均无本地副本；19000 与 9000 监听数均 0。新建且仅本波使用的 `aos-bg00o-eval-minio-data` 空卷成功，未挂载到容器；`/tmp/aos-bg00o-minio.env` 为 mode 0600 随机测试凭证文件，内容未输出或提交。
- `docker --context colima-aos-a0v-test-only pull minio/minio:RELEASE.2025-04-22T22-12-26Z` 第一次退出 1，Docker Hub registry HEAD 请求 TCP 443 超时；`curl -I --max-time 8 https://registry-1.docker.io/v2/` 也超时。按方案同一固定镜像重试一次，仍退出 1、TCP 443 超时。没有更换未知镜像或信任源。
- 复核：`docker volume inspect aos-bg00o-eval-minio-data` 成功；容器列表仍空，9000/19000 监听均 0。无 S3 PUT/GET、无业务对象、无当前 DB/卷/备份写入或删除。BG-00n 的 `13 passed, 1 skipped` 中 live MinIO 测试继续为 skipped；不能把该单元 GREEN 当实际存储回环。

结论：BG-00o 的真实隔离对象存储验收未通过，具体条件是固定镜像无法从 Docker Hub 下载。此条件只阻断对象存储实例验证；主线转做独立 Eval Judge/Target executor 权威与正式 G2 签发合同。当前 D01、Skill 发布/Binding、Host/worker/Provider 与自然首链继续禁入；不 push、不读商城源、不重放旧 Run。
