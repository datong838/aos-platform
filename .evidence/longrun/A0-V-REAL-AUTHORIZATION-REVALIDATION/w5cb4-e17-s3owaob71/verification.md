# b71隔离epoch候选验证

b70真实两RED保留。候选只改两测试文件，随机epoch表只在disposable库；原生产Store未改。受限命令Installation→Registry→exact epoch FOR SHARE→License→Binding/Receipt；原writer test-only连接包装同事务UPDATE epoch后原撤销/Receipt commit，保持SERIALIZABLE。

最初缺writer租户policy，影响0行，1 failed/7 warnings/16.88s，失败保留；补原aos_runtime仅test-only表SELECT/UPDATE(epoch)及tenant RLS，撤公共/默认宽权。最终撤销先：明确40001、Receipt0/version2；评测先：精确PID确认writer等eval，后续新key42501且Receipt0；各1 passed/7 warnings。b69/默认各1 passed；节点26.09/25.71/26.16/27.89秒包含启动清理；测试内约16秒。随机表/角色finally清理，test数据库49→49新增残留0；历史库不删。编译/diff通过，无UI变化浏览器不适用。

复审和剩余风险：这是test-only concurrency candidate，不是正式可信epoch权威；原writer所有入口/其他七源未强制接同合同。连接包装器在重放key前推进epoch，可能无意义改变epoch；错hash失败的epoch/event/Receipt整体回滚、重复key与并发同key尚待专门验证，不能声称幂等合同完备。正式化须覆盖writer DB强制门、epoch初始化/来源绑定/迁移恢复与多来源锁序后另波批准，不直接写135或上生产迁移。Host/worker/Provider关、不读商城源/旧Run/230L0、不push。

O4第二真实施工观察有方案/Task/两顺序与相邻证据，但独立复核与新thread实际定时到达尚待核验，不将两测试波当全天候效果通过。下一登记b72：epoch候选幂等/回滚RED及正式合同冻结；W-L20实例ToolBinding来源审计独立候选（已有代码仍只核tenant/active instance，无signed exact source/Owner/安装代次合同，不能由定义级Tool ref推导运行可用）。

readiness相邻24 passed/2既有xfail/7 warnings/5.83s；xfail不算正式门GREEN。
