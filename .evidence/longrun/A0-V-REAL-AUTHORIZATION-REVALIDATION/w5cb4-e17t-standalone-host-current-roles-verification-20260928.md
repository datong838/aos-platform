# W5CB4 E17-t｜独立 Host CLI 当前角色合同 verification

## 本波

`scripts/a0v_ecommerce_runtime_host.py:_load_credentials` 删除 2026-09-12 旧角色名常量，仅固定 Web/Runtime/Directory 三 plane；要求 0600 文件三项齐备，role/DSN 互异，各项 DSN `user`/`password` 与文件中 role/password 一致。错误只返回固定 `CREDENTIAL_FILE_INVALID`，不输出凭据。当前角色的实际物理连接、非特权、权限/role OID、assignment、八配置仍由 E17-l 只读预检负责；独立 CLI `main` 的 `FORMAL_OWNER_AUTHORITY_UNPROVEN` 硬门未改。

## 可复核结果

| 检查 | 命令与结果 |
| --- | --- |
| RED | `python -m pytest -q -o log_cli=false services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py -k credentials_require_private_current_distinct_roles --tb=short`：退出 1；旧代码把非 2026-09-12 角色拒绝。 |
| GREEN 专项 | 同文件全跑：退出 0，24 passed；DSN user/password 不符、role/DSN 重复和权限错误均固定拒绝。 |
| 邻接累计 | 该文件加 runtime connections、当前 Host preflight、production runtime、UI wiring、startup composition、installation API、current preview：退出 0，137 passed。`compileall`、`git diff --check` 退出 0。 |
| 当前运行 | E17-s 提交 `7a823534` 的签名预览 API 已重启，8080 `/v1/health` 与 `/v1/ready`、8434 `/aip/skill-publish` 均 200，Host `DISABLED`、18181 无监听，`aos-a0v-recovery-pg-data` 仍挂当前权威容器。本波只改独立 Host CLI，当前预览 API 不加载该脚本；没有启 Host。 |

## 风险与下波

本地凭据一致性不证明正式当前数据库角色或 Owner。当前仍缺正式三身份文件、精确 assignment/Owner、八配置及审批/预算；独立 CLI 的公开状态 `hostId` 还写死旧 2026-09-12 值，虽 `main` 现在不可进入 `_serve`，解除 Owner 硬门前必须绑定 E17-l 报告的精确 Host ID。下一波 E17-u 只读审计 Owner/Approval/Receipt 与 Host ID 来源，先方案后最小代码；无合法权威不得取消 `FORMAL_OWNER_AUTHORITY_UNPROVEN`。浏览器 `browser-pilot` 未恢复，无新截图。旧 Run/商城源/dev-org/230 L0 不动。
