# E17-a2b2b1 版本感知正式发行 selector verification

## RED 与实现

先复习 231、E17 正式启动方案及本波文件级计划。原 Growth1.13 Registry/安装/lifecycle/PreparationWorker 在可销毁 PG+OCI 建 active/current 同代 ready binding；新增测试调用 `select_formal_current_release` 时为 `AttributeError`，`1 failed, 7 warnings`，exit1。随后仅在 `scripts/a0v_current_preview_http.py` 增加只读 selector：要求 `org-org/dev-project`、E17-a2b2a 的当前签名 release/OCI 同代视图、代码/库 migration head 一致、唯一 Growth 1.13、镜像与 runtime member 精确集合；输出安装 revision/ETag、lock、Growth hash、binding generation/revision、schema 与 image/config digest，固定 `PREFLIGHT_ONLY_NO_RUNTIME_START`。原 pinned `preflight`、`--serve`、`--serve-limited` 代码未改。

## 验证结果

- 原 Growth1.13 PG+OCI：`1 passed, 7 warnings`，exit0；selector 读取 3 张 signed OCI image、精确 generation、schema `a0v_135`；错 generation 失败关闭。
- 原 Growth1.12 PG+OCI：`1 passed, 7 warnings`，exit0；旧版本即使原安装 active/ready，也以 `FORMAL_GROWTH_RELEASE_MISSING` 拒绝。
- 当前权威卷只读 signed preview 与相邻 preview/Host 启动门三文件：`31 passed, 7 warnings`，exit0；现存 approved@3/binding0 以 `FORMAL_RELEASE_EVIDENCE_INVALID` 拒绝。单元测试不把本地签名或 test-only 凭据作为当前实例正式身份。
- `py_compile`、`git diff --check` exit0；extension owner 容器列表空、18181 无监听。浏览器 `/aip/skill-publish` 为 `org-org/dev-project`，37项仅评测、0已发布、三阻断、按钮 disabled，电商工作台无可见入口；该轮浏览器工具截图留证。

## 一致性与剩余风险

selector 是**只读输入选择**，不接 `os.execve`，不放行 API/Host。当前 `--serve-limited` 与 Host CLI 仍走四旧版本/binding0 的 pinned preflight；独立 Host 仍固定 `FORMAL_OWNER_AUTHORITY_UNPROVEN`。正式 trust/root 来源、外部 OIDC、独立 API/Directory/Runtime/Web 身份、八配置、Owner/assignment 与 Growth1.13 当前发布/绑定均缺，不能把隔离测试的 test-only 签名接当前实例。后续 b2 要先固定正式来源输入合同，再接 API/Host，当前真库只读，Host/worker/Provider保持关闭。未读商城源、重放旧12 Run、手工 Run、碰230 L0或 push。
