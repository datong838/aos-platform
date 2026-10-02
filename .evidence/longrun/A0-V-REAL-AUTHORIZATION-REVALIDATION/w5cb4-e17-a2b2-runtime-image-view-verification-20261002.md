# E17-a2b2a 运行镜像只读证据视图 verification

## 范围与 RED

先复习 231-2/231-3、E17 方案与 `w5cb4-e17-a2b2-runtime-image-view-plan-20261002.md`。新增读者前，两个测试导入 `read_current_runtime_image_evidence` 报 `ImportError`（pytest collection exit 2）。只改当前发行读者及两个专项测试；其余工作树脏文件不纳入。

## GREEN 与现场

- 当前四旧包 approved、active/binding 缺失：当前实例读者专项 `4 passed`；新镜像视图拒绝 `INSTALLATION_NOT_ACTIVE`。
- 原 Growth 1.13 签名 producer 的可销毁 PG/OCI：串行执行 `test_growth_signed_installation_full_schema_pg.py`，`1 passed, 7 warnings`，exit 0。原 active/current 安装与 ready binding 时返回 3 个 signed image/config digest、`a0v_135` schema head、精确 generation；错 generation 拒绝；原 job 停止后 binding 非 ready 拒绝。重复执行增强断言仍 `1 passed, 7 warnings`，exit 0。
- 旧 Growth 1.12 PG/OCI 路径 `1 passed`，exit 0；相邻五文件（当前读者、preview HTTP、Host preflight、release revalidation、UI resources）`36 passed`，exit 0。
- `python -m py_compile`、`git diff --check` exit 0；`docker --context colima-aos-extension ps -a --filter label=aos.extension.owner` 无残留。并行 PG 迁移曾因共享 role `ALTER ROLE` 发生 `tuple concurrently updated`，改为串行后通过。
- 2026-10-02 浏览器只读核 `/aip/skill-publish`：`org-org/dev-project`，37 条已评测、0 已发布，三 blocker，发布按钮 disabled，侧栏“暂无可见工作台入口”。本波浏览器截图见该轮工具留证；本波无 UI 改动。

## 复审结论与边界

旧发行读者仍在同一 `REPEATABLE READ READ ONLY` 事务内核 lock、release、签名字节并返回 `EVIDENCE_ONLY_NO_START`。新读者在同事务加 active=current、同代 ready binding、资源 lease 集合与未过期状态、已签 OCI index/缓存 digest、schema head；结果也固定 `EVIDENCE_ONLY_NO_START`。未接受执行许可，未启 Host/worker/Provider，未写当前真实库，未读商城源、重发旧 Run 或手工 Run。

这是证据视图的完成，**不是正式 API/Host 启动 selector，也不是当前实例首链**。仍缺正式外部 OIDC、三独立身份/信任根、八类有效配置、精确 Owner/assignment 与当前 Growth 1.13 正式发布和绑定。下一步先在隔离原 producer 对正式 selector 做 RED，再最小接线；当前实例仍失败关闭。
