# S14 原完整 Provider 集合实测证据

方案先行，修改仅 test_provider_capacity_formal_boundary_pg.py 及本 Task 证据/原出版计划；业务代码未改。原Store实际创建两Provider账户与basis，两个引用均来自隔离正式历史fixture生产路径；额外Provider不是原申请providerRef。完整原Source proposal正向为drafted。只改变额外Provider head或payload.contentHash，原Source入口拒绝，原proposal数不增加。不是纯helper/TEMP组合替代原消费者；不调用真实供应商。

专项 provider-set-original-r1.log：3 passed/10.61s。整文件相邻 provider-set-original-adjacent.log：80 passed/106.22s，7既有warnings；各进程exit0，串行无重叠。source哈希及baseline见provider-set-original-sources.json。未修改现权威库、迁移、ACL、Owner权限、Goal或督导状态。

实际原链：allocation的_request先锁申请Provider current head并验证typed payload及canonical内容；Source随后锁三个Evidence的排序去重neutral epochs并复核原provenance，再按account Provider asset_id排序核每个current head及typed/canonical载荷。后继完整native入口须保留实际前缀顺序，不允许只校申请Provider、只校count/exists，亦不能移除原production provenance。当前三项是已有原完整集合行为的证据，不证明新S14全原生SQL等价、全writer锁图或完整Source发行/consumer COMMIT。

已消费独立督导自主RQ-02报告：共享pool P、未来物理账户A、bucket B、cost fence F、proposal Q、Binding C须按具体行/模式/connection列锁图；unknown义务不得仅按旧TTL统计切换。未把有限隔离probe升级成完整真实经营证明。AIS-003保持未闭合。
