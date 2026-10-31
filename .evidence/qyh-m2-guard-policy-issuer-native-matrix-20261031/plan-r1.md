# Guard policy issuer 隔离原生矩阵方案 r1

## 目标

在全新、独立、可保留复核的 PostgreSQL 与 Unix socket 资源中，证明 `a7c4528dd` 的专用连接和 `96520f821` 的私有 issuer 协议能按既有底层审批规则工作；不接 current stack，不形成真人批准或策略激活。

## 固定资源

- Docker context：`colima-aos-extension`
- PostgreSQL 容器：`qyh-m2-guard-issuer-native-r1-20261031-pg`
- 网络：`qyh-m2-guard-issuer-native-r1-20261031-net`
- 卷：`qyh-m2-guard-issuer-native-r1-20261031-data`
- 数据库：`aos_guard_issuer_native_r1`
- 本机只允许 `127.0.0.1:18459` 转发；测试结束关闭转发，不删除容器、卷或证据。
- Unix 目录：`/Users/ddt/work/projects/ai_agent/aos-recovery/qyh-m2-guard-issuer-native-r1-20261031`

## 顺序

1. 只读确认镜像摘要、端口未占用、资源名不存在。
2. 创建独立网络、卷、PG 容器；使用随机测试密码，仅写 0600 私有文件，不输出正文。
3. 创建测试数据库并跑当前完整迁移链；核 migration head、表/触发器/角色。
4. 仅在隔离数据库内把 `aos_guard_approval_issuer` 临时设为 LOGIN 并配置专用 passfile；测试后恢复 NOLOGIN/PASSWORD NULL。
5. 原生连接矩阵：readonly inquiry、serializable decision、错误租户、错误数据库、危险权限/成员、环境覆盖。
6. Unix socket 矩阵：frame 上限、重复 key、错误 method、错误 peer/tenant、一次 execute 后 inquiry；所有身份与测试 proposal 都是合成值。
7. 关闭 18459 转发，恢复临时 LOGIN，保存只读最终状态、资源身份、测试日志与 SHA。

## 停止与重试规则

- 任一数据库写命令结果未知：停止写入，只读核对，不重发。
- 只允许本 Task 的新资源；发现同名旧资源或端口占用即停止创建并对账。
- 不读取、复制或修改 current stack 凭据、卷、容器、角色。
- 不启动 Host/worker/Provider/模型/Schedule，不执行真实批准、消费或激活。

## r1 恢复决策（2026-10-31）

首次初始化误用镜像默认管理角色 `postgres`，迁移在 `w6_002` 首次引用项目基础角色
`aos_app` 时失败并完整回滚，数据库仍停在 `228assetintegration`，且不存在任何
`aos_*` 角色。权威旧隔离原生实验显示基础初始化角色应为 `aos_app`（LOGIN、
SUPERUSER），`aos_runtime` 则由后续 `228ti2e6` 迁移创建，不能提前猜建。

因此仅重建本 Task 内的空测试数据库 `aos_guard_issuer_native_r1`：保留容器、网络、
卷和 0600 私有密码文件，先按权威属性创建 `aos_app`，再以其为数据库 owner 从空库
重新执行官方 bootstrap 与完整迁移。重建前后均只读记录数据库名、owner、版本和
对象数量；不得触碰 current stack、当前业务库或任何真实数据。若 DROP/CREATE 结果
未知，立即停止写入并只读对账，不自动重发。

公共 PG 测试夹具会主动拒绝 `AOS_TEST_USE_SHARED_DATABASE=1`，不能直接用于本方案中
要求保留复核的指定数据库。新增证据级 runner
`test_native_guard_issuer_pg_r1.py`，只复用正式产品接口和本地 OIDC 测试签名器，并在
每次管理连接前强制断言 host=`127.0.0.1`、port=`18459`、database=
`aos_guard_issuer_native_r1`、session/current user=`aos_app`。runner 不修改公共夹具或
放松其安全断言；固定私有 attempt/passfile 目录，存在旧 attempt 时 fail-closed；结束
必须恢复 `aos_guard_approval_issuer` 为 NOLOGIN/PASSWORD NULL。

首个专用 runner 状态目录 `pg-matrix-r1` 在写提案前因 `meta_workspace` 父记录缺失而
失败；只读对账证明 proposal/approval/guard revision 均为 0，issuer 已恢复，目录内
仅保留已擦除的 passfile。该目录不删除、不复用。补齐隔离库中与既有 `twa_org /
twa_workspace` 同范围的 `meta_org / meta_workspace` 父记录后，runner 使用新目录
`pg-matrix-r2`；若 r2 已存在则继续 fail-closed，不覆盖任何 attempt。

## 完成判据

完整正负矩阵 GREEN、临时 LOGIN 恢复、转发关闭、资源保留且证据可重放审阅。该结果仅解除“审批 issuer 基础设施未经原生验证”的工程缺口；工程2/8、真实0/8不变。
