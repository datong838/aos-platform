# b63 文件级方案：可信 available 最终事务与发行角色拆分

## 事实和上位边界

- 231-3 要求 current active Installation/Binding/epoch/权限预算共同准入；BIND-1 要求 exact tenant operational readiness，激活前重算 freshness。b62/b62b 已在完整迁移及签名 Growth1.13 隔离库证明普通 issuer 能直接写 available/hash/Receipt。
- 当前 `AipCapabilityBindingService.evaluate()` 在 issuer 事务外用独立 Reader 算结果，随后另开 issuer 连接写 Binding/Receipt；`update(active)` 在写事务内仍调用独立 Reader。`AipBindingReadinessService.for_transaction(conn)` 已有，但既有 Router 仍装配独立 Reader/Issuer；它仅共享事务可见性，不提供签名证明或发行权。
- 既有 `RegistryIssuerConnectionFactory(command_family="capability_lifecycle")` 要求 `aip_capability_binding` 表级 UPDATE，正是普通 issuer 可直接改 readiness 的授权面。不可直接撤权而不改生命周期路径。Receipt INSERT 也需按 operation 配对 guard，不可仅收回列级 UPDATE。

## 唯一136前的目标合同

1. **身份**：目录 Reader 只读；普通 lifecycle issuer 只持 create 与状态/健康/版本等必要列的 UPDATE，不得 UPDATE `operational_readiness`、依赖 refs/hash、评价时间窗，不得伪造 `capability_binding.evaluate` Receipt；独立 evaluate 命令登录仅 EXECUTE、无 Binding/Receipt 直接 DML、不可 SET/INHERIT 高权 definer。正式凭证需另行签发，test-only 角色不接当前实例。
2. **事务**：受限 evaluate 命令先验 scope/session/幂等，按 Installation→Registry/version→CapabilityBinding 锁序，核唯一 active/current 签名来源和当期字节/信任根；由可信 evaluator 在同一最终事务读取并计算 provider/route/policy、gate/contract、license、data/tool、budget，拒绝未定义种类与过期/撤销。结果不能由可写 GUC、客户端 hash/readiness 决定。
3. **写入**：只在锁持有且证据一致时按 version/status CAS 更新 Binding exact refs、hash、时间窗；同事务插入唯一 evaluate Receipt。重复 key 先验 requestHash 只读回原结果；异 body 冲突；任何失败 Binding/Receipt 同回滚。`active` 转换必须在自己的最终事务重新核当前签名 Installation 与依赖，不能只信持久 snapshot。
4. **并发**：Registry revoke、安装换代和 evaluate 使用同锁/序列化；两种提交顺序只允许明确的旧提交读回或新失败关闭，不留半 Receipt。未知外部结果仅只读对账。

## 本波文件和 RED

- `services/aos-api/tests/aip/test_e17_s3oo_capability_reader_pg.py`：在 disposable `aos_test_*_ti4_test` 中给 lifecycle issuer 仅状态列 UPDATE，要求其仍能通过现有身份预检并且 readiness 列不可直写。先 RED，记录究竟是预检与列级权限不兼容还是已有路径足够；不改真实库/正式迁移。
- 若 RED 指向预检，下一小波只做该 preflight 的最小修正与相邻 create/update/隔离回归；Receipt operation guard、可信 evaluator/八依赖和唯一136正式迁移另行联合证明，不能把局部身份门当作 available GREEN。

## 文件之外的门

- 当前权威 `aos_current_preview_20260927@a0v_135` 只读；唯一136必须与专用卸载角色/ACL统筹，完整 isolated 全链后新备份、全恢复、零执行窗口。Host/worker/Provider关闭；org-org/dev-project 唯一正向，dev-org 仅零副作用 canary。
