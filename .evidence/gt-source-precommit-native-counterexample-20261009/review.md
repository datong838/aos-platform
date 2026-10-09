# 回调候选独立原生结论

本次仅检验 test-owned native callback 候选，不是 signed Source 整链。新 PG16.14 实验库与原 verifier 精确镜像基线独立；C 使用 -Wall -Werror 编译，两顺序是新单次尝试，无旧 Source/Run/Provider。

check→wait：xid733/pid55，期限 15:57:54.732165 UTC；单次 COMMIT 在 15:57:54.334595 开始，0.904587 秒后成功，后继 DB clock 为 15:57:55.240780，超过期限约 0.509 秒。C check 在 PRE_COMMIT 实际调用，之后另一个同事件回调 pg_usleep(900000)；独立回读唯一行和 committed xid。

wait→check：xid734/pid56，期限 15:57:55.651175 UTC；0.903071 秒后真实 23514 AOS_TEST_PRECOMMIT_DEADLINE_EXPIRED，明确回滚。独立 pg_xact_status=aborted，未保留对应行。两种排序均由 RegisterXactCallback 的 LIFO 实际建立，不用 SQL deferred trigger 冒称原生 callback。

独立核验 fsync/full_page_writes/synchronous_commit 全 on、PUBLIC 无 armer EXECUTE、原 verifier sha256 不变、92 个所有既有容器启动/挂载/端口未变。新实验资源和唯一已提交测试行保留，不删除义务，不重启任何旧资源。

结论：单个 PRE_COMMIT callback 即使实际检查 clock 也不自动构成严格完成截止门。反例只证明此机制候选不足，不能据它声明原产品 callback 已安装或真实 Source 漏洞由本次实验产生。完整可信结束协议仍须全部顺序/等待与失败语义设计；不得把延长 TTL 或改名最终检查当修复。独立 Model/input/全计划风险主线仍可推进，Goal active。
