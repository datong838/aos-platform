# b66 文件级方案：Capability evaluate Receipt 身份和同事务配对

## 依据与现状

- 231-3 要求当前签名 Installation/RuntimeBinding/epoch 与权限预算共同准入；BIND-1 要求组织级八类 exact dependency 的新鲜 readiness、expected-version CAS、租户隔离和幂等 Receipt。b63 合同规定 Installation→Registry→Binding 锁序及独立最终事务。
- `aip6_002_registry_receipts.py` 共享表只做 tenant RLS、append-only 和唯一键；普通 Capability lifecycle issuer 仍有该表 INSERT 供 create/update，因而可伪造 evaluate Receipt。b65 isolated RED 已实测。不能简单撤掉整个 INSERT，否则破坏合法 create/update。
- b22 isolated 原型已有 `s3owaob22_receipt_guard`：按 operation/Binding 版本/同事务 xmin 配对，并证实普通可用快照仍可被伪造。b46 isolated 原型已有仅 EXECUTE 的 SECURITY DEFINER blocked evaluate 命令，直接 Binding/Receipt DML 拒绝、同事务写入及重复/回滚验证；但尚无签名八依赖正向，也未进入正式迁移。

## Operation→身份矩阵

| 命令 | 普通 lifecycle issuer | 独立 evaluator 调用身份 | evaluator definer | 其他运行身份 |
|---|---|---|---|---|
| `capability_binding.create/update` Receipt | 仅与本事务对应 Binding CAS 配对后允许 | 拒绝 | 拒绝 | 拒绝 |
| `capability_binding.evaluate` Receipt | 拒绝 | 不得直接 INSERT；只可 EXECUTE 受限命令 | 同事务 CAS 和可信依赖计算后写且由 Trigger 核对 | 拒绝 |
| 其他共享 Registry Receipt | 按各自现有 issuer 合同；Capability 角色不得写 | 拒绝 | 拒绝 | 保留原合同 |

## 本波文件级施工

1. 在隔离 PG 测试中重用原 Capability fixture，先 RED 证明普通 issuer 可无 Binding 更新插入 evaluate Receipt；覆盖跨租户、错 binding/key、重复键与失败回滚的预期。不得用当前库。
2. 先验证小型 DB guard 原型：`BEFORE INSERT` 按 `NEW.operation` 与 `session_user/current_user` 拒绝普通 issuer 伪 evaluate；`AFTER INSERT` 配合 b22 的同事务 Binding version/operation 证据。普通 create/update Receipt 继续通过，独立 evaluator 只有受限命令可写。签名当前安装/八依赖尚不可在此测试中冒充正向。
3. 仅在兼容所有共享 Receipt command family、角色 ACL、原 signed 安装/卸载与唯一 migration head 后，才合并正式唯一136。当前 `a0v_135` 权威库保持只读，迁移另波须新独立备份、克隆全恢复演练和零执行窗口。

## 停止判据

任何跨 operation、伪 hash、旧快照、客户端 GUC、错租户、错 key、重复 Receipt 或失败半写均拒绝；replay 只读回原 exact Receipt。若本波仅完成隔离 SQL 合同/RED，Delivery 明确为 checkpoint，不标记正式可信 evaluator 或首链完成。
