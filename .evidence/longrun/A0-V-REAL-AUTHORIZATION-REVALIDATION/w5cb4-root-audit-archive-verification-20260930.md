# W5CB4 根目录 AOS 历史现场迁移验证

## 范围与过程

按 `w5cb4-root-audit-archive-plan-20260930.md`，先只读盘点：一级 `.aos-*` 目录 40 个、`du` 合计约 1,029 MiB，其中 `.aos-recovery-20260920` 约 894 MiB。文档、脚本和证据对多个历史路径有直接引用；r3 签名 Receipt 内含绝对构建/签名路径。进程、`lsof -F n`、`.env` 与 LaunchAgent 检查识别出在用路径。

迁移器 `/tmp/aos_migrate_root_history_20260930.py` 只对 32 个无打开文件且非正式当前来源的目录做同设备 `os.rename`，逐一创建旧路径相对符号链接，并在 `aos-recovery/migration-manifest.json` 记录 SHA-256 树摘要、文件数、字节数、新旧路径。异常分支会原路回滚。8 个当前使用/正式来源目录未迁；无库、卷、备份或文件被删除，内容未编辑。根 `.vscode/settings.json` 只列出 32 个兼容链接供 Explorer 隐藏，不隐藏 8 个在用目录。

| 检查 | 命令与结果 |
| --- | --- |
| 迁移 | `python3 /tmp/aos_migrate_root_history_20260930.py` → exit 0，`state=complete`、`moved=32`、`kept=8`、`compatibilityLinks=32`、`fileBytes=1029837483`。 |
| 完整性 | 独立重跑 manifest 所列 32 个目录的 `tree_digest` → exit 0，全部与迁移前 SHA-256 树摘要、文件数、字节数相同；旧链接全部解析到新目录。 |
| 路径与视图 | 物理根目录 `.aos-*` 8 个、符号链接 32 个、`aos-recovery` 内实体目录 32 个；`.vscode/settings.json` 解析成功，32 个隐藏项均为兼容链接、未包含 8 个保留目录。未做编辑器 GUI 截图。 |
| 服务读回 | 迁移前后 `curl http://127.0.0.1:8080/openapi.json` → 200；`curl http://127.0.0.1:8434/` → 200。 |
| 正式来源 | 迁移后 `scripts/a0v_growth_112_formal_source_audit.py` 使用旧签名 Receipt 绝对路径 → exit 0，`CURRENT_FORMAL_SOURCE_AUDIT_SAFE_BLOCKED`、`effects=0`、`formalReady=false`；当前/clone 物理目标及签名可读。 |

## 使用与回滚

历史命令继续使用原绝对路径，由兼容链接透明定位到 `aos-recovery`。回滚单个目录：确认无打开文件后移除旧路径的**链接**，将归档实体目录同设备移回旧路径，再按 manifest 复核树摘要。不要删除实体目录、数据库卷或备份。迁移仅整理文件位置，不证明备份可全库恢复，也不改变 E17 正式授权或首链状态。
