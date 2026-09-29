# W5CB4 BG-00u｜直接 Skill Eval Runner 不能产生无权威报告

方案 `w5cb4-bg00u-direct-skill-eval-runner-plan-20260929.md`，基线 `aos-platform/m1@85b153c0`、authority `AOS-000869`。复习 231/AIP-4 E1B/G2 后核代码：`run_by_contract` 已挡 Skill，公开 `run()` 仍在 `create_eval_run` 前无 Skill 身份核查；后续 E2 Gate 能挡发布，但 EvalRun/Report 本身可能被 caller callback 写出。当前权威库只读 `a0v_111`、栖月汇 Suite/Run/Report `0/0/0`，无历史真实行需变更。

## RED 与实现

- 隔离 `test_direct_skill_run_rejects_unattested_callbacks_before_persistence` 的旧代码 RED 退出 1：`Failed: DID NOT RAISE AipEvalAuthorityConflict`，说明 test-only 回调可写 Skill Run/Report。
- `AipEvalRunner.run` 在读取 exact Suite/Contract 后、任何 EvalRun 写入与 callback 前拒绝 Skill，沿用正式入口错误；Logic 原路径不变，无迁移/当前库写入。
- 原 Skill 发布负向测试所需“已存在历史 Run/Report”由隔离库显式种子写入，附测试专用标记，不再以新直接 Runner 生成。仍验证旧 Report 不能导出 Gate、旧 Gate 不能发布、旧 Event 不能发行新 Skill；旧正向 lambda 测试继续严格 xfail，不能计成功。

## 核验

- Runner/Authority/E2/Skill 发布/Binding/目录/激活相邻 7 文件：`55 passed, 1 xfailed`，退出 0。
- 业务调查与文本/内容 Logic Eval 相邻 4 文件：`29 passed`，退出 0。编译与 `git diff --check` 退出 0。
- 当前业务库 `BEGIN READ ONLY; ... COMMIT;` 再次读回 `a0v_111`、栖月汇 Suite/Run/Report `0/0/0`，退出 0。`aos-a0v-test-only` 仅有 PG；仓库固定 MinIO `minio/minio:RELEASE.2025-04-22T22-12-26Z` 拉取返回 Docker Hub manifest HEAD EOF（退出 1），没有 S3 PUT/GET，也未启动测试存储。
- `m1@da0d4893` 后原签名 Receipt 预检退出 0、`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`（approved、四 published bundle、Runtime Binding 0、库 `a0v_111`）。旧 API session `86682` Ctrl-C 退出 0；新 session `33351` 以最新代码运行。8080 健康/就绪、8434 Skill 页面各 HTTP 200，18181 无监听。页面 HTTP 结果不是浏览器业务或首链验收。

## 边界

这是写入前失败封闭，不是正式 Eval 正向可用。当前没有独立 Judge/Target executor 身份/签名、撤销和执行 Receipt；G2 签名包 Eval 仍是 BLOCKED placeholder。现有 bundle trust root 仅为 OCI/安装来源，不能借作 Eval 执行身份。正式正向合同与独立迁移/备份/克隆演练留后续波，D01、Host/worker/Provider 和自然首链禁入；旧 12 Run、230 L0 挂起，不读商城源、不 push。本波提交后用原签名 Receipt 预检和 API 重载。
