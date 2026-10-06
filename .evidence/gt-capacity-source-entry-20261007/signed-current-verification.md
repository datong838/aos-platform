# S17 签名登记材料当前性：局部验收

此记录只覆盖未来完整157入口所需的读取查询，不授予Source发布或业务执行权限。原Task保持ACTIVE，不出Source Delivery。

## 改动与方案一致性

- publication_store.py在原文件完整前缀之后追加6960字节查询；原前缀SHA256为381d75db661b2b266c29d314bc2cd7168ca33da4e3ef3a88668c511dd57d9a7a，逐字不变。
- 查询复用原153的policy、attestation、permit、bootstrap和root快照解析器，独立核登记原文、哈希、签名、部署库OID/cluster、根、当前窗口、撤销与epoch。
- registry_epoch的FOR SHARE属于未来完整入口的后缀；完整原Source撤回/Provider/Evidence顺序尚未接入，不能从本查询通过推导完整许可。
- 未改守卫、旧迁移、ACL、RLS、签名注册或撤销函数。普通角色实际调用被拒绝。
- 测试中每个登记材料用例使用独立保留库；复用既有创建/迁移流程并在该库期间重置两项建表缓存，最后还原父库环境及缓存。不会清空或复用其他用例的不可变注册域。

## 实际验证

- 首次缺查询常量RED：1FAIL/7.87s；最小查询正向：1PASS/7.75s。
- 故障r1：两处测试隔离故障；r2：三个setupERROR，因父库建表缓存未重置；保留日志、失败与数据库。
- 修复后专项r3：3PASS/24.75s。20项查询拒绝、2项存储CHECK拒绝分别计数；另有2项内部一致的身份漂移、2项重新签名的部署身份漂移，全部回滚后正向复验。
- 相邻r1：4PASS/1FAIL/38.92s。失败实际到达prepare并报UndefinedFunction42883。
- 实际签名撤销r1：1PASS，三个竞争参数在建库阶段DiskFull/recovery而ERROR，未计入业务验证。
- 环境恢复后撤销r2：4PASS/30.92s。撤销ROLLBACK恢复、实际COMMIT后3材料拒绝、精确重放单记录、历史原文/签名不变；两事务SERIALIZABLE与第三连接实际blocking_pids证明三种锁序，撤销先COMMIT时旧快照返回40001。
- 完整Source/epoch累计结果待同一活跃测试handle结束后追加，不能提前宣称通过。

## 环境修复

专用aos-a0v-test-only VM原磁盘30→50GiB；ext4 UUID c6232edb-863d-4bea-8fac-8aeea513dfb0不变。43个原容器的ID、镜像和挂载集合保留；28个原运行PG恢复ready。原测试容器及aos-capacity-publication-scram-20261006-data命名卷继续使用；WAL恢复完成，版本16.14、cluster7693564235776004128、原保留库迁移头156。三文档、来源、撤销独立SHA和Ed25519复验正确，Owner/issuer均NOLOGIN。恢复原预留块353854。没有删除、prune、换卷或正式系统重启。

## 历史失败分类更正

此前145PASS/5FAIL中，第一项是prepare缺失42883，另外四项在fixture注册域非空断言失败，未进入prepare。保留原日志和旧报告；本记录明确更正归因，不把当时未执行的路径当成证据。

## 剩余工作与风险

完整157 prepare→受控签名→commit→实际调用者COMMIT→当前消费者仍未实现；S18/S19供应商与原账户/basis的交叉合同、完整目录/信任注册审计和最终caller-COMMIT TTL尚未收口。本查询不得单独安装成许可入口。测试通过不证明自然经营首链。浏览器不适用于未安装的私有SQL读取前置检查；正式八工作台与业务验收另行执行。

## Final cumulative checkpoint
Source plus publication_epoch_locks: 152 PASS, 5 FAIL, 7 existing warnings, no SKIP, 350.37s. All five failures now actually reach missing public.prepare_capacity_source and observe42883; no registry fixture masking, DiskFull, or setupERROR in this final run. Parent tasks remainACTIVE and no SourceDelivery. Exact logs are hashed below. Original store prefix remains byte-identical; diff--check clean.
