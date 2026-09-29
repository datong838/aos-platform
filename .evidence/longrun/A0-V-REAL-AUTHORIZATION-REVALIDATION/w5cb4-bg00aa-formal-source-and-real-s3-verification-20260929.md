# W5CB4 BG-00aa｜正式 Eval 来源与真实 S3 只读核验

## 执行与可复核事实

- `git log -1 --oneline` 在本波开始为 `b2dbe96d`；`git status --short --branch` 显示 m1，并保留无关浏览器插件、`pnpm-lock.yaml` 与两个 w5c8i test-only 未跟踪文件，本波未触碰。
- 复习 `228-电商增长参谋长G2三个核心数字同事与CustomerLite实施方案.md` 第 276、291、294 行：G2.2 需要内容事实/渠道 Evals 和 Draft-only 负向门；这些是产品交付判据，不是当前 issuer 签发凭据。`231` 首链仍以当前安装和真实来源判定。
- 当前签名增长包 `solution.ecommerce.growth/1.11.0/content/evals/placeholder.json` SHA256 `e90c23c9234793da6f76f82cc78ceddd677ce47c4c6ed7ced8397bb11d0a69c2`，正文 `BLOCKED / Waiting for G2 review / Growth evals are produced by G2`。它明确说明正式内容尚未产生。不能把 `growth-gates.json` 的架构 owner 或 OCI trust root 代作 Eval producer/issuer。
- 当前权威库 `aos_current_preview_20260927@a0v_113` 中 `aip_eval_issuer_root`、`aip_eval_executor_identity`、`aip_eval_revocation`、`aip_eval_signed_execution_receipt` 均为 0 行；先前只读核验的 Suite/Run/Report 也均为 0。`rg -n 'eval_issuer_root|eval_executor_identity|eval_revocation|eval_signed_execution_receipt' services/aos-api/aos_api services/aos-api/tests/aip` 仅命中测试，不命中 `aos_api` 生产读取/写入。现有 `aip_eval_execution_authority.py` 为传入 mapping 的纯验证器；正式持久来源与批准链尚无代码接线。
- 在 `colima-aos-a0v-test-only` 对仓库固定镜像 `minio/minio:RELEASE.2025-04-22T22-12-26Z` 执行一次 `docker pull`，退出码 1，Docker Hub manifest HEAD 至 `199.59.148.106:443` 报 `i/o timeout`。随后 `docker images --digests` 无 MinIO，`docker ps -a` 无 bg00o/eval 容器，`lsof -nP -iTCP:19000 -sTCP:LISTEN` 退出 1、无监听。独立卷 `aos-bg00o-eval-minio-data` 与 test-only 凭据保留，未启动容器或 PUT/GET。

## 结果、风险与下一波

本波只读来源审计完成；正式 Eval issuer/Owner/批准、G2 内容及真实 S3 字节回环均**未通过**，当前实例仍失败封闭。没有把占位包、纯形状测试、空表、端口健康当作业务验收。当前库无写入；Host/worker/Provider/18181 关闭，旧 12 Run、商城源、dev-org 与 230 L0 未触碰。

下一波 BG-00ab 独立实现四表的只读、租户约束、撤销快照消费接口，并先以 RED 验证缺 issuer/identity、跨租户、撤销和无 Receipt 均拒绝；只用 test-only PG 做正向机制验证。不得填造正式行或开启 Runtime Host。真实 S3 在固定镜像可取得后再做隔离回环，正式 G2 producer/签发审批仍需合法外部 authority。未来新增表继续检查当前默认 ACL 的 `arwd` 漂移。
