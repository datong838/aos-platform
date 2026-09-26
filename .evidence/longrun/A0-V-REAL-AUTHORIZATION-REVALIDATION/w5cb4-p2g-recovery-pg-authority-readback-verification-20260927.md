# W5CB4 P2g22：18435 恢复 PG 只读权威读回

日期：2026-09-27。方案先行 `m1@54f6a381`。仅本机恢复容器；所有成功 SQL 均在 `SET TRANSACTION READ ONLY`、`org-org/dev-project` 精确 GUC 与租户过滤下执行，最后 rollback。不读商城源、旧 Run payload、secret 或原始内容。

## 前检与访问路径

- `colima-aos-extension` 的唯一 `aos-a0v-recovery-pg` 为 postgres:16、`restart=no`、running、loopback 18435，`pg_isready` accepting；8080/18181 无监听。未启动/重启任何进程。
- 先尝试容器内 `postgres` 系统用户无凭据元数据查询，被 `role "postgres" does not exist` 拒绝，无 SQL 成功执行；未猜测或重试口令。再复用仓库既有 `a0v_formal_text_model_renewal.database_connect("aos_meta_head")` 的限定恢复库连接工厂。仓库根 `uv` 环境缺 `cryptography` 导入，切至已有 `services/aos-api` 环境后成功；未修改凭据或打印 DSN。

## 只读结果

- `current_database=aos_meta_head`、`transaction_read_only=on`，Alembic 实际 `a0v_092`；当前代码头 `a0v_106`。`public.ecommerce_growth_improvement_target` 不存在（第三段 AIP 候选表存在），故当前第二/三段代码不能对该库启动。
- `org-org/dev-project` 的 `bundle_installation` 计数 135，其中 active_revision 非空 111；这是历史总量，不是当前签名安装/可信首链证明。Runtime binding 聚合：disabled/unknown/enabled=false/fenced=true 110，enabled/unknown/enabled=false/fenced=true 1，uninstalled/stopped/enabled=false/fenced=true 15。Host identity enabled 1、租户 assignment assigned 1，仅代表目录记录，不是活进程。
- 精确 `ecommerce_growth_content_review` dispatch 一条指向 extension，dispatch_fence=false；所连 Runtime 是 desired=enabled、observed=unknown、enabled=false、runtime_fence=true、execution_epoch 与 dispatch 不等。故当前权威明确**不可执行**，不能凭 dispatch 单字段开放。

## 判定与后续

- `VERIFIED`：恢复 DB 身份/迁移版本/元数据状态与当前不可执行围栏。
- `NOT_VERIFIED`：当前签名 Bundle/安装代次的 exact 文件与信任根、审批、来源、预算、真人决定、业务反馈自然结果。未查询相关业务行。
- **STOP_CURRENT_API_AND_WORKERS**：迁移 `092→106` 未评审/未执行，当前 Runtime unknown/fenced/epoch mismatch。不得以代码测试绿直接启动 8080/18181 的自然 worker 或打开新 flag。下一波先做 092→106 的迁移差异、备份/空间/回滚可行性与无效果预检方案；迁移属重大真实库写操作，单独波次执行并独立读回后才考虑 Host 恢复。浏览器本波不适用。
