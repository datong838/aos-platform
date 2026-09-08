# AR2-7D D1 读取观察 Evidence 验证

- 基线94159d35，AOS-000571；同一Task/Lease。新增 source_read_observation_evidence.py 与专项测试，补 canonical_population 的真实SQL验证；无迁移代码变更。
- Red为新模块不存在。实现复用aip_evidence不可变表及撤销表：同事务写后exact回读，完整观察/actor/语义声明内容地址，原始行仅用于写前摘要核验、不入表；factIds=[]。
- 独立设计纠偏：created_at显式clock_timestamp()，不使用事务开始时间NOW()；observed/freshness列仅描述读取事件，上游新鲜度未知写入正文。通用覆盖器实测：仅此Evidence无法覆盖非空Product事实需求，coverage/freshness均BLOCKED。
- 恢复专用Colima aos-extension，未改变默认context、未启动原aos-ar1c-pg。清单核对后创建本次拥有的tmpfs PostgreSQL容器aos-ar2-validation-20260909，回环18434；镜像本地postgres:16-alpine（7e7dbab8d3b4），无宿主目录挂载。只在此实例建测试角色aos_app和自动创建/删除的一次性测试库。
- 环境初次迁移因aos_app角色不存在失败，补新测试实例NOLOGIN角色后，前两切片/旧live八文件完整回归 **113 passed, 9 warnings in 3.87s**，此前5433缺失导致的live失败已在隔离环境关闭。
- 首次PG观察测试使用了晚于现场UTC时钟的固定fixture，按正确时间门失败；改用实际当前时间之前的观察fixture，未放宽实现。随后观察Evidence＋规范库SQL45项通过。
- 最终观察Evidence/规范库/观察合同/源观察/既有质量Evidence五文件 **90 passed, 9 warnings in 7.26s**。实际覆盖外层回滚、运行角色双连接并发内容去重、双租户RLS/无scope过滤的canary零可见、原Evidence撤销后读取及重放均拒绝；SQL验证99个有效对象、其他店铺/停用/删除排除、100个拒绝。
- 独立只读代码终审无阻断缺陷，实现SHA256=f86420af48247747406fd9462f9019dab5e8032f291772d85db6614bad6b7310；不是外部Prime回读。闭包ar2-1扫描1696、分类85、迁移57，五类错误零。未验ar2-7最终动态切换。
- 边界：不读取真实源、不回填历史采集、不调用Provider、不外部发布、不push；观察持久化不等于源配置exact版本、归一化对象关联或业务履约。下一项继续补这两条实际绑定，D1～D4和7E仍未封板。
