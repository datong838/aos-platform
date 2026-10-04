# b48｜可信签名与依赖评估来源协议（文件级计划）

时间：2026-10-04；基线：`m1@d2ed088d`、AOS-001306；当前真实库 `a0v_135` 只读。

## 上位约束与实情

- 复习 231-3 安装当前指针/ETag/运行禁入与 BIND-1 tenant CapabilityBinding 的 exact refs、CAS、唯一 Receipt 和 required 依赖失败关闭。
- `_read_exact_in_transaction` 读取安装 lock、Registry release，并通过 `ManifestLoader` 和 `ReleasePolicy` 验证文件字节、签名和信任根；`_read_unique_active_in_transaction` 可在调用者事务内复用，但读取本身不授运行权。
- b45 `AipBindingReadinessService.for_transaction(conn)` 保证依赖 Reader 使用同一连接/未提交事实；b47 的受限 SQL 函数只验证持久 composition 四键并写 blocked/PENDING，无法验证签名字节或完整依赖。现有 `AipCapabilityBindingService.evaluate` 在发行写事务之前算 readiness，不能证明最终时刻同源。

## 本波边界与协议结论

1. 只有 SQL 函数 EXECUTE 的账号不得通过可写参数/GUC、自称签名哈希、持久 composition 键或合法外形的快照使 Binding 变 `available`。当前 b47 函数硬编码 blocked；保留这一负门。
2. 最终正向协议需可信 evaluator 在**同一个 SERIALIZABLE 最终事务**中，先锁 exact active Installation/ETag 与 Registry 当前 release，再用实际签名字节/信任根和同连接八类依赖 Reader 计算；CAS Binding 与唯一 Receipt 在该事务提交。必须明确锁顺序、角色最小权限、撤销/换代竞争、依赖时间有效期、幂等回读和异常回滚。
3. 数据库无法从普通调用者提交的 Python 布尔值判断其是否运行过 Loader。正向协议需独立不可伪造的 evaluator 身份/受信证明，以及只向该身份开放的受限命令；普通发行或 runtime 登录不得同时拥有表直写与正向命令权限。证明的确切格式/密钥边界仍需设计和反例测试，未冻结前不新增 `a0v_136`、不放开 `available`、Host 或当前实例。
4. 已提交 revoke/replace 必须令带旧 ETag 的函数调用失败，Binding/Receipt 不留半提交；未提交的竞争必须等安装锁，不靠过期快照放行。客户端绕过 Python Reader 时只有 blocked 路径。

## 精确施工文件与验证

- `services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py`：在既有完整 signed Growth1.13 disposable PG/OCI 测试中，追加两个反例：受限调用者直写 `available`/Receipt 被拒；已提交安装 ETag 换代后重试受限命令失败且无 Receipt/Binding 半写。必要时再加真正并发的锁后重验，不能只拿即时旧值代替竞争证明。
- `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：继续作为单一完整 signed 测试入口，不新增正式迁移或生产开关。
- 本文件和随后 verification：记录 RED、GREEN、相邻回归、剩余不可信边界。代码任何改动先跑上述 RED，再最小修复。

实施修正：Registry 的状态守卫禁止直接 UPDATE；必须调用原 `RegistryService.revoke` 提交生命周期事件。完整测试 fixture 每个 pytest 进程只建一次同名克隆，因此撤销负例通过 `AOS_B48_COMMITTED_REVOKE=1` 独立运行同一测试入口，避免污染正常正向路径；不把此 test-only 开关带入生产。

本波成功仅指负门/协议 checkpoint；不代表当前正式角色、八配置、六 Binding、active Growth1.13、首链或发布 GREEN。当前卷只读，Host/worker/Provider 关闭。
