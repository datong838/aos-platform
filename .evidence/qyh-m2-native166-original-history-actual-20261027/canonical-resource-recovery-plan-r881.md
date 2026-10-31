# M2 canonical 隔离资源恢复方案 r881

时间：2026-10-31（Asia/Shanghai）

## 业务目的

恢复原 `qyh-m2-native166-canonical-r1-20261027-pg` 隔离 PostgreSQL，使后续能够继续验证同租户、同历史、受限 Owner 的多安装刷新与 M2。恢复资源本身不计 M2 或真实业务验收。

## 当前事实

- 当前线程是 2026-10-31 正式交接的 `currentThreadId`，Task/Lease 已完整转移；原业务义务未完成。
- 容器存在于 `colima-aos-extension`，状态为 `exited(255)`，`OOMKilled=false`、`Dead=false`、无错误文本；属于合盖或运行环境断联后的可恢复停止。
- 容器固定镜像为 `sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd`，持久卷为 `qyh-m2-native166-canonical-r1-20261027-data`，内部网络为 `qyh-m2-native166-canonical-r1-20261027-net`。
- 原标签仍指向 `AOS-002055`、nonce `8af8248e67b4128101100eda` 和 canonical lab；旧 owner 标签作为历史事实保留，不改写。

## 最小动作

1. 仅对精确容器执行一次 `docker start`；不创建新容器、卷、网络或端口映射。
2. 最多执行一次 readiness 轮询；失败后停止，不重复 start、不改 PostgreSQL 配置。
3. 使用容器内 `psql` 以只读事务读取：数据库名/OID、cluster name、版本、当前 Alembic head、正向租户数量、安装/命令/事件摘要以及原四条策略草稿事实。
4. 查询前设置 `default_transaction_read_only=on`；不执行 migration166、DDL、业务写入、激活、Schedule、Host、worker 或 Provider。
5. 保存本轮新鲜只读结果；若数据库身份、OID、cluster、版本或原历史漂移，立即停止后续 M2 动作并保留现状。

## 完成标准

- 精确容器恢复为 running/healthy，镜像、卷、网络、标签与冻结事实一致；
- `aos_refresh_activation_native`、OID `16384`、cluster `qyh-canonical166-8af8248e67b4128101100eda`、Alembic `a0v_165` 均精确匹配；
- `org-org/dev-project` 是唯一正向租户，`dev-org` 为零；
- 历史只读事实可读取且没有启动业务执行；
- 结果只证明原隔离资源恢复，不证明 migration166、M2、多安装刷新或真实经营首链完成。

## 风险与回滚

- PostgreSQL 启动会在隔离持久卷内部进行自身崩溃恢复，这是恢复原测试资源所必需，不接触当前业务库。
- 若启动后身份或历史不一致，保持容器运行仅用于只读诊断；不自动重建或覆盖持久卷。
- 本轮不删除任何资源。需要停止时仅停止该精确容器，持久卷保留。
