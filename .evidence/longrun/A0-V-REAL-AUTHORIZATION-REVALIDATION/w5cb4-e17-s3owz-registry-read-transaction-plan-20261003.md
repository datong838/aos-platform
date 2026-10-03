# s3o-w-z 第一切片｜原签名 Registry Reader 与受限事务协议

## 发现与边界

- 原 `ApprovedBIPreparationResolver.select` 同时要求原安装行、bundle 版本/artifact 和 `RegistrySnapshotReader`；此前签名克隆的 resolver 两条连接均用 owner，只有 Plan 写段使用 test-only BI 独立登录，所以**不能**把该正向升级成独立 issuer 完整链。
- s3o-w-w 的 BI 只读连接在返回前已绑定事务局部双租户 GUC、核实际 role 与 REPEATABLE READ/READ ONLY；原 `RegistrySnapshotReader.read` 又无条件发 `SET TRANSACTION`。PostgreSQL 不允许在事务已有查询后改变隔离级别，且先提交会丢 GUC。当前库只读、正式角色/ACL/IdP缺失；只在 disposable PG 复现与修正。

## 文件级步骤

1. `services/aos-api/tests/asset_registry/test_registry_snapshot.py`：RED 以真实一次性 PG 的已启动 READ COMMITTED/非只读连接证明原 Reader 的无条件 SET 有时会被 PG 接受，不能靠 SET 本身证明受限事务属性；另验证已配置正确读事务和现有默认路径。
2. `services/aos-api/aos_api/asset_registry/registry_snapshot.py`：只为显式 `prepared_transaction=True` 新增强校验：真实 psycopg、事务已启动、REPEATABLE READ 且 READ ONLY 才跳过 SET；不符一律 fail-closed。默认 `False` 的原读者继续原 SET，保持旧 fake/stub 与所有既有 Registry 消费者。不得自动 commit/清租户/GUC。
3. `services/aos-api/aos_api/aip_responsibility_template_authority.py`：`ApprovedBIPreparationResolver` 的 RegistrySnapshotReader 增加显式布尔传递位，默认关闭；未来 BI 专用进程组合使用 `True`。不得按调用方 GUC 或环境变量自动开启。
4. `services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py`：在原签名 full-schema 克隆的 test-only BI 角色窗口，用该登录注入原 resolver 并核第一精确 SQL/ACL 拒绝，再逐项记录需要的最小只读表/函数；不直接授 `PUBLIC`、owner/runtime 成员或当前库权限。本切片仅解决事务协议，不为过测给宽权。
5. 专项、相邻 Registry/BI 回归，适用时原签名 full schema；复审、verification、m1 精确提交、D-wave/624/Authority/Prime。

## 下一门

先完成原 resolver 所需最小只读来源与 RegistrySnapshot 的同一受限登录正向，再接有限 accept/原 Plan 服务/Receipt Reader；正式 IdP、角色/ACL迁移、六 active Agent、跨 UID 和首链均另证。当前 HTTP503/Host关，不重发旧 Run，不读商城源，不写真实库。
