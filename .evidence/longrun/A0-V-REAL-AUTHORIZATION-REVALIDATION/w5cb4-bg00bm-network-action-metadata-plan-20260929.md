# W5CB4 BG-00bm｜NetworkPolicy 正式动作元数据与数据库边界只读核查方案

上位规则：AGENTS.md、aos-engineering-delivery、231/231-5/231-9、E17 当前真实库只读与独立迁移波、BG-00bh～bl。目标是核对当前 `meta_object_type/meta_action_type` 实际行、ACL、代码头/库头和可恢复备份，确定受控 ActionType producer 的最小安全数据库增量。本波只读，不写当前 PG，不改变 alembic head。

文件与命令：读 `db.py`、`routers/actions.py`、`action_template_registry.py`、`aip_action_store.py`、最新 `a0v_114` 迁移及 231；当前容器执行 `BEGIN READ ONLY` 查 alembic_version、精确对象/动作行和 `information_schema.role_table_grants`；盘点当日备份目录，不读商城源内容。验收输出为缺口、权限边界、迁移/回滚与 test-only 克隆清单，verification、D-waves、上下文精确提交。
