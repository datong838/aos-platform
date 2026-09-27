# W5CB4 E02：当前卷可信备份与 a0v_107 迁移核验（2026-09-28）

## 结论

当前唯一 AOS 库 `aos_current_preview_20260927` 在保留原命名卷 `aos-a0v-recovery-pg-data` 的前提下，已从 `a0v_106` 精确迁移至 `a0v_107`。迁移为新增 D01 proposal/approval/revocation 历史表、RLS/ACL/受检函数；不更新/删除旧业务行，downgrade 明确拒绝。当前新增三表均 0 行，不能因此声称 D01 自然首链通过。

## 备份与独立恢复

- 新备份文件：`/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260928-cIitev/aos_current_preview_20260927.dump`；`pg_dump -Fc`，3,842,950 bytes，SHA-256 `cb2f1b63bee108ade2d20d4fa3b5583471332345111a02229db50ca43816533d`。未复用历史 `/backup` 空目录，未删除旧卷/备份。
- 恢复到独立新库 `aos_current_restorecheck_20260928_cIitev` 成功（`pg_restore --exit-on-error`），源与恢复库只读对比：版本 a0v_106、installation 1、包版本 4、Runtime binding 0、Skill revision 37 完全一致。再在恢复库先试迁 `106→107` 成功，隔离库保留供审计；不把同集群新库夸称异机灾备。

## 当前实例迁移与代码一致性

- 迁移前精确停 8080，18181 无监听；当前库预检为 a0v_106/binding 0，备份 SHA 再读一致。Alembic 一次执行 `a0v_106→a0v_107`，事务型 DDL 正常提交；只读复核为 `a0v_107|installation 1|published bundle 4|binding 0|proposal 0|approval 0|revocation 0`。
- `scripts/a0v_current_preview_http.py` 精确版本门改至 107；鲜活重装链的 `scripts/a0v_current_preview_bootstrap.py`、`scripts/a0v_current_preview_registry_publish.py`、`scripts/a0v_current_preview_installation.py` 同步改至 107，签名/安装/四包/零 binding/关闭 worker 门保持原样。专项 8/8，连同 D01 受检来源选择与 E01 邻接累计 59/59；仅已有 Pydantic/Starlette 警告。当前源码 preflight `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，返回 a0v_107。

## 提交后最新栈运行核验与下一波

代码/证据提交 `a85e0293` 后，精确重启同一 `colima-aos-extension/aos-a0v-recovery-pg` 容器/命名卷，Vite 守护恢复 8434，最新代码 API 启动 8080；库 preflight 仍 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`/a0v_107/安装 approved/4 包 published/binding0。API 明示 `migrationMode=disabled`、Host0、workers0；8080 OpenAPI 与 8434 `/workshop` 都 HTTP 200，18181 无监听。实际只读 D01 Skill 候选 GET 为 200/三组空、三 blocker；浏览器 reload `/aip/skill-publish` 见 37 evaluated/0 published、三 blocker、发布按钮 disabled，侧栏工作台无可见入口。

外部 AOS 总控上下文新 229 文件与 228 指针已提交 docs m1 `e11c954e`；AOS 共享记忆经 CAS 到 `AOS-000803`，Prime 三投影及本地强一致投影读回 CURRENT，docs m1 `0ed10c4b`。Codex 跨对话记忆另按用户“记住”指令写入增量 note。下一波 E03 继续正式 Skill/Logic/模型/职责来源和 C2b 联合正向；不回放旧 12 Run、不读取商城源。
