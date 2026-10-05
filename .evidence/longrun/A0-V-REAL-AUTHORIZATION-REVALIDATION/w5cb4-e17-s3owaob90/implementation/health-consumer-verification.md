# 正式 Health 消费当前施工证据

实际RED：8 failed/11 deselected/7 warnings/5.58s；真实专用SCRAM连接均触发原KeyError:0，原维护身份则未受native admission保护。日志health-consumer-red.log保留。

最小修复：dict_row epoch alias；native/SERIAL/专用双身份/无成员和高权/固定tenant检查；FormalExactRef严格重解析；原Provider-ID协调后最新两观测，错revision/hash不回退；DB clock及aware有效窗；保留原状态供后续Resolver。没有复制Health状态表、改变a143/a144、启动Provider或读任何Secret。

实际专项8 passed/5.70s；补充严格ref/canary零epoch与真实并发后，最终固定输入94 passed/1 xfailed/7 warnings/9.90s。范围为formal PG/strict contracts/原Health fence/ModelRuntime store。真实读者持锁使原append LockNotAvailable，释放后原append成功；旧snapshot消费新epoch保持原40001。所有PG只在5433 aos_test_*_ti4_test；临时专用角色finally恢复NOLOGIN/PASSWORD NULL。无当前142写入。

剩余strict xfail仍是完整evaluate_binding_in_transaction缺失，未删除/改弱。此为整体Task内部施工，非完整evaluator/API/Source/Budget/安装正向交付；Task保持ACTIVE、Authority1332未晋升GREEN。原八facts/审批纯内容复用/实际三写同调用方事务/完整signed fixture仍须实施。风险：目前只能证明此段Health事实消费，不能证明完整首链、所有候选Resolver保护或运行准入。

方案/代码复审：对照health-consumer-plan及主计划精确ref、DB时间、同caller锁与无副作用合同一致；没有UI变更，浏览器验收不适用。用户九个已有修改均未触碰。
