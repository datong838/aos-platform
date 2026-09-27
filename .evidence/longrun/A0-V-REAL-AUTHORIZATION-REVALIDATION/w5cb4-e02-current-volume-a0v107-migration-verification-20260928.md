# W5CB4 E02：当前卷可信备份与 a0v_107 迁移核验（2026-09-28）

## 结论

当前唯一 AOS 库 `aos_current_preview_20260927` 在保留原命名卷 `aos-a0v-recovery-pg-data` 的前提下，已从 `a0v_106` 精确迁移至 `a0v_107`。迁移为新增 D01 proposal/approval/revocation 历史表、RLS/ACL/受检函数；不更新/删除旧业务行，downgrade 明确拒绝。当前新增三表均 0 行，不能因此声称 D01 自然首链通过。

## 备份与独立恢复

- 新备份文件：`/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260928-cIitev/aos_current_preview_20260927.dump`；`pg_dump -Fc`，3,842,950 bytes，SHA-256 `cb2f1b63bee108ade2d20d4fa3b5583471332345111a02229db50ca43816533d`。未复用历史 `/backup` 空目录，未删除旧卷/备份。
- 恢复到独立新库 `aos_current_restorecheck_20260928_cIitev` 成功（`pg_restore --exit-on-error`），源与恢复库只读对比：版本 a0v_106、installation 1、包版本 4、Runtime binding 0、Skill revision 37 完全一致。再在恢复库先试迁 `106→107` 成功，隔离库保留供审计；不把同集群新库夸称异机灾备。

## 当前实例迁移与代码一致性

- 迁移前精确停 8080，18181 无监听；当前库预检为 a0v_106/binding 0，备份 SHA 再读一致。Alembic 一次执行 `a0v_106→a0v_107`，事务型 DDL 正常提交；只读复核为 `a0v_107|installation 1|published bundle 4|binding 0|proposal 0|approval 0|revocation 0`。
- `scripts/a0v_current_preview_http.py` 精确版本门改至 107；鲜活重装链的 `scripts/a0v_current_preview_bootstrap.py`、`scripts/a0v_current_preview_registry_publish.py`、`scripts/a0v_current_preview_installation.py` 同步改至 107，签名/安装/四包/零 binding/关闭 worker 门保持原样。专项 8/8，连同 D01 受检来源选择与 E01 邻接累计 59/59；仅已有 Pydantic/Starlette 警告。当前源码 preflight `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，返回 a0v_107。

## 尚待提交后运行核验

需在本证据与代码提交后以最新 m1 代码重启 8080/8434 和同一 PG 容器，浏览器读回工作台禁入与技能空候选；读回 18181、Host/worker 仍关闭，补录结果。下一波 E03 继续正式 Skill/Logic/模型/职责来源和 C2b 联合正向，不回放旧 12 Run、不读取商城源。
