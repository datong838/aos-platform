# AR1-c 持久 Runtime 宿主协议检查点

- 日期：2026-09-06
- 基线：`0581b1a7`
- 业务场景计数：0
- 页面变化：无；浏览器验收不适用

## 已实现

新增进程级 `RuntimeHost` 与不可变租户 assignment。宿主只接受精确类型的 `TenantScope`、`ExpiredResourceRecovery`、`ConfigurationConsumer` 和 `RuntimeDisableConsumer`，按租户稳定排序，并固定执行“单页过期资源恢复→配置消费一次→停用消费一次”。它不发现租户、不接收普通 callback，也不接入需要原 `PreparedJob` owner 的准备、验证或启用。

资源游标只作内存分页优化：非空页推进，空页归零，进程重建从零开始。每个 consumer 前重新核验同一 assignment 对象仍在当前可信快照；租户撤销或同租户 worker 替换都会停止旧 assignment 的后续执行。

宿主只保留一个当前 tick。调用方取消只取消等待，已进入的数据库/OCI线程继续收敛；`stop()` 先置 closing 拒绝新 tick，再等待当前 tick。内部 tick 与 close task 均登记异常观察，避免取消调用方后出现未领取后台异常。

## 验证

- 宿主、生产组合根和 lifespan 邻接专项：26 passed。
- 宿主专项稳定性：连续 5 轮各 15 passed。
- extension-runtime 非数据库累计：278 passed、429 skipped。
- Outbox、恢复批次、配置与停用消费者隔离 PostgreSQL 联合：50 passed。
- 编译与 `git diff --check`：通过。
- 独立 Prime 首审发现并推动闭合：子类白名单绕过、取消后异常无人领取、测试线程池竞态；最终快速复审判定宿主协议 GREEN、无新的确定性 blocker。

## 边界与下一切片

本检查点只完成宿主协议，不启动生产后台任务。`ExpiredResourceRecovery` 可能执行精确 OCI 删除，因此正式接线仍须同时具备可信租户目录、runtime-role connection、cleanup-only固定context driver、当前配置授权和真实排空 reader；任一缺失必须返回 INACTIVE、0 task、0 DB、0 OCI。

下一切片接入只读可信租户目录与生产 worker factory，然后做进程 A 中断→进程 B 重建→Outbox lease 新 attempt 重投/终态 ACK、资源精确恢复的隔离 PostgreSQL 联合验收。Preparation/Owned owner registry 继续独立施工，不能由本宿主泛化替代。

正式 assignment adapter 在目录 revision 未变化时必须复用同一 assignment 对象；后续生产接线将把目录 revision/token 显式化，避免把 Python 对象身份扩散为跨适配器协议。
