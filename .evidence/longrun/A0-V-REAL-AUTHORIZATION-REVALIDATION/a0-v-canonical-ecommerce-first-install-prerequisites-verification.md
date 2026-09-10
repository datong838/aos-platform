# A0-V Canonical 电商首装写入前置验证

## 1. 结果

`A0V_CANONICAL_ECOMMERCE_FIRST_INSTALL_WRITE_PREREQUISITES_GREEN`。

隔离恢复库身份、结构、控制角色和零 active 基线已通过只读检查；首装前逻辑备份已完成；仓库外持久 Ed25519 签名根和 v4 签名副本已创建并通过正式 ReleasePolicy 回读。此阶段未写 Registry、Composition、Installation 或 runtime 表。

## 2. 现场证据

- Docker context/container：`colima-aos-extension` / `aos-a0v-recovery-pg`。
- SQL `current_database()`：`aos_meta_head`。
- Alembic：唯一 `a0v_001`；13 个要求的 `public` relation 全部存在。
- `aos_app`、`aos_runtime`、`aos_extension_maintainer` 三个角色存在，当前隔离维护连接具备成员资格。
- 正向租户：composition 0、installation 0、active revision 0、runtime operation 0、runtime binding 0。
- 负向 canary：installation/runtime operation/runtime binding 均为 0。
- 四个目标 Registry version 均不存在，符合无 baseline 首装。
- 逻辑备份：4,323,274 bytes，`sha256:e438ba650162674a4215385d0f223d9043af22b6e4a6164c088f7cb2bfb35916`。
- 签名 key id：`a0v-local-ecommerce-canonical-v1`；私钥模式 0600；trust-root revision：`sha256:fc8d449ed6b5dea8b2b933ee0f573e794c9ebe86f540d8b6aab23462f12219c7`。
- 四包签名副本的 content hash 与 v4 build receipt 全部一致，源码 Candidate 与 v4 staging 未写入签名。

备份、私钥、trust-root 和签名 bundle tree 均位于仓库外 `.aos-recovery-20260910/state/a0v-canonical-ecommerce-first-install`。Git 证据只保留路径、文件模式、大小和摘要，不含私钥、公钥正文、口令或连接串。

## 3. 故障与修正

1. 首次真实准备误用仓库 `.env` 的失效 5433 端口，连接被拒绝并在任何副作用前停止。修正为从指定 Docker 容器读取映射端口和进程内凭据，同时核对容器身份与运行状态。
2. 第二次准备的 `pg_dump` 用户被写死为 `postgres`，容器使用自定义初始化用户，备份失败并清理临时文件。修正为从同一容器配置读取实际用户名；口令未进入命令行或输出。
3. 单元测试发现 ReleasePolicy 检查时刻早于 loader 证据观测时刻。调整为先加载全部签名 bundle、再固定检查时刻；没有放宽 evidence currentness。

## 4. 自测与边界

首装专项 `6 passed`，覆盖默认只读、精确数据库名、tree 篡改、持久密钥重放、错误备份目标、错误容器目标。既有七条依赖库 warning 和进程退出日志告警不影响结论。

下一步才允许执行受控 canonical Registry 写入。每个 bundle 必须先 exact get/create，再由不同 actor 完成 create-version、validate、publish；任何 partial 或 immutable drift 均停止并回读对账。
