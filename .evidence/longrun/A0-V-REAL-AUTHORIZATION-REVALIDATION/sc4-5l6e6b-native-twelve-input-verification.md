## 2026-09-15 SC4-5l6e6b 原生十二路输入独立提交

基线ddd11ab27c6e1b88ae62de329ab0db1386551691，m1串行。新增test_analysis_snapshot_native_ingress_pg.py，逐用例复用原完整数据库工厂建/销一次性DB，使用原GroupIngress、Journal、EcomConsistencyStore、aos_runtime身份。源读取及安装资产当前检查仍named，不读取真实商城；无影子表、SQL namespace替换、GRANT或禁用trigger。只在断言无Task/TaskRun/业务Run后提交fixture来源和控制设置，任何实际任务初始化事务不在此提交范围。

第一轮1 setup error：嵌套数据库初始化被tenant_catalog进程级_schema_ready缓存跳过，meta_workspace缺表（/tmp/sc4-e6b-first.log）。只在新fixture临时重置已确认tenant_catalog/data_os_store两个缓存标志并在结束恢复；没有为产品添加缺表。第二轮1 setup error：原host_case为rollback-only，只插入安装主记录，真实COMMIT触发缺draft revision的延迟FK（/tmp/sc4-e6b-second.log）。补齐测试canonical空组合Lock、draft revision和事件，原SQL计算hash，SET CONSTRAINTS ALL IMMEDIATE且所有trigger保持启用；该draft不代表真实激活，运行安装权限仍named。

最终4 passed/30.01s，七项既有警告（/tmp/sc4-e6b-third.log）：12许可/一组在另一连接可见后才执行一次named读取；原Journal全12输入保存；已提交输入确认丢失后exact重放且源调用仍1；许可确认丢失后源调用0且拒绝重发；第六输入保存失败后原12输入全部回滚，已提交许可保留，重复不再次读源。Ecom原Store读取checkpoint，原对象尚为0，不能称投影或首链完成。

AR2 1951/192/93，五类错误空（/tmp/sc4-e6b-closure.log）。主库未迁移、无真实Task/模型/发布/安装动作；用户三份既有改动保留，不push，230 L0挂起。下一波e6c继续同原生底座执行原对象/投影/数据集与完整组收尾，再接原初始化+Pending+快照证据+统一恢复；不能拿这四项输入验证替代最终业务链。
