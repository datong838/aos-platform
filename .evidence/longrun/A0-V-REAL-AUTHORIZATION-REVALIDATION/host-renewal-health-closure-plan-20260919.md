# Recoverable Store Host 续租与健康时钟闭包方案

## 1. 上位事实

- AF/AG 的长事务曾阻塞常规 installation/binding 锁，使三项资源租约到期；AH/AI/后续实跑证明
  recoverable Store in-flight 快路径可绕开长事务持有的 current 行锁并持续续租。
- 系统重启及远端控制数据库排队又证明：健康探针本身成功，但进入原子续租事务可能超过三秒 freshness；未来时钟
  仍必须立即拒绝，过期观测只允许完整重探一次。
- AM 两笔 attempt 已失败并正式退休，当前无 running attempt；本波只形成可检出的 Host 代码闭包，不恢复 AM、
  不产生 AN、不迁移主库。

## 2. 文件级范围

- `services/aos-api/aos_api/extension_runtime/lease_renewal.py`
- `services/aos-api/aos_api/extension_runtime/verification_commit.py`
- `services/aos-api/aos_api/extension_runtime/preparation_owner.py`
- `services/aos-api/tests/extension_runtime/test_lease_renewal.py`
- `services/aos-api/tests/extension_runtime/test_preparation_owner.py`
- 新增真实 PostgreSQL 锁竞争测试，证明另一事务锁住 binding/installation 时快路径仍能完成资源 CAS 续订。

`oci_driver.py`/`resource_recovery.py` 的未知清理结果核对属于下一独立闭包；
`pipeline_source_claim_owner.py` 属于 AN direct successor；两者均不夹带。

## 3. 快路径不变量

1. 只有同 tenant/installation/generation/epoch 恰好一个新鲜 running `recoverable_store` attempt 才进入。
2. binding 必须 enabled、unfenced、ready，并精确携带原 preparation operation 和完整资源 proofs。
3. 不锁 installation/binding；attempt、operation、三资源在短事务内锁定，最终 UPDATE 以 exact binding revision、
   epoch、状态和完整 handle 做 statement-time CAS。
4. 三资源必须仍 pending、未 release、未过期且与 handle 一一相等；只推进固定 180 秒并追加
   `runtime_inflight_lease_renewed`，不改 binding/attempt/definition/control/业务数据。
5. attempt terminal/过期/不新鲜、并行 attempt、binding 漂移、资源漂移或过期全部 fail closed；无 live attempt 时
   回到原完整 permission/revalidation 路径。

## 4. 健康时钟与一次重探

- 使用同一可信数据库时钟在探针前后各取一次；探针后时间不得早于探针前。
- 提交在锁定 current identity 后、慢 revalidation 前检查 freshness；未来时间为普通 `RuntimeConflict`，不可重试。
- 只有正向 age 超过三秒抛 `HealthObservationStale`；Owner 等首事务完全结算后，若仍持有整组资源，完整重做一次
  健康探针和数据库时钟读取，再调用同一 commit。第二次失败直接关闭 Owner，禁止循环重试。

## 5. 验证与退出

- 原纯测试覆盖 valid、terminal、fenced、epoch、attempt/resource/proof/binding 漂移与未来时钟拒绝。
- 新真实 18432 测试用两个连接制造 installation/binding 锁竞争，验证快路径不等待被锁 current 行，且
  statement-time binding 漂移时零续订、事务回滚。
- preparation owner/worker、owned verification、lifecycle、attempt/drain 与 Host 相关累计回归通过；静态编译、
  `git diff --check` 通过。
- 仅提交本波文件与证据；下一波再关闭 OCI unknown-cleanup，然后执行 a0v089 备份迁移和安全 Host reload。
