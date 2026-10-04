# b70 两顺序真实RED交付

唯一新thread写者，authority AOS-001329不变；只改两个opt-in测试文件，生产代码/真库/服务未改。

撤销先：signed disposable PG evaluator先形成SERIALIZABLE快照，精确PID等待Installation锁；原Store撤销及Receipt已commit后释放锁，evaluator仍applied/Receipt1/Binding version3（期望42501或40001/0/2）。1 failed/7 warnings，16.71s。

评测先：evaluator blocked Receipt未提交时，原Store writer提前commit，精确PID未等待共同锁。1 failed/7 warnings，15.69s。两项保留真正失败，不用xfail或修改期望掩盖。b70是反证收口，不是并发合同GREEN。

默认/b69/b67/b49/b50各1 passed/7 warnings；进程节点约25.4～26.9s（含启动/清理），新增测试库残留0（49→49历史库不动）；compile/diff exit0。无UI变化，浏览器不适用。O4第一真实业务施工观察：单写者Task/Lease归属实际shadow核对、两个新根因RED、兼容回归及精确交付；并非自然首链。

复审：immutable Evidence修订没有可变head，append-only revoke不能借Registry可变status锁的既有证明。下一候选b71仅一次性库中可变epoch fence演练：对exact来源单行FOR SHARE、原writer同事务先推进epoch再原撤销/Receipt；等待后旧SERIALIZABLE快照应40001，eval先writer应等。该fence不是现有正式权威、不立即写生产迁移，正式合同/多写者覆盖/重复key/缺源与多来源锁序仍须设计。独立W-L20来源审计继续保持已登记候选。
