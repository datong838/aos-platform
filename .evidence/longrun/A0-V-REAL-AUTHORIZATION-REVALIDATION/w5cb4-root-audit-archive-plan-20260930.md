# W5CB4 根目录历史现场迁移方案（仅路径整理）

## 已读事实

`/Users/ddt/work/projects/ai_agent` 下有 40 个一级 `.aos-*` 目录，合计约 1,029 MiB；`.aos-recovery-20260920` 约 894 MiB。正式当前签名树 `.aos-current-build-pyGkqQ` 被进程/审计引用；打开文件检查还发现 `.aos-current-backup-20260930-bg00ce-x0s2h8_x`、`.aos-current-backup-20260930-bg00ck-9us25js3`、`.aos-current-backup-20260930-daily0900-F2hDnz`、`.aos-recovery-20260917` 仍被打开。r3 successor 构建/签名目录由根目录签名 Receipt 引用。大量历史 verification 使用旧绝对路径。

## 迁移边界

用户要求仅迁移且不破坏使用。创建一级 `aos-recovery`，只把**无打开文件、非当前正式签名来源**的历史目录原设备原子重命名到其中；对每个已迁目录在原路径创建符号链接，使旧脚本、Receipt 和历史文档中的绝对路径继续可读。上述打开文件目录、当前签名目录和 r3 successor 构建/签名来源保持原位。目录/文件/卷/数据库/备份内容均不删除、不修改。迁移前后记录相对路径、文件大小和 SHA-256 树摘要，并保存 JSON manifest 与逐项验证结果；任何一步异常即停止，按 manifest 将已迁项目原路回滚。

工作区 `.vscode/settings.json` 只隐藏根级 `.aos-*` 兼容链接，`aos-recovery` 内仍可浏览；不更改 AOS 代码、运行配置、签名 Receipt 或数据库。若编辑器 glob 无法做到仅隐藏根级，则不写该设置，并如实报告视觉残留。

## 检查门

迁移前后核对路径可读、树摘要一致、当前 HTTP 健康与签名来源只读审计结果一致。打开文件、签名来源和权威数据卷不迁移；正式 Host/worker/Provider 不启。原目录符号链接数量增加是兼容事实，不表示备份复制。不要因本次整理声称恢复演练或业务首链通过。
