### SC4-5h4 原关系执行与精确投影验证

ControlledSnapshotGroupLinkExecutor 已接通原对象恢复、已提交命令准备、严格Store应用、原精确权威事件投影及最终当前核验。原 pipeline_controlled_projection 提取内部共用函数，保留单表父输入和派生校验/5000上限；组仅投影当前命令的<=24000事件，沿用tenant顺序锁/hash/前序阻塞/原Projector，未改全租户worker。

20项组合通过39.48秒（新7项、原精确投影9项、原单表4项）；增加返回relationship_scope=current_candidates_only后完整成功重放单例再通过10.86秒。真实隔离PG证明两对象+一关系仅3个原Receipt，图边一次，schedule仍running；准备commit ack丢失不apply；关系已commit但ack丢失保留原Receipt后续重放；图写入后异常回滚图边及投影标记；阶段间撤权无关系写入；更早无关事件阻塞、更晚无关事件保持pending，均不越界消费。源调用始终一次。

AR2扫描1922/187/93、五类错误为空。主部署/数据库未改变，测试源与发行资产仍fixture。该结果严格限定本轮candidate关系，不表示旧关系已清退、客户引用齐全、业务Readiness或Fulfillment。

下一波：补齐历史关系残留核验。当前事实是引用改向可能新增关系而旧边仍在；先以原当前输入、包规则、已提交候选命令和原Store核验出残留/缺失/不确定范围，禁止凭快照缺行推导删除。随后显式关系清退方案/策略和恢复，再接完整Readiness与正式Fulfillment。
