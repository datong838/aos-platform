# W5cat｜内容后继源候选核验与发布门冻结

## 结论

**PARTIAL：离线 `solution.ecommerce.growth@1.11.0` 源候选已冻结并测试；没有 build/OCI/签名/Registry 发布/安装切换。**方案同目录 `w5cat-content-signed-successor-plan-20260926.md`，基线 m1 `23c45d0c`，计划提交 `cc83409f`。不能把本文件称为正式签名后继或业务内容产物。

## 文件与最小差异

新增 `scripts/prepare_ecommerce_growth_1_11_candidate.py`，只从仓库版本化 1.10.0 候选复制，并以完整 SHA-256 固定的作者文件 overlay：`content_capability_runtime.py` 的 v2 PENDING 非终态、`ecommerce_content_campaign_workflow_contracts.py` 的已批准方法到内部 Task 映射、新 `sales_weapon_brief.py`。保留旧候选专用 `__init__.py` 静态贡献，不误用作者注册树；只更新 bundle version 和八个自引用。新目录 `bundles/candidates/ecommerce/solution.ecommerce.growth/1.11.0` 为 99 个源文件，tree hash `da4bb01fb0e577912d0ce02f97ba38fe1255441ab2a09123f7f0341450ef91a9`。旧 `evidence/bundle-evals.json`、旧签名、镜像索引/依赖锁不进入新候选；保留源 SBOM components 仅供后续 build 重新生成和审核，新增 provenance 明示 `UNBUILT_UNSIGNED`。原 1.10.0 hash `f473d9a452bdac2f5547525672b32cabf53a4f58dcddcfc8d75cd372e06fe688` 未变；历史 1.10.2 签名目录只读未改。

`test_ecommerce_growth_1_11_candidate.py` 先因新目录未存在 RED；修正脚本 Path 类型门后生成，再验证不能覆盖/漂移不能写、新源精确、Manifest/SDK 注册贡献相同。新候选与原内容能力、销售武器包测试共 **49 passed、7 既有 warnings**；候选 backend 与脚本编译、`git diff --check` 通过。无 UI/路由变化且未安装，浏览器验收 N/A。

## 当前停止门与下一波

8080 未监听；18181 由旧 W5c9a HTTP-only 诊断进程提供，Cron/snapshot/Runtime Host 均禁用。Registry/Installation GET 返回 401，当前发行/安装权威不可读；9 月 20 日 BN active 只是历史证据。按方案停止条件，没有签名、发布、禁入/迁移或真实 Provider 调用。第 4/5 步未完成，不能以离线 49 绿替代当前安装/Provider/审批/费用/来源与自然 TaskRun。

下一波 W5cau：先推进人工内容评审→续跑→EffectReview/Wiki 候选的可并行无效果 Owner/Host 接线，另列当前 Registry 身份和安装权威只读诊断；只有完整当前门可信才回到 1.11.0 build/sign/install 及一次自然执行。旧 12 Run 后置、不重发；商城源不读，230 L0 挂起，dev-org 零 canary。
