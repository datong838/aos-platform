# SC4-5l6m 异步排空检查验证

Rules：m1，方案先行，最小修改，隔离 PG，不 push、不迁移主库，230 L0 挂起。

方案 318745cd；Task SC4-5L6M-ASYNC-DRAIN-20260916。

RED：有效/过期租约的 running execution attempt 两个负例在修改前都 DID NOT RAISE。GREEN：a0v_054 收缩写入前检查同安装代次 running attempt、同 epoch claimed occurrence、claimed/unknown dispatch attempt；不凭租约判断完成。原 runtime/dispatch 锁及 serializable 事务保留。回执追加 drainEvidence 并参加 canonical hash。

五项恢复负例：running 有效租约、running 过期租约、claimed occurrence、claimed dispatch、unknown dispatch。均先拒绝且无 shrink Receipt；测试 fixture 中通过既有持久状态更新结束任务后，同 key 成功。该 fixture 更新不是生产对账操作授权，也不代表真实 unknown 任务已经解决。

聚焦 21 passed；连同原 cutover PG 回归 87 passed、1 skipped、7 既有警告，21.50 秒，退出 0。跳过 OCI 项不算通过；既有 JDBC cleanup 日志异常仍存在。diff check 通过，强一致投影均 CURRENT。

边界：保守的安装级在途检查可能暂时阻止与控制入口无关的读取期间收缩；成功记录是当前事务观察，不宣称九项保留入口之后永远无新任务。同步控制入口由先前组锁测试证明互斥。下一项：可选扩缩后 resumed disable/detach 实际组合；再完成完整 Service 签名审批与真实运行迁移。
