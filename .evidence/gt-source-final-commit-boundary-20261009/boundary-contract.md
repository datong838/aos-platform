# 实际提交截止合同审计结论

当前 HEAD 5861fd9fd、AOS-001649；原 Source body 过期后实际已提交的签名反例保持不变。此次官方 REL_16_14 源码及一个累计成功保留库的 SERIAL READ ONLY 审计通过，范围仅结构与当前目录事实。

新增发现：事务回调注册到链表头，执行沿链表顺序；因此新期限回调后面可能仍执行更早注册的回调。不能把“注册了 PRE_COMMIT”称作最后一次检查。PREPARE 使用独立 PRE_PREPARE，普通提交回调不覆盖两阶段准备。实际源码行号、hash、全部锚点见 boundary-audit.json；网页抽取行号不能替代保存文件行号。

PRE_COMMIT 后还有并行收尾、ON COMMIT、待同步文件、NOTIFY、序列化冲突核查，再进入禁止普通取消的阶段；RecordTransactionCommit 进入 critical section，记录提交 WAL、刷新 WAL、标记 CLOG，随后可能等待同步复制。这些顺序经程序核验，但没有通过此次只读审计证明本实例每一分支实际等待。原生库 fsync/full_page_writes/synchronous_commit 均 on；原 Source 签名、hash、来源与 committed xid 再次独立通过，临时公开签发函数缺席。

结论：必须区分“最后可回滚检查时间”、“WAL 持久化完成时间”和“客户端收到确认时间”。仅 SQL deferred trigger 或扩展 PRE_COMMIT callback 不足以兑现后两者的硬期限；把超时 ERROR 放在已记提交 WAL 后也不能安全回滚。不能补一次提交后删除、返额或忽略未知结果来假装原子失败；保持原正式效果门关闭。

下一候选一：冻结可信结束协议的实际可回滚判定点、全部后置等待、PREPARE 禁入、子事务绑定、回调顺序和未知终态对账；若仍要求 WAL/确认硬截止，需要独立核心协议/失败语义设计，不能默认为已授权修改数据库内核。候选二：已登记 typed Model/Route 签名执行协议的窄应用 Owner 及来源绑定，可在截止依赖未闭合期间继续安全实现，不能启动真实 Provider。当前整体 Goal active，局部门 RED 不导致长期施工停止。

没有安装 callback、修改源码或重放旧 Source；没有产品完整交付或自然首链正向结论。
