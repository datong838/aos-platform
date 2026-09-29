# W5CB4 BG-00t｜历史 Skill Binding / 安装目录准入验证

基线 `aos-platform/m1@27caa25c`、authority `AOS-000868`。先复习 231 首链与 AIP-6 组织级 SkillBinding 合同，并写本波 plan。只改 Skill Binding readiness、Registry 的只读检查入口、安装目录读取及其测试；无迁移、无当前业务库写入。

## RED 与最小实现

- `test_legacy_gate_without_report_does_not_make_skill_binding_available`：旧逻辑在 Gate passed/hash、Event published/target 齐全但 Eval Report 缺失时返回 `AVAILABLE`，隔离 RED 退出 1，断言 `AVAILABLE is not BLOCKED`。现同租户只读完整 Gate，核有效期/parent exact target，复用 E2 的 Gate/Report 证据复验；缺报告或正式 Skill 执行权威则返回 `SKILL_EVAL_GATE_BLOCKED`。
- `test_publication_event_from_other_gate_is_not_valid_authority`：旧代码仅核 Event 的 published/target，隔离 RED 退出 1，`[] != ['SKILL_PUBLICATION_REVOKED']`。现核 Event 对 exact Gate 的引用。
- 安装目录原代码只消费 cached `available`/TTL，可能把历史 active Binding 显示 runnable。目录 now 调用 Registry 只读 `inspect_binding_readiness`，重验失败或不可用时剔除该 cached Binding；即使重验 available，也要求非空且相等的依赖快照哈希。RED 在新检查函数缺失时收集失败 `ImportError`；新增负向/快照测试覆盖逻辑。没有刷新写库。

## 实测

- 专项 `test_aip_skill_binding_readiness_service.py` + `test_aip_catalog_item_runtime.py`：`12 passed`，追加快照测试后并入下列累计。
- Registry、发布 E2、Skill 发布、Binding、激活、安装目录相邻 7 文件：`42 passed, 1 xfailed`，退出 0。严格 xfail 是无正式 Judge/Target signer/执行 Receipt 的旧 lambda 正向链，不算正向验收。
- 安装定义/当前来源选择 2 文件：`15 passed, 1 skipped`，退出 0。`compileall -q` 和 `git diff --check` 退出 0。
- 容器 `aos-a0v-recovery-pg` 当前运行于 `colima-aos-extension`；`docker ... psql -U aos_app -d aos_current_preview_20260927 -Atc 'BEGIN READ ONLY; ... COMMIT;'` 退出 0，读回 `a0v_111`、栖月汇 Gate 0/Event 0、全库 published Skill 0。原先试用 `-U postgres` 返回 role does not exist，未产生写入；随后按容器 `POSTGRES_USER=aos_app` 复核成功。
- 代码 `m1@075171ff` 后，以原签名 Receipt 运行 `scripts/a0v_current_preview_http.py --signed-receipt .../signing-receipt.json` 退出 0，输出 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、安装 approved、四 published bundle、Runtime Binding 0、数据库 `a0v_111`。旧 API session `87854` Ctrl-C 正常退出；新 session `86682` 以最新代码启动。8080 `/v1/health`、`/v1/ready` 与 8434 `/aip/skill-publish` 均 HTTP 200；18181 无监听。此读回不替代浏览器业务/首链验收。

## 边界与后续

这波是代码消费门 GREEN，当前无历史 published Skill 可做真实正向重验；目录的纯函数旧正向样例只是合成合同，不是业务证明。正式 G2 内容 Owner、Judge/Target signer 与撤销、执行 Receipt、BG-00o MinIO 真实 S3 回环仍缺。D01、Host/worker/Provider 和首链保持禁入，旧 12 Run 与 230 L0 挂起，不读商城源、不 push。日内完整 PG/API/Web 重启证据仍是 09:04；本波代码提交后按正式签名 Receipt 做 API 预检和重载读回。
