# E17-a2｜Growth 1.13 原生产者隔离链 verification（2026-10-02）

## 边界与结论

依 `w5cb4-e17-a2-growth113-original-producer-plan-20261002.md`。只用仓外 **local test-only** Growth 1.13 签名 Receipt、pytest 自动创建的 `aos_test_*_ti4_test` 和独立 OCI；没有写当前 `aos_current_preview_20260927`、没有向正式 Registry 发布、没有启当前 Host/worker/Provider。原 RegistryService 发布四包、原安装 producer 生成 approved@3 exact lock、原 RuntimeLifecycleService/PreparationWorker 生成 active 安装与同代 ready binding；binding 仍 `enabled=false/operation_fence=true`、dispatch 0。E17-a1 读者能在 approved 和 active 两个时点只读核 Growth 1.13 精确发布，输出固定 `EVIDENCE_ONLY_NO_START`。错租户和空信任根拒绝。

## 命令与结果

- RED：新 PG 正例首次 `pytest ...test_growth_113_current_release_evidence_pg.py` 退出1 `RELEASE_EVIDENCE_INVALID`；原因是把已打开事务的 `aos_api.db.connect` 传给读者，读者要求在事务开始前设只读属性。测试改为新建 psycopg dict-row 连接，生产读者未改。复验 `1 passed, 7 warnings`，退出0。
- 隔离完整链：`AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_GROWTH113_SIGNED_RECEIPT=... PYTHONPATH=services/aos-api .../pytest -q --tb=short --disable-warnings --show-capture=no services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` → `1 passed, 7 warnings`，退出0。测试断言 binding generation 等于原资源 lease generation、安装 revision 等于 verified current、package lock hash 等于原 lock、未启用且无 dispatch；OCI owner 容器集合前后相同。
- 旧 1.12 相邻路径：同命令改 `AOS_GROWTH112_SIGNED_RECEIPT=...r3...` → `1 passed, 7 warnings`，退出0。
- 两条 PG 测试分别使用会话级库；同一 pytest 会话并跑曾以重复四包 Registry 坐标退出1。新增 approved-only 测试在 `AOS_EXTENSION_OCI_TEST=1` 时跳过，复验同会话 `1 passed, 1 skipped`，退出0。PG-only 单测前后临时库数量 `14→14`，未新增残留。
- 当前四旧签名包只读/启动门相邻五文件 → `36 passed, 7 warnings`，退出0；`py_compile`、`git diff --check` 均退出0。
- 当前旧 preview 签名预检：`.../.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt ...` → `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，代码/库 `a0v_135`，approved，4 published，binding0，退出0。此预检仍只对应旧预览，不是 Growth 1.13 正式实例。
- 内置浏览器 `/aip/skill-publish`：37 项仅评测、发布 0、三缺口、发布按钮 disabled，电商导航暂无可见入口；截图 `w5cb4-e17-a2-growth113-browser-20261002.png`。

## 方案/代码复审与未完成项

实现只改两份 PG 测试；本地签名树核树哈希、签名根 revision、四包 ManifestLoader/ReleasePolicy 与 content hash，原生产者生成正例；没有修改运行门或正式库。测试侧 `preparation_admission=lambda: True` 仅运行于自动销毁测试库，**不是当前 Host assignment 许可**。仍缺撤销/错 lock/旧代/OCI digest 的完整负例，以及正式 signer/checker/trust/OCI、外部 OIDC、独立身份、八配置、精确 Owner、当前正式 Growth 1.13 发布/绑定和自然首链。下一安全步是补这些负例与正式预检的独立代码项；当前实例继续失败封闭。Goal 保持 active。
