# 实验库容量恢复验收

原临时实例512MiB在累计测试中No space/PANIC，最终stopped/PID0确认，未把观察超时当终止。失败container及日志保留，未重放测试SQL/数据库操作。用已验证原physical archive d867248b...与原image/Env/CMD/18431 loopback恢复新实例qyh-source-boundary-clone-capacity-20261012，明确将tmpfs限额增1GiB；原systemid7695416748450308141与五原实验数据库集合一致，原生manifest/WAL校验及恢复启动通过，未重启VM或访问修改真实卷。

故障时新test fixtures未恢复，不虚称无损恢复失败测试现场；原维护前所有正式保留实验库5个在物理备份中，最新fresh159/160演练独立磁盘卷无影响。新测试session最终80PASS0skip、五数据库集合再次读回/无残留测试DB，tmpfs使用44%、余582888KiB。保留全部原backup/卷/container，不删除、不启Host/worker/Provider，实体业务无重放。

后续工具使用本目录result.json新name/CID/1GiB；旧维护映射有这一明确继任，不直接启动失败实例空内存盘。只交付本实验容量恢复，不计产品/正式身份/八工作台首链通过。
