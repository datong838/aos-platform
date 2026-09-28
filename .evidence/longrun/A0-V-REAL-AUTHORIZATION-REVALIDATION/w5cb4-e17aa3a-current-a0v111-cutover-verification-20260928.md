# W5CB4 E17-aa3a-cutover｜当前卷 a0v_111 与最新栈重启验证

## 备份与完整恢复克隆

- 源：`aos_current_preview_20260927@a0v_110`，容器 `aos-a0v-recovery-pg` 挂命名卷 `aos-a0v-recovery-pg-data`，签名预检 approved 安装 1 / published 包 4 / binding 0。`m1@7f4ab6cf` 代码迁移头 `a0v_111`。
- 源库 REPEATABLE READ READ ONLY 导出 snapshot；容器内 `pg_dump -Fc --snapshot` 创建 `/Users/ddt/work/projects/ai_agent/.aos-e17aa3a-backup-20260928-yl2w21o_/aos_current_preview_20260927_a0v110.dump`，文件 0600、3,916,165 bytes，SHA256 `f8d35e6962164dcb69e08002ae3a3d1c1d9fec8354b56a08b49a29d675eb6999`；`pg_restore --list` 成功且含 TABLE DATA。目录内 `proof.json` 保存精确路径和摘要；其中 `archiveCatalogLines=0` 来自恢复命令的 stdout，不是 TOC 行数，故此字段不可作为目录计数证据。
- 完整 `pg_restore --exit-on-error` 至新库 `aos_e17aa3a_restorecheck_20260928` 退出 0。源与恢复克隆版本同 `a0v_110`，575 张原 public 表行数摘要同为 `95906f9ea53102f5db297e462da3c2f7d469ce96f6ef078f99fd231036bdb1d6`，binding/active budget 均 0。克隆单步 `110→111` 退出 0，原表摘要不变，trigger 1；以克隆 `aos_runtime` 直写 active 得 `BUDGET_ACTIVATION_CONSUMPTION_REQUIRED` / SQLSTATE `23514`。这是同集群独立数据库恢复，不声称异机灾备。

## 零执行窗口和源库切换

- 先停止旧 API 会话与 `com.aos.a0v-web-8434`，8080/8434/18181 均无监听；当前源库非空闲其它会话 0、active budget 0、原表摘要同备份，SHA256 复核一致。
- 预检固定版本测试先改为 `a0v_111`：RED `1 failed, 2 passed`、退出 1；只把 `scripts/a0v_current_preview_http.py` 的 `EXPECTED_SCHEMA_HEAD` 改为 `a0v_111`，复测 `3 passed`、退出 0。
- 在上述窗口中，当前库只做 Alembic 单步 `a0v_110→a0v_111`，退出 0；源库 575 原表摘要不变，active budget 0、trigger 1。原 PG 容器重启后第一次 `pg_isready` 退出 2，第二次退出 0；卷名仍 `aos-a0v-recovery-pg-data`。
- 最新签名预检退出 0：`a0v_111`、安装 approved、4 published、binding 0。最新 API 以迁移禁用、Host/所有 worker 显式关闭启动，Web launchd 重载。8080 `/v1/health`、`/v1/ready` 200；8434 `/workbenches`、`/ecommerce`、`/aip/skill-publish`、`/apollo/assets` 均 200；18181 无监听。只读 DB：installation 1、published bundle 4、runtime binding 0、budget Head 0、active Revision 0、activation Decision 0、trigger 1。

## 回归与限制

- `AOS_DOTENV_DISABLED=1 services/aos-api/.venv/bin/pytest -q` 覆盖 current preview HTTP、预算 DB 门、Store、activation、模型治理和 W7 财务：`40 passed`、退出 0。扩大内容链测试仍因硬编码 `a0v_106` 在前置断言失败，属于独立未提交文件，未编辑、未声称累计全绿。
- 页面 HTTP 200 只证明路径可达，八工作台业务入口/交互和首条经营闭环仍未通过。browser-pilot 当前工具列表不可用，因此无截图，不能记浏览器验收 GREEN。
- 当前预算正式费用上界来源、外部账单完整性、第二独立 checker、八类配置和精确 Host Owner 仍缺，Host/worker/Provider 继续禁入；未读商城源、未重放旧 Run、未手工 run_definition、未写 `dev-org`、未推送。

## 下一波

E17-aa3b 以当前 `a0v_111` 为基线实现单次批准消费的精确 DB 合同；缺正式价格/外部用量时继续拒绝 active。并对齐独立内容链测试固定迁移头与测试种子，重跑累计门；随后核验八配置/Host Owner，授权齐备才做自然首链。
