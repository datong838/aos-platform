# b73 并发幂等和首次事件回滚

原探针直接父PID假设首跑失败1failed/7warnings/20.80s，仅harness问题不算业务RED，保留transaction-harness-red。修正为两个精确writer PID的pg_blocking_pids图均可追到已知epoch blocker，期限未延长。guard关闭实际业务RED：B73_DUPLICATE_KEY_EPOCH_DRIFT (2,1,1)，1failed/7warnings/14.97s，保留transaction-red。

guard开启候选两个顺序各1passed/7warnings，原b72及default各1passed/7warnings；完整节点24.49/25.01/24.37/28.78秒含disposable创建升级/签名安装/清理。fresh bundle事件首次commit前代理确认事务内真实event1/Receipt1，再抛异常，独立admin确认epoch/event/全部bundle Receipt为(0,0,0)。两个同key同bodywriter均精确锁链等待，释放后两个调用revoked=true，独立admin (1,1,1)；同key不同reason原ProductionContractIdempotencyConflict，状态仍(1,1,1)。原b70/b71/b72检查同时执行。

无共享可变key：b73每次invoke局部闭包绑定request_key；b72原串行闭包未作为b73并发证明。签名安装依赖现有Receipt；fresh bundle复制一次性fixture，不是正式issuance授权。模板源码/真正hash权威不改变。只新增两测试文件opt-in分支，默认路径无行为变动；编译/diffcheck通过，无UI变更浏览器不适用。

测试库前49/后49，历史库不删。生产Store/migration/readiness/135库/Host/worker/Provider未改，不push/不同步其他分支（231用户单写范围优先于Skill通用同步）。Scope canary和DB强制约束未证明；runtime仍可直接SQL绕过包装器，另见formal-writer-contract.md，不升级正式并发合同。不同key重复同已撤销来源的epoch语义候选还过宽，正式优先只在新增事件推进。

自复审与计划一致：RED、fresh首次回滚、并发同key、payload冲突均有实际证据；正式writer contract已冻结边界但未实现，八依赖与实例来源仍pending。下一b74 DB强制来源head候选，先原真实Store未包装epoch的RED，再隔离事件触发器、缺exact和tenant负向，不改真库。Goal继续active。
