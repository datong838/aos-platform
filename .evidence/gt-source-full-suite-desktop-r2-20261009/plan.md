# Desktop 原完整 Source 386 项累计复验方案

Rules：231 八步、AOS 工程交付、同线程 m1 唯一写者、证据不授业务权限。

候选一：原 101 函数 386 节点完整累计，已登记 Source 合同授权；依赖新 Desktop 原生 C/SCRAM 实验室两布局准备验收，现已通过。
候选二：真实 COMMIT 越过截止时间反例的终端语义调查，已登记联合原子合同授权；依赖保留反例和 PostgreSQL 终端语义，仍待修复。先选候选一，不以累计通过消除候选二。

文件范围仅本目录计划、运行器、原始结果和独立只读验收；不修改 services/apps。新目录 gt-source-full-suite-desktop-r2-20261009。使用现有 Desktop 实验容器、5440 端口、原生扩展及私有 passfile；保留每个新测试库，不回放旧尝试。冻结1963输入与原完整集合，386节点无过滤、maxfail=1。连接局部低内存配置和临时 caffeinate 保持，耐久开关保持 on。每节点容量门2.58GB；冻结两个 Docker 引擎全部既有资源。失败保留原始终态并只读诊断，不重复未知效果。通过后独立验 Source 原始签名/hash/xid/provenance、权限、清理、资源和输入；全量通过也不声称真实截止门、自然首链或长期 Goal 完成。

## 恢复授权与新尝试
2026-10-09用户明确“继续，后面不能再停了 Loop起来”，撤回暂停；产品Goal恢复控件能力缺口单独报告，不改私有存储。原r1 SIGINT exit2/20PASS不续跑或重发，原库保留，新attempt freshbootstrap。核原Source同ownerTask无Delivery、全重叠Lease和无liveprocess后官方CAS续期；本证据Task独立scope。全部1963输入hash及原386集合须精确不变。

### r2 收集路径修正
完整集合引用被全局字符串替换误改为不存在的whole-r2-collection，pytestexit3/结果与database_binding均0，未进入fixture。保留r2，不覆盖旧attempt。新增run_whole_r3.py，只将本次输出命名r3，原root-r7基准必须保持whole-r1-collection.json；新r3重新收集原386节点，不重放任何旧数据库操作。

### 累计等待期间的下一门只读调查
仅检查现有Source提交函数、保留逾期提交证据和PG16上游事务源码；不改冻结业务输入、不安装C扩展、不连接正式库，不增加第二数据库写者。整理提交结束阶段候选与剩余风险，供累计收口后后续已登记合同消费。

### r3 共享内存失败收口与修复候选
r3 terminal exit1，341PASS/1setupERROR；Docker日志另证明同backend signal11及自动WAL恢复，必须独立复验保留已提交证据，不能当普通断连重发。现有连接包装已覆盖SQLAlchemy loaded_dbapi.connect；绕过包装假设未证实。两候选：A仅调整新隔离实验室共享内存容量（新owned container/volume，旧ID与StartedAt不变）；B诊断PG统计动态共享内存增长及failure恢复。先执行B只读保留库审计，再A新实验室，明确shm-size256MiB、原768MiB内存上限，耐久开启。严禁清空统计或删除既有测试库来造绿。实际创建前须独立Task/Lease和文件级计划；此目录先新增verify_failure_readonly.py、failure-reconciliation.json、PG原始日志，不改services。

Terminal receipt: whole-r3-terminal-failed-shm-exhaustion-readonly-reconciled. Bounded evidence delivery only; actual COMMIT deadline remains pending.
